"""
One-time / operational CLI for the background bank.

    # create the 24 combo folders in R2 (writes a .keep marker in each)
    python -m esports_poster_ai.bank.seed --init-folders

    # show how many ready backgrounds each combo has
    python -m esports_poster_ai.bank.seed --status

    # fill every combo up to the target — synchronous, watch progress live.
    # Skips an image on a transient failure; re-run to pick up the remainder.
    python -m esports_poster_ai.bank.seed --fill

    # DURABLE fill: persist the owed work in MongoDB, wait patiently for a GPU,
    # and RETRY every background until the bank is full (never skips). This is the
    # production auto-refill entry point — safe to run under GPU shortage. Runs a
    # foreground drain loop; also spawned detached by the auto-refill trigger.
    python -m esports_poster_ai.bank.seed --refill

    # show the durable pending-work queue (what a --refill still owes)
    python -m esports_poster_ai.bank.seed --drain-status

`--fill` / `--refill` need RUNPOD_API_KEY + RUNPOD_ENDPOINT_ID configured;
`--init-folders`, `--status`, and `--drain-status` only need R2 / Mongo creds.
"""

from __future__ import annotations

import argparse
import logging

from esports_poster_ai.bank.refill import compute_deficits, refill_batched
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import get_settings


def _print_status(store: BankStore) -> None:
    counts = store.counts()
    target = store._settings.bg_bank_target_per_combo  # noqa: SLF001 — CLI convenience
    total = sum(counts.values())
    print(f"Bank status  (target {target}/combo, {len(counts)} combos, {total} images):")
    for slug, n in counts.items():
        flag = "" if n >= target else "  <- low" if n > store._settings.bg_bank_refill_threshold else "  <- REFILL"  # noqa: SLF001
        print(f"  {slug:<28} {n}{flag}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed / inspect the background bank.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init-folders", action="store_true", help="Create the 24 combo folders (.keep markers).")
    group.add_argument("--status", action="store_true", help="Print ready-count per combo.")
    group.add_argument("--fill", action="store_true", help="Generate every combo's deficit up to target (in-process, skip-on-fail).")
    group.add_argument("--refill", action="store_true", help="Durable fill: persist work, wait for GPU, retry until full (never skips).")
    group.add_argument("--drain-status", action="store_true", help="Print the durable pending-work queue.")
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Override target count per combo for --fill / --refill (e.g. 1 for a one-per-combo validation pass).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.target is not None:
        settings = settings.model_copy(update={"bg_bank_target_per_combo": args.target})
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s %(message)s")
    store = BankStore(settings=settings)

    if args.init_folders:
        prefixes = store.ensure_folders()
        print(f"Ensured {len(prefixes)} combo folders under '{store.prefix}/':")
        for p in prefixes:
            print(f"  {p}")
        return 0

    if args.status:
        _print_status(store)
        return 0

    if args.drain_status:
        from esports_poster_ai.bank.pending import DrainCoordinator, PendingBackgroundStore

        pending = PendingBackgroundStore(settings=settings)
        remaining = pending.count_remaining()
        live = DrainCoordinator(settings=settings).is_live()
        print(f"Durable refill queue: {remaining} background(s) owed; drainer {'LIVE' if live else 'idle'}.")
        for slug, n in sorted(pending.remaining_by_combo().items()):
            print(f"  {slug:<28} {n}")
        return 0

    if args.refill:
        print(
            "Durable refill: persisting owed work to MongoDB, then draining it via RunPod.\n"
            "Waits patiently for a free GPU and retries every background until the bank is "
            "full — safe to Ctrl-C and re-run (it resumes)."
        )
        from esports_poster_ai.bank.drain import run_refill_durable

        run_refill_durable(settings=settings)
        try:
            _print_status(store)
        except Exception as e:  # noqa: BLE001
            print(f"(could not list bank status: {type(e).__name__})")
        return 0

    if args.fill:
        print(
            f"Filling bank to target via RunPod (queue depth {settings.bg_bank_fill_concurrency}, "
            f"{settings.bg_bank_image_size}²). Keep the endpoint's Max Workers = 1 so it stays "
            "on one warm worker.\nFirst image cold-starts (~6 min); the rest run back-to-back warm."
        )

        def _progress(slug: str, done: int, total: int) -> None:
            print(f"  [{done}/{total}] +{slug}", flush=True)

        # Distinguish "nothing to generate" from "generated 0" (all attempts failed).
        deficit = sum(n for _, n in compute_deficits(store, settings.bg_bank_target_per_combo))
        added = refill_batched(settings=settings, store=store, on_progress=_progress)
        got = sum(added.values())
        if deficit == 0:
            print("Nothing to do — every combo is already at target.")
        elif got == 0:
            print(f"\n⚠️ Generated 0 of {deficit} — all attempts failed (check the log above).")
        else:
            print(f"\nAdded {got} of {deficit} images across {len(added)} combos.")
        try:
            _print_status(store)
        except Exception as e:  # noqa: BLE001 — don't let a status-list hiccup mask the result
            print(f"(could not list bank status: {type(e).__name__})")
        return 0

    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
