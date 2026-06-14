"""
Job handler — the function the RQ worker runs for each enqueued job.

`process_job` loads the job from the store, runs the pipeline, streams status
transitions back into the store, and records the result or the failure. It
never raises: a failed job is recorded as `failed` so the worker loop and the
billing trail stay intact.
"""

from __future__ import annotations

import logging

from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.modes.consistency import run_consistency
from esports_poster_ai.modes.fresh import run_fresh
from esports_poster_ai.modes.refine import run_refine
from esports_poster_ai.storage import get_keys

logger = logging.getLogger(__name__)


def process_job(job_id: str) -> None:
    """Execute one job by id. Invoked by the RQ worker."""
    store = JobStore()

    job = store.get(job_id)
    if job is None:
        logger.error("job.missing", extra={"job_id": job_id})
        return

    logger.info("job.start", extra={"job_id": job_id, "mode": job.mode})
    store.mark_running(job_id)

    def on_status(status: str) -> None:
        store.update_status(job_id, status)

    # Bind the key builder to the job's platform so every object this run writes
    # (and the Style DNA it reads) lands under platforms/{platform_id}/. None
    # platform → the historical flat layout.
    keys = get_keys(platform_id=job.platform_id)

    try:
        if job.mode == "refine":
            result = run_refine(
                job.input_data,
                org_id=job.org_id,
                tournament_id=job.tournament_id,
                on_status=on_status,
                keys=keys,
            )
        elif job.mode == "consistency":
            result = run_consistency(
                job.input_data,
                job.tournament_id,
                org_id=job.org_id,
                on_status=on_status,
                keys=keys,
            )
        else:
            result = run_fresh(
                job.input_data,
                org_id=job.org_id,
                tournament_id=job.tournament_id,
                on_status=on_status,
                keys=keys,
            )
        store.mark_completed(
            job_id,
            poster_id=result.poster_id,
            storage_key=result.storage_key,
            local_path=str(result.local_path),
        )
    except Exception as e:  # noqa: BLE001 — any failure must land as a failed job
        logger.exception("job.failed", extra={"job_id": job_id})
        store.mark_failed(job_id, error=f"{type(e).__name__}: {e}")


__all__ = ["process_job"]
