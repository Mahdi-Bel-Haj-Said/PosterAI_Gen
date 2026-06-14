"""
`/v1/social/*` — native social posting via Postiz.

This sits in front of the Postiz Public API. The frontend never talks to
Postiz directly (Postiz lives on a private subnet in prod, and we don't want
to leak the Postiz API key into a browser).

Endpoints
---------
GET  /v1/social/integrations
    Lightweight passthrough of the user's connected accounts so the UI can
    render a "post to:" picker.

POST /v1/social/post
    Schedule or immediately publish a poster to one or more connected
    accounts. The handler fetches the poster bytes from R2, uploads them to
    Postiz, then creates the post.

When Postiz isn't configured (no API key), both endpoints return 503 so the
frontend can hide the native-post UI cleanly — the share-intent buttons keep
working unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import PurePosixPath
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from esports_poster_ai.api.deps import AuthContext, get_auth_context
from esports_poster_ai.api.routes.posters import get_job_store
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.social import PostizClient, PostizError, get_postiz_client
from esports_poster_ai.storage import get_storage
from esports_poster_ai.storage.base import guess_content_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/social", tags=["social"])


# ---- DI helpers -------------------------------------------------------------


def get_postiz() -> PostizClient:
    """
    Resolve a configured PostizClient or 503.

    503 (not 500) is deliberate — "service unavailable" is the honest signal
    when the integration is simply switched off, and lets the frontend feature-
    detect by probing /v1/social/integrations.
    """
    client = get_postiz_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Postiz is not configured. Set POSTIZ_BASE_URL and "
                "POSTIZ_API_KEY in the API environment to enable native posting."
            ),
        )
    return client


# ---- schemas ----------------------------------------------------------------


class Integration(BaseModel):
    """One connected social account as surfaced to the frontend."""

    id: str
    name: Optional[str] = None
    platform: Optional[str] = Field(
        default=None,
        description="Platform identifier (x, facebook, instagram, linkedin, …).",
    )
    picture: Optional[str] = None

    @classmethod
    def from_postiz(cls, raw: dict) -> "Integration":
        # Postiz's response shape drifts a bit between versions; pull the
        # commonly-present fields and ignore the rest.
        return cls(
            id=str(raw.get("id") or raw.get("integrationId") or ""),
            name=raw.get("name") or raw.get("providerIdentifier") or raw.get("display"),
            platform=raw.get("identifier") or raw.get("provider") or raw.get("type"),
            picture=raw.get("picture") or raw.get("image"),
        )


class IntegrationsResponse(BaseModel):
    integrations: List[Integration]
    count: int


class CreatePostRequest(BaseModel):
    job_id: str = Field(..., description="Completed poster job to post.")
    integration_ids: List[str] = Field(
        ..., min_length=1, description="Postiz integration ids to post to."
    )
    content: str = Field(
        ..., min_length=1, max_length=4000, description="Caption / post body."
    )
    schedule_at: Optional[datetime] = Field(
        default=None,
        description=(
            "ISO-8601 timestamp (tz-aware). Omit to post immediately. "
            "Postiz enforces a minimum lead-time on its end."
        ),
    )


class CreatePostResponse(BaseModel):
    posted: bool
    scheduled: bool
    scheduled_for: Optional[datetime] = None
    integration_count: int
    postiz_response: Optional[dict] = None


# ---- routes -----------------------------------------------------------------


@router.get("/integrations", response_model=IntegrationsResponse)
def list_integrations(
    client: PostizClient = Depends(get_postiz),
) -> IntegrationsResponse:
    """List the social accounts the Postiz instance has connected."""
    try:
        raw = client.list_integrations()
    except PostizError as exc:
        # Surface a 502 — Postiz exists but is misbehaving.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    integrations = [Integration.from_postiz(item) for item in raw]
    return IntegrationsResponse(integrations=integrations, count=len(integrations))


@router.post("/post", response_model=CreatePostResponse, status_code=202)
def create_post(
    req: CreatePostRequest,
    store: JobStore = Depends(get_job_store),
    client: PostizClient = Depends(get_postiz),
    auth: AuthContext = Depends(get_auth_context),
) -> CreatePostResponse:
    """
    Push a completed poster to one or more connected social accounts.

    Flow:
      1. Look up the job, refuse if it's not a completed poster.
      2. Pull the image bytes from R2 (we already host it; no need to make
         Postiz fetch a signed URL that might expire mid-upload).
      3. Upload bytes to Postiz, get back a media id.
      4. Create the post (or schedule it) on every selected integration.
    """
    job = store.get(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {req.job_id}")
    auth.assert_platform(job.platform_id)
    if job.status != "completed" or not job.storage_key:
        raise HTTPException(
            status_code=400,
            detail=f"Job {req.job_id} is not a completed poster (status={job.status}).",
        )

    # Pull the bytes straight out of our storage — we trust our own copy and
    # avoid Postiz hitting an R2 signed URL that may have expired by upload time.
    storage = get_storage()
    try:
        image_bytes = storage.get_bytes(job.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=410,
            detail=f"Poster bytes are gone from storage: {job.storage_key}",
        ) from exc

    filename = PurePosixPath(job.storage_key).name or f"{job.job_id}.png"
    content_type = guess_content_type(filename)

    try:
        media = client.upload_media(filename, image_bytes, content_type)
        result = client.create_post(
            integration_ids=req.integration_ids,
            content=req.content,
            media_id=media.get("id"),
            schedule_at=req.schedule_at,
        )
    except PostizError as exc:
        # Bubble up Postiz's status code when we have it, otherwise 502.
        status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
        # 4xx from Postiz means the user's request was bad (validation, missing
        # integration permissions, etc.) — pass it through. 5xx means Postiz
        # itself is unhappy, which we report as a gateway error.
        if 400 <= status < 500:
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    scheduled = req.schedule_at is not None
    logger.info(
        "social.post.created",
        extra={
            "job_id": req.job_id,
            "integration_count": len(req.integration_ids),
            "scheduled": scheduled,
        },
    )
    return CreatePostResponse(
        posted=not scheduled,
        scheduled=scheduled,
        scheduled_for=req.schedule_at,
        integration_count=len(req.integration_ids),
        postiz_response=result if isinstance(result, dict) else None,
    )
