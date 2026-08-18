"""
Tests for refill_batched — the queue-full pipeline that keeps the RunPod worker
warm. Uses a fake submit/poll generator (no network) and forces economy prompts
(blank OpenAI key) so prompt-building is offline too.
"""

from __future__ import annotations

from esports_poster_ai.bank.combos import Combo, all_combos
from esports_poster_ai.bank.generator import BankGenerator
from esports_poster_ai.bank.refill import refill_batched
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import Settings
from esports_poster_ai.storage.local import LocalStorage


class FakeRunpod:
    """Stands in for RunpodBackgroundGenerator's submit/poll async API."""

    def __init__(self, *, complete_after: int = 1, fail_seq: set[int] | None = None):
        self.timeout_s = 900.0
        self.complete_after = complete_after
        self.fail_seq = fail_seq or set()  # 1-based submission indices that fail
        self._count = 0
        self._polls: dict[str, int] = {}
        self._fail_ids: set[str] = set()
        self._in_flight: set[str] = set()
        self.max_in_flight = 0
        self.submitted = 0

    def submit(self, prompt, *, seed) -> str:
        self._count += 1
        job_id = f"job{self._count}"
        self._polls[job_id] = 0
        if self._count in self.fail_seq:
            self._fail_ids.add(job_id)
        self._in_flight.add(job_id)
        self.max_in_flight = max(self.max_in_flight, len(self._in_flight))
        self.submitted += 1
        return job_id

    def poll(self, job_id):
        self._polls[job_id] += 1
        if job_id in self._fail_ids:
            self._in_flight.discard(job_id)
            raise RuntimeError("simulated job failure")
        if self._polls[job_id] >= self.complete_after:
            self._in_flight.discard(job_id)
            return ("COMPLETED", f"img-{job_id}".encode())
        return ("IN_PROGRESS", None)


def _setup(tmp_path, *, target=2, concurrency=3):
    settings = Settings(
        openai_api_key="",  # forces economy prompts → no network in build_prompt_for
        bg_bank_prefix="Bg_bank_lol",
        bg_bank_target_per_combo=target,
        bg_bank_fill_concurrency=concurrency,
    )
    store = BankStore(storage=LocalStorage(root=tmp_path), settings=settings)
    bank_gen = BankGenerator(settings, generator=object())  # generator unused by build_prompt_for
    return settings, store, bank_gen


def test_fills_every_combo_to_target(tmp_path):
    settings, store, bank_gen = _setup(tmp_path, target=2)
    runpod = FakeRunpod(complete_after=1)
    added = refill_batched(
        settings=settings, store=store, bank_gen=bank_gen, runpod=runpod, poll_interval=0
    )
    assert sum(added.values()) == 24 * 2
    assert runpod.submitted == 24 * 2
    assert all(store.count(c) == 2 for c in all_combos())


def test_concurrency_is_bounded(tmp_path):
    settings, store, bank_gen = _setup(tmp_path, target=2, concurrency=3)
    runpod = FakeRunpod(complete_after=2)  # takes 2 polls, so jobs overlap
    refill_batched(
        settings=settings, store=store, bank_gen=bank_gen, runpod=runpod, poll_interval=0
    )
    assert runpod.max_in_flight <= 3  # never exceeds the configured queue depth
    assert runpod.max_in_flight >= 1


def test_a_failed_job_skips_one_image_only(tmp_path):
    settings, store, bank_gen = _setup(tmp_path, target=2)
    runpod = FakeRunpod(complete_after=1, fail_seq={1})  # first submitted job fails
    added = refill_batched(
        settings=settings, store=store, bank_gen=bank_gen, runpod=runpod, poll_interval=0
    )
    # 48 tasks, 1 fails → 47 uploaded; the batch is not aborted
    assert sum(added.values()) == 47


def test_nothing_to_do_returns_empty(tmp_path):
    settings, store, bank_gen = _setup(tmp_path, target=1)
    for combo in all_combos():
        store.upload(combo, b"pre")  # already at target 1
    runpod = FakeRunpod()
    added = refill_batched(
        settings=settings, store=store, bank_gen=bank_gen, runpod=runpod, poll_interval=0
    )
    assert added == {}
    assert runpod.submitted == 0
