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
from esports_poster_ai.auth.store import ApiKeyStore
from esports_poster_ai.domain.platform import DEFAULT_SERVICE_TYPE, PlatformEconomics, ServiceType
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.platforms.store import PlatformStore
from esports_poster_ai.api.schemas import UsageResponse
from esports_poster_ai.billing import (
    SUBSCRIPTION_TIERS,
    SubscriptionTier,
    TierInfo,
    monthly_grant_for_tier,
    tier_for_org,
)
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

    # Red Coins wallet
    coins_balance: int = 0
    coins_used: int = 0
    coins_monthly_grant: int = 0

    # Tier utilization (percent of monthly cap used over the last 30d)
    tier_monthly_cap: int
    tier_utilization_pct: float = Field(..., ge=0.0)


class AdminTierBreakdown(BaseModel):
    """How many orgs are on each tier — drives the header chips."""
    free: int = 0
    pro: int = 0
    kratos: int = 0


class AdminTotals(BaseModel):
    """Cross-org aggregates rendered as the dashboard's headline numbers."""
    total_orgs: int
    total_completed_posters: int
    total_failed_jobs: int
    total_completed_30d: int
    total_estimated_spend_usd: float
    total_monthly_recurring_usd: float
    total_coins_balance: int = 0
    total_coins_used: int = 0


class AdminUsageResponse(BaseModel):
    """Top-level admin payload — one HTTP call drives the whole page."""
    orgs: List[AdminOrgStats]
    totals: AdminTotals
    by_tier: AdminTierBreakdown
    tiers: Dict[SubscriptionTier, TierInfo]
    generated_at: datetime


def _row_to_stats(row: Dict, cost_per: float, org_record=None) -> AdminOrgStats:
    """
    Convert one rollup dict (from `JobStore.list_orgs_aggregate`) into the
    Pydantic schema the route returns. Owns the tier lookup + spend math so
    the store stays free of billing concerns. `org_record` (if present) carries
    the real Red Coins wallet + the org's actual tier.
    """
    org_id = row["org_id"]
    completed = int(row.get("completed", 0))
    completed_30d = int(row.get("completed_30d", 0))
    total_jobs = int(row.get("total_jobs", 0))
    failed = int(row.get("failed", 0))

    # Prefer the org's real tier (set via subscribe) over the static map.
    tier_id = org_record.tier if org_record is not None else tier_for_org(org_id)
    tier = SUBSCRIPTION_TIERS.get(tier_id, SUBSCRIPTION_TIERS[tier_for_org(org_id)])

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

        coins_balance=int(getattr(org_record, "coins_balance", 0) or 0),
        coins_used=int(getattr(org_record, "coins_spent", 0) or 0),
        coins_monthly_grant=monthly_grant_for_tier(tier_id),
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
    # Real wallets keyed by org_id (Red Coins balance / spent / tier).
    try:
        org_records = {o.org_id: o for o in OrgStore().list_all()}
    except Exception:  # noqa: BLE001 — a wallet lookup hiccup must not 500 the page
        org_records = {}
    orgs = [_row_to_stats(r, cost_per, org_records.get(r["org_id"])) for r in rows]

    # Cross-org totals — sum what we already computed per row.
    total_completed = sum(o.completed for o in orgs)
    total_failed = sum(o.failed for o in orgs)
    total_30d = sum(o.completed_30d for o in orgs)
    total_spend = round(sum(o.estimated_spend_total_usd for o in orgs), 4)
    mrr = round(sum(o.monthly_price_usd for o in orgs), 2)
    total_coins_balance = sum(o.coins_balance for o in orgs)
    total_coins_used = sum(o.coins_used for o in orgs)

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
            total_coins_balance=total_coins_balance,
            total_coins_used=total_coins_used,
        ),
        by_tier=breakdown,
        tiers=SUBSCRIPTION_TIERS,
        generated_at=datetime.now(tz=timezone.utc),
    )


# ----------------------------------------------------------------------------
# Provider -> Clients (platforms) rollup. One level up from orgs: a row per
# integrating customer (platform), built generically from whatever exists in
# the api_keys / orgs / jobs collections — a new client appears automatically,
# no code change needed.
# ----------------------------------------------------------------------------
class PlatformStats(BaseModel):
    platform_id: Optional[str]
    label: Optional[str] = None
    # Provider <-> client commercial relationship (money + service type only;
    # Red Coins are an ORG concept and intentionally not here).
    service_type: str = DEFAULT_SERVICE_TYPE       # "hosted" | "byok"
    monthly_fee_usd: float = 0.0                    # what the client pays the provider
    cost_to_serve_usd: float = 0.0                  # provider's real cost (0 for BYOK)
    margin_usd: float = 0.0                         # fee - cost_to_serve
    api_keys: int = 0
    active_keys: int = 0
    orgs: int = 0
    tier_free: int = 0
    tier_pro: int = 0
    tier_kratos: int = 0
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    completed_30d: int = 0
    success_rate: float = 0.0
    last_activity_at: Optional[datetime] = None
    # The client's Red Coins economics config (editable per client).
    economics: Dict[str, float] = Field(default_factory=dict)


class PlatformsResponse(BaseModel):
    platforms: List[PlatformStats]
    generated_at: datetime


@admin_router.get("/platforms", response_model=PlatformsResponse)
def admin_platforms(store: JobStore = Depends(get_job_store)) -> PlatformsResponse:
    """
    Per-CLIENT (platform) rollup for the provider's Clients view.

    Generic: platforms are discovered from the union of api_keys, orgs, and jobs,
    so any new client shows up with no code change. Ungated like the sibling
    admin endpoint — add ``Depends(require_admin)`` (api/deps.py) to lock it down.
    """
    cost_per = get_settings().cost_per_poster_usd
    try:
        orgs = OrgStore().list_all()
    except Exception:  # noqa: BLE001
        orgs = []
    try:
        keys = ApiKeyStore().list_all()
    except Exception:  # noqa: BLE001
        keys = []
    try:
        plat_records = {p.platform_id or None: p for p in PlatformStore().list_all()}
    except Exception:  # noqa: BLE001
        plat_records = {}
    job_rows = {r["platform_id"]: r for r in store.list_platforms_aggregate()}

    platform_ids = set()
    for o in orgs:
        platform_ids.add(o.platform_id)
    for k in keys:
        platform_ids.add(k.platform_id)
    for pid in job_rows:
        platform_ids.add(pid)
    for pid in plat_records:
        platform_ids.add(pid)
    if not platform_ids:
        platform_ids.add(None)

    out: List[PlatformStats] = []
    for pid in platform_ids:
        porgs = [o for o in orgs if o.platform_id == pid]
        pkeys = [k for k in keys if k.platform_id == pid]
        jr = job_rows.get(pid, {})

        completed = int(jr.get("completed", 0))
        total_jobs = int(jr.get("total_jobs", 0))

        tier_counts = {"free": 0, "pro": 0, "kratos": 0}
        for o in porgs:
            if o.tier in tier_counts:
                tier_counts[o.tier] += 1

        rec = plat_records.get(pid)
        service_type = rec.service_type if rec else DEFAULT_SERVICE_TYPE
        fee = float(rec.monthly_fee_usd) if rec else 0.0
        # BYOK clients run on their own keys/storage, so the provider's cost to
        # serve is ~0 (they pay their own OpenAI/R2). Hosted clients cost us the
        # real generation spend.
        cost_to_serve = 0.0 if service_type == "byok" else round(completed * cost_per, 4)

        out.append(PlatformStats(
            platform_id=pid,
            label=(rec.name if rec and rec.name else next((k.name for k in pkeys if k.name), None)),
            service_type=service_type,
            monthly_fee_usd=round(fee, 2),
            cost_to_serve_usd=cost_to_serve,
            margin_usd=round(fee - cost_to_serve, 2),
            api_keys=len(pkeys),
            active_keys=len([k for k in pkeys if not k.revoked]),
            orgs=len(porgs),
            tier_free=tier_counts["free"], tier_pro=tier_counts["pro"], tier_kratos=tier_counts["kratos"],
            total_jobs=total_jobs,
            completed=completed,
            failed=int(jr.get("failed", 0)),
            completed_30d=int(jr.get("completed_30d", 0)),
            success_rate=round(completed / total_jobs, 4) if total_jobs > 0 else 0.0,
            last_activity_at=jr.get("last_activity_at"),
            economics=(rec.economics if rec else PlatformEconomics()).model_dump(),
        ))

    out.sort(key=lambda p: p.completed, reverse=True)
    return PlatformsResponse(platforms=out, generated_at=datetime.now(tz=timezone.utc))


class MetricBucket(BaseModel):
    """One value of a dimension (e.g. vibe='cyberpunk') with its share + rating."""
    key: str
    count: int
    pct: float = Field(..., ge=0.0, le=100.0)         # share within its dimension
    rated: int = 0                                     # how many of these were rated
    avg_rating: Optional[float] = None                 # mean 1–5 rating, if any


class ContentMetricsResponse(BaseModel):
    """
    Everything the content-metrics dashboard needs in one call: the distribution
    of user design choices + how each is rated. Percentages within a dimension
    sum to ~100 across the jobs that specified that dimension.
    """
    total_jobs: int
    ratings_count: int
    avg_rating: Optional[float] = None
    rating_histogram: Dict[str, int]                   # {"1":n, … "5":n}

    by_vibe: List[MetricBucket]
    by_energy: List[MetricBucket]
    by_combo: List[MetricBucket]
    by_poster_type: List[MetricBucket]
    by_quality: List[MetricBucket]
    by_game: List[MetricBucket]
    by_background_source: List[MetricBucket]
    by_color_mode: List[MetricBucket]

    generated_at: datetime


def _buckets(dim: Dict[str, Dict[str, int]]) -> List[MetricBucket]:
    """Turn a raw {key: {count, rating_sum, rating_count}} map into sorted buckets."""
    total = sum(v["count"] for v in dim.values()) or 1
    out = [
        MetricBucket(
            key=key,
            count=v["count"],
            pct=round(100.0 * v["count"] / total, 1),
            rated=v["rating_count"],
            avg_rating=round(v["rating_sum"] / v["rating_count"], 2) if v["rating_count"] else None,
        )
        for key, v in dim.items()
    ]
    out.sort(key=lambda b: b.count, reverse=True)
    return out


@admin_router.get("/metrics", response_model=ContentMetricsResponse)
def admin_content_metrics(store: JobStore = Depends(get_job_store)) -> ContentMetricsResponse:
    """
    Content analytics for the metrics dashboard: which vibes / energies / combos /
    poster types / qualities / games users pick, the AI-generated vs upload split,
    color-mode usage, and average satisfaction ratings per choice.

    Sourced from the durable `jobs` collection (every poster stores its full input)
    plus the `rating` field — no separate events table needed. Ungated like the
    sibling admin endpoints; add ``Depends(require_admin)`` to lock it down later.
    """
    m = store.content_metrics()
    counted = m["counted"]
    r = m["ratings"]
    return ContentMetricsResponse(
        total_jobs=m["total_jobs"],
        ratings_count=r["count"],
        avg_rating=round(r["sum"] / r["count"], 2) if r["count"] else None,
        rating_histogram=r["histogram"],
        by_vibe=_buckets(counted["vibe"]),
        by_energy=_buckets(counted["energy"]),
        by_combo=_buckets(counted["combo"]),
        by_poster_type=_buckets(counted["poster_type"]),
        by_quality=_buckets(counted["quality"]),
        by_game=_buckets(counted["game"]),
        by_background_source=_buckets(counted["background_source"]),
        by_color_mode=_buckets(counted["color_mode"]),
        generated_at=datetime.now(tz=timezone.utc),
    )


class SetPlatformRequest(BaseModel):
    name: Optional[str] = None
    service_type: Optional[ServiceType] = None
    monthly_fee_usd: Optional[float] = None
    notes: Optional[str] = None
    # Partial economics patch — only the fields sent are changed.
    economics: Optional[Dict[str, float]] = None


@admin_router.post("/platforms/{platform_id}")
def set_platform(platform_id: str, body: SetPlatformRequest) -> Dict[str, object]:
    """
    Set a client's commercial metadata (service type, fee, name) AND/OR their
    Red Coins economics. Use the path value `__none__` for the dev / no-API-key
    client. Creates the record if absent; economics merge onto existing values.
    """
    pid = None if platform_id in ("__none__", "none", "null", "-") else platform_id
    p = PlatformStore().upsert(
        pid,
        name=body.name,
        service_type=body.service_type,
        monthly_fee_usd=body.monthly_fee_usd,
        notes=body.notes,
        economics=body.economics,
    )
    return {
        "platform_id": pid,
        "name": p.name,
        "service_type": p.service_type,
        "monthly_fee_usd": p.monthly_fee_usd,
        "economics": p.economics.model_dump(),
    }
