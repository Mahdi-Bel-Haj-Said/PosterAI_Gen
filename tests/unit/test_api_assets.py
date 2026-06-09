"""Tests for the /v1/assets HTTP endpoints. TestClient, no network."""

from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from esports_poster_ai.api.app import app
from esports_poster_ai.api.routes import assets as assets_route
from esports_poster_ai.assets.store import AssetStore


class _FakeStorage:
    """In-memory storage stub — put/get/signed_url/delete all without network."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, *, content_type=None) -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    def signed_url(self, key: str, **kwargs) -> str:
        return f"https://signed.example/{key}"

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self.objects


@pytest.fixture
def store() -> AssetStore:
    return AssetStore(collection=mongomock.MongoClient()["testdb"]["assets"])


@pytest.fixture
def fake_storage() -> _FakeStorage:
    return _FakeStorage()


@pytest.fixture
def client(store, fake_storage, monkeypatch) -> TestClient:
    app.dependency_overrides[assets_route.get_asset_store] = lambda: store
    monkeypatch.setattr(assets_route, "get_storage", lambda: fake_storage)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_asset_writes_to_storage_and_returns_signed_url(client, fake_storage):
    resp = client.post(
        "/v1/assets",
        files={"file": ("fnatic.png", b"PNGBYTES", "image/png")},
        data={"org_id": "1", "asset_type": "team-logos", "name": "FNATIC logo"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["org_id"] == "1"
    assert body["asset_type"] == "team-logos"
    assert body["filename"] == "fnatic.png"
    assert body["size_bytes"] == len(b"PNGBYTES")
    assert body["signed_url"].startswith("https://signed.example/")
    # The bytes actually reached the (fake) storage.
    assert body["storage_key"] in fake_storage.objects
    assert fake_storage.objects[body["storage_key"]] == b"PNGBYTES"


def test_upload_empty_file_returns_400(client):
    resp = client.post(
        "/v1/assets",
        files={"file": ("empty.png", b"", "image/png")},
        data={"org_id": "1", "asset_type": "team-logos"},
    )
    assert resp.status_code == 400


def test_upload_non_image_returns_400(client):
    resp = client.post(
        "/v1/assets",
        files={"file": ("doc.txt", b"hello", "text/plain")},
        data={"org_id": "1", "asset_type": "team-logos"},
    )
    assert resp.status_code == 400


def test_list_assets_filters_by_org(client):
    for org in ("1", "1", "2"):
        client.post(
            "/v1/assets",
            files={"file": ("x.png", b"PNG", "image/png")},
            data={"org_id": org, "asset_type": "team-logos"},
        )
    body = client.get("/v1/assets", params={"org_id": "1"}).json()
    assert body["count"] == 2
    assert all(a["org_id"] == "1" for a in body["assets"])


def test_get_asset_404_when_missing(client):
    assert client.get("/v1/assets/nope").status_code == 404


def test_get_asset_returns_metadata_and_signed_url(client):
    created = client.post(
        "/v1/assets",
        files={"file": ("logo.png", b"PNG", "image/png")},
        data={"org_id": "1", "asset_type": "team-logos"},
    ).json()
    resp = client.get(f"/v1/assets/{created['asset_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["asset_id"] == created["asset_id"]
    assert body["signed_url"].startswith("https://signed.example/")


def test_delete_asset_removes_storage_and_row(client, fake_storage):
    created = client.post(
        "/v1/assets",
        files={"file": ("logo.png", b"PNG", "image/png")},
        data={"org_id": "1", "asset_type": "team-logos"},
    ).json()
    key = created["storage_key"]
    assert key in fake_storage.objects

    resp = client.delete(f"/v1/assets/{created['asset_id']}")
    assert resp.status_code == 204
    assert key not in fake_storage.objects
    assert client.get(f"/v1/assets/{created['asset_id']}").status_code == 404
