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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from esports_poster_ai.billing import SubscriptionTier
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.org import Org, OrgRateLimits
from esports_poster_ai.platforms import economics_for

logger = logging.getLogger(__name__)

# Length of a monthly grant window.
_GRANT_PERIOD = timedelta(days=30)


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
        effective_tier = tier or Org.model_fields["tier"].default
        org = Org(
            org_id=org_id,
            platform_id=platform_id,
            name=name,
            tier=effective_tier,
            limits=limits or OrgRateLimits(),
            metadata=metadata or {},
            # Seed the first monthly Red Coins grant on creation.
            coins_balance=economics_for(platform_id).grant_for(effective_tier),
            coins_period_start=_now(),
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

    def list_all(self, *, limit: int = 1000) -> List[Org]:
        """Every org across platforms — used by the admin usage rollup."""
        return [_from_doc(d) for d in self._col.find().limit(limit)]

    def list_for_platform(self, platform_id: str, *, limit: int = 200) -> List[Org]:
        cursor = (
            self._col.find({"platform_id": platform_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [_from_doc(d) for d in cursor]

    # ---------------------------------------------------------------- coins
    def ensure_monthly_grant(self, platform_id: str, org_id: str) -> Optional[Org]:
        """
        Credit any due monthly Red Coins grant(s) and return the fresh org.

        Idempotent and safe to call on every balance read / charge:
          * `coins_period_start is None`  -> first-ever grant (covers legacy orgs
            created before coins existed): credit one grant, start the window now.
          * window elapsed                -> credit one grant per whole period
            that has passed and advance the window. Unused coins roll over.
        """
        org = self.get(platform_id, org_id)
        if org is None:
            return None

        grant = economics_for(platform_id).grant_for(org.tier)
        now = _now()

        if org.coins_period_start is None:
            self._col.update_one(
                {"_id": _doc_id(platform_id, org_id)},
                {"$set": {"coins_period_start": now, "updated_at": now},
                 "$inc": {"coins_balance": grant}},
            )
            return self.get(platform_id, org_id)

        elapsed = now - org.coins_period_start
        periods = int(elapsed // _GRANT_PERIOD)
        if periods >= 1 and grant > 0:
            self._col.update_one(
                {"_id": _doc_id(platform_id, org_id)},
                {"$set": {"coins_period_start": org.coins_period_start + _GRANT_PERIOD * periods,
                          "updated_at": now},
                 "$inc": {"coins_balance": grant * periods}},
            )
            return self.get(platform_id, org_id)
        return org

    def charge_coins(self, platform_id: str, org_id: str, tokens: int) -> Tuple[bool, int]:
        """
        Atomically deduct `tokens` if the balance covers it.

        Returns (charged, balance_after). `charged` is False (no change) when the
        balance is insufficient — the caller decides what to do.
        """
        tokens = max(0, int(tokens))
        if tokens == 0:
            org = self.get(platform_id, org_id)
            return True, (org.coins_balance if org else 0)
        result = self._col.update_one(
            {"_id": _doc_id(platform_id, org_id), "coins_balance": {"$gte": tokens}},
            {"$inc": {"coins_balance": -tokens, "coins_spent": tokens}, "$set": {"updated_at": _now()}},
        )
        org = self.get(platform_id, org_id)
        balance = org.coins_balance if org else 0
        return (result.modified_count == 1), balance

    def subscribe(self, platform_id: str, org_id: str, tier: SubscriptionTier) -> Org:
        """
        Switch the org to `tier` and start a fresh billing cycle: credit that
        tier's monthly grant and reset the grant window to now. Creates the org
        if it doesn't exist yet (which grants the tier amount once on creation).
        """
        grant = economics_for(platform_id).grant_for(tier)
        now = _now()
        res = self._col.update_one(
            {"_id": _doc_id(platform_id, org_id)},
            {"$set": {"tier": tier, "coins_period_start": now, "updated_at": now},
             "$inc": {"coins_balance": grant}},
        )
        if res.matched_count == 0:
            return self.register(platform_id=platform_id, org_id=org_id, tier=tier)
        return self.get(platform_id, org_id)

    def add_coins(self, platform_id: str, org_id: str, tokens: int) -> Optional[int]:
        """Credit `tokens` (a top-up purchase). Returns the new balance, or None."""
        tokens = max(0, int(tokens))
        result = self._col.update_one(
            {"_id": _doc_id(platform_id, org_id)},
            {"$inc": {"coins_balance": tokens}, "$set": {"updated_at": _now()}},
        )
        if result.matched_count == 0:
            return None
        org = self.get(platform_id, org_id)
        return org.coins_balance if org else None

    # ---------------------------------------------------------------- delete
    def delete(self, platform_id: str, org_id: str) -> bool:
        """Remove the org record. Returns True if a row was deleted."""
        result = self._col.delete_one({"_id": _doc_id(platform_id, org_id)})
        return result.deleted_count > 0


__all__ = ["OrgStore"]
