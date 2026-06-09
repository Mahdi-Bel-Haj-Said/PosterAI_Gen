"""Tests for /v1/usage — aggregates job counts and estimated cost."""

from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from esports_poster_ai.api.app import app
from esports_poster_ai.api.routes import posters as posters_route
from esports_poster_ai.jobs.store import JobStore


@pytest.fixture
def job_store() -> JobStore:
    return JobStore(collection=mongomock.MongoClient()["testdb"]["jobs"])


@pytest.fixture
def client(job_store) -> TestClient:
    app.dependency_overrides[posters_route.get_job_store] = lambda: job_store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_jobs(store: JobStore, org_id: str, *, completed: int, failed: int, queued: int):
    for _ in range(queued):
        store.create(input_data={}, org_id=org_id, tournament_id="t", mode="fresh")
    for _ in range(completed):
        job = store.create(input_data={}, org_id=org_id, tournament_id="t", mode="fresh")
        store.mark_completed(
            job.job_id, poster_id="p", storage_key="k", local_path="/tmp/p.png"
        )
    for _ in range(failed):
        job = store.create(input_data={}, org_id=org_id, tournament_id="t", mode="fresh")
        store.mark_failed(job.job_id, "boom")


def test_usage_empty_when_no_jobs(client):
    body = client.get("/v1/usage", params={"org_id": "1"}).json()
    assert body["total_jobs"] == 0
    assert body["completed"] == 0
    assert body["failed"] == 0
    assert body["estimated_cost_usd"] == 0


def test_usage_counts_by_status_and_estimates_cost(client, job_store):
    _seed_jobs(job_store, "1", completed=4, failed=2, queued=1)
    _seed_jobs(job_store, "2", completed=10, failed=0, queued=0)  # other org

    body = client.get("/v1/usage", params={"org_id": "1"}).json()
    assert body["total_jobs"] == 7
    assert body["completed"] == 4
    assert body["failed"] == 2
    assert body["queued"] == 1
    assert body["counts_by_status"]["completed"] == 4
    # 4 completed × $0.054 (default cost_per_poster_usd) = $0.216.
    assert body["estimated_cost_usd"] == pytest.approx(0.216, rel=1e-3)


def test_usage_filters_to_one_org(client, job_store):
    _seed_jobs(job_store, "1", completed=3, failed=0, queued=0)
    _seed_jobs(job_store, "2", completed=10, failed=0, queued=0)

    body = client.get("/v1/usage", params={"org_id": "2"}).json()
    assert body["completed"] == 10
