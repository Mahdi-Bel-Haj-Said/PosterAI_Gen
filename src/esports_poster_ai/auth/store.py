"""
ApiKeyStore — MongoDB-backed repository for API keys.

The plaintext key is returned ONCE from `issue()`. The DB never stores it —
only the SHA-256 hash plus a short prefix (used as the fast-lookup index at
verify time). Revocation is a soft delete (the row stays so the audit trail
survives).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.api_key import ApiKey

logger = logging.getLogger(__name__)


KEY_TOKEN_PREFIX = "epai_"         # all plaintext keys start with this
KEY_PREFIX_LENGTH = 12             # how much of the plaintext we store as a lookup prefix


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_key() -> Tuple[str, str, str]:
    """
    Generate a fresh key.

    Returns (plaintext, prefix, sha256_hex). The plaintext must be returned
    to the caller exactly once and then forgotten.
    """
    token = secrets.token_urlsafe(32)
    plaintext = f"{KEY_TOKEN_PREFIX}{token}"
    prefix = plaintext[:KEY_PREFIX_LENGTH]
    return plaintext, prefix, hash_key(plaintext)


def hash_key(plaintext: str) -> str:
    """SHA-256 hex of the plaintext key. Keys are high entropy → no salt needed."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _to_doc(api_key: ApiKey) -> Dict[str, Any]:
    doc = api_key.model_dump()
    doc["_id"] = doc.pop("key_id")
    return doc


def _from_doc(doc: Dict[str, Any]) -> ApiKey:
    data = dict(doc)
    data["key_id"] = data.pop("_id")
    return ApiKey.model_validate(data)


class ApiKeyStore:
    """Repository over the `api_keys` collection in MongoDB."""

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
        self._col = client[s.mongodb_db]["api_keys"]

    # ---------------------------------------------------------------- issue
    def issue(self, *, platform_id: str, name: Optional[str] = None) -> Tuple[ApiKey, str]:
        """
        Generate, store, and return a new API key for a platform.

        Returns `(api_key_record, plaintext_key)`. The plaintext is the caller's
        only chance to see the secret — it is never stored or retrievable later.
        """
        plaintext, prefix, key_hash = generate_key()
        api_key = ApiKey(
            platform_id=platform_id,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
        )
        self._col.insert_one(_to_doc(api_key))
        logger.info(
            "api_key.issued",
            extra={"key_id": api_key.key_id, "platform_id": platform_id, "key_prefix": prefix},
        )
        return api_key, plaintext

    # ---------------------------------------------------------------- read
    def get(self, key_id: str) -> Optional[ApiKey]:
        doc = self._col.find_one({"_id": key_id})
        return _from_doc(doc) if doc else None

    def list_all(self, *, include_revoked: bool = True, limit: int = 1000) -> List[ApiKey]:
        """Every API key across platforms — used by the provider Clients view."""
        query: Dict[str, Any] = {} if include_revoked else {"revoked": False}
        return [_from_doc(d) for d in self._col.find(query).limit(limit)]

    def list_for_platform(
        self, platform_id: str, *, include_revoked: bool = False, limit: int = 100
    ) -> List[ApiKey]:
        query: Dict[str, Any] = {"platform_id": platform_id}
        if not include_revoked:
            query["revoked"] = False
        cursor = self._col.find(query).sort("created_at", -1).limit(limit)
        return [_from_doc(d) for d in cursor]

    # ---------------------------------------------------------------- revoke
    def revoke(self, key_id: str) -> bool:
        """Soft delete — mark revoked. Returns True if a row was affected."""
        result = self._col.update_one(
            {"_id": key_id, "revoked": False},
            {"$set": {"revoked": True, "revoked_at": _now()}},
        )
        if result.modified_count > 0:
            logger.info("api_key.revoked", extra={"key_id": key_id})
            return True
        return False

    # ---------------------------------------------------------------- verify
    def verify(self, plaintext: str) -> Optional[ApiKey]:
        """
        Resolve a plaintext key to its record (or `None`).

        Used by the future auth middleware: takes the bearer token from the
        Authorization header, looks up by prefix, verifies the hash, refuses
        revoked keys, and stamps `last_used_at`.
        """
        if not plaintext or not plaintext.startswith(KEY_TOKEN_PREFIX):
            return None
        prefix = plaintext[:KEY_PREFIX_LENGTH]
        expected_hash = hash_key(plaintext)
        doc = self._col.find_one(
            {"key_prefix": prefix, "key_hash": expected_hash, "revoked": False}
        )
        if doc is None:
            return None
        self._col.update_one({"_id": doc["_id"]}, {"$set": {"last_used_at": _now()}})
        return _from_doc(doc)


__all__ = ["ApiKeyStore", "generate_key", "hash_key", "KEY_TOKEN_PREFIX", "KEY_PREFIX_LENGTH"]
