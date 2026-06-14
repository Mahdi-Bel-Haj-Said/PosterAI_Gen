"""
`/v1/api-keys` — admin-only endpoints to issue, list, and revoke API keys.

Protected by the `require_admin` dependency (`X-Admin-Token` header). The
plaintext key is returned ONCE on creation and never again — only the
metadata (id, prefix, created/revoked timestamps) is queryable later.

Revoke is a soft delete: the row stays for the audit trail; the key just
stops verifying.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from esports_poster_ai.api.deps import require_admin
from esports_poster_ai.api.schemas import (
    ApiKeyListResponse,
    ApiKeyResponse,
    IssueApiKeyRequest,
    IssuedApiKeyResponse,
)
from esports_poster_ai.auth.store import ApiKeyStore

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/api-keys",
    tags=["api-keys"],
    dependencies=[Depends(require_admin)],  # every route in this router is admin-only
)


def get_api_key_store() -> ApiKeyStore:
    """FastAPI dependency providing an ApiKeyStore. Overridable in tests."""
    return ApiKeyStore()


@router.post("", status_code=201, response_model=IssuedApiKeyResponse)
def issue_api_key(
    req: IssueApiKeyRequest,
    store: ApiKeyStore = Depends(get_api_key_store),
) -> IssuedApiKeyResponse:
    """
    Issue a new API key for a platform. The plaintext is shown only here — save it.
    """
    api_key, plaintext = store.issue(platform_id=req.platform_id, name=req.name)
    logger.info(
        "api.api_key.issued",
        extra={"key_id": api_key.key_id, "platform_id": api_key.platform_id},
    )
    return IssuedApiKeyResponse(
        key_id=api_key.key_id,
        platform_id=api_key.platform_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=plaintext,
        created_at=api_key.created_at,
    )


@router.get("", response_model=ApiKeyListResponse)
def list_api_keys(
    platform_id: str = Query(..., description="Platform id to list keys for."),
    include_revoked: bool = Query(False, description="Include soft-deleted keys."),
    limit: int = Query(100, ge=1, le=500),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> ApiKeyListResponse:
    """List a platform's keys (no plaintext — that's gone forever after creation)."""
    keys = store.list_for_platform(platform_id, include_revoked=include_revoked, limit=limit)
    return ApiKeyListResponse(
        keys=[ApiKeyResponse.from_api_key(k) for k in keys],
        count=len(keys),
    )


@router.delete("/{key_id}", status_code=204)
def revoke_api_key(
    key_id: str,
    store: ApiKeyStore = Depends(get_api_key_store),
) -> Response:
    """Revoke an API key (soft delete — the audit row stays)."""
    if store.get(key_id) is None:
        raise HTTPException(status_code=404, detail=f"API key not found: {key_id}")
    store.revoke(key_id)
    return Response(status_code=204)
