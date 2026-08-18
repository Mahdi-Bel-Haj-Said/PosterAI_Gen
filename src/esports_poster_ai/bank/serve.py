"""
Serve a background from the bank for a poster request.

This is the glue the background stage calls when `background.source ==
"generated"`. It maps the request's (energy, vibe) to a combo, serves one image
delete-on-serve, and — if that serve dropped the combo to the refill threshold —
kicks off a (locked, single-flight) refill. A miss returns None so the caller
can fall back to live generation.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any, Dict, Optional

from esports_poster_ai.bank.combos import combo_or_none
from esports_poster_ai.bank.refill import maybe_trigger_refill
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- reservation
# The bank serves delete-on-serve, so a background is removed the instant it's
# handed to the pipeline — BEFORE the poster is known to succeed. If generation
# then fails (e.g. a transient vision-model hiccup), that background would be
# permanently lost even though the user got nothing. To prevent that waste we
# remember the served background for the duration of the job; the job handler
# COMMITS the delete on success or RESTORES the background on failure.
#
# A contextvar (not a global) so the marker is request-scoped and can't leak
# between jobs. The worker runs one job at a time synchronously, so the marker
# set deep in `try_serve_from_bank` is visible to the handler that wraps it.
_last_served: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "bank_last_served", default=None
)


def begin_serve_scope() -> None:
    """Clear any prior marker at the start of a job (defensive; the handler resets)."""
    _last_served.set(None)


def commit_serve_scope() -> None:
    """Poster succeeded — the delete-on-serve stands. Drop the marker."""
    _last_served.set(None)


def rollback_serve_scope() -> None:
    """
    Poster FAILED — put the consumed background back in the bank so a failed
    generation never costs a bank image. Best-effort; never raises.
    """
    rec = _last_served.get()
    _last_served.set(None)
    if not rec:
        return
    try:
        BankStore(settings=rec["settings"]).upload(rec["combo"], rec["image"])
        logger.info("bank.serve.restored_after_failure", extra={"combo": rec["combo"].slug})
    except Exception as e:  # noqa: BLE001 — restoring must never mask the real failure
        logger.warning(
            "bank.serve.restore_failed",
            extra={"combo": rec["combo"].slug, "error": f"{type(e).__name__}: {e}"},
        )


def try_serve_from_bank(
    input_data: Dict[str, Any], *, settings: Optional[Settings] = None
) -> Optional[bytes]:
    """
    Return a ready background for this request's combo, or None on a bank miss.

    Never raises: any bank/storage error degrades to None (→ live fallback).
    """
    s = settings or get_settings()
    design = (input_data or {}).get("design") or {}
    combo = combo_or_none(design.get("energy"), design.get("vibe"))
    if combo is None:
        logger.info(
            "bank.serve.no_combo",
            extra={"energy": design.get("energy"), "vibe": design.get("vibe")},
        )
        return None

    store = BankStore(settings=s)
    try:
        served = store.serve_and_delete(combo)
    except Exception as e:  # noqa: BLE001 — a bank hiccup falls back to live
        logger.warning(
            "bank.serve.error", extra={"combo": combo.slug, "error": f"{type(e).__name__}: {e}"}
        )
        return None

    if served is None:
        logger.info("bank.serve.miss", extra={"combo": combo.slug})
        return None

    # Remember what we consumed so the job handler can restore it if the poster
    # ultimately fails (see the reservation helpers above).
    _last_served.set({"combo": combo, "image": served.image, "settings": s})

    if served.remaining <= s.bg_bank_refill_threshold:
        maybe_trigger_refill(settings=s)  # own error handling; never raises

    return served.image


__all__ = [
    "try_serve_from_bank",
    "begin_serve_scope",
    "commit_serve_scope",
    "rollback_serve_scope",
]
