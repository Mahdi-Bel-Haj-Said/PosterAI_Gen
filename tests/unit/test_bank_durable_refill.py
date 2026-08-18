"""
Tests for the durable, never-give-up bank refill.

Covers:
- `PendingBackgroundStore` work-queue semantics (claim / done / retry-with-backoff).
- `plan_refill` persisting exactly the deficit as pending records.
- `drain_pending` uploading every background and, crucially, RETRYING a failed job
  until it succeeds — never skipping (the whole point of the durable path).

All in-memory: mongomock for the queue, LocalStorage for the bank, a fake RunPod.
No network, no real GPU.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock

from esports_poster_ai.bank import pending as pending_mod
from esports_poster_ai.bank import drain as drain_mod
from esports_poster_ai.bank.combos import Combo, all_combos
from esports_poster_ai.bank.drain import drain_pending, plan_refill
from esports_poster_ai.bank.pending import PendingBackgroundStore
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import Settings
from esports_poster_ai.storage.local import LocalStorage


def _pending_store() -> PendingBackgroundStore:
    col = mongomock.MongoClient()["testdb"]["bg_bank_pending"]
    return PendingBackgroundStore(collection=col)


def _bank(tmp_path, *, target=2) -> tuple[BankStore, Settings]:
    settings = Settings(bg_bank_prefix="Bg_bank", bg_bank_target_per_combo=target)
    store = BankStore(storage=LocalStorage(root=tmp_path), settings=settings)
    return store, settings


class _FakeGen:
    """Stand-in BankGenerator.build_prompt_for — no LLM."""

    def build_prompt_for(self, combo: Combo):
        return SimpleNamespace(
            prompt=f"p-{combo.slug}", negative_prompt="neg", width=1536, height=1536
        )


class _FakeRunpod:
    """
    Fake RunPod. The first `fail_first` submitted jobs FAIL on poll; every later job
    COMPLETES with image bytes. Lets us prove a failed background is retried, not
    skipped.
    """

    def __init__(self, *, fail_first: int = 0):
        self.fail_first = fail_first
        self.submits = 0
        self.cancelled: list[str] = []

    def submit_raw(self, **kwargs) -> str:
        self.submits += 1
        return f"job{self.submits}"

    def poll(self, job_id: str):
        n = int(job_id.removeprefix("job"))
        if n <= self.fail_first:
            raise RuntimeError("RunPod job FAILED")
        return "COMPLETED", f"img-{job_id}".encode()

    def cancel(self, job_id: str) -> None:
        self.cancelled.append(job_id)


# ------------------------------------------------------------- pending store
def test_claim_marks_in_progress_and_is_not_double_claimed():
    store = _pending_store()
    store.add_tasks(
        [{"combo_slug": "chill_cyberpunk", "prompt_text": "p", "width": 8, "height": 8, "seed": 1}],
        batch_id="b1",
    )
    first = store.claim_one()
    assert first is not None and first["status"] == "in_progress"
    # Freshly claimed (not stale) → not handed out again.
    assert store.claim_one() is None
    assert store.count_remaining() == 1  # in_progress still counts as owed


def test_mark_done_removes_the_record():
    store = _pending_store()
    store.add_tasks(
        [{"combo_slug": "chill_cyberpunk", "prompt_text": "p", "width": 8, "height": 8, "seed": 1}],
        batch_id="b1",
    )
    task = store.claim_one()
    store.mark_done(task["_id"])
    assert store.count_remaining() == 0


def test_mark_failed_backs_off_then_becomes_claimable_again(monkeypatch):
    clock = {"t": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    monkeypatch.setattr(pending_mod, "_now", lambda: clock["t"])
    store = _pending_store()
    store.add_tasks(
        [{"combo_slug": "chill_cyberpunk", "prompt_text": "p", "width": 8, "height": 8, "seed": 1}],
        batch_id="b1",
    )

    task = store.claim_one()
    store.mark_failed(task["_id"], error="boom", backoff_s=30)
    # Still owed, but inside the backoff window it is NOT claimable.
    assert store.count_remaining() == 1
    assert store.claim_one() is None
    # After the backoff elapses it comes back for another attempt (never dropped).
    clock["t"] += timedelta(seconds=31)
    again = store.claim_one()
    assert again is not None and again["attempts"] == 1


# ------------------------------------------------------------- plan_refill
def test_plan_refill_persists_exactly_the_deficit(tmp_path):
    bank, settings = _bank(tmp_path, target=2)
    bank.upload(Combo("chill", "cyberpunk"), b"one")  # 1 of 2 for this combo
    pending = _pending_store()

    added = plan_refill(settings, bank_store=bank, bank_gen=_FakeGen(), pending=pending)

    assert added == 24 * 2 - 1  # every combo owes 2, except the seeded one owes 1
    by_combo = pending.remaining_by_combo()
    assert by_combo["chill_cyberpunk"] == 1
    assert by_combo[Combo("intense", "cosmic").slug] == 2


# ------------------------------------------------------------- drain_pending
def test_drain_uploads_every_pending_background(tmp_path):
    bank, settings = _bank(tmp_path, target=1)
    pending = _pending_store()
    slugs = [Combo("chill", "cyberpunk").slug, Combo("intense", "cosmic").slug]
    pending.add_tasks(
        [{"combo_slug": s, "prompt_text": "p", "width": 8, "height": 8, "seed": i} for i, s in enumerate(slugs)],
        batch_id="b1",
    )

    uploaded = drain_pending(
        settings, pending=pending, bank_store=bank, runpod=_FakeRunpod(), poll_interval=0.0
    )

    assert sum(uploaded.values()) == 2
    assert pending.count_remaining() == 0  # queue fully drained
    assert bank.count(Combo("chill", "cyberpunk")) == 1
    assert bank.count(Combo("intense", "cosmic")) == 1


def test_drain_retries_a_failed_job_until_it_succeeds(tmp_path, monkeypatch):
    """The core guarantee: a failed background is re-submitted, never skipped."""
    bank, settings = _bank(tmp_path, target=1)
    # Controllable clock so the retry backoff elapses instantly instead of waiting.
    clock = {"t": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    monkeypatch.setattr(pending_mod, "_now", lambda: clock["t"])
    monkeypatch.setattr(drain_mod.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + timedelta(seconds=max(s, 60))))

    pending = _pending_store()
    pending.add_tasks(
        [{"combo_slug": Combo("chill", "cyberpunk").slug, "prompt_text": "p", "width": 8, "height": 8, "seed": 1}],
        batch_id="b1",
    )

    runpod = _FakeRunpod(fail_first=1)  # job1 FAILS, job2 (the retry) succeeds
    uploaded = drain_pending(
        settings, pending=pending, bank_store=bank, runpod=runpod, poll_interval=1.0
    )

    assert runpod.submits == 2  # proves it re-submitted after the failure
    assert sum(uploaded.values()) == 1
    assert pending.count_remaining() == 0
    assert bank.count(Combo("chill", "cyberpunk")) == 1


def test_drain_on_empty_queue_is_a_noop(tmp_path):
    bank, settings = _bank(tmp_path, target=1)
    pending = _pending_store()
    runpod = _FakeRunpod()
    assert drain_pending(settings, pending=pending, bank_store=bank, runpod=runpod) == {}
    assert runpod.submits == 0
