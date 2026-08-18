"""
Job handler — the function the RQ worker runs for each enqueued job.

`process_job` loads the job from the store, runs the pipeline, streams status
transitions back into the store, and records the result or the failure. It
never raises: a failed job is recorded as `failed` so the worker loop and the
billing trail stay intact.
"""

from __future__ import annotations

import logging

from esports_poster_ai.billing import quality_multiplier
from esports_poster_ai.errors import UserFacingError
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.platforms import economics_for
from esports_poster_ai.modes.consistency import run_consistency
from esports_poster_ai.modes.fresh import run_fresh
from esports_poster_ai.modes.refine import run_refine
from esports_poster_ai.storage import get_keys

logger = logging.getLogger(__name__)


def _emit_webhook(store: JobStore, job_id: str, event: str) -> None:
    """
    Fire a webhook for a finished job — best-effort, never raises.

    Lazily imported and fully guarded so that webhooks (a) cost nothing when
    disabled and (b) can never fail or slow down job processing. `emit_job_event`
    itself is a no-op unless WEBHOOKS_ENABLED is on and the job's platform has a
    matching subscription.
    """
    try:
        from esports_poster_ai.webhooks import emit_job_event

        fresh = store.get(job_id)
        if fresh is not None:
            emit_job_event(fresh, event)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — webhooks must never break the pipeline
        logger.exception("webhook.emit_failed", extra={"job_id": job_id, "event": event})


def _charge_coins(job) -> None:
    """Deduct Red Coins for a successfully completed poster. Best-effort.

    Charged only on success (the submit gate already verified the balance), so a
    failed poster never costs the user anything. Never raises — a billing hiccup
    must not turn a completed poster into a failed one.
    """
    try:
        quality = ((job.input_data or {}).get("_meta") or {}).get("quality", "medium")
        # Use the client's own economics so the charge matches the submit-time
        # estimate the org saw (same base cost, markup, exchange rate).
        tokens = economics_for(job.platform_id).estimate_tokens(quality_multiplier(quality))
        charged, balance = OrgStore().charge_coins(job.platform_id, job.org_id, tokens)
        logger.info(
            "coins.charged",
            extra={"job_id": job.job_id, "tokens": tokens, "charged": charged, "balance": balance},
        )
    except Exception:  # noqa: BLE001 — billing must never break job completion
        logger.exception("coins.charge_failed", extra={"job_id": getattr(job, "job_id", "?")})


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

    # A bank background is delete-on-serve. Track what this job consumes so we can
    # restore it if generation fails — otherwise a failed poster silently burns a
    # bank image (see bank/serve.py).
    from esports_poster_ai.bank.serve import (
        begin_serve_scope,
        commit_serve_scope,
        rollback_serve_scope,
    )

    begin_serve_scope()
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
        commit_serve_scope()  # success — the served bank image stays consumed
        _charge_coins(job)  # success only — failed posters are free
        _emit_webhook(store, job_id, "poster.completed")
    except UserFacingError as e:
        # Known, actionable failure (e.g. rejected background) — store the plain
        # message so the UI shows it verbatim, no exception-type prefix.
        logger.warning("job.failed_user_facing", extra={"job_id": job_id, "error": str(e)})
        rollback_serve_scope()  # put the consumed bank background back
        store.mark_failed(job_id, error=str(e))
        _emit_webhook(store, job_id, "poster.failed")
    except Exception as e:  # noqa: BLE001 — any failure must land as a failed job
        logger.exception("job.failed", extra={"job_id": job_id})
        rollback_serve_scope()  # put the consumed bank background back
        store.mark_failed(job_id, error=f"{type(e).__name__}: {e}")
        _emit_webhook(store, job_id, "poster.failed")


__all__ = ["process_job"]
