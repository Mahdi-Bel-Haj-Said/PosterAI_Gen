"""
A bank background is delete-on-serve, so it's removed before the poster is known
to succeed. If generation fails, the job handler must RESTORE it — a failed
poster should never burn a bank image. These tests cover the serve-scope
commit/rollback helpers.
"""

from __future__ import annotations

import esports_poster_ai.bank.serve as serve_mod
import esports_poster_ai.bank.store as store_mod
from esports_poster_ai.bank.combos import Combo
from esports_poster_ai.bank.serve import (
    begin_serve_scope,
    commit_serve_scope,
    rollback_serve_scope,
    try_serve_from_bank,
)
from esports_poster_ai.bank.store import BankStore
from esports_poster_ai.config import Settings
from esports_poster_ai.storage.local import LocalStorage


def _settings():
    return Settings(bg_bank_prefix="Bg_bank", bg_bank_target_per_combo=5, bg_bank_refill_threshold=2)


def _wire(monkeypatch, tmp_path):
    storage = LocalStorage(root=tmp_path)
    monkeypatch.setattr(store_mod, "get_storage", lambda settings=None: storage)
    monkeypatch.setattr(serve_mod, "maybe_trigger_refill", lambda **kw: None)
    return storage


def _seed(store, combo, n):
    for i in range(n):
        store.upload(combo, f"bg{i}".encode())


def test_failed_poster_restores_the_served_background(monkeypatch, tmp_path):
    s = _settings()
    _wire(monkeypatch, tmp_path)
    store = BankStore(settings=s)
    combo = Combo("intense", "dark_fantasy")
    _seed(store, combo, 3)

    begin_serve_scope()
    out = try_serve_from_bank({"design": {"energy": "intense", "vibe": "dark_fantasy"}}, settings=s)
    assert out is not None
    assert store.count(combo) == 2          # one consumed by delete-on-serve

    rollback_serve_scope()                  # poster failed → put it back
    assert store.count(combo) == 3          # restored to full


def test_successful_poster_keeps_the_background_consumed(monkeypatch, tmp_path):
    s = _settings()
    _wire(monkeypatch, tmp_path)
    store = BankStore(settings=s)
    combo = Combo("intense", "cosmic")
    _seed(store, combo, 3)

    begin_serve_scope()
    try_serve_from_bank({"design": {"energy": "intense", "vibe": "cosmic"}}, settings=s)
    assert store.count(combo) == 2

    commit_serve_scope()                    # success → no restore
    assert store.count(combo) == 2


def test_rollback_without_a_serve_is_a_noop(monkeypatch, tmp_path):
    s = _settings()
    _wire(monkeypatch, tmp_path)
    store = BankStore(settings=s)
    combo = Combo("chill", "minimal")
    _seed(store, combo, 2)

    begin_serve_scope()                     # nothing served (e.g. a user-upload poster)
    rollback_serve_scope()                  # must not raise or touch the bank
    assert store.count(combo) == 2


def test_bank_miss_records_nothing_to_restore(monkeypatch, tmp_path):
    s = _settings()
    _wire(monkeypatch, tmp_path)
    store = BankStore(settings=s)
    combo = Combo("chill", "cyberpunk")     # empty combo → miss

    begin_serve_scope()
    assert try_serve_from_bank({"design": {"energy": "chill", "vibe": "cyberpunk"}}, settings=s) is None
    rollback_serve_scope()
    assert store.count(combo) == 0          # nothing conjured up
