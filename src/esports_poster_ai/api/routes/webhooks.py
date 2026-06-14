"""
`/v1/webhook` — a platform manages its outbound webhook (server-to-server push).

A platform registers one callback URL; we POST a signed event there whenever one
of its posters completes or fails, so the platform's backend doesn't have to poll.

All routes require an authenticated platform (a valid API key) — a key carries
the platform identity these settings attach to. The signing secret is shown only
at creation / rotation, exactly like the API key itself.

See `webhooks/` for the delivery engine and `domain/webhook.py` for the models.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import AnyUrl, BaseModel, Field

from esports_poster_ai.api.deps import AuthContext, get_auth_context
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.webhook import (
    DEFAULT_EVENTS,
    WebhookConfig,
    WebhookDelivery,
    WebhookEvent,
)
from esports_poster_ai.webhooks import signing
from esports_poster_ai.webhooks.delivery import deliver_once
from esports_poster_ai.webhooks.store import WebhookConfigStore, WebhookDeliveryStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhook", tags=["webhooks"])


def get_webhook_config_store() -> WebhookConfigStore:
    """FastAPI dependency providing a WebhookConfigStore (overridable in tests)."""
    return WebhookConfigStore()


def get_webhook_delivery_store() -> WebhookDeliveryStore:
    """FastAPI dependency providing a WebhookDeliveryStore (overridable in tests)."""
    return WebhookDeliveryStore()


def _require_platform(auth: AuthContext) -> str:
    """Webhook management needs an authenticated platform (a valid API key)."""
    if not auth.authenticated or not auth.platform_id:
        raise HTTPException(
            status_code=401,
            detail="Webhook management requires an API key (Authorization: Bearer <key>).",
        )
    return auth.platform_id


# ---- schemas ----------------------------------------------------------------


class SetWebhookRequest(BaseModel):
    url: AnyUrl = Field(description="HTTPS callback URL we POST signed events to.")
    events: Optional[List[WebhookEvent]] = Field(
        default=None, description="Events to receive. Defaults to completed + failed."
    )
    enabled: bool = True


class WebhookConfigResponse(BaseModel):
    platform_id: str
    url: str
    events: List[WebhookEvent]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    secret: Optional[str] = Field(
        default=None,
        description="Signing secret — returned ONLY when created or rotated. Save it.",
    )

    @classmethod
    def from_config(cls, cfg: WebhookConfig, *, secret: Optional[str] = None) -> "WebhookConfigResponse":
        return cls(
            platform_id=cfg.platform_id,
            url=cfg.url,
            events=cfg.events,
            enabled=cfg.enabled,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
            secret=secret,
        )


class WebhookDeliveryResponse(BaseModel):
    delivery_id: str
    event: WebhookEvent
    url: str
    status: str
    attempts: int
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None

    @classmethod
    def from_delivery(cls, d: WebhookDelivery) -> "WebhookDeliveryResponse":
        return cls(
            delivery_id=d.delivery_id, event=d.event, url=d.url, status=d.status,
            attempts=d.attempts, last_status_code=d.last_status_code,
            last_error=d.last_error, created_at=d.created_at, delivered_at=d.delivered_at,
        )


class WebhookDeliveryListResponse(BaseModel):
    deliveries: List[WebhookDeliveryResponse]
    count: int


class WebhookTestResponse(BaseModel):
    ok: bool
    status_code: Optional[int] = None
    error: Optional[str] = None


# ---- routes -----------------------------------------------------------------


def _validate_url(url: str) -> None:
    s = get_settings()
    if not signing.is_safe_callback_url(url, allow_insecure=s.webhook_allow_insecure_urls):
        raise HTTPException(
            status_code=422,
            detail=(
                "Callback URL must be https and resolve to a public host "
                "(loopback/private/internal addresses are rejected). Set "
                "WEBHOOK_ALLOW_INSECURE_URLS=true for local testing only."
            ),
        )


@router.put("", response_model=WebhookConfigResponse)
def set_webhook(
    req: SetWebhookRequest,
    auth: AuthContext = Depends(get_auth_context),
    store: WebhookConfigStore = Depends(get_webhook_config_store),
) -> WebhookConfigResponse:
    """
    Create or update this platform's webhook.

    On first creation a signing secret is generated and returned ONCE. Updating
    the url/events keeps the existing secret (rotate it explicitly if needed).
    """
    platform_id = _require_platform(auth)
    url = str(req.url)
    _validate_url(url)
    events = req.events or list(DEFAULT_EVENTS)

    existing = store.get(platform_id)
    if existing is None:
        secret = signing.generate_secret()
        cfg = WebhookConfig(platform_id=platform_id, url=url, secret=secret,
                            events=events, enabled=req.enabled)
        store.upsert(cfg)
        return WebhookConfigResponse.from_config(cfg, secret=secret)  # shown once

    updated = existing.model_copy(update={"url": url, "events": events, "enabled": req.enabled})
    store.upsert(updated)
    return WebhookConfigResponse.from_config(updated)  # secret NOT re-shown


@router.get("", response_model=WebhookConfigResponse)
def get_webhook(
    auth: AuthContext = Depends(get_auth_context),
    store: WebhookConfigStore = Depends(get_webhook_config_store),
) -> WebhookConfigResponse:
    """Return the platform's webhook config (without the secret)."""
    platform_id = _require_platform(auth)
    cfg = store.get(platform_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="No webhook configured.")
    return WebhookConfigResponse.from_config(cfg)


@router.post("/rotate-secret", response_model=WebhookConfigResponse)
def rotate_secret(
    auth: AuthContext = Depends(get_auth_context),
    store: WebhookConfigStore = Depends(get_webhook_config_store),
) -> WebhookConfigResponse:
    """Generate a new signing secret (invalidates the old one). Returned ONCE."""
    platform_id = _require_platform(auth)
    cfg = store.get(platform_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="No webhook configured.")
    secret = signing.generate_secret()
    store.set_fields(platform_id, secret=secret)
    return WebhookConfigResponse.from_config(
        cfg.model_copy(update={"secret": secret}), secret=secret
    )


@router.delete("", status_code=204)
def delete_webhook(
    auth: AuthContext = Depends(get_auth_context),
    store: WebhookConfigStore = Depends(get_webhook_config_store),
) -> Response:
    """Remove the platform's webhook (events stop firing)."""
    platform_id = _require_platform(auth)
    store.delete(platform_id)
    return Response(status_code=204)


@router.post("/test", response_model=WebhookTestResponse)
def test_webhook(
    auth: AuthContext = Depends(get_auth_context),
    store: WebhookConfigStore = Depends(get_webhook_config_store),
) -> WebhookTestResponse:
    """
    Send a synthetic `ping` to the configured URL right now (synchronous, no
    retries) so the platform can confirm its endpoint accepts our signed request.
    """
    platform_id = _require_platform(auth)
    cfg = store.get(platform_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="No webhook configured.")
    payload = {
        "id": "evt_test",
        "event": "ping",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "data": {"message": "EsportsPostAI webhook test"},
    }
    result = deliver_once(cfg.url, cfg.secret, payload)
    return WebhookTestResponse(**result)


@router.get("/deliveries", response_model=WebhookDeliveryListResponse)
def list_deliveries(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter: pending / delivered / failed."),
    auth: AuthContext = Depends(get_auth_context),
    store: WebhookDeliveryStore = Depends(get_webhook_delivery_store),
) -> WebhookDeliveryListResponse:
    """List recent delivery attempts for this platform (audit / debugging)."""
    platform_id = _require_platform(auth)
    deliveries = store.list_for_platform(platform_id, limit=limit, status=status)  # type: ignore[arg-type]
    return WebhookDeliveryListResponse(
        deliveries=[WebhookDeliveryResponse.from_delivery(d) for d in deliveries],
        count=len(deliveries),
    )


@router.post("/deliveries/{delivery_id}/replay", status_code=202)
def replay_delivery(
    delivery_id: str,
    auth: AuthContext = Depends(get_auth_context),
    store: WebhookDeliveryStore = Depends(get_webhook_delivery_store),
) -> dict:
    """Re-enqueue a past delivery (e.g. a dead-lettered one) for another attempt."""
    platform_id = _require_platform(auth)
    delivery = store.get(delivery_id)
    if delivery is None or delivery.platform_id != platform_id:
        raise HTTPException(status_code=404, detail=f"Delivery not found: {delivery_id}")
    from esports_poster_ai.webhooks.delivery import _enqueue_delivery

    _enqueue_delivery(delivery_id)
    return {"delivery_id": delivery_id, "status": "re-enqueued"}
