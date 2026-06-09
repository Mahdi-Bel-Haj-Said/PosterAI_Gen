"""Tests for the /v1/style-dnas HTTP endpoints. TestClient, no network."""

from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from esports_poster_ai.api.app import app
from esports_poster_ai.api.routes import posters as posters_route
from esports_poster_ai.api.routes import style_dnas as style_dnas_route
from esports_poster_ai.domain.style_dna import StyleDNA
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.storage.local import LocalStorage
from esports_poster_ai.style_dna import repository as repo


ORG = "1"
TID = "ewc_2025"


def _fake_dna(tournament_id: str = TID, status: str = "draft") -> StyleDNA:
    return StyleDNA(
        tournament_id=tournament_id,
        status=status,  # type: ignore[arg-type]
        palette=["#FF5C00", "#0A0A1A"],
        color_temperature="warm",
        lighting="neon",
        atmosphere="dark electric",
        particle_effects="sparks",
        energy="intense",
        sd_style_keywords="cyberpunk",
    )


@pytest.fixture
def job_store() -> JobStore:
    return JobStore(collection=mongomock.MongoClient()["testdb"]["jobs"])


@pytest.fixture
def client(job_store, tmp_path, monkeypatch) -> TestClient:
    # Real LocalStorage backed by tmp_path → save/load/delete actually work.
    storage = LocalStorage(root=tmp_path / "storage")
    # The lambdas must accept any call signature — the repository calls
    # `get_storage(s)` with the settings, the route calls `get_storage()`.
    monkeypatch.setattr(style_dnas_route, "get_storage", lambda *a, **kw: storage)
    monkeypatch.setattr(repo, "get_storage", lambda *a, **kw: storage)

    # The extract route uses the JobStore (to look up the source poster job).
    app.dependency_overrides[posters_route.get_job_store] = lambda: job_store

    yield TestClient(app)
    app.dependency_overrides.clear()


# ----------------------------------------------------------------- extract
def test_extract_requires_completed_source_job(client, job_store):
    # Source job that is still queued — extract must refuse.
    job = job_store.create(input_data={}, org_id=ORG, tournament_id=TID, mode="fresh")
    resp = client.post(
        f"/v1/style-dnas/{TID}",
        json={"org_id": ORG, "source_job_id": job.job_id},
    )
    assert resp.status_code == 400


def test_extract_404_when_source_job_unknown(client):
    resp = client.post(
        f"/v1/style-dnas/{TID}",
        json={"org_id": ORG, "source_job_id": "does-not-exist"},
    )
    assert resp.status_code == 404


def test_extract_saves_draft_for_completed_job(client, job_store, monkeypatch):
    # Build a completed job whose storage_key is a fake key, and seed bytes there.
    job = job_store.create(input_data={}, org_id=ORG, tournament_id=TID, mode="fresh")
    job_store.mark_completed(
        job.job_id,
        poster_id="p1",
        storage_key="some/poster/key.png",
        local_path="/tmp/p1.png",
    )
    # The route fetches bytes via get_storage().get_bytes(storage_key) — put them there.
    storage = style_dnas_route.get_storage()
    storage.put_bytes("some/poster/key.png", b"FAKE_POSTER_BYTES")

    # Don't hit OpenAI — stub the extractor to return a fake DNA.
    def fake_extract(*, poster_bytes, tournament_id, source_reference=None, **kw):
        assert poster_bytes == b"FAKE_POSTER_BYTES"
        return _fake_dna(tournament_id=tournament_id)

    monkeypatch.setattr(style_dnas_route, "extract_style_dna", fake_extract)

    resp = client.post(
        f"/v1/style-dnas/{TID}",
        json={"org_id": ORG, "source_job_id": job.job_id},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tournament_id"] == TID
    assert body["status"] == "draft"
    assert body["palette"] == ["#FF5C00", "#0A0A1A"]


# ----------------------------------------------------------------- get
def test_get_returns_active_dna(client):
    repo.save_draft(_fake_dna(), ORG)
    body = client.get(f"/v1/style-dnas/{TID}", params={"org_id": ORG}).json()
    assert body["status"] == "draft"
    assert body["energy"] == "intense"


def test_get_404_when_no_dna(client):
    resp = client.get(f"/v1/style-dnas/{TID}", params={"org_id": ORG})
    assert resp.status_code == 404


# ----------------------------------------------------------------- update
def test_put_replaces_draft(client):
    repo.save_draft(_fake_dna(), ORG)
    edited = _fake_dna().model_dump(mode="json")
    edited["lighting"] = "edited-lighting"
    resp = client.put(
        f"/v1/style-dnas/{TID}",
        json={"org_id": ORG, "dna": edited},
    )
    assert resp.status_code == 200
    assert resp.json()["lighting"] == "edited-lighting"
    assert resp.json()["status"] == "draft"


def test_put_422_on_invalid_dna(client):
    bad = _fake_dna().model_dump(mode="json")
    bad["energy"] = "weird"  # not in the Literal
    resp = client.put(
        f"/v1/style-dnas/{TID}",
        json={"org_id": ORG, "dna": bad},
    )
    assert resp.status_code == 422


# ----------------------------------------------------------------- approve
def test_approve_promotes_draft(client):
    repo.save_draft(_fake_dna(), ORG)
    resp = client.post(
        f"/v1/style-dnas/{TID}/approve",
        json={"org_id": ORG},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    # Draft should be gone.
    assert repo.load_draft(ORG, TID) is None
    assert repo.load_approved(ORG, TID) is not None


def test_approve_404_when_no_draft(client):
    resp = client.post(
        f"/v1/style-dnas/{TID}/approve",
        json={"org_id": ORG},
    )
    assert resp.status_code == 404


# ----------------------------------------------------------------- delete
def test_delete_removes_both_draft_and_approved(client):
    repo.save_draft(_fake_dna(), ORG)
    repo.save_approved(_fake_dna(status="approved"), ORG)

    resp = client.delete(f"/v1/style-dnas/{TID}", params={"org_id": ORG})
    assert resp.status_code == 204
    assert repo.load_active(ORG, TID) is None
