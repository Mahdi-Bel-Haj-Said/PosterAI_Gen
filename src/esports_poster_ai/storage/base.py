"""
Storage abstraction.

A `Storage` is a flat key -> bytes blob store. It knows nothing about the
key scheme — `storage.keys.StorageKeys` owns that. This keeps the pipeline
identical whether it runs against the local filesystem (dev / tests) or
Cloudflare R2 (production).
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import List, Optional, Protocol, runtime_checkable


class StorageError(RuntimeError):
    """Raised for storage-layer failures that are not a missing key."""


_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".json": "application/json",
}


def guess_content_type(key: str) -> str:
    """Best-effort MIME type from a key's extension."""
    suffix = PurePosixPath(key).suffix.lower()
    return _CONTENT_TYPES.get(suffix, "application/octet-stream")


@runtime_checkable
class Storage(Protocol):
    """Minimal object-storage interface. Implementations: LocalStorage, R2Storage."""

    def get_bytes(self, key: str) -> bytes:
        """Return the object's bytes. Raises FileNotFoundError if absent."""
        ...

    def put_bytes(
        self, key: str, data: bytes, *, content_type: Optional[str] = None
    ) -> None:
        """Write bytes at `key`, creating/overwriting. Content type is guessed if omitted."""
        ...

    def exists(self, key: str) -> bool:
        """True if an object exists at `key`."""
        ...

    def delete(self, key: str) -> None:
        """Delete the object at `key`. A no-op if it does not exist."""
        ...

    def signed_url(self, key: str, *, expires_in: int = 3600) -> str:
        """Return a time-limited URL for reading the object."""
        ...

    def list_keys(self, prefix: str) -> List[str]:
        """Return all keys under `prefix` (used for poster history listings)."""
        ...


__all__ = ["Storage", "StorageError", "guess_content_type"]
