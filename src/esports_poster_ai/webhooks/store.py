"""
MongoDB-backed stores for webhooks.

`WebhookConfigStore` — one config per platform (`webhook_configs`, `_id =
platform_id`). `WebhookDeliveryStore` — the delivery/retry audit trail
(`webhook_deliveries`, `_id = delivery_id`).

Lazy pymongo import; tests inject a `mongomock` collection. These collections
are created on first write — no migration, and nothing touches the existing
`jobs` / `orgs` / `assets` collections.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.webhook import (
    DeliveryStatus,
    WebhookConfig,
    WebhookDelivery,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _config_to_doc(cfg: WebhookConfig) -> Dict[str, Any]:
    doc = cfg.model_dump()
    doc["_id"] = doc.pop("platform_id")
    return doc


def _config_from_doc(doc: Dict[str, Any]) -> WebhookConfig:
    data = dict(doc)
    data["platform_id"] = data.pop("_id")
    return WebhookConfig.model_validate(data)


class WebhookConfigStore:
    """Repository over the `webhook_configs` collection (one row per platform)."""

    def __init__(self, *, settings: Optional[Settings] = None, collection: Any = None) -> None:
        if collection is not None:
            self._col = collection
            return
        s = settings or get_settings()
        from pymongo import MongoClient  # lazy

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db]["webhook_configs"]

    def get(self, platform_id: str) -> Optional[WebhookConfig]:
        doc = self._col.find_one({"_id": platform_id})
        return _config_from_doc(doc) if doc else None

    def upsert(self, cfg: WebhookConfig) -> WebhookConfig:
        cfg = cfg.model_copy(update={"updated_at": _now()})
        self._col.replace_one({"_id": cfg.platform_id}, _config_to_doc(cfg), upsert=True)
        logger.info("webhook.config_set", extra={"platform_id": cfg.platform_id})
        return cfg

    def set_fields(self, platform_id: str, **fields: Any) -> Optional[WebhookConfig]:
        fields["updated_at"] = _now()
        res = self._col.update_one({"_id": platform_id}, {"$set": fields})
        if res.matched_count == 0:
            return None
        return self.get(platform_id)

    def delete(self, platform_id: str) -> bool:
        return self._col.delete_one({"_id": platform_id}).deleted_count > 0


def _delivery_to_doc(d: WebhookDelivery) -> Dict[str, Any]:
    doc = d.model_dump()
    doc["_id"] = doc.pop("delivery_id")
    return doc


def _delivery_from_doc(doc: Dict[str, Any]) -> WebhookDelivery:
    data = dict(doc)
    data["delivery_id"] = data.pop("_id")
    return WebhookDelivery.model_validate(data)


class WebhookDeliveryStore:
    """Repository over the `webhook_deliveries` collection (the retry/audit trail)."""

    def __init__(self, *, settings: Optional[Settings] = None, collection: Any = None) -> None:
        if collection is not None:
            self._col = collection
            return
        s = settings or get_settings()
        from pymongo import MongoClient  # lazy

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db]["webhook_deliveries"]

    def create(self, delivery: WebhookDelivery) -> WebhookDelivery:
        self._col.insert_one(_delivery_to_doc(delivery))
        return delivery

    def get(self, delivery_id: str) -> Optional[WebhookDelivery]:
        doc = self._col.find_one({"_id": delivery_id})
        return _delivery_from_doc(doc) if doc else None

    def record_attempt(
        self,
        delivery_id: str,
        *,
        status: DeliveryStatus,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        changes: Dict[str, Any] = {
            "status": status,
            "last_status_code": status_code,
            "last_error": error,
            "updated_at": _now(),
        }
        if status == "delivered":
            changes["delivered_at"] = _now()
        self._col.update_one(
            {"_id": delivery_id},
            {"$set": changes, "$inc": {"attempts": 1}},
        )

    def list_for_platform(
        self, platform_id: str, *, limit: int = 50, status: Optional[DeliveryStatus] = None
    ) -> List[WebhookDelivery]:
        query: Dict[str, Any] = {"platform_id": platform_id}
        if status is not None:
            query["status"] = status
        cursor = self._col.find(query).sort("created_at", -1).limit(limit)
        return [_delivery_from_doc(d) for d in cursor]


__all__ = ["WebhookConfigStore", "WebhookDeliveryStore"]
