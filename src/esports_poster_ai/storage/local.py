"""
Local filesystem Storage implementation.

Used for development and tests. Objects are stored as files under a root
directory, with the object key as the relative path. Lets the entire
pipeline run with zero R2 credentials.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from esports_poster_ai.storage.base import guess_content_type

logger = logging.getLogger(__name__)


class LocalStorage:
    """Stores objects as files under `root`. Keys map directly to relative paths."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Resolve and confirm the key stays inside root (defense against
        # a malformed key with '..' segments).
        p = (self.root / key).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"Key escapes storage root: {key!r}")
        return p

    def get_bytes(self, key: str) -> bytes:
        p = self._path(key)
        if not p.is_file():
            raise FileNotFoundError(f"No object at key: {key}")
        return p.read_bytes()

    def put_bytes(
        self, key: str, data: bytes, *, content_type: Optional[str] = None
    ) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        logger.info(
            "storage.local.put",
            extra={"key": key, "bytes": len(data), "content_type": content_type or guess_content_type(key)},
        )

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
        logger.info("storage.local.delete", extra={"key": key})

    def signed_url(self, key: str, *, expires_in: int = 3600) -> str:
        # No signing locally — return a file:// URI to the object.
        return self._path(key).as_uri()

    def list_keys(self, prefix: str) -> List[str]:
        base = self._path(prefix) if prefix else self.root
        search_root = base if base.is_dir() else base.parent
        keys: List[str] = []
        for p in sorted(search_root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(self.root).as_posix()
            if rel.startswith(prefix):
                keys.append(rel)
        return keys


__all__ = ["LocalStorage"]
