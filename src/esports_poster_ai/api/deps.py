"""
Cross-cutting FastAPI dependencies — admin auth and per-tenant API-key auth.

Two distinct auth surfaces live here:

* ``require_admin`` protects the API-key *management* endpoints. It checks the
  ``X-Admin-Token`` request header against the ``admin_token`` setting. If the
  setting is unset, the endpoints refuse all requests (safe by default).

* ``get_auth_context`` is the per-tenant gate used by every org-scoped endpoint.
  It reads ``Authorization: Bearer <api-key>``, resolves it to a **platform** via
  ``ApiKeyStore.verify``, and hands routes an :class:`AuthContext`. The service is
  sold to *platforms* (the integrating customers); a single key authenticates one
  platform, and that platform addresses **many orgs** by passing ``org_id`` on
  each request. The key therefore carries ``platform_id`` (not an org), and the
  request's ``org_id`` is validated as belonging to that platform.

  Behaviour depends on ``settings.api_key_required``:

    - key present  → always verified; an invalid/revoked key is 401. The request
                     is scoped to the key's platform, and ``org_id`` must name an
                     org registered under that platform.
    - key absent   → 401 when ``api_key_required`` is True; otherwise the request
                     runs in "dev mode" (``platform_id is None``): no platform
                     namespacing, no ownership/registration enforcement — the
                     historical single-tenant localhost behaviour, untouched.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from esports_poster_ai.auth.store import KEY_TOKEN_PREFIX, ApiKeyStore
from esports_poster_ai.config import get_settings
from esports_poster_ai.orgs.store import OrgStore


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


# --------------------------------------------------------------- tenant auth


def get_api_key_store() -> ApiKeyStore:
    """Construct an ApiKeyStore. Module-level so tests can monkeypatch it."""
    return ApiKeyStore()


def get_org_store() -> OrgStore:
    """Construct an OrgStore. Module-level so tests can monkeypatch / override it."""
    return OrgStore()


class AuthContext:
    """
    The authenticated platform context for one request.

    ``authenticated`` is True only when a valid API key was presented, in which
    case ``platform_id`` is the platform that key belongs to. Routes call
    :meth:`require_org` (org_id always comes from the request — one platform
    owns many orgs), :meth:`assert_platform` (guard a loaded resource against
    cross-platform access), and :meth:`require_org_registered` (the org named in
    the request must exist under the platform).
    """

    __slots__ = ("platform_id", "authenticated", "key_id")

    def __init__(
        self,
        *,
        platform_id: Optional[str],
        authenticated: bool,
        key_id: Optional[str] = None,
    ) -> None:
        self.platform_id = platform_id
        self.authenticated = authenticated
        self.key_id = key_id

    def require_org(self, requested: Optional[str] = None) -> str:
        """
        Return the org_id for an org-scoped request.

        org_id always comes from the request — a platform addresses many orgs.
        It is mandatory in every mode; without it we cannot scope the request.
        Registration under the platform is checked separately (needs the store)
        via :meth:`require_org_registered`.
        """
        if requested is None or not str(requested).strip():
            raise HTTPException(status_code=422, detail="org_id is required.")
        return str(requested)

    def require_org_registered(self, org_id: str, org_store: OrgStore) -> None:
        """
        Enforce that ``org_id`` is registered under the authenticated platform.

        A no-op in dev mode (no platform). When authenticated, an unregistered
        org is a 404 (register it first via ``POST /v1/orgs``).
        """
        if not self.authenticated:
            return
        assert self.platform_id is not None
        if not org_store.exists(self.platform_id, org_id):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Org '{org_id}' is not registered under this platform. "
                    "Register it first via POST /v1/orgs."
                ),
            )

    def resolve_org_limits(self, org_id: str, org_store: OrgStore) -> Optional[dict]:
        """
        Enforce registration (when authenticated) AND return the org's quota override.

        Combines :meth:`require_org_registered` with a fetch of the org's
        per-org `limits` (day/week/month, edited by the platform). Returns the
        limits dict, or None when there's no org record (dev / unregistered →
        the service defaults apply). A no-op-style registration check in dev.
        """
        org = org_store.get(self.platform_id, org_id)
        if self.authenticated and org is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Org '{org_id}' is not registered under this platform. "
                    "Register it first via POST /v1/orgs."
                ),
            )
        if org is None:
            return None
        return org.limits.model_dump()

    def assert_platform(self, resource_platform_id: Optional[str]) -> None:
        """
        Guard a resource loaded by id (job, asset, …) against cross-platform access.

        Returns 404 (not 403) on mismatch so we never reveal that a resource
        exists under another platform. A no-op in dev mode (no key).
        """
        if self.authenticated and resource_platform_id != self.platform_id:
            raise HTTPException(status_code=404, detail="Not found.")


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    """Pull the token from an Authorization header. Accepts a raw key too."""
    if not authorization:
        return None
    value = authorization.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip() or None
    # Convenience: allow the raw key without the "Bearer " prefix.
    if value.startswith(KEY_TOKEN_PREFIX):
        return value
    return None


def get_auth_context(
    authorization: Optional[str] = Header(
        None,
        description="Tenant API key as 'Bearer <key>'. Optional in dev mode.",
    ),
) -> AuthContext:
    """Resolve the request's tenant context from the Authorization header."""
    token = _extract_bearer(authorization)
    if token:
        key = get_api_key_store().verify(token)
        if key is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
        return AuthContext(
            platform_id=key.platform_id, authenticated=True, key_id=key.key_id
        )

    if get_settings().api_key_required:
        raise HTTPException(
            status_code=401,
            detail="API key required. Pass 'Authorization: Bearer <key>'.",
        )
    return AuthContext(platform_id=None, authenticated=False)


__all__ = [
    "require_admin",
    "AuthContext",
    "get_auth_context",
    "get_api_key_store",
    "get_org_store",
]
