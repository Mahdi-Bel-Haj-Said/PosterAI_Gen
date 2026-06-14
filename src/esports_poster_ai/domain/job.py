"""
Job domain model — one poster-generation request tracked through the async
pipeline.

A `Job` is the system of record for a request: its status, the input, the
result, and timestamps. It is persisted in MongoDB by `jobs.store.JobStore`.
Redis/RQ only moves the work; this document is the durable trail (and the
basis for the future billing report).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal[
    "queued",
    "generating_prompt",
    "generating_poster",
    "applying_sponsor_bar",
    "completed",
    "failed",
]

JobMode = Literal["fresh", "consistency", "refine"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Job(BaseModel):
    """A single poster-generation job."""

    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(default_factory=lambda: uuid4().hex)
    status: JobStatus = "queued"

    # Routing / tenancy. `platform_id` is the integrating platform (from the API
    # key); None for CLI / dev single-tenant runs. `org_id` is unique within the
    # platform.
    platform_id: Optional[str] = None
    org_id: str
    tournament_id: str
    mode: JobMode

    # The poster input JSON, stored verbatim so the worker is self-contained.
    input_data: Dict[str, Any]

    # Result (set on completion).
    poster_id: Optional[str] = None
    storage_key: Optional[str] = None
    local_path: Optional[str] = None

    # Lazily-generated social caption (Gemini). Populated on first call to
    # POST /v1/posters/{job_id}/caption and reused thereafter.
    caption: Optional[str] = None

    # Failure detail.
    error: Optional[str] = None
    attempts: int = 0

    # Billing trail (estimate acceptable for v0).
    cost_usd: Optional[float] = None

    # Timestamps.
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


__all__ = ["Job", "JobStatus", "JobMode"]
