"""
`POST /v1/posters/express` — the simple integration surface.

One call in, a poster out. No org registration, no coin balance, no quota tier,
no tenancy hierarchy to adopt. The integrator gates access in their own code,
against their own users, with their own pricing:

    if (wallet.balance >= price && mayGenerate(user)) {
        const poster = await posterAI.express(input)
        await debit(user, price)
    }

Deliberately absent, and why:

  - **No coin gate.** `POST /v1/posters` runs `_assert_coins_or_raise` and can
    answer 402 from the service's own economy. That forces every integrator to
    adopt Red Coins or neutralise them. Express never gates on balance.
  - **No org registration.** `org_id` on the classic route must name an org
    registered under the platform. Express takes an optional free-text
    `group_id` used only to namespace Style DNA and history.
  - **No per-org quota.** Rate limiting here protects the provider's own
    infrastructure, not the integrator's product.

Deliberately kept:

  - **Metering.** Every generation records `platform_id` and cost. That is how
    the provider invoices the integrator — a counter, not a gate.
  - **Idempotency.** A poster costs real money; a retried call must not produce
    (and bill for) a second one.
  - **The queue.** Express *looks* synchronous but still goes through the
    worker pool, so concurrency stays bounded and one slow poster cannot tie up
    an API worker. A sync façade over an async engine.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, ValidationError

try:  # pymongo is a lazy/optional dependency — tests inject a mongomock collection
    from pymongo.errors import DuplicateKeyError
except ImportError:  # pragma: no cover
    class DuplicateKeyError(Exception):  # type: ignore[no-redef]
        """Stand-in so the duplicate-key handler stays valid without pymongo."""

from esports_poster_ai.api.deps import AuthContext, get_auth_context
from esports_poster_ai.billing import quality_multiplier
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.inputs import PosterInput
from esports_poster_ai.domain.job import Job
from esports_poster_ai.jobs import enqueue_poster_job
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/posters", tags=["posters"])

#: How long a caller may ask us to hold the connection.
#:
#: A poster takes 20-90s. Many proxies cut a request well before that — nginx
#: defaults to 60s, Heroku hard-kills at 30s, Cloudflare at 100s — so the ceiling
#: sits just under the most common hard limit and callers behind a stricter
#: proxy should lower it and take the 202 path.
MAX_WAIT_SECONDS = 100
DEFAULT_WAIT_SECONDS = 90

#: Gap between job-status reads while waiting. Short enough to return promptly,
#: long enough not to hammer Mongo for the whole wait.
_POLL_INTERVAL_SECONDS = 1.5

_TERMINAL = ("completed", "failed")


def get_job_store() -> JobStore:
    """FastAPI dependency providing a JobStore. Overridable in tests."""
    return JobStore()


class ExpressPosterRequest(BaseModel):
    """Body of `POST /v1/posters/express`."""

    input: Dict[str, Any] = Field(
        description=(
            "The poster input document, validated as PosterInput. Logo fields "
            "accept a public https URL as well as an uploaded storage key, so "
            "assets on your own CDN need no pre-upload."
        )
    )
    group_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional. Groups posters that should share a visual identity — a "
            "tournament, a season, a team. Only used to namespace Style DNA and "
            "history; it is never checked for access and needs no registration. "
            "Omit for a standalone poster."
        ),
    )


class ExpressCost(BaseModel):
    usd: float = Field(description="Provider-side cost of this generation, in USD.")
    quality: str = Field(description="Quality tier actually used.")


class ExpressPosterResponse(BaseModel):
    """
    Answer to an express generation.

    `status` is `completed` (200, `image_url` populated), `failed` (200, `error`
    populated), or still in-flight (202 — poll `poll_url`).
    """

    job_id: str
    status: str
    image_url: Optional[str] = Field(default=None, description="Signed, time-limited URL.")
    error: Optional[str] = None
    cost: ExpressCost
    poll_url: Optional[str] = Field(
        default=None, description="Set on 202: GET this until status is terminal."
    )


def _standalone_group(platform_id: Optional[str]) -> str:
    """
    Style DNA is stored per group, so a group is always needed internally even
    when the caller does not care. Keyed per platform so two integrators never
    share a bucket.
    """
    return f"express-{platform_id or 'local'}"


def _cost_usd(quality: Optional[str]) -> float:
    settings = get_settings()
    return round(settings.cost_per_poster_usd * quality_multiplier(quality), 6)


def _to_response(job: Job, *, poll_url: Optional[str] = None) -> ExpressPosterResponse:
    image_url = None
    if job.status == "completed" and job.storage_key:
        try:
            image_url = get_storage().signed_url(job.storage_key)
        except Exception as e:  # noqa: BLE001 — a signing failure must not 500 the call
            logger.warning("express.sign_failed", extra={"job_id": job.job_id, "error": str(e)})

    return ExpressPosterResponse(
        job_id=job.job_id,
        status=job.status,
        image_url=image_url,
        error=job.error,
        cost=ExpressCost(
            usd=job.cost_usd if job.cost_usd is not None else _cost_usd(_quality_of(job)),
            quality=_quality_of(job) or "medium",
        ),
        poll_url=poll_url,
    )


def _quality_of(job: Job) -> Optional[str]:
    meta = (job.input_data or {}).get("_meta") or {}
    quality = meta.get("quality")
    return quality if isinstance(quality, str) else None


@router.post(
    "/express",
    response_model=ExpressPosterResponse,
    status_code=200,
    summary="Generate a poster in one call",
)
async def create_poster_express(
    req: ExpressPosterRequest,
    wait: int = Query(
        default=DEFAULT_WAIT_SECONDS,
        ge=0,
        le=MAX_WAIT_SECONDS,
        description=(
            "Seconds to hold the connection waiting for the poster. 0 returns a "
            "job id immediately. If the poster is not ready in time the call "
            "answers 202 with a job id — the generation continues either way."
        ),
    ),
    store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
    idempotency_key: Optional[str] = Header(
        default=None,
        alias="X-Idempotency-Key",
        description=(
            "Optional. Repeating a request with the same key returns the original "
            "poster instead of generating — and charging for — a second one."
        ),
    ),
) -> Any:
    """
    Generate a poster and return it.

    Gating is the caller's job: this endpoint checks nothing about who the poster
    is for, whether they have credit, or how many they have made. It validates
    the input, generates, and reports what it cost.
    """
    from fastapi.responses import JSONResponse

    # ---------------------------------------------------------------- replay
    if idempotency_key:
        existing = await run_in_threadpool(
            store.find_by_idempotency_key, idempotency_key, platform_id=auth.platform_id
        )
        if existing is not None:
            logger.info(
                "express.idempotent_replay",
                extra={"job_id": existing.job_id, "idempotency_key": idempotency_key},
            )
            payload = _to_response(existing)
            status_code = 200 if existing.status in _TERMINAL else 202
            if status_code == 202:
                payload.poll_url = f"/v1/posters/{existing.job_id}"
            return JSONResponse(
                status_code=status_code,
                content=jsonable_encoder(payload),
                headers={"X-Idempotent-Replay": "true"},
            )

    # -------------------------------------------------------------- validate
    try:
        poster = PosterInput.model_validate(req.input)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=jsonable_encoder(e.errors()))

    group_id = (req.group_id or "").strip() or _standalone_group(auth.platform_id)

    # ---------------------------------------------------------------- enqueue
    # No coin gate, no org lookup, no quota check — by design.
    try:
        job = await run_in_threadpool(
            enqueue_poster_job,
            input_data=req.input,
            org_id=group_id,
            tournament_id=group_id,
            mode=poster.meta.mode,
            platform_id=auth.platform_id,
            idempotency_key=idempotency_key,
        )
    except DuplicateKeyError:
        # A concurrent twin won the unique index — answer with its job.
        twin = (
            await run_in_threadpool(
                store.find_by_idempotency_key, idempotency_key, platform_id=auth.platform_id
            )
            if idempotency_key
            else None
        )
        if twin is None:
            raise
        return JSONResponse(
            status_code=200 if twin.status in _TERMINAL else 202,
            content=jsonable_encoder(_to_response(twin)),
            headers={"X-Idempotent-Replay": "true"},
        )

    logger.info(
        "express.created",
        extra={"job_id": job.job_id, "platform_id": auth.platform_id, "wait": wait},
    )

    if wait == 0:
        payload = _to_response(job, poll_url=f"/v1/posters/{job.job_id}")
        return JSONResponse(status_code=202, content=jsonable_encoder(payload))

    # ------------------------------------------------------------------ wait
    finished = await _await_terminal(store, job.job_id, wait)

    if finished is None:
        # Still generating. The caller keeps the job id — nothing is lost, and
        # they are not billed twice for polling it out.
        logger.info("express.timeout", extra={"job_id": job.job_id, "waited": wait})
        payload = _to_response(job, poll_url=f"/v1/posters/{job.job_id}")
        return JSONResponse(status_code=202, content=jsonable_encoder(payload))

    return JSONResponse(status_code=200, content=jsonable_encoder(_to_response(finished)))


async def _await_terminal(store: JobStore, job_id: str, wait_seconds: int) -> Optional[Job]:
    """
    Poll until the job reaches a terminal state or the budget runs out.

    `async` on purpose: a `def` route would occupy one of FastAPI's threadpool
    slots for the whole wait, and a handful of concurrent express calls would
    starve every other endpoint. Here only the short store reads touch a thread.
    """
    deadline = time.monotonic() + wait_seconds

    while True:
        job = await run_in_threadpool(store.get, job_id)
        if job is not None and job.status in _TERMINAL:
            return job

        if time.monotonic() >= deadline:
            return None

        await asyncio.sleep(min(_POLL_INTERVAL_SECONDS, max(0.0, deadline - time.monotonic())))
