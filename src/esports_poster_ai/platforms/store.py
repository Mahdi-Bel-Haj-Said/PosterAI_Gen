"""
PlatformStore — MongoDB registry of client (platform) commercial metadata.

Stored in the `platforms` collection, `_id` = the platform id. The dev / no-key
bucket (platform_id None) is stored under the sentinel `__none__` so it can hold
a service type too. Records are optional: a client with no record just shows the
default service type until the provider sets it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.platform import (
    CLIENT_EDITABLE_BLOCKS,
    Platform,
    PlatformEconomics,
    ServiceType,
)

logger = logging.getLogger(__name__)

_NONE_KEY = "__none__"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key(platform_id: Optional[str]) -> str:
    return platform_id if platform_id else _NONE_KEY


class PlatformStore:
    def __init__(self, *, settings: Optional[Settings] = None, collection: Any = None) -> None:
        if collection is not None:
            self._col = collection
            return
        s = settings or get_settings()
        from pymongo import MongoClient  # lazy

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db]["platforms"]

    def get(self, platform_id: Optional[str]) -> Optional[Platform]:
        doc = self._col.find_one({"_id": _key(platform_id)})
        if not doc:
            return None
        data = dict(doc)
        data.pop("_id", None)
        data.setdefault("platform_id", platform_id or "")
        return Platform.model_validate(data)

    def list_all(self, *, limit: int = 1000) -> List[Platform]:
        out: List[Platform] = []
        for doc in self._col.find().limit(limit):
            data = dict(doc)
            _id = data.pop("_id", None)
            data.setdefault("platform_id", "" if _id == _NONE_KEY else (_id or ""))
            try:
                out.append(Platform.model_validate(data))
            except Exception:  # noqa: BLE001 — skip malformed rows
                continue
        return out

    def upsert(
        self,
        platform_id: Optional[str],
        *,
        name: Optional[str] = None,
        service_type: Optional[ServiceType] = None,
        monthly_fee_usd: Optional[float] = None,
        notes: Optional[str] = None,
        economics: Optional[Dict[str, Any]] = None,
    ) -> Platform:
        """Create or patch a platform's commercial metadata + economics."""
        changes: Dict[str, Any] = {"updated_at": _now(), "platform_id": platform_id or ""}
        if name is not None:
            changes["name"] = name
        if service_type is not None:
            changes["service_type"] = service_type
        if monthly_fee_usd is not None:
            changes["monthly_fee_usd"] = float(monthly_fee_usd)
        if notes is not None:
            changes["notes"] = notes
        if economics is not None:
            # Merge onto the existing config so a partial update (just one field)
            # doesn't wipe the rest; validate through the model to clamp/coerce.
            existing = self.get(platform_id)
            base = existing.economics.model_dump() if existing else PlatformEconomics().model_dump()
            base.update({k: v for k, v in economics.items() if v is not None})
            changes["economics"] = PlatformEconomics.model_validate(base).model_dump()
        self._col.update_one(
            {"_id": _key(platform_id)},
            {"$set": changes, "$setOnInsert": {"created_at": _now()}},
            upsert=True,
        )
        logger.info("platform.upsert", extra={"platform_id": platform_id, "service_type": service_type})
        return self.get(platform_id)

    def patch_config(self, platform_id: Optional[str], patch: Dict[str, Any]) -> Platform:
        """
        Deep-merge a partial CLIENT-OWNED config patch (the self-serve surface).

        Only the blocks in CLIENT_EDITABLE_BLOCKS are touched — commercial fields
        (service_type, monthly_fee_usd) are never changed here, so a client can't
        edit their own deal terms. Nested blocks merge field-by-field; `tiers`
        merges per tier id. The result is validated through the Platform model.
        """
        existing = self.get(platform_id)
        base = (existing.model_dump() if existing
                else Platform(platform_id=platform_id or "").model_dump())

        for block in CLIENT_EDITABLE_BLOCKS:
            if block not in patch or not isinstance(patch[block], dict):
                continue
            if block == "tiers":
                base.setdefault("tiers", {})
                for tid, tv in patch["tiers"].items():
                    if isinstance(tv, dict):
                        cur = dict(base["tiers"].get(tid) or {})
                        cur.update({k: v for k, v in tv.items() if v is not None})
                        base["tiers"][tid] = cur
            else:
                cur = dict(base.get(block) or {})
                cur.update({k: v for k, v in patch[block].items() if v is not None})
                base[block] = cur

        base["platform_id"] = platform_id or ""
        base["updated_at"] = _now()
        validated = Platform.model_validate(base)
        doc = validated.model_dump()
        doc["_id"] = _key(platform_id)
        self._col.replace_one({"_id": _key(platform_id)}, doc, upsert=True)
        logger.info("platform.patch_config", extra={"platform_id": platform_id, "blocks": list(patch.keys())})
        return validated


__all__ = ["PlatformStore"]
