"""
`GET /v1/usage` — usage / cost report for an org.

Aggregates over the `jobs` collection — counts by status and an estimated
cost (number of completed posters × `cost_per_poster_usd` from settings).
For now this is the billing trail; a dedicated `usage_events` table can
follow if finer-grained per-call detail is needed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from typing import List

from fastapi import APIRouter, Depends, Query

from esports_poster_ai.api.routes.posters import get_job_store
from esports_poster_ai.api.schemas import UsageResponse
from esports_poster_ai.config import get_settings
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.quotas import WindowQuota, compute_quotas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
def get_usage(
    org_id: str = Query(..., description="Organization id."),
    since: Optional[datetime] = Query(
        None, description="ISO-8601 lower bound on job created_at (inclusive)."
    ),
    until: Optional[datetime] = Query(
        None, description="ISO-8601 upper bound on job created_at (inclusive)."
    ),
    store: JobStore = Depends(get_job_store),
) -> UsageResponse:
    """Aggregate jobs by status and return an estimated cost for the period."""
    counts = store.usage_summary(org_id, since=since, until=until)
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
    org_id: str = Query(..., description="Organization id."),
    store: JobStore = Depends(get_job_store),
) -> List[WindowQuota]:
    """
    Per-org rate-limit state for the rolling day / week / month windows.

    The UI calls this on the dashboard and after each generate attempt to
    show "today X/Y" chips and the reset time when a window is full.
    Failed jobs do not count toward usage.
    """
    return compute_quotas(org_id, job_store=store)
