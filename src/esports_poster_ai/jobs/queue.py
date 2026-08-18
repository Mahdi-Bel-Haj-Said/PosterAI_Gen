"""
RQ job queue.

Redis is the *transport* — it moves a job_id from the enqueuer to a worker.
The MongoDB `jobs` collection (see `store.py`) is the system of record.

The queue is named `poster-ai`, which namespaces this service's keys inside a
Redis instance that may be shared with Defendr. `redis` and `rq` are imported
lazily so importing this module does not require them.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.job import Job, JobMode
from esports_poster_ai.jobs.store import JobStore

logger = logging.getLogger(__name__)

QUEUE_NAME = "poster-ai"
JOB_HANDLER = "esports_poster_ai.jobs.handlers.process_job"
JOB_TIMEOUT_SECONDS = 900  # max RUN time once a worker starts it (cold live-bg + edit)
# Max time a job may sit QUEUED (no worker) before RQ discards it. Guards against
# jobs stranded forever when the worker is down; the frontend also times out the
# UI so the user is never stuck on a silent "queued" screen.
JOB_QUEUE_TTL_SECONDS = 1800


def get_redis(settings: Optional[Settings] = None) -> Any:
    """Build a Redis connection from settings."""
    from redis import Redis  # lazy

    s = settings or get_settings()
    return Redis.from_url(s.redis_url)


def get_queue(settings: Optional[Settings] = None) -> Any:
    """Return the RQ queue, namespaced as `poster-ai`."""
    from rq import Queue  # lazy

    return Queue(QUEUE_NAME, connection=get_redis(settings))


def enqueue_poster_job(
    *,
    input_data: Dict[str, Any],
    org_id: str,
    tournament_id: str,
    mode: JobMode,
    platform_id: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> Job:
    """
    Create a `queued` Job in MongoDB and push it onto the RQ queue.

    Returns the created `Job` (its `job_id` is the handle the caller polls).
    `platform_id` (from the API key) scopes storage + isolation; None for CLI.
    """
    s = settings or get_settings()

    store = JobStore(settings=s)
    job = store.create(
        input_data=input_data,
        org_id=org_id,
        tournament_id=tournament_id,
        mode=mode,
        platform_id=platform_id,
    )

    # The Mongo job is written first; the Redis push is a separate step. If the
    # push fails, the job would otherwise be stranded in `queued` forever with
    # no worker ever picking it up — so mark it failed and surface the error.
    try:
        get_queue(s).enqueue(
            JOB_HANDLER,
            job.job_id,
            job_timeout=JOB_TIMEOUT_SECONDS,
            ttl=JOB_QUEUE_TTL_SECONDS,
        )
    except Exception as e:  # noqa: BLE001 — any push failure must un-strand the job
        store.mark_failed(job.job_id, error=f"enqueue failed: {type(e).__name__}: {e}")
        logger.error("job.enqueue_failed", extra={"job_id": job.job_id, "error": str(e)})
        raise

    logger.info("job.enqueued", extra={"job_id": job.job_id, "queue": QUEUE_NAME})
    return job


__all__ = ["enqueue_poster_job", "get_queue", "get_redis", "QUEUE_NAME"]
