"""
OrgStore — MongoDB-backed registry of orgs, scoped under a platform.

Documents live in the `orgs` collection, keyed by the composite *(platform_id,
org_id)* so the same `org_id` can exist under two different platforms. The
`_id` is the composite string `"{platform_id}:{org_id}"`; callers always pass
both ids, never the raw `_id`.

`pymongo` is imported lazily; tests inject a `mongomock` collection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from esports_poster_ai.billing import SubscriptionTier
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.org import Org, OrgRateLimits

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _doc_id(platform_id: str, org_id: str) -> str:
    return f"{platform_id}:{org_id}"


def _to_doc(org: Org) -> Dict[str, Any]:
    doc = org.model_dump()
    doc["_id"] = _doc_id(org.platform_id, org.org_id)
    return doc


def _from_doc(doc: Dict[str, Any]) -> Org:
    data = dict(doc)
    data.pop("_id", None)
    return Org.model_validate(data)


class OrgStore:
    """Repository over the `orgs` collection in MongoDB."""

    def __init__(
        self, *, settings: Optional[Settings] = None, collection: Any = None
    ) -> None:
        if collection is not None:
            self._col = collection
            return
        s = settings or get_settings()
        from pymongo import MongoClient  # lazy

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db]["orgs"]

    # ---------------------------------------------------------------- write
    def register(
        self,
        *,
        platform_id: str,
        org_id: str,
        name: Optional[str] = None,
        tier: Optional[SubscriptionTier] = None,
        limits: Optional[OrgRateLimits] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Org:
        """
        Create the org if absent, or return the existing one (idempotent).

        Registration never silently overwrites an existing org's settings —
        use `update()` for that. This keeps a re-registration call safe.
        """
        existing = self.get(platform_id, org_id)
        if existing is not None:
            return existing
        org = Org(
            org_id=org_id,
            platform_id=platform_id,
            name=name,
            tier=tier or Org.model_fields["tier"].default,
            limits=limits or OrgRateLimits(),
            metadata=metadata or {},
        )
        self._col.insert_one(_to_doc(org))
        logger.info("org.registered", extra={"platform_id": platform_id, "org_id": org_id})
        return org

    def update(
        self,
        platform_id: str,
        org_id: str,
        *,
        name: Optional[str] = None,
        tier: Optional[SubscriptionTier] = None,
        limits: Optional[OrgRateLimits] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Org]:
        """Patch mutable fields. Returns the updated org, or None if it's absent."""
        changes: Dict[str, Any] = {"updated_at": _now()}
        if name is not None:
            changes["name"] = name
        if tier is not None:
            changes["tier"] = tier
        if limits is not None:
            changes["limits"] = limits.model_dump()
        if metadata is not None:
            changes["metadata"] = metadata
        result = self._col.update_one(
            {"_id": _doc_id(platform_id, org_id)}, {"$set": changes}
        )
        if result.matched_count == 0:
            return None
        return self.get(platform_id, org_id)

    def ensure(self, platform_id: str, org_id: str) -> Org:
        """Register-on-first-use helper (used by dev-mode convenience paths)."""
        return self.register(platform_id=platform_id, org_id=org_id)

    # ---------------------------------------------------------------- read
    def get(self, platform_id: str, org_id: str) -> Optional[Org]:
        doc = self._col.find_one({"_id": _doc_id(platform_id, org_id)})
        return _from_doc(doc) if doc else None

    def exists(self, platform_id: str, org_id: str) -> bool:
        return self._col.find_one(
            {"_id": _doc_id(platform_id, org_id)}, {"_id": 1}
        ) is not None

    def list_for_platform(self, platform_id: str, *, limit: int = 200) -> List[Org]:
        cursor = (
            self._col.find({"platform_id": platform_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [_from_doc(d) for d in cursor]

    # ---------------------------------------------------------------- delete
    def delete(self, platform_id: str, org_id: str) -> bool:
        """Remove the org record. Returns True if a row was deleted."""
        result = self._col.delete_one({"_id": _doc_id(platform_id, org_id)})
        return result.deleted_count > 0


__all__ = ["OrgStore"]
