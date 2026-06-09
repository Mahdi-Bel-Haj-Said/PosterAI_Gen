"""
Cross-cutting FastAPI dependencies — admin auth, etc.

`require_admin` protects the API-key management endpoints. It checks the
`X-Admin-Token` request header against the `admin_token` setting. If the
setting is unset, the endpoints refuse all requests (safe by default).
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from esports_poster_ai.config import get_settings


def require_admin(
    x_admin_token: Optional[str] = Header(
        None,
        alias="X-Admin-Token",
        description="Admin bearer token; must match the service's ADMIN_TOKEN setting.",
    ),
) -> None:
    """FastAPI dependency that 401s anything without the configured admin token."""
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin endpoints are not configured (ADMIN_TOKEN unset).",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing admin token.")


__all__ = ["require_admin"]
