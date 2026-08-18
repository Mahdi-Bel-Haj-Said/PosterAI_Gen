"""Tests for BankStore — counts, upload, serve-and-delete, folder seeding."""

from __future__ import annotations

from esports_poster_ai.bank.combos import Combo, all_combos
from esports_poster_ai.bank.store import BankStore, combo_of_key
from esports_poster_ai.config import Settings
from esports_poster_ai.storage.local import LocalStorage


def _store(tmp_path) -> BankStore:
    return BankStore(
        storage=LocalStorage(root=tmp_path),
        settings=Settings(bg_bank_prefix="Bg_bank", bg_bank_target_per_combo=5),
    )


def test_empty_combo_counts_zero(tmp_path):
    store = _store(tmp_path)
    assert store.count(Combo("chill", "cyberpunk")) == 0


def test_upload_increments_count_and_keys_are_namespaced(tmp_path):
    store = _store(tmp_path)
    combo = Combo("intense", "cosmic")
    key = store.upload(combo, b"png-bytes")
    assert key.startswith("Bg_bank/intense_cosmic/")
    assert key.endswith(".png")
    assert store.count(combo) == 1


def test_ensure_folders_creates_24_but_keep_is_not_counted(tmp_path):
    store = _store(tmp_path)
    prefixes = store.ensure_folders()
    assert len(prefixes) == 24
    # .keep markers exist but are never counted as servable images
    assert all(store.count(c) == 0 for c in all_combos())
    assert sum(store.counts().values()) == 0


def test_serve_and_delete_returns_bytes_and_removes_object(tmp_path):
    store = _store(tmp_path)
    combo = Combo("balanced", "minimal")
    store.upload(combo, b"only-one")
    served = store.serve_and_delete(combo)
    assert served is not None
    assert served.image == b"only-one"
    assert served.remaining == 0
    assert store.count(combo) == 0  # deleted on serve


def test_serve_decrements_remaining(tmp_path):
    store = _store(tmp_path)
    combo = Combo("explosive", "fire_energy")
    for i in range(3):
        store.upload(combo, f"img{i}".encode())
    served = store.serve_and_delete(combo)
    assert served.remaining == 2
    assert store.count(combo) == 2


def test_serve_empty_combo_returns_none(tmp_path):
    store = _store(tmp_path)
    assert store.serve_and_delete(Combo("chill", "cinematic")) is None


def test_serve_never_hands_out_the_keep_marker(tmp_path):
    store = _store(tmp_path)
    combo = Combo("chill", "cyberpunk")
    store.ensure_folders()  # writes .keep in every combo
    assert store.serve_and_delete(combo) is None  # only .keep present → miss


def test_counts_covers_all_combos(tmp_path):
    store = _store(tmp_path)
    counts = store.counts()
    assert len(counts) == 24
    assert set(counts.values()) == {0}


def test_combo_of_key():
    assert combo_of_key("Bg_bank/chill_cyberpunk/abc.png", prefix="Bg_bank") == "chill_cyberpunk"
    assert combo_of_key("other/x.png", prefix="Bg_bank") is None
