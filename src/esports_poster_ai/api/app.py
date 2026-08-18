"""
FastAPI application — EsportsPostAI HTTP API.

Tier 1: poster job endpoints + a health check. Auth, assets, and style-DNA
endpoints come in later tiers.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from esports_poster_ai.api.routes.api_keys import router as api_keys_router
from esports_poster_ai.api.routes.assets import router as assets_router
from esports_poster_ai.api.routes.coins import router as coins_router
from esports_poster_ai.api.routes.backgrounds import router as backgrounds_router
from esports_poster_ai.api.routes.me import router as me_router
from esports_poster_ai.api.routes.orgs import router as orgs_router
from esports_poster_ai.api.routes.posters import router as posters_router
from esports_poster_ai.api.routes.share import router as share_router
from esports_poster_ai.api.routes.social import router as social_router
from esports_poster_ai.api.routes.style_dnas import router as style_dnas_router
from esports_poster_ai.api.routes.taglines import router as taglines_router
from esports_poster_ai.api.routes.usage import admin_router as admin_usage_router
from esports_poster_ai.api.routes.usage import router as usage_router
from esports_poster_ai.api.routes.webhooks import router as webhooks_router
from esports_poster_ai.api.schemas import HealthResponse
from esports_poster_ai.jobs.queue import get_redis
from esports_poster_ai.jobs.store import JobStore

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EsportsPostAI API",
    version="1.0.0",
    description="Generate esports posters via async jobs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(posters_router)
app.include_router(assets_router)
app.include_router(style_dnas_router)
app.include_router(api_keys_router)
app.include_router(usage_router)
app.include_router(admin_usage_router)
app.include_router(share_router)
app.include_router(social_router)
app.include_router(me_router)
app.include_router(orgs_router)
app.include_router(backgrounds_router)
app.include_router(webhooks_router)
app.include_router(coins_router)
app.include_router(taglines_router)


def _mongodb_ok() -> bool:
    try:
        JobStore().ping()
        return True
    except Exception:  # noqa: BLE001 — health check must never raise
        return False


def _redis_ok() -> bool:
    try:
        get_redis().ping()
        return True
    except Exception:  # noqa: BLE001 — health check must never raise
        return False


@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health(response: Response) -> HealthResponse:
    """Liveness/readiness — checks MongoDB and Redis. 503 if either is down."""
    mongo = _mongodb_ok()
    redis = _redis_ok()
    healthy = mongo and redis
    if not healthy:
        response.status_code = 503
    return HealthResponse(
        status="ok" if healthy else "degraded",
        mongodb="ok" if mongo else "down",
        redis="ok" if redis else "down",
    )
