"""
Durable, never-give-up bank refill.

Flow (all off the serve path, in a detached process):

    plan_refill        compute the deficit, generate a prompt per owed background,
                       and PERSIST them as pending records (survives crashes).
    drain_pending      submit each to RunPod, wait PATIENTLY for a GPU (jobs sit in
                       RunPod's queue until one frees), upload on success, and only
                       then delete the record. Any failure/timeout keeps the record
                       pending and retries it — the bank is guaranteed to fill.
    run_refill_durable claim single-flight ownership, then loop plan→drain until the
                       bank is at target with nothing pending.
    ensure_drain_running spawn the detached drainer if one isn't already alive
                       (used by the serve-path trigger and by worker-startup recovery).

The only way a background is dropped is if it succeeds. There is no skip-on-timeout.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from esports_poster_ai.bank.combos import all_combos, combo_from_slug
from esports_poster_ai.bank.generator import BankGenerator
from esports_poster_ai.bank.pending import DrainCoordinator, PendingBackgroundStore
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- planning
def plan_refill(
    settings: Settings,
    *,
    bank_store: BankStore,
    bank_gen: BankGenerator,
    pending: PendingBackgroundStore,
    coordinator: Optional[DrainCoordinator] = None,
) -> int:
    """
    Persist a pending record for every background the bank still owes (deficit to
    target), each with a freshly built prompt + diffusion seed. Returns how many.

    Building N premium prompts is slow (one LLM call each), so `coordinator` is
    beaten as we go — otherwise the heartbeat would go stale during planning and a
    concurrent trigger could spawn a second, double-filling drainer.
    """
    import random

    target = settings.bg_bank_target_per_combo
    counts = bank_store.counts()
    tasks: List[Dict[str, Any]] = []
    for combo in all_combos():
        deficit = target - counts.get(combo.slug, 0)
        for _ in range(max(0, deficit)):
            if coordinator is not None:
                coordinator.beat()  # keep single-flight ownership alive while we build
            kp = bank_gen.build_prompt_for(combo)  # premium prompt, sized to the bank
            tasks.append(
                {
                    "combo_slug": combo.slug,
                    "prompt_text": kp.prompt,
                    "negative_prompt": kp.negative_prompt,
                    "width": kp.width,
                    "height": kp.height,
                    "seed": random.randrange(2**31),
                }
            )
    if not tasks:
        return 0
    return pending.add_tasks(tasks, batch_id=uuid.uuid4().hex)


# ------------------------------------------------------------------- draining
def drain_pending(
    settings: Settings,
    *,
    pending: PendingBackgroundStore,
    bank_store: BankStore,
    runpod: Any,
    coordinator: Optional[DrainCoordinator] = None,
    concurrency: Optional[int] = None,
    poll_interval: float = 5.0,
) -> Dict[str, int]:
    """
    Process pending records until NONE remain. Patient + retry-until-success.

    Keeps `concurrency` jobs in RunPod's queue; a job that stays queued (no GPU) is
    polled patiently up to `bg_bank_job_max_wait_seconds`, then cancelled and
    RETRIED (never skipped). Uploaded backgrounds are deleted from the queue.
    Returns `{combo_slug: uploaded}`.
    """
    concurrency = max(1, concurrency or settings.bg_bank_fill_concurrency)
    max_wait = settings.bg_bank_job_max_wait_seconds
    uploaded: Dict[str, int] = {}
    in_flight: Dict[str, Dict[str, Any]] = {}  # job_id -> {task, deadline}

    while True:
        if coordinator is not None:
            coordinator.beat()

        if pending.count_remaining() == 0 and not in_flight:
            break

        # Top RunPod's queue back up from the durable pending store.
        while len(in_flight) < concurrency:
            task = pending.claim_one(stale_after_s=settings.bg_bank_refill_lock_ttl_seconds)
            if task is None:
                break
            try:
                job_id = runpod.submit_raw(
                    prompt_text=task["prompt_text"],
                    negative_prompt=task.get("negative_prompt", ""),
                    width=task["width"],
                    height=task["height"],
                    seed=task["seed"],
                )
                in_flight[job_id] = {"task": task, "deadline": time.monotonic() + max_wait}
            except Exception as e:  # noqa: BLE001 — submit hiccup → retry this record later
                pending.mark_failed(task["_id"], error=f"submit: {type(e).__name__}: {e}", backoff_s=30)

        # Poll everything in flight (patiently — a queued job is NOT a failure).
        finished: List[str] = []
        for job_id, meta in list(in_flight.items()):
            task = meta["task"]
            try:
                _, image = runpod.poll(job_id)
            except Exception as e:  # noqa: BLE001 — RunPod FAILED/dropped → retry
                pending.mark_failed(task["_id"], error=f"job: {type(e).__name__}: {e}", backoff_s=30)
                finished.append(job_id)
                continue
            if image is not None:
                try:
                    bank_store.upload(combo_from_slug(task["combo_slug"]), image)
                    pending.mark_done(task["_id"])
                    uploaded[task["combo_slug"]] = uploaded.get(task["combo_slug"], 0) + 1
                    logger.info("bank.drain.filled", extra={"combo": task["combo_slug"]})
                except Exception as e:  # noqa: BLE001 — upload failure → retry
                    pending.mark_failed(task["_id"], error=f"upload: {e}", backoff_s=15)
                finished.append(job_id)
            elif time.monotonic() > meta["deadline"]:
                # Safety valve: waited very long with no GPU → cancel + RETRY (not skip).
                try:
                    runpod.cancel(job_id)
                except Exception:  # noqa: BLE001
                    pass
                pending.mark_failed(task["_id"], error="waited too long for a GPU; retrying", backoff_s=30)
                finished.append(job_id)
            # else: still queued/running on RunPod → keep polling, do not give up.

        for job_id in finished:
            in_flight.pop(job_id, None)

        # Pace: waiting on in-flight jobs, or everything is in backoff.
        time.sleep(poll_interval if in_flight else min(poll_interval * 3, 20.0))

    logger.info("bank.drain.done", extra={"uploaded": sum(uploaded.values())})
    return uploaded


# ------------------------------------------------------------- durable entry
def run_refill_durable(*, settings: Optional[Settings] = None) -> None:
    """
    The detached refill process: own single-flight, then loop plan→drain until the
    bank is at target with nothing pending. Resumes any leftover pending work.
    """
    s = settings or get_settings()
    coordinator = DrainCoordinator(settings=s)
    if not coordinator.claim():
        logger.info("bank.drain.already_running")
        return
    try:
        pending = PendingBackgroundStore(settings=s)
        bank_store = BankStore(settings=s)
        bank_gen = BankGenerator(s)
        from esports_poster_ai.clients.runpod_client import RunpodBackgroundGenerator

        runpod = RunpodBackgroundGenerator(
            s,
            steps=s.bg_bank_steps,
            guidance=s.bg_bank_guidance,
            poll_interval_s=5.0,
            timeout_s=s.bg_bank_job_max_wait_seconds,
        )
        while True:
            if pending.count_remaining() == 0:
                added = plan_refill(
                    s, bank_store=bank_store, bank_gen=bank_gen, pending=pending, coordinator=coordinator
                )
                logger.info("bank.refill.planned", extra={"added": added})
                if added == 0:
                    break  # bank is at target, nothing owed
            drain_pending(
                s,
                pending=pending,
                bank_store=bank_store,
                runpod=runpod,
                coordinator=coordinator,
            )
    finally:
        coordinator.release()


def ensure_drain_running(*, settings: Optional[Settings] = None, only_if_pending: bool = False) -> bool:
    """
    Spawn the detached durable-refill process if one isn't already alive.

    `only_if_pending` (worker-startup recovery) spawns only when leftover pending
    work exists. Returns True if a drainer was spawned. Never raises.
    """
    s = settings or get_settings()
    try:
        coordinator = DrainCoordinator(settings=s)
        if coordinator.is_live():
            return False
        if only_if_pending and PendingBackgroundStore(settings=s).count_remaining() == 0:
            return False
        _spawn_detached_refill(s)
        logger.info("bank.drain.spawned")
        return True
    except Exception as e:  # noqa: BLE001 — refill wiring must never break its caller
        logger.warning("bank.drain.spawn_failed", extra={"error": f"{type(e).__name__}: {e}"})
        return False


def _spawn_detached_refill(settings: Settings) -> None:
    import os
    import subprocess
    import sys

    kwargs: Dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, "-m", "esports_poster_ai.bank.seed", "--refill"],
        cwd=str(settings.project_root),
        **kwargs,
    )


__all__ = ["plan_refill", "drain_pending", "run_refill_durable", "ensure_drain_running"]
