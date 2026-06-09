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

    # ---------------------------------------------------------------- create
    def create(
        self,
        *,
        input_data: Dict[str, Any],
        org_id: str,
        tournament_id: str,
        mode: JobMode,
    ) -> Job:
        """Insert a new `queued` job and return it."""
        job = Job(
            org_id=org_id,
            tournament_id=tournament_id,
            mode=mode,
            input_data=input_data,
        )
        self._col.insert_one(_to_doc(job))
        logger.info("job.created", extra={"job_id": job.job_id, "mode": mode})
        return job

    def ping(self) -> None:
        """Raise if the database is unreachable (used by the API health check)."""
        self._col.database.command("ping")

    # ---------------------------------------------------------------- read
    def get(self, job_id: str) -> Optional[Job]:
        doc = self._col.find_one({"_id": job_id})
        return _from_doc(doc) if doc else None

    def list_for_org(self, org_id: str, *, limit: int = 50) -> List[Job]:
        """Most-recent jobs for an org (poster history / billing)."""
        cursor = (
            self._col.find({"org_id": org_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [_from_doc(d) for d in cursor]

    def usage_summary(
        self,
        org_id: str,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Return a `{status: count}` map across all of an org's jobs in the window.

        Used by `GET /v1/usage` to compute billing totals. Iterates all matching
        jobs but only reads the `status` field, so it scales to a large history.
        """
        query: Dict[str, Any] = {"org_id": org_id}
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
        local_path: str,
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
