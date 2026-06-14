"""
Tests for the per-platform API-key auth gate, the org registry, and the
self-serve endpoints (`/v1/me`, `/v1/orgs`, `/v1/backgrounds`,
`GET /v1/style-dnas`). TestClient, no network.

Model: an API key authenticates a *platform* (the integrating customer). The
platform addresses many orgs by passing `org_id` per request; the key carries
`platform_id`. Isolation is per platform.

Modes (switched by `settings.api_key_required`):
* dev (default): org_id passed directly; no platform, no enforcement.
* required: a valid Bearer key is mandatory; org_id must name an org registered
  under the key's platform; data is confined to that platform.
"""

from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from esports_poster_ai.api import deps as api_deps
from esports_poster_ai.api.app import app
from esports_poster_ai.api.routes import posters as posters_route
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.api_key import ApiKey
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.orgs.store import OrgStore


def _valid_input(mode: str = "fresh") -> dict:
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "gameday",
            "mode": mode,
            "output_format": "portrait_1080x1920",
        }
    }


class _FakeKeyStore:
    """Resolve a fixed token -> platform_id map; anything else is invalid."""

    def __init__(self, mapping: dict) -> None:
        self._m = mapping

    def verify(self, token: str):
        platform = self._m.get(token)
        if platform is None:
            return None
        return ApiKey(platform_id=platform, key_prefix=token[:12], key_hash="x")


@pytest.fixture
def store() -> JobStore:
    # tz_aware mirrors the real JobStore (MongoClient(tz_aware=True)) so rolling-
    # window datetime math matches production.
    return JobStore(collection=mongomock.MongoClient(tz_aware=True)["jobsdb"]["jobs"])


@pytest.fixture
def org_store() -> OrgStore:
    return OrgStore(collection=mongomock.MongoClient(tz_aware=True)["orgsdb"]["orgs"])


@pytest.fixture
def client(store, org_store, monkeypatch) -> TestClient:
    app.dependency_overrides[posters_route.get_job_store] = lambda: store
    app.dependency_overrides[api_deps.get_org_store] = lambda: org_store

    def fake_enqueue(*, input_data, org_id, tournament_id, mode, platform_id=None, settings=None):
        return store.create(
            input_data=input_data, org_id=org_id, tournament_id=tournament_id,
            mode=mode, platform_id=platform_id,
        )

    monkeypatch.setattr(posters_route, "enqueue_poster_job", fake_enqueue)
    # Valid key "epai_keyP1" authenticates platform "P1".
    monkeypatch.setattr(api_deps, "get_api_key_store", lambda: _FakeKeyStore({"epai_keyP1": "P1"}))

    yield TestClient(app)
    app.dependency_overrides.clear()


P1 = {"Authorization": "Bearer epai_keyP1"}


def _require_keys(monkeypatch, on: bool = True) -> None:
    monkeypatch.setattr(get_settings(), "api_key_required", on)


def _register(client, org_id: str) -> None:
    assert client.post("/v1/orgs", json={"org_id": org_id}, headers=P1).status_code == 201


# ----------------------------------------------------------------- dev mode


def test_dev_mode_org_id_in_body_works(client):
    resp = client.post(
        "/v1/posters",
        json={"org_id": "1", "tournament_id": "t", "input": _valid_input()},
    )
    assert resp.status_code == 202


def test_dev_mode_missing_org_id_is_422(client):
    resp = client.post("/v1/posters", json={"tournament_id": "t", "input": _valid_input()})
    assert resp.status_code == 422


# ----------------------------------------------------------------- required mode


def test_required_mode_without_key_is_401(client, monkeypatch):
    _require_keys(monkeypatch)
    resp = client.post(
        "/v1/posters",
        json={"org_id": "1", "tournament_id": "t", "input": _valid_input()},
    )
    assert resp.status_code == 401


def test_required_mode_invalid_key_is_401(client, monkeypatch):
    _require_keys(monkeypatch)
    resp = client.post(
        "/v1/posters",
        json={"org_id": "1", "tournament_id": "t", "input": _valid_input()},
        headers={"Authorization": "Bearer epai_wrong"},
    )
    assert resp.status_code == 401


def test_authenticated_unregistered_org_is_404(client, monkeypatch):
    _require_keys(monkeypatch)
    resp = client.post(
        "/v1/posters",
        json={"org_id": "ghost", "tournament_id": "t", "input": _valid_input()},
        headers=P1,
    )
    assert resp.status_code == 404


def test_authenticated_registered_org_pins_platform(client, monkeypatch):
    _require_keys(monkeypatch)
    _register(client, "alpha")
    resp = client.post(
        "/v1/posters",
        json={"org_id": "alpha", "tournament_id": "t", "input": _valid_input()},
        headers=P1,
    )
    assert resp.status_code == 202
    assert resp.json()["org_id"] == "alpha"


def test_authenticated_missing_org_is_422(client, monkeypatch):
    _require_keys(monkeypatch)
    resp = client.post(
        "/v1/posters",
        json={"tournament_id": "t", "input": _valid_input()},
        headers=P1,
    )
    assert resp.status_code == 422


# ----------------------------------------------------------------- platform isolation


def test_cross_platform_get_is_404(client, store):
    # Job owned by another platform "P2"; key authenticates "P1".
    other = store.create(
        input_data={}, org_id="x", tournament_id="t", mode="fresh", platform_id="P2"
    )
    resp = client.get(f"/v1/posters/{other.job_id}", headers=P1)
    assert resp.status_code == 404


def test_same_platform_get_succeeds(client, store):
    mine = store.create(
        input_data={}, org_id="x", tournament_id="t", mode="fresh", platform_id="P1"
    )
    resp = client.get(f"/v1/posters/{mine.job_id}", headers=P1)
    assert resp.status_code == 200
    assert resp.json()["org_id"] == "x"


# ----------------------------------------------------------------- /v1/me


def test_me_dev_mode_is_unauthenticated(client):
    body = client.get("/v1/me").json()
    assert body["authenticated"] is False
    assert body["platform_id"] is None


def test_me_with_key_reports_platform(client):
    body = client.get("/v1/me", headers=P1).json()
    assert body["authenticated"] is True
    assert body["platform_id"] == "P1"


# ----------------------------------------------------------------- /v1/orgs


def test_org_register_list_and_get(client):
    reg = client.post(
        "/v1/orgs", json={"org_id": "alpha", "name": "Team Alpha"}, headers=P1
    )
    assert reg.status_code == 201
    assert reg.json()["tier"] == "free"

    listed = client.get("/v1/orgs", headers=P1).json()
    assert listed["count"] == 1
    assert listed["orgs"][0]["org_id"] == "alpha"

    detail = client.get("/v1/orgs/alpha", headers=P1).json()
    assert detail["org_id"] == "alpha"
    assert {w["window"] for w in detail["quota"]} == {"day", "week", "month"}


def test_org_register_duplicate_is_409(client):
    _register(client, "alpha")
    dup = client.post("/v1/orgs", json={"org_id": "alpha"}, headers=P1)
    assert dup.status_code == 409


def test_org_tier_update(client):
    _register(client, "alpha")
    patched = client.patch("/v1/orgs/alpha", json={"tier": "pro"}, headers=P1)
    assert patched.status_code == 200
    assert patched.json()["tier"] == "pro"
    assert patched.json()["tier_info"]["monthly_poster_cap"] == 200


def test_client_editable_per_org_limits_are_enforced(client, monkeypatch):
    _require_keys(monkeypatch)
    # Register an org with a hard daily cap of 1 (the platform sets this freely).
    reg = client.post(
        "/v1/orgs", json={"org_id": "capped", "limits": {"day": 1}}, headers=P1
    )
    assert reg.status_code == 201
    assert reg.json()["limits"]["day"] == 1

    body = {"org_id": "capped", "tournament_id": "t", "input": _valid_input()}
    assert client.post("/v1/posters", json=body, headers=P1).status_code == 202
    # Second within the same 24h window exceeds the org's own limit.
    blocked = client.post("/v1/posters", json=body, headers=P1)
    assert blocked.status_code == 429

    # The quota endpoint reflects the org's edited limit, not the service default.
    detail = client.get("/v1/orgs/capped", headers=P1).json()
    day = next(w for w in detail["quota"] if w["window"] == "day")
    assert day["limit"] == 1


def test_org_limits_raisable_via_patch(client):
    _register(client, "alpha")
    patched = client.patch(
        "/v1/orgs/alpha", json={"limits": {"day": 10, "week": 50, "month": 100}}, headers=P1
    )
    assert patched.status_code == 200
    assert patched.json()["limits"] == {"day": 10, "week": 50, "month": 100}


# ----------------------------------------------------------------- misc endpoints


def test_backgrounds_lists_pool(client, monkeypatch):
    monkeypatch.setattr(
        "esports_poster_ai.api.routes.backgrounds.list_pool",
        lambda: ["arena.png", "stage.jpg"],
    )
    names = {b["name"] for b in client.get("/v1/backgrounds").json()["backgrounds"]}
    assert {"arena.png", "stage.jpg"} <= names


def test_style_dna_list_returns_shape(client):
    body = client.get("/v1/style-dnas", params={"org_id": "emptyorg"}).json()
    assert body["count"] == 0
    assert body["style_dnas"] == []
