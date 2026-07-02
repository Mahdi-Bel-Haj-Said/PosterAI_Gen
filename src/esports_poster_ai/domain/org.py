"""
Org domain model — an organization registered *under a platform*.

A platform (the integrating customer, identified by its API key) registers the
orgs it generates posters for. Org ids are unique only WITHIN a platform, so two
different platforms can both have an org called `team-alpha` with no collision —
the storage layer namespaces every object under `platforms/{platform_id}/`.

Each org carries its own subscription `tier` (per-org billing), defaulting to
`free` on registration and settable via the management endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from esports_poster_ai.billing import DEFAULT_TIER, SubscriptionTier


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OrgRateLimits(BaseModel):
    """
    Per-org rolling-window quota overrides, set by the platform that owns the org.

    Each field caps COMPLETED posters in a rolling window (day = 24h, week = 7d,
    month = 30d). A `None` field means "use the service default" — so a platform
    can raise just the daily cap and leave the rest on defaults. The platform
    edits these freely per org via `POST`/`PATCH /v1/orgs`.
    """

    model_config = ConfigDict(extra="ignore")

    day: Optional[int] = Field(default=None, ge=0)
    week: Optional[int] = Field(default=None, ge=0)
    month: Optional[int] = Field(default=None, ge=0)


class Org(BaseModel):
    """An org registered under a platform."""

    model_config = ConfigDict(extra="ignore")

    org_id: str                          # unique within the platform
    platform_id: Optional[str] = None    # owning platform (from the API key); None in dev
    name: Optional[str] = None
    # Optional free-form label. Billing is negotiated out-of-band, so this is NOT
    # a price/cap — the enforced quota lives in `limits`.
    tier: SubscriptionTier = DEFAULT_TIER
    limits: OrgRateLimits = Field(default_factory=OrgRateLimits)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Red Coins (token) balance. `coins_period_start` is when the current monthly
    # grant window began; None means "never granted yet" (legacy orgs get their
    # first grant on first access). See billing/coins.py + orgs/store.py.
    coins_balance: int = 0
    coins_spent: int = 0                  # lifetime Red Coins spent on posters
    coins_period_start: Optional[datetime] = None

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


__all__ = ["Org", "OrgRateLimits"]
