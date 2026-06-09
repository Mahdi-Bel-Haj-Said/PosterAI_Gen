"""Tests for JobStore — uses mongomock, no real MongoDB / no network."""

from __future__ import annotations

import mongomock
import pytest

from esports_poster_ai.jobs.store import JobStore


@pytest.fixture
def store() -> JobStore:
    collection = mongomock.MongoClient()["testdb"]["jobs"]
    return JobStore(collection=collection)


def test_create_and_get_roundtrip(store: JobStore):
    job = store.create(
        input_data={"_meta": {"game": "valorant"}},
        org_id="1",
        tournament_id="ewc_2025",
        mode="fresh",
    )
    assert job.status == "queued"

    loaded = store.get(job.job_id)
    assert loaded is not None
    assert loaded.job_id == job.job_id
    assert loaded.org_id == "1"
    assert loaded.tournament_id == "ewc_2025"
    assert loaded.input_data == {"_meta": {"game": "valorant"}}


def test_get_missing_returns_none(store: JobStore):
    assert store.get("does-not-exist") is None


def test_update_status(store: JobStore):
    job = store.create(input_data={}, org_id="1", tournament_id="t", mode="fresh")
    store.update_status(job.job_id, "generating_poster")
    assert store.get(job.job_id).status == "generating_poster"


def test_mark_running_sets_started_at(store: JobStore):
    job = store.create(input_data={}, org_id="1", tournament_id="t", mode="fresh")
    assert store.get(job.job_id).started_at is None
    store.mark_running(job.job_id)
    assert store.get(job.job_id).started_at is not None


def test_mark_completed(store: JobStore):
    job = store.create(input_data={}, org_id="1", tournament_id="t", mode="fresh")
    store.mark_completed(
        job.job_id, poster_id="p1", storage_key="orgs/1/.../p1.png", local_path="/tmp/p1.png"
    )
    loaded = store.get(job.job_id)
    assert loaded.status == "completed"
    assert loaded.poster_id == "p1"
    assert loaded.storage_key == "orgs/1/.../p1.png"
    assert loaded.local_path == "/tmp/p1.png"
    assert loaded.completed_at is not None


def test_mark_failed_records_error_and_increments_attempts(store: JobStore):
    job = store.create(input_data={}, org_id="1", tournament_id="t", mode="fresh")
    store.mark_failed(job.job_id, "RuntimeError: boom")
    loaded = store.get(job.job_id)
    assert loaded.status == "failed"
    assert loaded.error == "RuntimeError: boom"
    assert loaded.attempts == 1


def test_list_for_org_filters_by_org(store: JobStore):
    store.create(input_data={}, org_id="1", tournament_id="t", mode="fresh")
    store.create(input_data={}, org_id="1", tournament_id="t", mode="consistency")
    store.create(input_data={}, org_id="2", tournament_id="t", mode="fresh")

    org1 = store.list_for_org("1")
    assert len(org1) == 2
    assert all(j.org_id == "1" for j in org1)

    assert len(store.list_for_org("2")) == 1
    assert store.list_for_org("nobody") == []
