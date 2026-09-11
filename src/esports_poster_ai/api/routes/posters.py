"""
`/v1/posters` endpoints — a thin HTTP layer over the async job system.

`POST` enqueues a job; `GET` reads the durable record from MongoDB. No
pipeline logic lives here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel, Field, ValidationError

try:  # pymongo is a lazy/optional dependency — tests inject a mongomock collection
    from pymongo.errors import DuplicateKeyError
except ImportError:  # pragma: no cover
    class DuplicateKeyError(Exception):  # type: ignore[no-redef]
        """Stand-in so the duplicate-key handler stays valid without pymongo."""

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.api.schemas import (
    CreatePosterRequest,
    JobListResponse,
    JobResponse,
    RefinePosterRequest,
)
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.billing import quality_multiplier
from esports_poster_ai.platforms import branding_for, economics_for, features_for
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.inputs import PosterInput
from esports_poster_ai.domain.job import Job
from esports_poster_ai.jobs import enqueue_poster_job
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.quotas import apply_quota_headers, check_quota_or_raise
from esports_poster_ai.stages.caption_generator import CaptionError, generate_caption_for_job
from esports_poster_ai.storage import get_storage
from esports_poster_ai.storage.base import Storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/posters", tags=["posters"])


def _assert_coins_or_raise(
    org_store: OrgStore, auth: AuthContext, org_id: str, quality: str | None
) -> int:
    """
    Ensure the org has enough Red Coins for one poster at this quality.

    Credits any due monthly grant first, then blocks with HTTP 402 if the balance
    is short. Returns the estimated token cost so callers can surface it.
    """
    est = economics_for(auth.platform_id).estimate_tokens(quality_multiplier(quality))
    org = org_store.ensure_monthly_grant(auth.platform_id, org_id)
    if org is None:
        # Dev path: org not registered yet — create it (seeds its first grant).
        org_store.ensure(auth.platform_id, org_id)
        org = org_store.ensure_monthly_grant(auth.platform_id, org_id)
    balance = org.coins_balance if org else 0
    if balance < est:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_coins",
                "message": "Not enough Red Coins for this poster.",
                "needed": est,
                "balance": balance,
            },
        )
    return est


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
def create_poster(
    req: CreatePosterRequest,
    response: Response,
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
    idempotency_key: Optional[str] = Header(
        default=None,
        alias="X-Idempotency-Key",
        description=(
            "Optional. Repeating a request with the same key returns the "
            "original job instead of generating (and charging for) a second "
            "poster. Scoped per platform."
        ),
    ),
) -> JobResponse:
    """
    Enqueue a poster-generation job.

    The `input` document is validated as a `PosterInput`; the generation mode
    is taken from its `_meta.mode`. Returns the job immediately (202) — poll
    `GET /v1/posters/{job_id}` for the result.

    `org_id` comes from the request and (when authenticated) must name an org
    registered under the caller's platform. The job is scoped to that platform.
    Per-org rate limit (rolling day / week / month) is checked before enqueue and
    the standard `X-RateLimit-*` headers are stamped on the response. A breach
    returns HTTP 429 with `Retry-After`.

    Supplying `X-Idempotency-Key` makes the call safe to retry: a duplicate
    returns the original job (202, `X-Idempotent-Replay: true`) without spending
    quota or coins. A poster costs real money, so a network retry or a
    double-clicked button must never produce two.
    """
    # Cheap pre-check: catches the overwhelmingly common case (a retry arriving
    # after the first request finished) before doing any validation or quota
    # work. The genuine race is caught by the unique index at insert time.
    if idempotency_key:
        existing = store.find_by_idempotency_key(
            idempotency_key, platform_id=auth.platform_id
        )
        if existing is not None:
            response.headers["X-Idempotent-Replay"] = "true"
            logger.info(
                "api.poster.idempotent_replay",
                extra={"job_id": existing.job_id, "idempotency_key": idempotency_key},
            )
            return JobResponse.from_job(existing)

    org_id = auth.require_org(req.org_id)
    limits = auth.resolve_org_limits(org_id, org_store)

    try:
        poster = PosterInput.model_validate(req.input)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=jsonable_encoder(e.errors()))

    # Feature entitlements for this client (what they enabled for their orgs).
    feats = features_for(auth.platform_id)
    if poster.meta.mode == "consistency" and not feats.consistency:
        raise HTTPException(status_code=403, detail="Consistency mode is not enabled on this plan.")
    if poster.meta.quality not in feats.allowed_qualities:
        raise HTTPException(
            status_code=422,
            detail=f"Quality '{poster.meta.quality}' is not available on this plan.",
        )

    quotas = check_quota_or_raise(
        org_id, platform_id=auth.platform_id, limits=limits, job_store=store
    )
    # Red Coins gate (in addition to the rolling quota). Charged on success.
    _assert_coins_or_raise(org_store, auth, org_id, poster.meta.quality)

    try:
        job = enqueue_poster_job(
            input_data=req.input,
            org_id=org_id,
            tournament_id=req.tournament_id,
            mode=poster.meta.mode,
            platform_id=auth.platform_id,
            idempotency_key=idempotency_key,
        )
    except DuplicateKeyError:
        # Two identical submits raced past the pre-check. The unique index let
        # exactly one through; this is the loser, so return the winner's job.
        # Without this the caller would see a 500 and most likely retry — the
        # very thing the key exists to prevent.
        existing = store.find_by_idempotency_key(
            idempotency_key, platform_id=auth.platform_id
        ) if idempotency_key else None
        if existing is None:
            raise
        response.headers["X-Idempotent-Replay"] = "true"
        logger.info(
            "api.poster.idempotent_race",
            extra={"job_id": existing.job_id, "idempotency_key": idempotency_key},
        )
        return JobResponse.from_job(existing)

    apply_quota_headers(response, quotas)
    logger.info("api.poster.created", extra={"job_id": job.job_id})
    return JobResponse.from_job(job)


class EstimateRequest(BaseModel):
    org_id: Optional[str] = Field(default=None, description="Org id (taken from the key when omitted).")
    input: Dict[str, Any] = Field(..., description="A PosterInput document, same shape as POST /v1/posters.")


@router.post("/estimate")
def estimate_poster(
    req: EstimateRequest,
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> Dict[str, Any]:
    """
    Price a poster WITHOUT generating it — returns the Red Coins it would cost
    under this client's economics, the org's current balance, and whether it's
    affordable. Clients call this to show a cost before the user hits generate,
    instead of reimplementing the pricing formula.
    """
    org_id = auth.require_org(req.org_id)
    try:
        poster = PosterInput.model_validate(req.input)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=jsonable_encoder(e.errors()))

    econ = economics_for(auth.platform_id)
    tokens = econ.estimate_tokens(quality_multiplier(poster.meta.quality))
    org = org_store.ensure_monthly_grant(auth.platform_id, org_id)
    balance = org.coins_balance if org else 0
    return {
        "org_id": org_id,
        "quality": poster.meta.quality,
        "tokens": tokens,                         # cost of THIS poster, in coins
        "balance": balance,
        "sufficient": balance >= tokens,
        "coin_symbol": branding_for(auth.platform_id).coin_symbol,
        "est_per_poster": {q: econ.estimate_tokens(quality_multiplier(q)) for q in ("low", "medium", "high")},
    }


@router.post("/{job_id}/refine", status_code=202, response_model=JobResponse)
def refine_poster(
    job_id: str,
    req: RefinePosterRequest,
    response: Response,
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
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
    auth.assert_platform(parent.platform_id)
    if parent.status != "completed" or not parent.storage_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Parent job is not a completed poster (status={parent.status}); "
                "only a completed poster can be refined."
            ),
        )

    parent_org = org_store.get(parent.platform_id, parent.org_id)
    parent_limits = parent_org.limits.model_dump() if parent_org else None
    quotas = check_quota_or_raise(
        parent.org_id, platform_id=parent.platform_id, limits=parent_limits, job_store=store
    )

    if not features_for(auth.platform_id).refine:
        raise HTTPException(status_code=403, detail="Refine is not enabled on this plan.")
    parent_meta = (parent.input_data or {}).get("_meta") or {}
    refine_quality = parent_meta.get("quality", "medium")
    # Red Coins gate — a refine is a full image-edit pass, so it costs too.
    _assert_coins_or_raise(org_store, auth, parent.org_id, refine_quality)
    refine_input = {
        "_meta": {
            "game": parent_meta.get("game", "league_of_legends"),
            "poster_type": parent_meta.get("poster_type", "gameday"),
            "mode": "refine",
            "output_format": parent_meta.get("output_format", "portrait_1080x1920"),
            "quality": refine_quality,
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
        platform_id=parent.platform_id,
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
    auth: AuthContext = Depends(get_auth_context),
) -> JobResponse:
    """Get a job's status and result (a signed URL once completed)."""
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    auth.assert_platform(job.platform_id)
    return _job_to_response(job, get_storage())


@router.get("/{job_id}/download")
def download_poster(
    job_id: str,
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
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
    auth.assert_platform(job.platform_id)
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
    auth: AuthContext = Depends(get_auth_context),
) -> JobResponse:
    """
    Get or generate a social caption for this completed poster.

    Generated on demand, never as part of poster generation: most posters are
    never shared, so captioning every one spent a model call per poster for a
    feature few users opened.

    First call generates and caches on the job document; subsequent calls return
    the cached caption unless ``regenerate=true``. Returns 503 when no API key
    is configured so the frontend can hide the feature.
    """
    if not features_for(auth.platform_id).caption:
        raise HTTPException(status_code=403, detail="Captions are not enabled on this plan.")
    if not get_settings().openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set; caption generation is disabled.",
        )

    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    auth.assert_platform(job.platform_id)
    if job.status != "completed" or not job.storage_key:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not a completed poster (status={job.status}).",
        )

    if job.caption and not regenerate:
        return _job_to_response(job, get_storage())

    try:
        caption = generate_caption_for_job(job)
    except CaptionError as exc:
        # 502 — upstream LLM problem. Frontend shows the error inline so the
        # user can retry without leaving the page.
        raise HTTPException(status_code=502, detail=f"Caption: {exc}") from exc

    store.set_caption(job_id, caption)
    # Re-fetch so the response carries the persisted caption.
    fresh = store.get(job_id) or job
    return _job_to_response(fresh, get_storage())


class RatePosterRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="User satisfaction rating, 1–5.")


@router.post("/{job_id}/rating", response_model=JobResponse)
def rate_poster(
    job_id: str,
    req: RatePosterRequest,
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
) -> JobResponse:
    """
    Record the user's 1–5 rating of a completed poster.

    Feeds the content-metrics dashboard (avg rating per vibe / energy / combo),
    which is how we learn which design choices produce posters users actually
    like. Idempotent — re-rating overwrites the previous value.
    """
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    auth.assert_platform(job.platform_id)
    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not a completed poster (status={job.status}); only completed posters can be rated.",
        )
    store.set_rating(job_id, req.rating)
    fresh = store.get(job_id) or job
    return _job_to_response(fresh, get_storage())


@router.get("", response_model=JobListResponse)
def list_posters(
    org_id: Optional[str] = Query(
        None, description="Organization id. Omit when authenticating with an API key."
    ),
    tournament_id: Optional[str] = Query(None, description="Optional tournament filter."),
    limit: int = Query(50, ge=1, le=200),
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
) -> JobListResponse:
    """List an org's posters, most recent first. Completed posters include a signed URL."""
    org_id = auth.require_org(org_id)
    jobs = store.list_for_org(org_id, limit=limit, platform_id=auth.platform_id)
    if tournament_id:
        jobs = [j for j in jobs if j.tournament_id == tournament_id]
    storage = get_storage()
    return JobListResponse(
        jobs=[_job_to_response(j, storage) for j in jobs],
        count=len(jobs),
    )
