"""
Pre-generated background bank.

Backgrounds are generated **offline in batches** and served **instantly** from
R2 (delete-on-serve), decoupling serving latency from model inference. When any
combo runs low, a durable, never-give-up refill tops every combo back up — it
persists the owed work, waits patiently for a GPU, and retries until the bank
is full.

Modules:
- `combos`     — the 24 (energy, vibe) combos.
- `store`      — `BankStore`: counts, serve-and-delete, upload, folder seeding.
- `generator`  — `BankGenerator`: combo → prompt → RunPod → image bytes.
- `pending`    — durable pending-work store + drain coordinator (MongoDB).
- `drain`      — the durable refill: plan → drain (patient, retry-until-full).
- `refill`     — deficits, the synchronous `refill_batched`, `maybe_trigger_refill`.
- `serve`      — `try_serve_from_bank`: the background-stage glue.
- `seed`       — one-time CLI to create folders / fill the bank.
"""

from __future__ import annotations

from esports_poster_ai.bank.combos import (
    Combo,
    all_combos,
    combo_from_slug,
    combo_or_none,
)
from esports_poster_ai.bank.drain import (
    drain_pending,
    ensure_drain_running,
    plan_refill,
    run_refill_durable,
)
from esports_poster_ai.bank.generator import BankGenerator
from esports_poster_ai.bank.refill import (
    compute_deficits,
    maybe_trigger_refill,
    refill_batched,
    refill_once,
)
from esports_poster_ai.bank.serve import try_serve_from_bank
from esports_poster_ai.bank.store import BankServe, BankStore

__all__ = [
    "Combo",
    "all_combos",
    "combo_from_slug",
    "combo_or_none",
    "BankStore",
    "BankServe",
    "BankGenerator",
    "compute_deficits",
    "refill_once",
    "refill_batched",
    "maybe_trigger_refill",
    "plan_refill",
    "drain_pending",
    "run_refill_durable",
    "ensure_drain_running",
    "try_serve_from_bank",
]
