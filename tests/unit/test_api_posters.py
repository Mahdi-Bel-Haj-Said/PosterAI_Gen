"""Tests for the HTTP API — Tier 1 poster endpoints. TestClient, no network."""

from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from esports_poster_ai.api import app as app_module
from esports_poster_ai.api.app import app
from esports_poster_ai.api.routes import posters as posters_route
from esports_poster_ai.jobs.store import JobStore


def _valid_input(mode: str = "fresh") -> dict:
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "gameday",
            "mode": mode,
            "output_format": "portrait_1080x1920",
        }
    }


class _FakeStorage:
    """Stand-in storage — signed_url is deterministic, no network."""

    def signed_url(self, key, **kwargs):
        return f"https://signed.example/{key}"


@pytest.fixture
def store() -> JobStore:
    return JobStore(collection=mongomock.MongoClient()["testdb"]["jobs"])


@pytest.fixture
def client(store, monkeypatch) -> TestClient:
    # GET routes resolve their JobStore via this dependency.
    app.dependency_overrides[posters_route.get_job_store] = lambda: store

    # POST calls enqueue_poster_job — swap it for one that writes to the
    # mongomock store and skips Redis.
    def fake_enqueue(*, input_data, org_id, tournament_id, mode, platform_id=None, settings=None):
        return store.create(
            input_data=input_data, org_id=org_id, tournament_id=tournament_id,
            mode=mode, platform_id=platform_id,
        )

    monkeypatch.setattr(posters_route, "enqueue_poster_job", fake_enqueue)

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_poster_returns_202(client):
    resp = client.post(
        "/v1/posters",
        json={"org_id": "1", "tournament_id": "ewc_2025", "input": _valid_input()},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert body["mode"] == "fresh"


def test_create_poster_invalid_input_returns_422(client):
    bad = _valid_input()
    bad["_meta"]["game"] = "dota2"  # not an allowed game
    resp = client.post(
        "/v1/posters",
        json={"org_id": "1", "tournament_id": "t", "input": bad},
    )
    assert resp.status_code == 422


def test_get_poster_404_for_unknown_id(client):
    assert client.get("/v1/posters/does-not-exist").status_code == 404


def test_get_poster_returns_job(client):
    created = client.post(
        "/v1/posters",
        json={"org_id": "1", "tournament_id": "ewc_2025", "input": _valid_input()},
    ).json()
    resp = client.get(f"/v1/posters/{created['job_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == created["job_id"]
    assert body["org_id"] == "1"
    assert body["tournament_id"] == "ewc_2025"
    assert body["status"] == "queued"


def test_list_posters_filters_by_org(client):
    for _ in range(2):
        client.post(
            "/v1/posters",
            json={"org_id": "1", "tournament_id": "ewc_2025", "input": _valid_input()},
        )
    client.post(
        "/v1/posters",
        json={"org_id": "2", "tournament_id": "t", "input": _valid_input()},
    )
    body = client.get("/v1/posters", params={"org_id": "1"}).json()
    assert body["count"] == 2
    assert all(j["org_id"] == "1" for j in body["jobs"])


def test_get_poster_includes_signed_url_when_completed(client, store, monkeypatch):
    job = store.create(input_data={}, org_id="1", tournament_id="t", mode="fresh")
    store.mark_completed(
        job.job_id, poster_id="p1", storage_key="orgs/1/posters/p1.png", local_path="/tmp/p1.png"
    )
    monkeypatch.setattr(posters_route, "get_storage", lambda: _FakeStorage())

    body = client.get(f"/v1/posters/{job.job_id}").json()
    assert body["status"] == "completed"
    assert body["signed_url"] == "https://signed.example/orgs/1/posters/p1.png"


def test_list_posters_includes_signed_url_for_completed(client, store, monkeypatch):
    job = store.create(input_data={}, org_id="1", tournament_id="t", mode="fresh")
    store.mark_completed(
        job.job_id, poster_id="p1", storage_key="k1.png", local_path="/tmp/p1.png"
    )
    monkeypatch.setattr(posters_route, "get_storage", lambda: _FakeStorage())

    body = client.get("/v1/posters", params={"org_id": "1"}).json()
    item = body["jobs"][0]
    assert item["status"] == "completed"
    assert item["signed_url"] == "https://signed.example/k1.png"


def test_health_ok(monkeypatch):
    monkeypatch.setattr(app_module, "_mongodb_ok", lambda: True)
    monkeypatch.setattr(app_module, "_redis_ok", lambda: True)
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_degraded_when_redis_down(monkeypatch):
    monkeypatch.setattr(app_module, "_mongodb_ok", lambda: True)
    monkeypatch.setattr(app_module, "_redis_ok", lambda: False)
    resp = TestClient(app).get("/health")
    assert resp.status_code == 503
    assert resp.json()["redis"] == "down"
