"""
AssetStore — MongoDB-backed repository for asset metadata.

Bytes live in R2 (the `Storage` layer); this store holds the metadata that
lets the API list, retrieve, and delete uploaded assets. Same pattern as
`JobStore`: lazy pymongo import, injectable collection for tests.
"""

from __future__ import annotations

import logging
import re as _re
from typing import Any, Dict, List, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.asset import Asset
from esports_poster_ai.storage.keys import AssetType

logger = logging.getLogger(__name__)


def _to_doc(asset: Asset) -> Dict[str, Any]:
    """Asset -> Mongo document (asset_id becomes _id)."""
    doc = asset.model_dump()
    doc["_id"] = doc.pop("asset_id")
    return doc


def _from_doc(doc: Dict[str, Any]) -> Asset:
    """Mongo document -> Asset (_id becomes asset_id)."""
    data = dict(doc)
    data["asset_id"] = data.pop("_id")
    return Asset.model_validate(data)


class AssetStore:
    """Repository over the `assets` collection in MongoDB."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        collection: Any = None,
    ) -> None:
        if collection is not None:
            self._col = collection
            return

        s = settings or get_settings()
        from pymongo import MongoClient  # lazy

        client: Any = MongoClient(s.mongodb_url, tz_aware=True)
        self._col = client[s.mongodb_db]["assets"]

    # ---------------------------------------------------------------- create
    def create(
        self,
        *,
        org_id: str,
        asset_type: AssetType,
        asset_id: str,
        filename: str,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        name: Optional[str] = None,
        team: Optional[str] = None,
    ) -> Asset:
        asset = Asset(
            asset_id=asset_id,
            org_id=org_id,
            asset_type=asset_type,
            filename=filename,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
            name=name,
            team=team,
        )
        self._col.insert_one(_to_doc(asset))
        logger.info(
            "asset.created",
            extra={"asset_id": asset.asset_id, "asset_type": str(asset_type)},
        )
        return asset

    # ---------------------------------------------------------------- read
    def get(self, asset_id: str) -> Optional[Asset]:
        doc = self._col.find_one({"_id": asset_id})
        return _from_doc(doc) if doc else None

    def list_for_org(
        self,
        org_id: str,
        *,
        asset_type: Optional[AssetType] = None,
        team: Optional[str] = None,
        limit: int = 50,
    ) -> List[Asset]:
        query: Dict[str, Any] = {"org_id": org_id}
        if asset_type is not None:
            query["asset_type"] = (
                asset_type.value if hasattr(asset_type, "value") else str(asset_type)
            )
        if team is not None:
            # Case-insensitive exact match so "GNG" and "gng" are the same team.
            query["team"] = {"$regex": f"^{_re.escape(team)}$", "$options": "i"}
        cursor = self._col.find(query).sort("created_at", -1).limit(limit)
        return [_from_doc(d) for d in cursor]

    # ---------------------------------------------------------------- delete
    def delete(self, asset_id: str) -> bool:
        """Remove the metadata row. Returns True if a row was deleted."""
        result = self._col.delete_one({"_id": asset_id})
        deleted = result.deleted_count > 0
        if deleted:
            logger.info("asset.deleted", extra={"asset_id": asset_id})
        return deleted


__all__ = ["AssetStore"]
