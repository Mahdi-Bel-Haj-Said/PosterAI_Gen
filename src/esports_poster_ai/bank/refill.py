"""
Bank refill — keep every combo topped up to the target.

Two code paths share this module:

- **Synchronous fill** (`refill_batched`) — the manual `bank.seed --fill`. Builds
  all prompts up front, keeps RunPod's queue full, and skips an image on a
  transient failure (re-run to pick up the remainder). Watch it run live.

- **Durable auto-refill** (`maybe_trigger_refill` → `bank.drain`) — the production
  trigger. Whenever a served combo drops to <= `bg_bank_refill_threshold`, it
  spawns the durable drainer, which persists the owed work in MongoDB, waits
  patiently for a GPU, and RETRIES every background until the bank is full. It
  runs as a DETACHED process so it can never block poster generation, and its
  single-flight is enforced by the drain coordinator (not a Redis lock).
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, Dict, List, Optional, Tuple

from esports_poster_ai.bank.combos import Combo, all_combos
from esports_poster_ai.bank.generator import BankGenerator
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)


def compute_deficits(store: BankStore, target: int) -> List[Tuple[Combo, int]]:
    """Combos below `target`, paired with how many images each still needs."""
    counts = store.counts()
    out: List[Tuple[Combo, int]] = []
    for combo in all_combos():
        deficit = target - counts.get(combo.slug, 0)
        if deficit > 0:
            out.append((combo, deficit))
    return out


def refill_once(
    *,
    settings: Optional[Settings] = None,
    store: Optional[BankStore] = None,
    generator: Optional[BankGenerator] = None,
) -> Dict[str, int]:
    """
    Do the actual work: generate every combo's deficit and upload each image.

    Returns a `{combo_slug: images_added}` map. A single image failing (e.g. a
    transient RunPod error) is logged and skipped — it never aborts the batch,
    and the next refill simply picks up the remaining deficit.
    """
    s = settings or get_settings()
    store = store or BankStore(settings=s)
    generator = generator or BankGenerator(s)
    target = s.bg_bank_target_per_combo

    added: Dict[str, int] = {}
    deficits = compute_deficits(store, target)
    logger.info(
        "bank.refill.start",
        extra={"combos_needing": len(deficits), "total_deficit": sum(d for _, d in deficits)},
    )
    for combo, deficit in deficits:
        for _ in range(deficit):
            try:
                image = generator.generate_one(combo)
                store.upload(combo, image)
                added[combo.slug] = added.get(combo.slug, 0) + 1
            except Exception as e:  # noqa: BLE001 — one bad image must not kill the batch
                logger.warning(
                    "bank.refill.image_failed",
                    extra={"combo": combo.slug, "error": f"{type(e).__name__}: {e}"},
                )
    logger.info("bank.refill.done", extra={"added": sum(added.values())})
    return added


def refill_batched(
    *,
    settings: Optional[Settings] = None,
    store: Optional[BankStore] = None,
    bank_gen: Optional[BankGenerator] = None,
    runpod=None,
    concurrency: Optional[int] = None,
    poll_interval: float = 3.0,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, int]:
    """
    Fill every combo's deficit while keeping RunPod's queue continuously full.

    Sequential generation lets the serverless worker scale to zero between images
    (each restart cold-reloads the 20B model, ~6 min of wasted GPU). This instead
    keeps `concurrency` jobs in flight so the worker always has a next job queued
    → it cold-starts ONCE, then runs every image back-to-back warm, and scales to
    zero only when the whole fill is done. Requires the endpoint's Max Workers = 1
    so the extra queued jobs don't spin up additional (cold-starting) workers.

    All prompts are built up front (LLM calls done before any GPU work), so the
    generation phase has no prompt-building gaps. Per-image failures are logged and
    skipped; the next refill picks up the remainder. Returns `{slug: images_added}`.
    """
    s = settings or get_settings()
    store = store or BankStore(settings=s)
    bank_gen = bank_gen or BankGenerator(s)
    if runpod is None:
        from esports_poster_ai.clients.runpod_client import RunpodBackgroundGenerator

        runpod = RunpodBackgroundGenerator(
            s,
            steps=s.bg_bank_steps,
            guidance=s.bg_bank_guidance,
            poll_interval_s=5.0,
            timeout_s=900.0,
        )
    concurrency = max(1, concurrency or s.bg_bank_fill_concurrency)

    # 1. Pre-build every prompt (all LLM work up front → no GPU idle mid-fill).
    tasks: List[Tuple[Combo, object, int]] = []
    for combo, deficit in compute_deficits(store, s.bg_bank_target_per_combo):
        for _ in range(deficit):
            tasks.append((combo, bank_gen.build_prompt_for(combo), random.randrange(2**31)))
    total = len(tasks)
    if not total:
        return {}
    logger.info("bank.fill.start", extra={"total": total, "concurrency": concurrency})

    # 2. Rolling window: keep the queue full, upload each result as it lands.
    added: Dict[str, int] = {}
    in_flight: Dict[str, Tuple[Combo, float]] = {}  # job_id -> (combo, deadline)
    next_task = 0
    processed = 0
    job_timeout = getattr(runpod, "timeout_s", 900.0)

    while next_task < total or in_flight:
        # Top the queue back up to `concurrency`.
        while len(in_flight) < concurrency and next_task < total:
            combo, prompt, seed = tasks[next_task]
            next_task += 1
            try:
                job_id = runpod.submit(prompt, seed=seed)
                in_flight[job_id] = (combo, time.monotonic() + job_timeout)
            except Exception as e:  # noqa: BLE001 — a submit hiccup skips one image
                processed += 1
                logger.warning(
                    "bank.fill.submit_failed",
                    extra={"combo": combo.slug, "error": f"{type(e).__name__}: {e}"},
                )

        # Poll everything in flight once.
        finished: List[str] = []
        for job_id, (combo, deadline) in list(in_flight.items()):
            try:
                _, image = runpod.poll(job_id)
            except Exception as e:  # noqa: BLE001 — a failed job skips one image
                finished.append(job_id)
                processed += 1
                logger.warning(
                    "bank.fill.job_failed",
                    extra={"combo": combo.slug, "job_id": job_id, "error": f"{type(e).__name__}: {e}"},
                )
                continue
            if image is not None:
                try:
                    store.upload(combo, image)
                    added[combo.slug] = added.get(combo.slug, 0) + 1
                except Exception as e:  # noqa: BLE001 — upload failure skips one image
                    logger.warning("bank.fill.upload_failed", extra={"combo": combo.slug, "error": str(e)})
                finished.append(job_id)
                processed += 1
                if on_progress:
                    on_progress(combo.slug, processed, total)
            elif time.monotonic() > deadline:
                finished.append(job_id)
                processed += 1
                logger.warning("bank.fill.job_timeout", extra={"combo": combo.slug, "job_id": job_id})

        for job_id in finished:
            in_flight.pop(job_id, None)

        # Nothing finished this pass but jobs are still running → wait before re-poll.
        if in_flight and not finished:
            time.sleep(poll_interval)

    logger.info("bank.fill.done", extra={"added": sum(added.values()), "total": total})
    return added


def maybe_trigger_refill(*, settings: Optional[Settings] = None) -> bool:
    """
    Kick off a DURABLE bank refill without touching the poster job worker.

    Guarded by the auto-refill kill-switch. Delegates to the durable drainer
    (`bank.drain`), which persists the owed work in MongoDB, waits patiently for a
    GPU, and retries every background until the bank is filled — it never skips.
    Single-flight is enforced by the drain coordinator (a live drainer is not
    duplicated). Returns True if a drainer was spawned, False if disabled / already
    running. Never raises — serving must not fail on refill wiring.
    """
    s = settings or get_settings()
    if not s.bg_bank_auto_refill_enabled:
        logger.info("bank.refill.disabled")
        return False
    from esports_poster_ai.bank.drain import ensure_drain_running

    return ensure_drain_running(settings=s, only_if_pending=False)


__all__ = [
    "compute_deficits",
    "refill_once",
    "refill_batched",
    "maybe_trigger_refill",
]
