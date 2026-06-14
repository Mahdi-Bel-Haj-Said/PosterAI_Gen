"""
Webhook delivery — build, enqueue, and deliver (with retries) one event.

Flow:
  worker finishes a job
    -> emit_job_event(job, "poster.completed")     # safe no-op unless enabled
         -> create a pending WebhookDelivery row
         -> enqueue deliver_webhook(delivery_id) on the `epai-webhooks` queue
  webhook worker
    -> deliver_webhook(delivery_id)
         -> sign + POST to the platform's url
         -> 2xx: mark delivered
         -> else: record attempt; re-enqueue with backoff, or dead-letter

The poster pipeline never blocks on delivery (separate queue/worker), and
`emit_job_event` is a no-op when `WEBHOOKS_ENABLED` is false or the job has no
platform — so with the flag off the existing system is completely unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.webhook import WebhookConfig, WebhookDelivery, WebhookEvent
from esports_poster_ai.webhooks import signing
from esports_poster_ai.webhooks.store import WebhookConfigStore, WebhookDeliveryStore

logger = logging.getLogger(__name__)

WEBHOOK_QUEUE = "epai-webhooks"
DELIVER_HANDLER = "esports_poster_ai.webhooks.delivery.deliver_webhook"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- payloads
def build_event_payload(job: Any, event: WebhookEvent) -> Dict[str, Any]:
    """Build the JSON body for a job event. Signs a fresh URL for completed posters."""
    signed_url = None
    storage_key = getattr(job, "storage_key", None)
    if event == "poster.completed" and storage_key:
        try:
            from esports_poster_ai.storage import get_storage

            signed_url = get_storage().signed_url(storage_key)
        except Exception:  # noqa: BLE001 — a missing signer must not block delivery
            signed_url = None
    return {
        "event": event,
        "created_at": _now().isoformat(),
        "data": {
            "job_id": job.job_id,
            "org_id": job.org_id,
            "tournament_id": job.tournament_id,
            "status": job.status,
            "storage_key": storage_key,
            "signed_url": signed_url,
            "caption": getattr(job, "caption", None),
            "error": getattr(job, "error", None),
        },
    }


# ---------------------------------------------------------------- enqueue
def _enqueue_delivery(
    delivery_id: str, *, delay_seconds: float = 0.0, settings: Optional[Settings] = None
) -> None:
    """Push a delivery onto the webhooks queue. Isolated so tests can monkeypatch it."""
    from rq import Queue  # lazy

    from esports_poster_ai.jobs.queue import get_redis

    q = Queue(WEBHOOK_QUEUE, connection=get_redis(settings))
    if delay_seconds and delay_seconds > 0:
        q.enqueue_in(timedelta(seconds=delay_seconds), DELIVER_HANDLER, delivery_id)
    else:
        q.enqueue(DELIVER_HANDLER, delivery_id)


def emit_job_event(
    job: Any,
    event: WebhookEvent,
    *,
    settings: Optional[Settings] = None,
    config_store: Optional[WebhookConfigStore] = None,
    delivery_store: Optional[WebhookDeliveryStore] = None,
) -> Optional[str]:
    """
    Create + enqueue a delivery for a job event. No-op (returns None) when
    webhooks are disabled, the job has no platform, or the platform has no
    enabled subscription for this event. Never raises for an expected miss.
    """
    s = settings or get_settings()
    if not s.webhooks_enabled:
        return None
    platform_id = getattr(job, "platform_id", None)
    if not platform_id:
        return None

    cfgs = config_store or WebhookConfigStore(settings=s)
    cfg = cfgs.get(platform_id)
    if cfg is None or not cfg.enabled or event not in cfg.events:
        return None

    payload = build_event_payload(job, event)
    delivery = WebhookDelivery(
        platform_id=platform_id, event=event, url=cfg.url, payload=payload
    )
    (delivery_store or WebhookDeliveryStore(settings=s)).create(delivery)
    _enqueue_delivery(delivery.delivery_id, settings=s)
    logger.info(
        "webhook.enqueued",
        extra={"delivery_id": delivery.delivery_id, "platform_id": platform_id, "event": event},
    )
    return delivery.delivery_id


# ---------------------------------------------------------------- deliver
def _http_post(url: str, body: bytes, headers: Dict[str, str], timeout: float) -> int:
    """POST raw bytes and return the status code. Isolated for test monkeypatching."""
    import httpx  # lazy

    resp = httpx.post(url, content=body, headers=headers, timeout=timeout)
    return resp.status_code


def deliver_once(
    url: str, secret: str, payload: Dict[str, Any], *, settings: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Sign + POST a payload a single time (no retries, no queue, no Redis).

    Used by the `POST /v1/webhook/test` button so a client gets immediate
    feedback on whether their endpoint accepts our signed request. Returns
    `{ok, status_code, error}`.
    """
    import json

    s = settings or get_settings()
    body = json.dumps(payload).encode("utf-8")
    ts = int(_now().timestamp())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EsportsPostAI-Webhooks/1.0",
        "X-EPAI-Event": str(payload.get("event", "ping")),
        "X-EPAI-Signature": signing.signature_header(secret, ts, body),
    }
    try:
        code = _http_post(url, body, headers, s.webhook_timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status_code": None, "error": f"{type(exc).__name__}: {exc}"}
    ok = 200 <= code < 300
    return {"ok": ok, "status_code": code, "error": None if ok else f"HTTP {code}"}


def deliver_webhook(delivery_id: str, *, settings: Optional[Settings] = None) -> bool:
    """
    Deliver one webhook (the RQ handler). Returns True on success.

    On a non-2xx / network error it records the attempt and re-enqueues with
    exponential backoff until `webhook_max_attempts`, then dead-letters
    (status stays `failed`). Never raises — the webhook worker stays drained.
    """
    import json

    s = settings or get_settings()
    deliveries = WebhookDeliveryStore(settings=s)
    delivery = deliveries.get(delivery_id)
    if delivery is None:
        logger.error("webhook.delivery_missing", extra={"delivery_id": delivery_id})
        return False
    if delivery.status == "delivered":
        return True

    cfg = WebhookConfigStore(settings=s).get(delivery.platform_id)
    if cfg is None or not cfg.enabled:
        deliveries.record_attempt(delivery_id, status="failed", error="no active webhook config")
        return False

    body = json.dumps({"id": delivery.delivery_id, **delivery.payload}).encode("utf-8")
    ts = int(_now().timestamp())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EsportsPostAI-Webhooks/1.0",
        "X-EPAI-Event": delivery.event,
        "X-EPAI-Delivery": delivery.delivery_id,
        "X-EPAI-Signature": signing.signature_header(cfg.secret, ts, body),
    }

    attempt_no = delivery.attempts + 1
    try:
        code = _http_post(cfg.url, body, headers, s.webhook_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 — network failures are expected; retry
        code = None
        err = f"{type(exc).__name__}: {exc}"
    else:
        err = None if 200 <= code < 300 else f"HTTP {code}"

    if code is not None and 200 <= code < 300:
        deliveries.record_attempt(delivery_id, status="delivered", status_code=code)
        logger.info("webhook.delivered", extra={"delivery_id": delivery_id, "attempt": attempt_no})
        return True

    # Failure path: retry with backoff, or dead-letter.
    if attempt_no < s.webhook_max_attempts:
        deliveries.record_attempt(delivery_id, status="pending", status_code=code, error=err)
        delay = s.webhook_backoff_base_seconds * (2 ** (attempt_no - 1))
        _enqueue_delivery(delivery_id, delay_seconds=delay, settings=s)
        logger.warning(
            "webhook.retry",
            extra={"delivery_id": delivery_id, "attempt": attempt_no, "in_seconds": delay, "error": err},
        )
    else:
        deliveries.record_attempt(delivery_id, status="failed", status_code=code, error=err)
        logger.error(
            "webhook.dead_letter",
            extra={"delivery_id": delivery_id, "attempts": attempt_no, "error": err},
        )
    return False


__all__ = [
    "WEBHOOK_QUEUE",
    "build_event_payload",
    "emit_job_event",
    "deliver_webhook",
    "deliver_once",
]
