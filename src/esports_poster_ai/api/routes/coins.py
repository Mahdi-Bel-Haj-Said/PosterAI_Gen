"""
`/v1/coins` — the org's Red Coins (token) wallet.

`GET` returns the current balance (crediting any due monthly grant first) plus
the per-poster estimate so the UI can price things in tokens, never dollars.
`POST /purchase` tops the wallet up (pay-as-you-go); it's a stub until a real
payment provider is wired in.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.billing import SUBSCRIPTION_TIERS, quality_multiplier
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.platforms import economics_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/coins", tags=["coins"])


def _org_with_grant(org_store: OrgStore, auth: AuthContext, org_id: str):
    """Fetch the org, crediting any due monthly grant; auto-register in dev."""
    org = org_store.ensure_monthly_grant(auth.platform_id, org_id)
    if org is None:
        org_store.ensure(auth.platform_id, org_id)
        org = org_store.ensure_monthly_grant(auth.platform_id, org_id)
    return org


@router.get("")
def get_coins(
    org_id: Optional[str] = Query(None, description="Organization id."),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> Dict[str, Any]:
    org_id = auth.require_org(org_id)
    org = _org_with_grant(org_store, auth, org_id)
    tier = org.tier if org else "free"
    econ = economics_for(auth.platform_id)
    return {
        "org_id": org_id,
        "balance": org.coins_balance if org else 0,
        "tier": tier,
        "monthly_grant": econ.grant_for(tier),
        "est_per_poster": {
            q: econ.estimate_tokens(quality_multiplier(q)) for q in ("low", "medium", "high")
        },
        # Client's economics — the UI prices everything in tokens using these.
        "tokens_per_usd": econ.tokens_per_usd,
        "poster_markup": econ.poster_markup,
        "topup_usd_per_10k": econ.topup_usd_per_10k,
    }


@router.post("/subscribe")
def subscribe(
    body: Dict[str, Any] = Body(...),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> Dict[str, Any]:
    """
    Switch the org's subscription tier and credit that plan's monthly grant.

    STUB: payment is assumed successful (no provider wired). The frontend collects
    card details for show only — confirming here just applies the plan.
    """
    org_id = auth.require_org(body.get("org_id"))
    tier = body.get("tier")
    if tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tier '{tier}'. Choose one of: {', '.join(SUBSCRIPTION_TIERS)}.",
        )
    org = org_store.subscribe(auth.platform_id, org_id, tier)
    logger.info("coins.subscribe", extra={"org_id": org_id, "tier": tier, "balance": org.coins_balance})
    return {"org_id": org_id, "tier": org.tier, "balance": org.coins_balance,
            "monthly_grant": economics_for(auth.platform_id).grant_for(org.tier)}


@router.post("/purchase")
def purchase_coins(
    body: Dict[str, Any] = Body(...),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> Dict[str, Any]:
    """
    Top up the wallet. Pass either `tokens` (exact) or `usd` (converted at the
    top-up rate). STUB: no real charge is taken — wire a payment provider here.
    """
    org_id = auth.require_org(body.get("org_id"))
    tokens = body.get("tokens")
    if tokens is None and body.get("usd") is not None:
        tokens = economics_for(auth.platform_id).topup_tokens_for_usd(body.get("usd"))
    tokens = int(tokens or 0)
    if tokens <= 0:
        raise HTTPException(status_code=400, detail="Provide `tokens` or `usd` greater than 0.")

    org_store.ensure(auth.platform_id, org_id)
    balance = org_store.add_coins(auth.platform_id, org_id, tokens)
    logger.info("coins.topup", extra={"org_id": org_id, "added": tokens, "balance": balance})
    return {"org_id": org_id, "added": tokens, "balance": balance}


__all__ = ["router"]
