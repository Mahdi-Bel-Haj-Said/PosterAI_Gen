"""Tests for /v1/api-keys — admin-protected key management endpoints."""

from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from esports_poster_ai.api import deps as api_deps
from esports_poster_ai.api.app import app
from esports_poster_ai.api.routes import api_keys as api_keys_route
from esports_poster_ai.auth.store import ApiKeyStore, KEY_TOKEN_PREFIX


ADMIN_TOKEN = "testadmin"


@pytest.fixture
def store() -> ApiKeyStore:
    return ApiKeyStore(collection=mongomock.MongoClient()["testdb"]["api_keys"])


@pytest.fixture
def client(store, monkeypatch) -> TestClient:
    # Inject our test store.
    app.dependency_overrides[api_keys_route.get_api_key_store] = lambda: store

    # Configure the admin token so the routes accept the X-Admin-Token header.
    class _FakeSettings:
        admin_token = ADMIN_TOKEN

    monkeypatch.setattr(api_deps, "get_settings", lambda: _FakeSettings())

    yield TestClient(app)
    app.dependency_overrides.clear()


# ----------------------------------------------------------------- admin auth
def test_post_requires_admin_token(client):
    resp = client.post("/v1/api-keys", json={"platform_id": "1"})
    assert resp.status_code == 401  # no X-Admin-Token header


def test_post_rejects_wrong_admin_token(client):
    resp = client.post(
        "/v1/api-keys",
        json={"platform_id": "1"},
        headers={"X-Admin-Token": "wrong"},
    )
    assert resp.status_code == 401


# ----------------------------------------------------------------- issue
def test_post_issues_key_and_returns_plaintext_once(client, store):
    resp = client.post(
        "/v1/api-keys",
        json={"platform_id": "1", "name": "prod"},
        headers={"X-Admin-Token": ADMIN_TOKEN},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["platform_id"] == "1"
    assert body["name"] == "prod"
    assert body["key"].startswith(KEY_TOKEN_PREFIX)
    assert body["key_prefix"] and len(body["key_prefix"]) == 12
    # Subsequent reads must never expose the plaintext.
    saved = store.get(body["key_id"])
    assert saved is not None
    assert body["key"] not in saved.model_dump_json()


# ----------------------------------------------------------------- list
def test_list_returns_org_keys_without_plaintext(client):
    headers = {"X-Admin-Token": ADMIN_TOKEN}
    client.post("/v1/api-keys", json={"platform_id": "1"}, headers=headers)
    client.post("/v1/api-keys", json={"platform_id": "1", "name": "ci"}, headers=headers)
    client.post("/v1/api-keys", json={"platform_id": "2"}, headers=headers)

    body = client.get(
        "/v1/api-keys", params={"platform_id": "1"}, headers=headers
    ).json()
    assert body["count"] == 2
    for k in body["keys"]:
        assert "key" not in k  # no plaintext
        assert k["revoked"] is False


# ----------------------------------------------------------------- revoke
def test_delete_revokes_and_404_after(client, store):
    headers = {"X-Admin-Token": ADMIN_TOKEN}
    issued = client.post(
        "/v1/api-keys", json={"platform_id": "1"}, headers=headers
    ).json()
    key_id = issued["key_id"]

    resp = client.delete(f"/v1/api-keys/{key_id}", headers=headers)
    assert resp.status_code == 204
    # The record stays (soft delete) but it's now revoked.
    record = store.get(key_id)
    assert record is not None
    assert record.revoked is True
    # And it's excluded from the default list.
    listed = client.get(
        "/v1/api-keys", params={"platform_id": "1"}, headers=headers
    ).json()
    assert listed["count"] == 0


def test_delete_404_when_unknown(client):
    headers = {"X-Admin-Token": ADMIN_TOKEN}
    resp = client.delete("/v1/api-keys/nope", headers=headers)
    assert resp.status_code == 404
