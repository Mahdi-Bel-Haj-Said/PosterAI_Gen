"""
Storage package.

`get_storage()` returns R2Storage when R2 is configured in the environment,
otherwise LocalStorage — so the pipeline runs identically in dev and prod.
`get_keys()` returns the key builder bound to the configured prefix.
"""

from __future__ import annotations

import logging
from typing import Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.storage.base import Storage, StorageError, guess_content_type
from esports_poster_ai.storage.keys import AssetType, StorageKeys
from esports_poster_ai.storage.local import LocalStorage
from esports_poster_ai.storage.r2 import R2Storage

logger = logging.getLogger(__name__)


def _r2_configured(s: Settings) -> bool:
    return bool(
        s.r2_access_key_id and s.r2_secret_access_key and s.r2_endpoint and s.r2_bucket
    )


def get_storage(settings: Optional[Settings] = None) -> Storage:
    """
    Return the active Storage backend.

    R2 when fully configured in `.env`; otherwise a LocalStorage rooted at
    `scratch/storage/` under the project root (dev / tests).
    """
    s = settings or get_settings()
    if _r2_configured(s):
        logger.info("storage.backend", extra={"backend": "r2", "bucket": s.r2_bucket})
        return R2Storage(settings=s)

    local_root = s.project_root / "scratch" / "storage"
    logger.info("storage.backend", extra={"backend": "local", "root": str(local_root)})
    return LocalStorage(root=local_root)


def get_keys(settings: Optional[Settings] = None) -> StorageKeys:
    """Return the key builder bound to the configured R2_KEY_PREFIX."""
    s = settings or get_settings()
    return StorageKeys(prefix=s.r2_key_prefix)


__all__ = [
    "Storage",
    "StorageError",
    "StorageKeys",
    "AssetType",
    "LocalStorage",
    "R2Storage",
    "get_storage",
    "get_keys",
    "guess_content_type",
]
