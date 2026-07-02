"""
Static subscription tiers — placeholder for the real billing integration.

We expose three tiers for the admin dashboard to render:

  * free   — 1,500 Red Coins/month, $0
  * pro    — 30,000 Red Coins/month, ~$3
  * kratos — 100,000 Red Coins/month, ~$10

``tier_for_org()`` is currently a hardcoded map keyed by ``org_id``. When the
real billing layer (Stripe, Defendr's billing service, etc.) lands, this
function is the only place that needs to change — every caller in the
codebase looks up tiers through here, not by reaching into a constants dict.

Why hardcoded for now
---------------------
The admin / usage view needs SOMETHING to display tier badges and quota
utilization. Building a full subscriptions table + payment integration is
weeks of work; this stub gives the dashboard real-looking output today and
makes the seam where billing plugs in obvious.
"""

from __future__ import annotations

from typing import Dict, Literal

from pydantic import BaseModel, Field


# The canonical tier identifiers. Used as Literal values everywhere downstream
# so the type system catches typos at boundary.
SubscriptionTier = Literal["free", "pro", "kratos"]


class TierInfo(BaseModel):
    """Display + quota metadata for one subscription tier."""

    id: SubscriptionTier
    label: str = Field(..., description="Human-readable name shown in the UI.")
    monthly_poster_cap: int = Field(
        ..., description="Cap on COMPLETED posters per calendar month."
    )
    monthly_price_usd: float = Field(
        ..., description="Listed monthly price for this tier."
    )
    monthly_token_grant: int = Field(
        0, description="Red Coins (tokens) credited to the org each month on this tier."
    )
    color_token: str = Field(
        ...,
        description=(
            "CSS color variable name the frontend uses for the badge — keeps "
            "branding centralised so we never sprinkle hex codes."
        ),
    )


# Single source of truth. Editing one number here updates the admin dashboard,
# tier badges, and quota utilization math in one go.
SUBSCRIPTION_TIERS: Dict[SubscriptionTier, TierInfo] = {
    "free": TierInfo(
        id="free",
        label="Free",
        monthly_poster_cap=30,
        monthly_price_usd=0.0,
        monthly_token_grant=1500,
        color_token="--fg-3",
    ),
    "pro": TierInfo(
        id="pro",
        label="Pro",
        monthly_poster_cap=200,
        monthly_price_usd=3.0,
        monthly_token_grant=30000,
        color_token="--cy",
    ),
    "kratos": TierInfo(
        id="kratos",
        label="Kratos",
        monthly_poster_cap=2000,
        monthly_price_usd=10.0,
        monthly_token_grant=100000,
        color_token="--crim",
    ),
}


DEFAULT_TIER: SubscriptionTier = "free"


# Static org → tier mapping. New orgs not in this map default to FREE.
# Real version: read from a `subscriptions` Mongo collection or the billing
# provider's API; the function signature stays identical.
_STATIC_ORG_TIER: Dict[str, SubscriptionTier] = {
    "1": "pro",         # the existing demo org
    "demo-kratos": "kratos",
    "demo-pro": "pro",
}


def tier_for_org(org_id: str) -> SubscriptionTier:
    """
    Return the subscription tier for ``org_id``.

    Unknown orgs default to ``free``. This is the single chokepoint —
    real billing logic plugs in here without touching callers.
    """
    return _STATIC_ORG_TIER.get(org_id, DEFAULT_TIER)
