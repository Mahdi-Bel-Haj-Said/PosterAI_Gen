"""Tests for AssetStore — mongomock, no real MongoDB / no network."""

from __future__ import annotations

import mongomock
import pytest

from esports_poster_ai.assets.store import AssetStore
from esports_poster_ai.storage.keys import AssetType


@pytest.fixture
def store() -> AssetStore:
    return AssetStore(collection=mongomock.MongoClient()["testdb"]["assets"])


def test_create_and_get_roundtrip(store: AssetStore):
    asset = store.create(
        org_id="1",
        asset_type=AssetType.TEAM_LOGO,
        asset_id="abc123",
        filename="FNATIC.png",
        storage_key="orgs/1/assets/team-logos/abc123.png",
        content_type="image/png",
        size_bytes=1234,
        name="FNATIC logo",
    )
    assert asset.asset_id == "abc123"

    loaded = store.get("abc123")
    assert loaded is not None
    assert loaded.org_id == "1"
    assert loaded.asset_type == AssetType.TEAM_LOGO.value
    assert loaded.filename == "FNATIC.png"
    assert loaded.size_bytes == 1234


def test_get_missing_returns_none(store: AssetStore):
    assert store.get("nope") is None


def test_list_filters_by_asset_type(store: AssetStore):
    for i, kind in enumerate(
        (AssetType.TEAM_LOGO, AssetType.TEAM_LOGO, AssetType.PLAYER_IMAGE)
    ):
        store.create(
            org_id="1",
            asset_type=kind,
            asset_id=f"id-{i}",
            filename="x.png",
            storage_key="k",
            content_type="image/png",
            size_bytes=1,
        )

    all_for_org = store.list_for_org("1")
    assert len(all_for_org) == 3

    team_logos = store.list_for_org("1", asset_type=AssetType.TEAM_LOGO)
    assert len(team_logos) == 2
    assert all(a.asset_type == AssetType.TEAM_LOGO.value for a in team_logos)


def test_list_filters_by_org(store: AssetStore):
    store.create(
        org_id="1", asset_type=AssetType.TEAM_LOGO, asset_id="a",
        filename="", storage_key="k", content_type="image/png", size_bytes=1,
    )
    store.create(
        org_id="2", asset_type=AssetType.TEAM_LOGO, asset_id="b",
        filename="", storage_key="k", content_type="image/png", size_bytes=1,
    )
    assert len(store.list_for_org("1")) == 1
    assert len(store.list_for_org("2")) == 1
    assert store.list_for_org("nobody") == []


def test_delete_removes_the_row(store: AssetStore):
    store.create(
        org_id="1", asset_type=AssetType.TEAM_LOGO, asset_id="zap",
        filename="", storage_key="k", content_type="image/png", size_bytes=1,
    )
    assert store.delete("zap") is True
    assert store.get("zap") is None
    assert store.delete("zap") is False  # idempotent
