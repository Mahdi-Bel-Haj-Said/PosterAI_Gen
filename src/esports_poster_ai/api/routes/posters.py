"""
`/v1/posters` endpoints — a thin HTTP layer over the async job system.

`POST` enqueues a job; `GET` reads the durable record from MongoDB. No
pipeline logic lives here.
"""

from __future__ import annotations

import logging
from typing import Optional

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response as FastAPIResponse
from pydantic import ValidationError

from esports_poster_ai.api.schemas import (
    CreatePosterRequest,
    JobListResponse,
    JobResponse,
    RefinePosterRequest,
)
from esports_poster_ai.clients.gemini_client import GeminiError
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.inputs import PosterInput
from esports_poster_ai.domain.job import Job
from esports_poster_ai.jobs import enqueue_poster_job
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.quotas import apply_quota_headers, check_quota_or_raise
from esports_poster_ai.stages.caption_generator import generate_caption_for_job
from esports_poster_ai.storage import get_storage
from esports_poster_ai.storage.base import Storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/posters", tags=["posters"])


def get_job_store() -> JobStore:
    """FastAPI dependency providing a JobStore. Overridable in tests."""
    return JobStore()


def _job_to_response(job: Job, storage: Storage) -> JobResponse:
    """Build a JobResponse, attaching a signed R2 URL for completed posters."""
    signed_url = None
    if job.status == "completed" and job.storage_key:
        signed_url = storage.signed_url(job.storage_key)
    return JobResponse.from_job(job, signed_url=signed_url)


@router.post("", status_code=202, response_model=JobResponse)
def create_poster(req: CreatePosterRequest, response: Response) -> JobResponse:
    """
    Enqueue a poster-generation job.

    The `input` document is validated as a `PosterInput`; the generation mode
    is taken from its `_meta.mode`. Returns the job immediately (202) — poll
    `GET /v1/posters/{job_id}` for the result.

    Per-org rate limit (rolling day / week / month) is checked before enqueue
    and the standard `X-RateLimit-*` headers are stamped on the response.
    A breach returns HTTP 429 with `Retry-After` and a structured detail.
    """
    try:
        poster = PosterInput.model_validate(req.input)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=jsonable_encoder(e.errors()))

    quotas = check_quota_or_raise(req.org_id)

    job = enqueue_poster_job(
        input_data=req.input,
        org_id=req.org_id,
        tournament_id=req.tournament_id,
        mode=poster.meta.mode,
    )
    apply_quota_headers(response, quotas)
    logger.info("api.poster.created", extra={"job_id": job.job_id})
    return JobResponse.from_job(job)


@router.post("/{job_id}/refine", status_code=202, response_model=JobResponse)
def refine_poster(
    job_id: str,
    req: RefinePosterRequest,
    response: Response,
    store: JobStore = Depends(get_job_store),
) -> JobResponse:
    """
    Apply a freeform edit to an existing completed poster.

    Image-edit pass on `gpt-image-2`: parent poster bytes become the canvas,
    the user's prompt drives the change, the result is a new sibling poster
    under the same tournament. Best for VISUAL tweaks; factual-text edits
    (time / score / names) should re-run the pipeline from edited input data.
    """
    parent = store.get(job_id)
    if parent is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if parent.status != "completed" or not parent.storage_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Parent job is not a completed poster (status={parent.status}); "
                "only a completed poster can be refined."
            ),
        )

    quotas = check_quota_or_raise(parent.org_id)

    parent_meta = (parent.input_data or {}).get("_meta") or {}
    refine_input = {
        "_meta": {
            "game": parent_meta.get("game", "league_of_legends"),
            "poster_type": parent_meta.get("poster_type", "gameday"),
            "mode": "refine",
            "output_format": parent_meta.get("output_format", "portrait_1080x1920"),
        },
        "refine": {
            "parent_job_id": parent.job_id,
            "parent_storage_key": parent.storage_key,
            "user_prompt": req.prompt,
        },
    }

    job = enqueue_poster_job(
        input_data=refine_input,
        org_id=parent.org_id,
        tournament_id=parent.tournament_id,
        mode="refine",
    )
    apply_quota_headers(response, quotas)
    logger.info(
        "api.poster.refine_enqueued",
        extra={"job_id": job.job_id, "parent_job_id": parent.job_id},
    )
    return JobResponse.from_job(job)


@router.get("/{job_id}", response_model=JobResponse)
def get_poster(
    job_id: str,
    store: JobStore = Depends(get_job_store),
) -> JobResponse:
    """Get a job's status and result (a signed URL once completed)."""
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return _job_to_response(job, get_storage())


@router.get("/{job_id}/download")
def download_poster(
    job_id: str,
    store: JobStore = Depends(get_job_store),
) -> FastAPIResponse:
    """
    Stream the completed poster bytes back as an ``attachment`` download.

    We proxy through this endpoint instead of pointing the browser straight at
    the R2 signed URL because:
      * R2 signed URLs don't carry ``Content-Disposition: attachment``, so the
        browser opens the PNG in a new tab instead of saving it.
      * Cross-origin ``fetch()`` calls from the frontend to R2 fail CORS — the
        quick-share modal needs the bytes as a blob to trigger a download
        programmatically. Same-origin (this API) avoids the issue entirely.
    """
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if job.status != "completed" or not job.storage_key:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not a completed poster (status={job.status}).",
        )

    storage = get_storage()
    try:
        data = storage.get_bytes(job.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=410,
            detail=f"Poster bytes are gone from storage: {job.storage_key}",
        ) from exc

    # Build a sensible filename — prefer the tournament + job id so users with
    # a downloads folder full of posters can tell them apart at a glance.
    suffix = PurePosixPath(job.storage_key).suffix or ".png"
    safe_tournament = "".join(
        c if c.isalnum() or c in ("-", "_") else "_"
        for c in (job.tournament_id or "poster")
    )[:48]
    filename = f"{safe_tournament}_{job.job_id}{suffix}"

    content_type = "image/png" if suffix.lower() == ".png" else "application/octet-stream"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        # Short cache so a re-download is fast but storage churn doesn't pile up.
        "Cache-Control": "private, max-age=60",
    }
    return FastAPIResponse(content=data, media_type=content_type, headers=headers)


@router.post("/{job_id}/caption", response_model=JobResponse)
def generate_caption(
    job_id: str,
    regenerate: bool = Query(False, description="Force a new caption even if one is cached."),
    store: JobStore = Depends(get_job_store),
) -> JobResponse:
    """
    Get or generate a social caption for this completed poster.

    First call generates via Gemini and caches on the job document; subsequent
    calls return the cached caption unless ``regenerate=true``. Returns 503
    when GEMINI_API_KEY isn't configured so the frontend can hide the feature.
    """
    if not get_settings().gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set; caption generation is disabled.",
        )

    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if job.status != "completed" or not job.storage_key:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not a completed poster (status={job.status}).",
        )

    if job.caption and not regenerate:
        return _job_to_response(job, get_storage())

    try:
        caption = generate_caption_for_job(job)
    except GeminiError as exc:
        # 502 — upstream LLM problem. Frontend shows the error inline so the
        # user can retry without leaving the page.
        raise HTTPException(status_code=502, detail=f"Gemini: {exc}") from exc

    store.set_caption(job_id, caption)
    # Re-fetch so the response carries the persisted caption.
    fresh = store.get(job_id) or job
    return _job_to_response(fresh, get_storage())


@router.get("", response_model=JobListResponse)
def list_posters(
    org_id: str = Query(..., description="Organization id to list posters for."),
    tournament_id: Optional[str] = Query(None, description="Optional tournament filter."),
    limit: int = Query(50, ge=1, le=200),
    store: JobStore = Depends(get_job_store),
) -> JobListResponse:
    """List an org's posters, most recent first. Completed posters include a signed URL."""
    jobs = store.list_for_org(org_id, limit=limit)
    if tournament_id:
        jobs = [j for j in jobs if j.tournament_id == tournament_id]
    storage = get_storage()
    return JobListResponse(
        jobs=[_job_to_response(j, storage) for j in jobs],
        count=len(jobs),
    )
