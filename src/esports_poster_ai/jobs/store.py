"""
JobStore — the MongoDB-backed repository for `Job` documents.

This is the *system of record* for jobs. Redis/RQ moves the work; this store
holds durable status, results, and the billing trail. Every method maps the
Mongo document's `_id` to the `Job.job_id` field.

`pymongo` is imported lazily so the module (and tests that inject a collection)
work without pymongo installed. Tests pass a `mongomock` collection directly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.job import Job, JobMode, JobStatus

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_doc(job: Job) -> Dict[str, Any]:
    """Job -> Mongo document (job_id becomes _id)."""
    doc = job.model_dump()
    doc["_id"] = doc.pop("job_id")
    return doc


def _from_doc(doc: Dict[str, Any]) -> Job:
    """Mongo document -> Job (_id becomes job_id)."""
    data = dict(doc)
    data["job_id"] = data.pop("_id")
    return Job.model_validate(data)


# Index creation is idempotent but still a round trip, and JobStore is built per
# request via FastAPI's Depends — so do it once per process, not once per call.
_indexes_ready = False


def _ensure_indexes(collection: Any) -> None:
    """
    Create the idempotency index if it isn't there.

    Partial + unique on (platform_id, idempotency_key), restricted to documents
    where the key is actually a string. Without the partial filter every job that
    predates this field — and every CLI job — would collide on `null`.

    A failure here is logged, not raised: an index is an optimisation and a
    safety net, and the API should still start if the user lacks index rights.
    The duplicate-key path in `create()` is what actually enforces correctness.
    """
    global _indexes_ready
    if _indexes_ready:
        return

    try:
        collection.create_index(
            [("platform_id", 1), ("idempotency_key", 1)],
            unique=True,
            partialFilterExpression={"idempotency_key": {"$type": "string"}},
            name="uniq_platform_idempotency_key",
        )
        _indexes_ready = True
    except Exception as e:  # noqa: BLE001 — never block startup on an index
        logger.warning("job.index.failed", extra={"error": str(e)})


class JobStore:
    """Repository over the `jobs` collection in MongoDB."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        collection: Any = None,
    ) -> None:
        """
        Args:
            settings: Settings override (connection URL / db name).
            collection: A pre-built collection to use directly — lets tests
                inject a `mongomock` collection. When omitted, a real
                `pymongo` collection is created from settings.
        """
        if collection is not None:
            self._col = collection
            return

        s = settings or get_settings()
        from pymongo import MongoClient  # lazy: only needed for the real backend

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db]["jobs"]
        _ensure_indexes(self._col)

    # ---------------------------------------------------------------- create
    def create(
        self,
        *,
        input_data: Dict[str, Any],
        org_id: str,
        tournament_id: str,
        mode: JobMode,
        platform_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Job:
        """Insert a new `queued` job and return it."""
        job = Job(
            platform_id=platform_id,
            org_id=org_id,
            tournament_id=tournament_id,
            mode=mode,
            input_data=input_data,
            idempotency_key=idempotency_key,
        )
        self._col.insert_one(_to_doc(job))
        logger.info("job.created", extra={"job_id": job.job_id, "mode": mode})
        return job

    def find_by_idempotency_key(
        self, idempotency_key: str, *, platform_id: Optional[str] = None
    ) -> Optional[Job]:
        """
        The job a previous request with this key created, if any.

        Scoped by `platform_id` so two platforms can pick the same key without
        seeing each other's jobs — the same reasoning as the org-id namespacing.
        """
        doc = self._col.find_one(
            {"idempotency_key": idempotency_key, "platform_id": platform_id}
        )
        return _from_doc(doc) if doc else None

    def ping(self) -> None:
        """Raise if the database is unreachable (used by the API health check)."""
        self._col.database.command("ping")

    # ---------------------------------------------------------------- read
    def get(self, job_id: str) -> Optional[Job]:
        doc = self._col.find_one({"_id": job_id})
        return _from_doc(doc) if doc else None

    def list_for_org(
        self, org_id: str, *, limit: int = 50, platform_id: Optional[str] = None
    ) -> List[Job]:
        """Most-recent jobs for an org (poster history / billing).

        When `platform_id` is given, results are confined to that platform — the
        isolation boundary for an authenticated request. None = no platform
        filter (CLI / dev / cross-platform admin)."""
        query: Dict[str, Any] = {"org_id": org_id}
        if platform_id is not None:
            query["platform_id"] = platform_id
        cursor = self._col.find(query).sort("created_at", -1).limit(limit)
        return [_from_doc(d) for d in cursor]

    def usage_summary(
        self,
        org_id: str,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        platform_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Return a `{status: count}` map across all of an org's jobs in the window.

        Used by `GET /v1/usage` and the quota counter. Confined to `platform_id`
        when given (the isolation boundary). Iterates matching jobs but only
        reads the `status` field, so it scales to a large history.
        """
        query: Dict[str, Any] = {"org_id": org_id}
        if platform_id is not None:
            query["platform_id"] = platform_id
        if since is not None or until is not None:
            time_filter: Dict[str, Any] = {}
            if since is not None:
                time_filter["$gte"] = since
            if until is not None:
                time_filter["$lte"] = until
            query["created_at"] = time_filter

        counts: Dict[str, int] = {}
        for doc in self._col.find(query, {"status": 1, "_id": 0}):
            status = doc.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    # ---------------------------------------------------------------- admin
    def list_orgs_aggregate(self) -> List[Dict[str, Any]]:
        """
        Per-org rollup for the admin Usage & Billing view.

        Single Mongo aggregation pipeline (one round trip) returning, per
        org_id:
          * total_jobs / completed / failed
          * counts in the last 24h, 7d, 30d
          * mode breakdown (fresh / consistency / refine)
          * first_activity_at / last_activity_at
          * days_active_30d — distinct calendar days with at least one job

        Returns plain dicts (not Pydantic) — the route layer wraps them in
        the AdminOrgStats schema after adding tier / spend computations.
        """
        now = _now()
        # ms-precision is fine; the windows are coarse business buckets.
        since_24h  = datetime.fromtimestamp(now.timestamp() - 24 * 3600,        tz=timezone.utc)
        since_7d   = datetime.fromtimestamp(now.timestamp() - 7 * 24 * 3600,    tz=timezone.utc)
        since_30d  = datetime.fromtimestamp(now.timestamp() - 30 * 24 * 3600,   tz=timezone.utc)

        def _completed_within(since: datetime) -> Dict[str, Any]:
            """Build a $cond that counts a job iff status=completed AND created_at >= since."""
            return {
                "$cond": [
                    {"$and": [
                        {"$eq": ["$status", "completed"]},
                        {"$gte": ["$created_at", since]},
                    ]},
                    1, 0,
                ]
            }

        pipeline = [
            {"$group": {
                "_id": "$org_id",
                "total_jobs": {"$sum": 1},
                "completed":  {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                "failed":     {"$sum": {"$cond": [{"$eq": ["$status", "failed"]},    1, 0]}},

                # Mode breakdown counts only completed posters — these are the
                # billable rows that the customer actually got value out of.
                "mode_fresh":       {"$sum": {"$cond": [{"$and": [{"$eq": ["$status", "completed"]}, {"$eq": ["$mode", "fresh"]}]},       1, 0]}},
                "mode_consistency": {"$sum": {"$cond": [{"$and": [{"$eq": ["$status", "completed"]}, {"$eq": ["$mode", "consistency"]}]}, 1, 0]}},
                "mode_refine":      {"$sum": {"$cond": [{"$and": [{"$eq": ["$status", "completed"]}, {"$eq": ["$mode", "refine"]}]},      1, 0]}},

                # Rolling windows
                "completed_24h":  {"$sum": _completed_within(since_24h)},
                "completed_7d":   {"$sum": _completed_within(since_7d)},
                "completed_30d":  {"$sum": _completed_within(since_30d)},

                "first_activity_at": {"$min": "$created_at"},
                "last_activity_at":  {"$max": "$created_at"},

                # Collect each completed-job day so we can count distinct days
                # after the pipeline returns (Mongo's $addToSet works on full
                # values; we extract the date in Python to keep the pipeline
                # portable across Mongo versions / mongomock).
                "completed_days_30d": {"$addToSet": {
                    "$cond": [
                        {"$and": [
                            {"$eq": ["$status", "completed"]},
                            {"$gte": ["$created_at", since_30d]},
                        ]},
                        {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        None,
                    ]
                }},
            }},
            {"$sort": {"completed": -1}},   # busiest orgs first
        ]

        rows: List[Dict[str, Any]] = []
        try:
            cursor = self._col.aggregate(pipeline)
        except Exception:  # noqa: BLE001 — mongomock or pre-3.6 Mongo may not support $dateToString
            cursor = self._fallback_orgs_aggregate(
                since_24h=since_24h, since_7d=since_7d, since_30d=since_30d
            )

        for doc in cursor:
            # Strip the null sentinel that $addToSet emits for non-matching rows.
            days = [d for d in (doc.get("completed_days_30d") or []) if d]
            doc["days_active_30d"] = len(set(days))
            doc.pop("completed_days_30d", None)
            doc["org_id"] = doc.pop("_id")
            rows.append(doc)
        return rows

    def _fallback_orgs_aggregate(
        self,
        *,
        since_24h: datetime,
        since_7d: datetime,
        since_30d: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Python-side aggregation fallback for environments that can't run the
        $dateToString pipeline (mongomock in tests, very old Mongo).

        Iterates the collection once, accumulating the same counters the
        pipeline produces. Slower on big collections but keeps the route
        working everywhere.
        """
        rollup: Dict[str, Dict[str, Any]] = {}
        for doc in self._col.find(
            {},
            {"org_id": 1, "status": 1, "mode": 1, "created_at": 1, "_id": 0},
        ):
            org = doc.get("org_id") or "unknown"
            row = rollup.setdefault(org, {
                "_id": org,
                "total_jobs": 0,
                "completed": 0,
                "failed": 0,
                "mode_fresh": 0,
                "mode_consistency": 0,
                "mode_refine": 0,
                "completed_24h": 0,
                "completed_7d": 0,
                "completed_30d": 0,
                "first_activity_at": None,
                "last_activity_at": None,
                "completed_days_30d": set(),
            })
            row["total_jobs"] += 1
            status = doc.get("status")
            mode = doc.get("mode")
            created_at = doc.get("created_at")
            if status == "completed":
                row["completed"] += 1
                if mode in ("fresh", "consistency", "refine"):
                    row[f"mode_{mode}"] += 1
                if created_at:
                    if created_at >= since_24h: row["completed_24h"] += 1
                    if created_at >= since_7d:  row["completed_7d"]  += 1
                    if created_at >= since_30d:
                        row["completed_30d"] += 1
                        row["completed_days_30d"].add(created_at.date().isoformat())
            elif status == "failed":
                row["failed"] += 1
            if created_at:
                if row["first_activity_at"] is None or created_at < row["first_activity_at"]:
                    row["first_activity_at"] = created_at
                if row["last_activity_at"] is None or created_at > row["last_activity_at"]:
                    row["last_activity_at"] = created_at
        # Convert the day-set into a list so the consumer's `len(set(...))`
        # works the same way as for the Mongo path.
        out: List[Dict[str, Any]] = []
        for row in rollup.values():
            row["completed_days_30d"] = list(row["completed_days_30d"])
            out.append(row)
        out.sort(key=lambda r: r.get("completed", 0), reverse=True)
        return out

    def list_platforms_aggregate(self) -> List[Dict[str, Any]]:
        """
        Per-platform rollup (groups jobs by `platform_id`) for the provider's
        Clients view. Python-side so it works on every Mongo/mongomock; the
        volume here is one row per integrating customer, not per poster.

        Returns dicts keyed by platform with totals + 30d window + activity.
        `platform_id` may be None (dev / no API key) — that's a valid bucket.
        """
        now = _now()
        since_30d = datetime.fromtimestamp(now.timestamp() - 30 * 24 * 3600, tz=timezone.utc)
        rollup: Dict[Any, Dict[str, Any]] = {}
        for doc in self._col.find(
            {}, {"platform_id": 1, "status": 1, "created_at": 1, "_id": 0}
        ):
            pid = doc.get("platform_id")
            row = rollup.setdefault(pid, {
                "platform_id": pid, "total_jobs": 0, "completed": 0, "failed": 0,
                "completed_30d": 0, "first_activity_at": None, "last_activity_at": None,
            })
            row["total_jobs"] += 1
            status, ca = doc.get("status"), doc.get("created_at")
            if status == "completed":
                row["completed"] += 1
                if ca and ca >= since_30d:
                    row["completed_30d"] += 1
            elif status == "failed":
                row["failed"] += 1
            if ca:
                if row["first_activity_at"] is None or ca < row["first_activity_at"]:
                    row["first_activity_at"] = ca
                if row["last_activity_at"] is None or ca > row["last_activity_at"]:
                    row["last_activity_at"] = ca
        return list(rollup.values())

    # ---------------------------------------------------------------- update
    def mark_running(self, job_id: str) -> None:
        """Stamp `started_at` when the worker picks the job up."""
        self._col.update_one(
            {"_id": job_id},
            {"$set": {"started_at": _now(), "updated_at": _now()}},
        )

    def update_status(self, job_id: str, status: JobStatus) -> None:
        """Record a status transition (used as the pipeline's status callback)."""
        self._col.update_one(
            {"_id": job_id},
            {"$set": {"status": status, "updated_at": _now()}},
        )
        logger.info("job.status", extra={"job_id": job_id, "status": status})

    def mark_completed(
        self,
        job_id: str,
        *,
        poster_id: str,
        storage_key: str,
        local_path: Optional[str] = None,
    ) -> None:
        self._col.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "poster_id": poster_id,
                    "storage_key": storage_key,
                    "local_path": local_path,
                    "completed_at": _now(),
                    "updated_at": _now(),
                }
            },
        )
        logger.info("job.completed", extra={"job_id": job_id, "storage_key": storage_key})

    def set_caption(self, job_id: str, caption: str) -> None:
        """Persist a Gemini-generated social caption on the job document."""
        self._col.update_one(
            {"_id": job_id},
            {"$set": {"caption": caption, "updated_at": _now()}},
        )

    def set_rating(self, job_id: str, rating: int) -> bool:
        """
        Persist the user's 1-5 satisfaction rating on the job. Returns True if a
        job matched. The metrics dashboard reads these to compute avg rating per
        vibe / energy / combo — the main signal for which choices produce posters
        users actually like.
        """
        res = self._col.update_one(
            {"_id": job_id},
            {"$set": {"rating": int(rating), "updated_at": _now()}},
        )
        return getattr(res, "matched_count", 0) == 1

    # ---------------------------------------------------------------- metrics
    def content_metrics(self, *, platform_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate the design CHOICES users make (and how they rate the results)
        across every job — the data behind the content-metrics dashboard.

        Every poster stores its full request in `input_data`, so the distributions
        of vibe / energy / combo / poster_type / quality / game / background source
        / color mode are all derivable here with no extra capture. Ratings come
        from the `rating` field (set via the rating endpoint).

        Returns raw accumulators (counts + rating sums); the route layer turns
        them into percentages + averages. One pass over the collection, reading
        only the fields it needs, so it scales with history.
        """
        dims = ("vibe", "energy", "combo", "poster_type", "quality", "game",
                "background_source", "color_mode")
        counted: Dict[str, Dict[str, Dict[str, int]]] = {d: {} for d in dims}
        ratings = {"count": 0, "sum": 0, "histogram": {str(i): 0 for i in range(1, 6)}}
        total = 0

        query: Dict[str, Any] = {}
        if platform_id is not None:
            query["platform_id"] = platform_id

        def _bump(dim: str, key: Optional[str], rating: Optional[int]) -> None:
            if not key:
                return
            slot = counted[dim].setdefault(key, {"count": 0, "rating_sum": 0, "rating_count": 0})
            slot["count"] += 1
            if isinstance(rating, int) and 1 <= rating <= 5:
                slot["rating_sum"] += rating
                slot["rating_count"] += 1

        for doc in self._col.find(query, {"input_data": 1, "rating": 1, "_id": 0}):
            total += 1
            data = doc.get("input_data") or {}
            meta = data.get("_meta") or {}
            design = data.get("design") or {}
            bg = data.get("background") or {}
            rating = doc.get("rating")

            if isinstance(rating, int) and 1 <= rating <= 5:
                ratings["count"] += 1
                ratings["sum"] += rating
                ratings["histogram"][str(rating)] += 1

            vibe = design.get("vibe")
            energy = design.get("energy")
            _bump("vibe", vibe, rating)
            _bump("energy", energy, rating)
            _bump("combo", f"{energy}_{vibe}" if (energy and vibe) else None, rating)
            _bump("poster_type", meta.get("poster_type"), rating)
            _bump("quality", meta.get("quality"), rating)
            _bump("game", meta.get("game"), rating)
            _bump("color_mode", design.get("color_mode"), rating)

            # Background source: normalise to ai_generated / upload / none. Mirrors
            # the resolution order in stages/background.py.
            src = (bg.get("source") or "").strip().lower()
            if src == "generated":
                bg_key = "ai_generated"
            elif src == "custom" or bg.get("image_path"):
                bg_key = "upload"
            else:
                bg_key = "none"
            _bump("background_source", bg_key, rating)

        return {"total_jobs": total, "counted": counted, "ratings": ratings}

    def mark_failed(self, job_id: str, error: str) -> None:
        self._col.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "error": error,
                    "completed_at": _now(),
                    "updated_at": _now(),
                },
                "$inc": {"attempts": 1},
            },
        )
        logger.error("job.failed", extra={"job_id": job_id, "error": error})


__all__ = ["JobStore"]
