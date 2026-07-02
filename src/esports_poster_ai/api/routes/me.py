"""
`GET /v1/me` — the authenticated platform's own account view.

The service is integrated by *platforms* (the paying customers); a single API
key authenticates one platform. `/v1/me` reports that platform's identity and
how many orgs it has registered. Per-org tier and quota live on the org and are
returned by `GET /v1/orgs/{org_id}`.

In dev mode (no key) there is no platform — `platform_id` is null and
`authenticated` is false.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.domain.platform import CLIENT_EDITABLE_BLOCKS, Platform
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.platforms import PlatformStore, platform_for

router = APIRouter(prefix="/v1/me", tags=["me"])


def _config_view(p: Platform) -> Dict[str, Any]:
    """Client-facing config view — secrets masked, commercial fields read-only."""
    data = p.model_dump()
    byok = data.pop("byok", {}) or {}
    return {
        # Read-only (provider-owned) — shown so the client knows their plan.
        "service_type": data.get("service_type"),
        "monthly_fee_usd": data.get("monthly_fee_usd"),
        # Editable client-owned blocks.
        "economics": data.get("economics"),
        "branding": data.get("branding"),
        "features": data.get("features"),
        "quotas": data.get("quotas"),
        "tiers": data.get("tiers"),
        # BYOK presence only, never the secret values.
        "byok_set": {k: bool(v) for k, v in byok.items()},
    }


class MeResponse(BaseModel):
    """The caller's platform identity."""

    platform_id: Optional[str] = Field(
        default=None, description="The platform this API key belongs to; null in dev mode."
    )
    authenticated: bool = Field(
        description="True when the request carried a valid API key."
    )
    org_count: int = Field(
        default=0, description="Number of orgs registered under this platform."
    )
    generated_at: datetime


@router.get("", response_model=MeResponse)
def get_me(
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> MeResponse:
    """Return the caller's platform identity and registered-org count."""
    org_count = 0
    if auth.authenticated and auth.platform_id is not None:
        org_count = len(org_store.list_for_platform(auth.platform_id, limit=1000))
    return MeResponse(
        platform_id=auth.platform_id,
        authenticated=auth.authenticated,
        org_count=org_count,
        generated_at=datetime.now(tz=timezone.utc),
    )


@router.get("/config")
def get_my_config(auth: AuthContext = Depends(get_auth_context)) -> Dict[str, Any]:
    """The caller's own self-serve configuration (branding, features, economics,
    tiers, quotas). Commercial fields are read-only; BYOK secrets are masked."""
    rec = platform_for(auth.platform_id) or Platform(platform_id=auth.platform_id or "")
    return _config_view(rec)


@router.patch("/config")
def update_my_config(
    body: Dict[str, Any] = Body(...),
    auth: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    """
    Update the caller's OWN config. Clients self-serve here with their API key.
    Only client-owned blocks are accepted; service_type / monthly_fee_usd are
    ignored (those are the provider's to set).
    """
    patch = {k: v for k, v in body.items() if k in CLIENT_EDITABLE_BLOCKS}
    p = PlatformStore().patch_config(auth.platform_id, patch)
    return _config_view(p)
