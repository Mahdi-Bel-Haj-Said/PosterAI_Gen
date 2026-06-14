"""
Asset domain model — an uploaded image (logo, player photo, sponsor logo,
tournament logo) the org can reuse across posters.

The image bytes live in R2 at the key the StorageKeys builder produced; this
document holds the metadata that lets us list, look up, and delete it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from esports_poster_ai.storage.keys import AssetType


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Asset(BaseModel):
    """Metadata for one uploaded asset; the bytes live in R2 at `storage_key`."""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    asset_id: str = Field(default_factory=lambda: uuid4().hex)
    platform_id: Optional[str] = None   # integrating platform (None for CLI/dev)
    org_id: str
    asset_type: AssetType
    filename: str = ""                  # original upload filename
    storage_key: str                    # R2 key
    content_type: str                   # MIME type
    size_bytes: int
    name: Optional[str] = None          # optional human label
    team: Optional[str] = None          # owning team (team-logos / player-images)
    created_at: datetime = Field(default_factory=_now)


__all__ = ["Asset", "AssetType"]
