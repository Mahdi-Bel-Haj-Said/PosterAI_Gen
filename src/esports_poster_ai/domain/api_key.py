"""
API key domain model.

The plaintext key is only ever returned ONCE — at creation. The database
stores the SHA-256 hash plus a short prefix used for fast lookup at auth
time. Revocation is a soft delete (a row stays for the audit trail).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApiKey(BaseModel):
    """Stored metadata for an issued API key. Never contains the plaintext."""

    model_config = ConfigDict(extra="ignore")

    key_id: str = Field(default_factory=lambda: uuid4().hex)
    org_id: str
    name: Optional[str] = None        # human label ("Defendr production", "test key")
    key_prefix: str                    # first ~12 chars of the plaintext, for lookup
    key_hash: str                      # sha256 hex of the full plaintext key

    created_at: datetime = Field(default_factory=_now)
    last_used_at: Optional[datetime] = None
    revoked: bool = False
    revoked_at: Optional[datetime] = None


__all__ = ["ApiKey"]
