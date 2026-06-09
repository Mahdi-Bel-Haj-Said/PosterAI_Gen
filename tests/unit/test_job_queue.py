"""Tests for jobs.queue.enqueue_poster_job — no Redis / no network."""

from __future__ import annotations

import mongomock
import pytest

from esports_poster_ai.jobs.store import JobStore


def test_enqueue_marks_job_failed_when_redis_push_fails(monkeypatch):
    """
    Regression: if the Redis push fails after the Mongo job is created, the job
    must not be left stranded in `queued` — it should be marked `failed`.
    """
    collection = mongomock.MongoClient()["testdb"]["jobs"]

    # enqueue_poster_job builds its own JobStore — swap it for one backed by
    # our mongomock collection so we can inspect the result.
    monkeypatch.setattr(
        "esports_poster_ai.jobs.queue.JobStore",
        lambda **kwargs: JobStore(collection=collection),
    )

    # Make the Redis push fail.
    def _boom(*args, **kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr("esports_poster_ai.jobs.queue.get_queue", _boom)

    from esports_poster_ai.jobs.queue import enqueue_poster_job

    with pytest.raises(RuntimeError):
        enqueue_poster_job(
            input_data={}, org_id="1", tournament_id="t", mode="fresh"
        )

    jobs = list(collection.find())
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"
    assert "enqueue failed" in jobs[0]["error"]
