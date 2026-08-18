"""
BankStore — the R2 view of the pre-generated background bank.

Layout (top-level folder, one sub-folder per combo):

    {bg_bank_prefix}/{energy}_{vibe}/{uuid}.png
    {bg_bank_prefix}/{energy}_{vibe}/.keep      <- folder placeholder, never served

"How many are ready in a combo" is simply the count of `.png` objects under the
combo prefix — no separate database, which is fine at the current (~1000-user)
scale. The bank is served with **delete-on-serve**: an image handed to a user is
removed so it can never be served twice.

Race note: without an atomic-claim store (deliberately out of scope until
10-100x scale), two concurrent servers *could* pick the same object in the
gap between read and delete. We minimise it by picking at random (spreading
concurrent picks across the pool) and by skipping objects that vanish under us.
"""

from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Dict, List, Optional

from esports_poster_ai.bank.combos import Combo, all_combos
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.storage import get_storage
from esports_poster_ai.storage.base import Storage

logger = logging.getLogger(__name__)

# Zero-byte placeholder that makes an otherwise-empty combo folder visible in the
# R2 console. It is never counted and never served.
_KEEP_MARKER = ".keep"


@dataclass(frozen=True)
class BankServe:
    """Result of a successful serve-and-delete: the image + what's left behind."""

    image: bytes
    key: str
    remaining: int  # count of ready images in the combo AFTER this serve


class BankStore:
    """Counts, serves (delete-on-serve), uploads, and seeds the R2 bank."""

    def __init__(
        self,
        storage: Optional[Storage] = None,
        *,
        settings: Optional[Settings] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._storage = storage or get_storage(self._settings)

    # ------------------------------------------------------------------ keys
    @property
    def prefix(self) -> str:
        return self._settings.bg_bank_prefix.strip().strip("/")

    def combo_prefix(self, combo: Combo) -> str:
        return f"{self.prefix}/{combo.slug}/"

    def _object_key(self, combo: Combo, name: str) -> str:
        return f"{self.combo_prefix(combo)}{name}"

    def _keep_key(self, combo: Combo) -> str:
        return self._object_key(combo, _KEEP_MARKER)

    # ---------------------------------------------------------------- counts
    def _ready_keys(self, combo: Combo) -> List[str]:
        """The servable `.png` object keys under a combo (excludes `.keep`)."""
        return [
            k
            for k in self._storage.list_keys(self.combo_prefix(combo))
            if k.lower().endswith(".png")
        ]

    def count(self, combo: Combo) -> int:
        return len(self._ready_keys(combo))

    def counts(self) -> Dict[str, int]:
        """Ready count per combo slug, for every combo (missing → 0)."""
        return {combo.slug: self.count(combo) for combo in all_combos()}

    # --------------------------------------------------------------- writing
    def upload(self, combo: Combo, data: bytes) -> str:
        """Store one generated background under a fresh uuid; return its key."""
        key = self._object_key(combo, f"{uuid.uuid4().hex}.png")
        self._storage.put_bytes(key, data, content_type="image/png")
        logger.info("bank.upload", extra={"combo": combo.slug, "key": key, "bytes": len(data)})
        return key

    # --------------------------------------------------------------- serving
    def serve_and_delete(self, combo: Combo) -> Optional[BankServe]:
        """
        Pick a random ready background, delete it, and return it.

        Returns None when the combo is empty (caller should fall back to live
        generation). Objects that vanish mid-serve (a concurrent serve won the
        race) are skipped rather than erroring.
        """
        candidates = self._ready_keys(combo)
        random.shuffle(candidates)
        for i, key in enumerate(candidates):
            try:
                data = self._storage.get_bytes(key)
            except FileNotFoundError:
                continue  # raced away — try the next candidate
            self._storage.delete(key)
            remaining = len(candidates) - i - 1
            logger.info(
                "bank.served", extra={"combo": combo.slug, "key": key, "remaining": remaining}
            )
            return BankServe(image=data, key=key, remaining=remaining)
        return None

    # --------------------------------------------------------------- seeding
    def ensure_folders(self) -> List[str]:
        """
        Create the 24 combo folders by writing a `.keep` placeholder in each
        (idempotent). Returns the combo prefixes that now exist. R2 has no real
        folders — these markers just make the structure visible in the console.
        """
        created: List[str] = []
        for combo in all_combos():
            keep = self._keep_key(combo)
            if not self._storage.exists(keep):
                self._storage.put_bytes(keep, b"", content_type="text/plain")
            created.append(self.combo_prefix(combo))
        logger.info("bank.folders_ensured", extra={"count": len(created)})
        return created


def combo_of_key(key: str, *, prefix: str) -> Optional[str]:
    """Extract the combo slug from a full bank object key, if it is one."""
    root = prefix.strip().strip("/") + "/"
    if not key.startswith(root):
        return None
    rest = key[len(root):]
    parts = PurePosixPath(rest).parts
    return parts[0] if parts else None


__all__ = ["BankStore", "BankServe", "combo_of_key"]
