"""
`GET /v1/me` — the authenticated platform's own account view.

The service is integrated by *platforms* (the paying customers); a single API
key authenticates one platform. `/v1/me` reports that platform's identity and
how many orgs it has registered. Per-org tier and quota live on the org and are
returned by `GET /v1/orgs/{org_id}`.

In dev mode (no key) there is no platform — `platform_id` is null and
`authenticated` is false.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.orgs.store import OrgStore

router = APIRouter(prefix="/v1/me", tags=["me"])


class MeResponse(BaseModel):
    """The caller's platform identity."""

    platform_id: Optional[str] = Field(
        default=None, description="The platform this API key belongs to; null in dev mode."
    )
    authenticated: bool = Field(
        description="True when the request carried a valid API key."
    )
    org_count: int = Field(
        default=0, description="Number of orgs registered under this platform."
    )
    generated_at: datetime


@router.get("", response_model=MeResponse)
def get_me(
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> MeResponse:
    """Return the caller's platform identity and registered-org count."""
    org_count = 0
    if auth.authenticated and auth.platform_id is not None:
        org_count = len(org_store.list_for_platform(auth.platform_id, limit=1000))
    return MeResponse(
        platform_id=auth.platform_id,
        authenticated=auth.authenticated,
        org_count=org_count,
        generated_at=datetime.now(tz=timezone.utc),
    )
