"""
Idempotency on job creation.

A poster costs real money, so a retried or double-clicked submit must return the
original job rather than generating (and billing) a second one. These tests
cover the store layer, where correctness actually lives — the route's pre-check
is only an optimisation on top of it.
"""

from __future__ import annotations

import mongomock
import pytest

from esports_poster_ai.jobs.store import JobStore


@pytest.fixture()
def store() -> JobStore:
    collection = mongomock.MongoClient().db.jobs
    return JobStore(collection=collection)


def _create(store: JobStore, *, key=None, platform_id="defendr", org_id="org-1"):
    return store.create(
        input_data={"_meta": {"mode": "fresh"}},
        org_id=org_id,
        tournament_id="t-1",
        mode="fresh",
        platform_id=platform_id,
        idempotency_key=key,
    )


def test_key_is_persisted_and_findable(store: JobStore) -> None:
    job = _create(store, key="abc-123")

    found = store.find_by_idempotency_key("abc-123", platform_id="defendr")

    assert found is not None
    assert found.job_id == job.job_id
    assert found.idempotency_key == "abc-123"


def test_unknown_key_returns_none(store: JobStore) -> None:
    _create(store, key="abc-123")

    assert store.find_by_idempotency_key("nope", platform_id="defendr") is None


def test_lookup_is_scoped_per_platform(store: JobStore) -> None:
    """
    Two platforms picking the same key must not see each other's jobs — the same
    isolation rule that applies to org ids.
    """
    mine = _create(store, key="shared-key", platform_id="defendr")
    _create(store, key="shared-key", platform_id="acme")

    found = store.find_by_idempotency_key("shared-key", platform_id="defendr")

    assert found is not None
    assert found.job_id == mine.job_id


def test_jobs_without_a_key_do_not_collide(store: JobStore) -> None:
    """
    CLI runs and clients that don't send the header leave the field None. Those
    must never be treated as duplicates of one another — which is why the unique
    index is partial on `{"idempotency_key": {"$type": "string"}}`.
    """
    first = _create(store, key=None)
    second = _create(store, key=None)

    assert first.job_id != second.job_id
    assert first.idempotency_key is None
    assert second.idempotency_key is None


def test_key_defaults_to_none(store: JobStore) -> None:
    """The field is optional — omitting it must not change existing behaviour."""
    job = store.create(
        input_data={},
        org_id="org-1",
        tournament_id="t-1",
        mode="fresh",
    )

    assert job.idempotency_key is None


def test_lookup_distinguishes_null_platform(store: JobStore) -> None:
    """
    Dev-mode jobs carry `platform_id=None`. A lookup for a real platform must not
    match them, or legacy single-tenant rows would leak into a tenant's replay.
    """
    _create(store, key="k", platform_id=None)

    assert store.find_by_idempotency_key("k", platform_id="defendr") is None
    assert store.find_by_idempotency_key("k", platform_id=None) is not None
