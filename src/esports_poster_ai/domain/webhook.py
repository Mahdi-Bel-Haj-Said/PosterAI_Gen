"""
Webhook domain models.

`WebhookConfig` is a platform's callback registration (one per platform): where
to POST events, the signing secret, and which events it wants. `WebhookDelivery`
is one attempted (and retried) delivery of one event — the audit + retry trail.

Both are persisted by `webhooks.store`. Nothing here imports the pipeline, so
this module is safe to load regardless of the `WEBHOOKS_ENABLED` flag.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# The events a platform can subscribe to. `ping` is the synthetic test event.
WebhookEvent = Literal["poster.completed", "poster.failed", "ping"]

DeliveryStatus = Literal["pending", "delivered", "failed"]

# Default subscription when a platform registers without naming events.
DEFAULT_EVENTS: List[WebhookEvent] = ["poster.completed", "poster.failed"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WebhookConfig(BaseModel):
    """A platform's webhook registration. The `secret` is never returned after creation."""

    model_config = ConfigDict(extra="ignore")

    platform_id: str
    url: str
    secret: str                       # HMAC signing secret (shown to the client once)
    events: List[WebhookEvent] = Field(default_factory=lambda: list(DEFAULT_EVENTS))
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class WebhookDelivery(BaseModel):
    """One delivery of one event to a platform's URL — created pending, then retried."""

    model_config = ConfigDict(extra="ignore")

    delivery_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    platform_id: str
    event: WebhookEvent
    url: str
    payload: Dict[str, Any]
    status: DeliveryStatus = "pending"
    attempts: int = 0
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    delivered_at: Optional[datetime] = None


__all__ = [
    "WebhookEvent",
    "DeliveryStatus",
    "DEFAULT_EVENTS",
    "WebhookConfig",
    "WebhookDelivery",
]
