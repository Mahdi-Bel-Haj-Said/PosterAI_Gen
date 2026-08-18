"""Tests for the serve glue: bank hit/miss + refill triggering."""

from __future__ import annotations

import esports_poster_ai.bank.serve as serve_mod
import esports_poster_ai.bank.store as store_mod
from esports_poster_ai.bank.combos import Combo
from esports_poster_ai.bank.serve import try_serve_from_bank
from esports_poster_ai.config import Settings
from esports_poster_ai.storage.local import LocalStorage


def _settings():
    return Settings(bg_bank_prefix="Bg_bank", bg_bank_target_per_combo=5, bg_bank_refill_threshold=2)


def _wire_local_storage(monkeypatch, tmp_path):
    """Force BankStore (built inside serve) to use a local temp storage."""
    storage = LocalStorage(root=tmp_path)
    monkeypatch.setattr(store_mod, "get_storage", lambda settings=None: storage)
    return storage


def _capture_refill(monkeypatch):
    calls: list[bool] = []
    monkeypatch.setattr(serve_mod, "maybe_trigger_refill", lambda **kw: calls.append(True))
    return calls


def _input(energy, vibe):
    return {"design": {"energy": energy, "vibe": vibe}}


def test_unknown_combo_returns_none(monkeypatch, tmp_path):
    _wire_local_storage(monkeypatch, tmp_path)
    _capture_refill(monkeypatch)
    assert try_serve_from_bank(_input("chill", "bogus"), settings=_settings()) is None


def test_hit_returns_bytes(monkeypatch, tmp_path):
    from esports_poster_ai.bank.store import BankStore

    s = _settings()
    _wire_local_storage(monkeypatch, tmp_path)
    _capture_refill(monkeypatch)
    BankStore(settings=s).upload(Combo("intense", "cosmic"), b"ready-bg")

    out = try_serve_from_bank(_input("intense", "cosmic"), settings=s)
    assert out == b"ready-bg"


def test_miss_returns_none_for_empty_combo(monkeypatch, tmp_path):
    _wire_local_storage(monkeypatch, tmp_path)
    _capture_refill(monkeypatch)
    assert try_serve_from_bank(_input("chill", "cyberpunk"), settings=_settings()) is None


def test_refill_triggers_when_dropping_to_threshold(monkeypatch, tmp_path):
    from esports_poster_ai.bank.store import BankStore

    s = _settings()  # threshold 2
    _wire_local_storage(monkeypatch, tmp_path)
    calls = _capture_refill(monkeypatch)
    store = BankStore(settings=s)
    combo = Combo("balanced", "minimal")
    for i in range(3):  # serving one leaves 2 == threshold → should trigger
        store.upload(combo, f"b{i}".encode())

    try_serve_from_bank(_input("balanced", "minimal"), settings=s)
    assert calls == [True]


def test_refill_not_triggered_when_plenty_left(monkeypatch, tmp_path):
    from esports_poster_ai.bank.store import BankStore

    s = _settings()
    _wire_local_storage(monkeypatch, tmp_path)
    calls = _capture_refill(monkeypatch)
    store = BankStore(settings=s)
    combo = Combo("explosive", "fire_energy")
    for i in range(5):  # serving one leaves 4 > threshold → no trigger
        store.upload(combo, f"b{i}".encode())

    try_serve_from_bank(_input("explosive", "fire_energy"), settings=s)
    assert calls == []
