"""Tests for storage.local — the LocalStorage backend."""

from __future__ import annotations

import pytest

from esports_poster_ai.storage.base import Storage
from esports_poster_ai.storage.local import LocalStorage


def test_put_then_get_round_trip(tmp_path):
    s = LocalStorage(root=tmp_path)
    s.put_bytes("defendr-poster-ai/orgs/1/posters/p.png", b"poster-bytes")
    assert s.get_bytes("defendr-poster-ai/orgs/1/posters/p.png") == b"poster-bytes"


def test_get_missing_raises_file_not_found(tmp_path):
    s = LocalStorage(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        s.get_bytes("nope/missing.png")


def test_exists(tmp_path):
    s = LocalStorage(root=tmp_path)
    assert s.exists("a/b.png") is False
    s.put_bytes("a/b.png", b"x")
    assert s.exists("a/b.png") is True


def test_put_creates_nested_dirs(tmp_path):
    s = LocalStorage(root=tmp_path)
    s.put_bytes("deep/nested/path/file.json", b"{}")
    assert (tmp_path / "deep" / "nested" / "path" / "file.json").is_file()


def test_list_keys_filters_by_prefix(tmp_path):
    s = LocalStorage(root=tmp_path)
    s.put_bytes("orgs/1/posters/a.png", b"a")
    s.put_bytes("orgs/1/posters/b.png", b"b")
    s.put_bytes("orgs/2/posters/c.png", b"c")

    org1 = s.list_keys("orgs/1/posters/")
    assert org1 == ["orgs/1/posters/a.png", "orgs/1/posters/b.png"]
    assert s.list_keys("orgs/2/posters/") == ["orgs/2/posters/c.png"]


def test_signed_url_is_file_uri(tmp_path):
    s = LocalStorage(root=tmp_path)
    s.put_bytes("x.png", b"x")
    assert s.signed_url("x.png").startswith("file://")


def test_key_escaping_root_is_rejected(tmp_path):
    s = LocalStorage(root=tmp_path)
    with pytest.raises(ValueError):
        s.put_bytes("../escape.png", b"x")


def test_satisfies_storage_protocol(tmp_path):
    s = LocalStorage(root=tmp_path)
    assert isinstance(s, Storage)
