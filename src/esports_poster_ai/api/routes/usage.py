"""
`GET /v1/usage` — usage / cost report for an org.

Aggregates over the `jobs` collection — counts by status and an estimated
cost (number of completed posters × `cost_per_poster_usd` from settings).
For now this is the billing trail; a dedicated `usage_events` table can
follow if finer-grained per-call detail is needed.

Admin surface
-------------
``GET /v1/admin/usage/orgs`` returns per-org rollups for the admin dashboard:
total posters, daily / weekly / monthly averages, mode breakdown, subscription
tier, spend, tier-cap utilization. Currently UNGATED so the existing demo UI
keeps working; flip the dependency to ``require_admin`` (see api/deps.py) to
make it admin-only when you're ready.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.api.routes.posters import get_job_store
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.api.schemas import UsageResponse
from esports_poster_ai.billing import SUBSCRIPTION_TIERS, SubscriptionTier, TierInfo, tier_for_org
from esports_poster_ai.config import get_settings
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.quotas import WindowQuota, compute_quotas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/usage", tags=["usage"])

# Separate router so the admin endpoints have their own /v1/admin prefix.
# Wired into app.py alongside the existing usage router.
admin_router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("", response_model=UsageResponse)
def get_usage(
    org_id: Optional[str] = Query(
        None, description="Organization id. Omit when authenticating with an API key."
    ),
    since: Optional[datetime] = Query(
        None, description="ISO-8601 lower bound on job created_at (inclusive)."
    ),
    until: Optional[datetime] = Query(
        None, description="ISO-8601 upper bound on job created_at (inclusive)."
    ),
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
) -> UsageResponse:
    """Aggregate jobs by status and return an estimated cost for the period."""
    org_id = auth.require_org(org_id)
    counts = store.usage_summary(
        org_id, since=since, until=until, platform_id=auth.platform_id
    )
    completed = counts.get("completed", 0)
    failed = counts.get("failed", 0)
    queued = counts.get("queued", 0)
    total = sum(counts.values())

    cost_per = get_settings().cost_per_poster_usd
    estimated_cost = round(completed * cost_per, 4)

    return UsageResponse(
        org_id=org_id,
        period_start=since,
        period_end=until,
        total_jobs=total,
        completed=completed,
        failed=failed,
        queued=queued,
        counts_by_status=counts,
        estimated_cost_usd=estimated_cost,
    )


@router.get("/quota", response_model=List[WindowQuota])
def get_quota(
    org_id: Optional[str] = Query(
        None, description="Organization id. Omit when authenticating with an API key."
    ),
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> List[WindowQuota]:
    """
    Per-org rate-limit state for the rolling day / week / month windows.

    Reflects the org's own (platform-edited) limits. The UI calls this on the
    dashboard and after each generate attempt to show "today X/Y" chips and the
    reset time when a window is full. Failed jobs do not count toward usage.
    """
    org_id = auth.require_org(org_id)
    limits = auth.resolve_org_limits(org_id, org_store)
    return compute_quotas(
        org_id, platform_id=auth.platform_id, limits=limits, job_store=store
    )


# ---- Admin: per-org rollups ------------------------------------------------


class AdminOrgStats(BaseModel):
    """One row in the admin Usage & Billing table."""

    org_id: str
    tier: SubscriptionTier

    # Volumes
    total_jobs: int
    completed: int
    failed: int
    success_rate: float = Field(..., ge=0.0, le=1.0)

    # Rolling windows (completed posters only)
    completed_24h: int
    completed_7d: int
    completed_30d: int

    # Derived averages over the last 30 days
    avg_per_day_30d: float
    avg_per_week_30d: float
    avg_per_month_30d: float  # = completed_30d (sliding 30-day window)

    # Activity timestamps + engagement
    first_activity_at: Optional[datetime]
    last_activity_at: Optional[datetime]
    days_active_30d: int

    # Mode breakdown (completed only)
    mode_fresh: int
    mode_consistency: int
    mode_refine: int

    # Money
    estimated_spend_total_usd: float
    estimated_spend_30d_usd: float
    monthly_price_usd: float

    # Tier utilization (percent of monthly cap used over the last 30d)
    tier_monthly_cap: int
    tier_utilization_pct: float = Field(..., ge=0.0)


class AdminTierBreakdown(BaseModel):
    """How many orgs are on each tier — drives the header chips."""
    free: int = 0
    pro: int = 0
    enterprise: int = 0


class AdminTotals(BaseModel):
    """Cross-org aggregates rendered as the dashboard's headline numbers."""
    total_orgs: int
    total_completed_posters: int
    total_failed_jobs: int
    total_completed_30d: int
    total_estimated_spend_usd: float
    total_monthly_recurring_usd: float


class AdminUsageResponse(BaseModel):
    """Top-level admin payload — one HTTP call drives the whole page."""
    orgs: List[AdminOrgStats]
    totals: AdminTotals
    by_tier: AdminTierBreakdown
    tiers: Dict[SubscriptionTier, TierInfo]
    generated_at: datetime


def _row_to_stats(row: Dict, cost_per: float) -> AdminOrgStats:
    """
    Convert one rollup dict (from `JobStore.list_orgs_aggregate`) into the
    Pydantic schema the route returns. Owns the tier lookup + spend math so
    the store stays free of billing concerns.
    """
    org_id = row["org_id"]
    completed = int(row.get("completed", 0))
    completed_30d = int(row.get("completed_30d", 0))
    total_jobs = int(row.get("total_jobs", 0))
    failed = int(row.get("failed", 0))

    tier_id = tier_for_org(org_id)
    tier = SUBSCRIPTION_TIERS[tier_id]

    success_rate = (completed / total_jobs) if total_jobs > 0 else 0.0
    avg_per_day = completed_30d / 30.0
    avg_per_week = completed_30d / (30.0 / 7.0)

    utilization = (
        100.0 * completed_30d / tier.monthly_poster_cap
        if tier.monthly_poster_cap > 0
        else 0.0
    )

    return AdminOrgStats(
        org_id=org_id,
        tier=tier_id,

        total_jobs=total_jobs,
        completed=completed,
        failed=failed,
        success_rate=round(success_rate, 4),

        completed_24h=int(row.get("completed_24h", 0)),
        completed_7d=int(row.get("completed_7d", 0)),
        completed_30d=completed_30d,

        avg_per_day_30d=round(avg_per_day, 2),
        avg_per_week_30d=round(avg_per_week, 2),
        avg_per_month_30d=float(completed_30d),

        first_activity_at=row.get("first_activity_at"),
        last_activity_at=row.get("last_activity_at"),
        days_active_30d=int(row.get("days_active_30d", 0)),

        mode_fresh=int(row.get("mode_fresh", 0)),
        mode_consistency=int(row.get("mode_consistency", 0)),
        mode_refine=int(row.get("mode_refine", 0)),

        estimated_spend_total_usd=round(completed * cost_per, 4),
        estimated_spend_30d_usd=round(completed_30d * cost_per, 4),
        monthly_price_usd=tier.monthly_price_usd,

        tier_monthly_cap=tier.monthly_poster_cap,
        tier_utilization_pct=round(utilization, 1),
    )


@admin_router.get("/usage/orgs", response_model=AdminUsageResponse)
def admin_org_usage(
    store: JobStore = Depends(get_job_store),
) -> AdminUsageResponse:
    """
    Per-org rollup for the admin Usage & Billing screen.

    One Mongo aggregation collects volumes, mode mix, rolling windows, and
    activity timestamps in a single round trip; we layer tier + spend on top
    in Python and return everything the dashboard needs.

    Currently ungated — the demo UI is shared across roles. To make this
    admin-only later, add ``token = Depends(require_admin_token)`` to the
    signature and the existing ``ADMIN_TOKEN`` plumbing in ``api/deps.py``
    enforces it.
    """
    cost_per = get_settings().cost_per_poster_usd
    rows = store.list_orgs_aggregate()
    orgs = [_row_to_stats(r, cost_per) for r in rows]

    # Cross-org totals — sum what we already computed per row.
    total_completed = sum(o.completed for o in orgs)
    total_failed = sum(o.failed for o in orgs)
    total_30d = sum(o.completed_30d for o in orgs)
    total_spend = round(sum(o.estimated_spend_total_usd for o in orgs), 4)
    mrr = round(sum(o.monthly_price_usd for o in orgs), 2)

    # Tier histogram for the header chips.
    breakdown = AdminTierBreakdown()
    for o in orgs:
        setattr(breakdown, o.tier, getattr(breakdown, o.tier) + 1)

    return AdminUsageResponse(
        orgs=orgs,
        totals=AdminTotals(
            total_orgs=len(orgs),
            total_completed_posters=total_completed,
            total_failed_jobs=total_failed,
            total_completed_30d=total_30d,
            total_estimated_spend_usd=total_spend,
            total_monthly_recurring_usd=mrr,
        ),
        by_tier=breakdown,
        tiers=SUBSCRIPTION_TIERS,
        generated_at=datetime.now(tz=timezone.utc),
    )
