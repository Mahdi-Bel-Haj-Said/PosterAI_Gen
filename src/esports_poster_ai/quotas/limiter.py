"""
Rate limiter — rolling-window quotas per org.

Three windows (last 24h, last 7d, last 30d). A poster job counts toward the
quota unless its status is `failed` — the user shouldn't be punished for our
errors. The MongoDB `jobs` collection is the source of truth (`JobStore`),
so quotas and the rest of the billing trail can never drift.

Per-org limits live in the `org_limits` collection. Missing org -> defaults
from `Settings`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Response
from pydantic import BaseModel, Field

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.jobs.store import JobStore

logger = logging.getLogger(__name__)


# Status values that do NOT consume a quota slot. Failed jobs are excluded
# so a transient OpenAI error never costs a user one of their daily slots.
_NON_COUNTED_STATUSES = {"failed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- per-org limits

class OrgLimits(BaseModel):
    """Mongo-backed per-org rate-limit overrides. Missing fields use defaults."""

    org_id: str
    day: Optional[int] = Field(default=None, ge=0)
    week: Optional[int] = Field(default=None, ge=0)
    month: Optional[int] = Field(default=None, ge=0)


class OrgLimitsStore:
    """Tiny repository over the `org_limits` MongoDB collection."""

    def __init__(self, *, settings: Optional[Settings] = None, collection: Any = None) -> None:
        if collection is not None:
            self._col = collection
            return
        s = settings or get_settings()
        from pymongo import MongoClient  # lazy
        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db]["org_limits"]

    def get_effective(self, org_id: str, settings: Optional[Settings] = None) -> Dict[str, int]:
        """Return the effective {day, week, month} caps for an org."""
        s = settings or get_settings()
        defaults = {
            "day": s.quota_day_default,
            "week": s.quota_week_default,
            "month": s.quota_month_default,
        }
        doc = self._col.find_one({"_id": org_id})
        if not doc:
            return defaults
        effective = dict(defaults)
        for k in ("day", "week", "month"):
            v = doc.get(k)
            if isinstance(v, int) and v >= 0:
                effective[k] = v
        return effective

    def set_limits(self, org_id: str, *, day: Optional[int] = None,
                   week: Optional[int] = None, month: Optional[int] = None) -> None:
        """Upsert limits for an org. None means 'use default' (clears the override)."""
        update: Dict[str, Any] = {}
        unset: Dict[str, Any] = {}
        for key, val in (("day", day), ("week", week), ("month", month)):
            if val is None:
                unset[key] = ""
            else:
                update[key] = int(val)
        op: Dict[str, Any] = {}
        if update:
            op["$set"] = update
        if unset:
            op["$unset"] = unset
        if not op:
            return
        self._col.update_one({"_id": org_id}, op, upsert=True)


# ---------------------------------------------------------------- window query

_WINDOWS: List[tuple] = [
    # (label, duration)
    ("day",   timedelta(days=1)),
    ("week",  timedelta(days=7)),
    ("month", timedelta(days=30)),
]


@dataclass
class _WindowState:
    label: str
    used: int
    limit: int
    oldest_at: Optional[datetime]   # earliest counted job in the window
    duration: timedelta


def _count_in_window(
    store: JobStore,
    org_id: str,
    since: datetime,
    platform_id: Optional[str] = None,
) -> tuple[int, Optional[datetime]]:
    """
    Count org jobs since `since` excluding failed; also return the oldest
    counted job's `created_at` so callers can compute a precise reset time.

    Confined to `platform_id` when given — quota is per (platform, org).
    """
    counts = store.usage_summary(org_id, since=since, platform_id=platform_id)
    used = sum(c for status, c in counts.items() if status not in _NON_COUNTED_STATUSES)

    # Oldest counted job in the window — drives the reset_at calculation.
    oldest_at: Optional[datetime] = None
    col = getattr(store, "_col", None)
    if col is not None and used > 0:
        oldest_query: Dict[str, Any] = {
            "org_id": org_id,
            "created_at": {"$gte": since},
            "status": {"$nin": list(_NON_COUNTED_STATUSES)},
        }
        if platform_id is not None:
            oldest_query["platform_id"] = platform_id
        cursor = col.find(
            oldest_query,
            {"created_at": 1, "_id": 0},
        ).sort("created_at", 1).limit(1)
        for doc in cursor:
            oldest_at = doc.get("created_at")
            break
    return used, oldest_at


# ---------------------------------------------------------------- public API

class WindowQuota(BaseModel):
    """One rolling window's current state."""

    window: str         # "day" | "week" | "month"
    used: int
    limit: int
    remaining: int
    oldest_at: Optional[datetime] = None    # oldest counted job in this window
    reset_at: Optional[datetime] = None     # when one slot frees up (oldest + duration)


def _effective_from_override(override: Dict[str, Any], s: Settings) -> Dict[str, int]:
    """Merge a per-org limits override (possibly with None fields) over the defaults."""
    eff = {
        "day": s.quota_day_default,
        "week": s.quota_week_default,
        "month": s.quota_month_default,
    }
    for k in ("day", "week", "month"):
        v = override.get(k)
        if isinstance(v, int) and v >= 0:
            eff[k] = v
    return eff


def compute_quotas(
    org_id: str,
    *,
    platform_id: Optional[str] = None,
    limits: Optional[Dict[str, Any]] = None,
    job_store: Optional[JobStore] = None,
    limits_store: Optional[OrgLimitsStore] = None,
    settings: Optional[Settings] = None,
    now: Optional[datetime] = None,
) -> List[WindowQuota]:
    """Return the org's current state for all three rolling windows.

    Confined to `platform_id` when given — quota is per (platform, org). When
    `limits` (the org's own day/week/month override, edited by the platform) is
    supplied it wins; otherwise the legacy `org_limits` collection / service
    defaults apply."""
    s = settings or get_settings()
    js = job_store or JobStore(settings=s)
    if limits is not None:
        effective = _effective_from_override(limits, s)
    else:
        ls = limits_store or OrgLimitsStore(settings=s)
        effective = ls.get_effective(org_id, settings=s)
    limits = effective
    t = now or _now()

    results: List[WindowQuota] = []
    for label, duration in _WINDOWS:
        since = t - duration
        used, oldest_at = _count_in_window(js, org_id, since, platform_id)
        limit = limits[label]
        reset_at = (oldest_at + duration) if oldest_at is not None else None
        results.append(
            WindowQuota(
                window=label,
                used=used,
                limit=limit,
                remaining=max(0, limit - used),
                oldest_at=oldest_at,
                reset_at=reset_at,
            )
        )
    return results


def check_quota_or_raise(
    org_id: str,
    *,
    platform_id: Optional[str] = None,
    limits: Optional[Dict[str, Any]] = None,
    job_store: Optional[JobStore] = None,
    limits_store: Optional[OrgLimitsStore] = None,
    settings: Optional[Settings] = None,
    now: Optional[datetime] = None,
) -> List[WindowQuota]:
    """
    Compute current usage and raise HTTPException(429) if any window is full.

    Returns the computed quotas on success so callers can attach the standard
    `X-RateLimit-*` headers to the success response.
    """
    quotas = compute_quotas(
        org_id, platform_id=platform_id, limits=limits, job_store=job_store,
        limits_store=limits_store, settings=settings, now=now,
    )
    exceeded = [q for q in quotas if q.remaining <= 0]
    if exceeded:
        first = exceeded[0]  # tightest window listed first by design
        retry_after = None
        if first.reset_at is not None:
            retry_after = max(1, int((first.reset_at - (now or _now())).total_seconds()))
        detail = {
            "code": "rate_limited",
            "message": (
                f"Rate limit exceeded on '{first.window}' window "
                f"({first.used}/{first.limit})."
            ),
            "windows": [q.model_dump(mode="json") for q in quotas],
        }
        headers: Dict[str, str] = {}
        for q in quotas:
            cap = q.window.capitalize()
            headers[f"X-RateLimit-Limit-{cap}"] = str(q.limit)
            headers[f"X-RateLimit-Remaining-{cap}"] = str(q.remaining)
            if q.reset_at is not None:
                headers[f"X-RateLimit-Reset-{cap}"] = str(int(q.reset_at.timestamp()))
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        logger.info(
            "quota.exceeded",
            extra={"org_id": org_id, "window": first.window,
                   "used": first.used, "limit": first.limit},
        )
        raise HTTPException(status_code=429, detail=detail, headers=headers)
    return quotas


def apply_quota_headers(response: Response, quotas: List[WindowQuota]) -> None:
    """Stamp `X-RateLimit-*` headers on a success response."""
    for q in quotas:
        cap = q.window.capitalize()
        response.headers[f"X-RateLimit-Limit-{cap}"] = str(q.limit)
        response.headers[f"X-RateLimit-Remaining-{cap}"] = str(q.remaining)
        if q.reset_at is not None:
            response.headers[f"X-RateLimit-Reset-{cap}"] = str(int(q.reset_at.timestamp()))
