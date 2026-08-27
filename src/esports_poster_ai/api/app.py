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
from esports_poster_ai.api.routes.express import router as express_router
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
from esports_poster_ai.config import get_settings
from esports_poster_ai.jobs.queue import get_redis
from esports_poster_ai.jobs.store import JobStore

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EsportsPostAI API",
    version="1.0.0",
    description="Generate esports posters via async jobs.",
)

# CORS is an env-driven allowlist rather than a hardcoded "*".
#
# `CORS_ALLOW_ORIGINS=*`  — any origin (dev default; what the reference SPA needs)
# `CORS_ALLOW_ORIGINS=""` — no cross-origin browser access at all (production)
# `CORS_ALLOW_ORIGINS=https://a.gg,https://b.gg` — just those
#
# Production for the Defendr integration is the empty case: the browser talks to
# Defendr's backend, which proxies to this API server-side. Nothing needs a CORS
# grant, so nothing gets one.
_cors_setting = get_settings().cors_allow_origins.strip()
_cors_origins = (
    ["*"] if _cors_setting == "*"
    else [origin.strip() for origin in _cors_setting.split(",") if origin.strip()]
)

if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    if _cors_origins == ["*"]:
        logger.warning(
            "api.cors.wildcard — any origin may call this API from a browser. "
            "Set CORS_ALLOW_ORIGINS before exposing it beyond localhost."
        )
else:
    logger.info("api.cors.disabled — no cross-origin browser access permitted")

# Express must be registered before the classic posters router: that router
# declares GET/POST on "/{job_id}", which would otherwise match "express"
# as a job id.
app.include_router(express_router)
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
