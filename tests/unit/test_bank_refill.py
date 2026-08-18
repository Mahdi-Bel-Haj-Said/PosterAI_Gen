"""Tests for refill deficit computation and the batch fill (with a fake model)."""

from __future__ import annotations

from esports_poster_ai.bank.combos import Combo, all_combos
from esports_poster_ai.bank.refill import compute_deficits, refill_once
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import Settings
from esports_poster_ai.storage.local import LocalStorage


class FakeGenerator:
    """Stands in for BankGenerator — records calls, returns deterministic bytes."""

    def __init__(self):
        self.calls: list[str] = []

    def generate_one(self, combo: Combo) -> bytes:
        self.calls.append(combo.slug)
        return f"img-{combo.slug}-{len(self.calls)}".encode()


def _make(tmp_path, *, target=2):
    settings = Settings(bg_bank_prefix="Bg_bank", bg_bank_target_per_combo=target)
    store = BankStore(storage=LocalStorage(root=tmp_path), settings=settings)
    return store, settings


def test_compute_deficits_only_reports_shortfalls(tmp_path):
    store, _ = _make(tmp_path)
    full = Combo("chill", "cyberpunk")
    store.upload(full, b"a")
    store.upload(full, b"b")  # this combo is now at target (2)

    deficits = dict((c.slug, n) for c, n in compute_deficits(store, target=2))
    assert full.slug not in deficits          # at target → no deficit
    assert deficits[Combo("chill", "cinematic").slug] == 2  # untouched → full deficit
    assert len(deficits) == 23


def test_refill_once_fills_every_combo_to_target(tmp_path):
    store, settings = _make(tmp_path)
    gen = FakeGenerator()
    added = refill_once(settings=settings, store=store, generator=gen)

    assert sum(added.values()) == 24 * 2          # 24 combos x deficit 2
    assert len(gen.calls) == 24 * 2
    assert all(store.count(c) == 2 for c in all_combos())


def test_refill_only_generates_the_deficit(tmp_path):
    store, settings = _make(tmp_path)
    combo = Combo("intense", "cosmic")
    store.upload(combo, b"pre-existing")  # already has 1 of 2

    gen = FakeGenerator()
    added = refill_once(settings=settings, store=store, generator=gen)

    assert added[combo.slug] == 1                  # only the missing one
    assert store.count(combo) == 2
    assert gen.calls.count(combo.slug) == 1        # never regenerated the full combo


def test_refill_at_target_is_a_noop(tmp_path):
    store, settings = _make(tmp_path, target=0)
    gen = FakeGenerator()
    assert refill_once(settings=settings, store=store, generator=gen) == {}
    assert gen.calls == []


def test_one_failed_image_does_not_abort_the_batch(tmp_path):
    store, settings = _make(tmp_path)

    class FlakyGen(FakeGenerator):
        def generate_one(self, combo):
            if combo.slug == "chill_cyberpunk" and len(self.calls) == 0:
                self.calls.append(combo.slug)
                raise RuntimeError("transient RunPod error")
            return super().generate_one(combo)

    added = refill_once(settings=settings, store=store, generator=FlakyGen())
    # the one failure means that combo lands 1 short, everything else is filled
    assert added["chill_cyberpunk"] == 1
    assert store.count(Combo("chill", "cyberpunk")) == 1
    assert store.count(Combo("balanced", "minimal")) == 2
