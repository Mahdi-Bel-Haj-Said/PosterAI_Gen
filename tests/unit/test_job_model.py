"""Tests for the Job domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from esports_poster_ai.domain.job import Job


def _job(**overrides) -> Job:
    base = dict(org_id="1", tournament_id="ewc_2025", mode="fresh", input_data={})
    base.update(overrides)
    return Job(**base)  # type: ignore[arg-type]


def test_job_defaults():
    job = _job()
    assert job.status == "queued"
    assert job.attempts == 0
    assert job.poster_id is None
    assert job.error is None
    assert job.created_at is not None
    assert job.started_at is None


def test_job_id_is_generated_and_unique():
    assert _job().job_id != _job().job_id
    assert len(_job().job_id) == 32  # uuid4 hex


def test_job_rejects_invalid_status():
    with pytest.raises(ValidationError):
        _job(status="banana")


def test_job_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        _job(mode="weird")


def test_job_keeps_input_data():
    payload = {"_meta": {"game": "valorant"}, "match": {}}
    assert _job(input_data=payload).input_data == payload
