"""
`/v1/orgs` — the platform's org registry.

A platform (authenticated by its API key) registers the orgs it generates
posters for, and manages them here. Org ids are unique *within* the platform;
the storage layer namespaces every object under `platforms/{platform_id}/`, so
two platforms can reuse the same org id with no collision.

Each org carries its own subscription `tier` (per-org billing). `GET
/v1/orgs/{org_id}` returns that tier plus the org's live rolling quota.

In dev mode (no API key) these endpoints operate under the null platform — the
same single-tenant surface the rest of the dev API uses.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.api.routes.posters import get_job_store
from esports_poster_ai.billing import SUBSCRIPTION_TIERS, SubscriptionTier, TierInfo
from esports_poster_ai.domain.org import Org, OrgRateLimits
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.quotas import WindowQuota, compute_quotas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/orgs", tags=["orgs"])


# ---- schemas ----------------------------------------------------------------


class RegisterOrgRequest(BaseModel):
    org_id: Optional[str] = Field(
        default=None,
        description="Desired org id (unique within your platform). Generated if omitted.",
    )
    name: Optional[str] = Field(default=None, description="Human label for the org.")
    tier: Optional[SubscriptionTier] = Field(
        default=None, description="Optional free-form label. Not a price/cap."
    )
    limits: Optional[OrgRateLimits] = Field(
        default=None,
        description="Per-org rolling quota (day/week/month). Omit a field to keep "
        "the service default. You can change these any time via PATCH.",
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    tier: Optional[SubscriptionTier] = None
    limits: Optional[OrgRateLimits] = Field(
        default=None, description="New per-org rolling quota (day/week/month)."
    )
    metadata: Optional[Dict[str, Any]] = None


class OrgResponse(BaseModel):
    org_id: str
    platform_id: Optional[str] = None
    name: Optional[str] = None
    tier: SubscriptionTier
    tier_info: TierInfo
    limits: OrgRateLimits
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_org(cls, org: Org) -> "OrgResponse":
        return cls(
            org_id=org.org_id,
            platform_id=org.platform_id,
            name=org.name,
            tier=org.tier,
            tier_info=SUBSCRIPTION_TIERS[org.tier],
            limits=org.limits,
            metadata=org.metadata,
            created_at=org.created_at,
            updated_at=org.updated_at,
        )


class OrgListResponse(BaseModel):
    orgs: List[OrgResponse]
    count: int


class OrgDetailResponse(OrgResponse):
    """One org plus its live rolling quota."""

    quota: List[WindowQuota]


# ---- routes -----------------------------------------------------------------


@router.post("", status_code=201, response_model=OrgResponse)
def register_org(
    req: RegisterOrgRequest,
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> OrgResponse:
    """
    Register an org under the caller's platform.

    Idempotent on `org_id`: re-registering an existing org returns it unchanged
    (use PATCH to edit). If `org_id` is omitted, a fresh one is generated.
    """
    org_id = (req.org_id or "").strip() or f"org_{uuid4().hex[:10]}"
    # Guard the id as a clean path segment (it becomes part of storage keys).
    if "/" in org_id or "\\" in org_id or org_id in {".", ".."}:
        raise HTTPException(status_code=422, detail=f"Invalid org_id: {org_id!r}")

    existing = org_store.get(auth.platform_id, org_id)
    if existing is not None and req.org_id:
        # Explicit id that already exists → conflict (don't silently alias).
        raise HTTPException(
            status_code=409, detail=f"Org '{org_id}' already exists under this platform."
        )

    org = org_store.register(
        platform_id=auth.platform_id,
        org_id=org_id,
        name=req.name,
        tier=req.tier,
        limits=req.limits,
        metadata=req.metadata,
    )
    logger.info(
        "api.org.registered",
        extra={"platform_id": auth.platform_id, "org_id": org_id},
    )
    return OrgResponse.from_org(org)


@router.get("", response_model=OrgListResponse)
def list_orgs(
    limit: int = Query(200, ge=1, le=1000),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> OrgListResponse:
    """List the orgs registered under the caller's platform."""
    orgs = org_store.list_for_platform(auth.platform_id, limit=limit)
    return OrgListResponse(
        orgs=[OrgResponse.from_org(o) for o in orgs], count=len(orgs)
    )


@router.get("/{org_id}", response_model=OrgDetailResponse)
def get_org(
    org_id: str,
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
    job_store: JobStore = Depends(get_job_store),
) -> OrgDetailResponse:
    """Get one org plus its live rolling quota (tier + usage in one call)."""
    org = org_store.get(auth.platform_id, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
    quota = compute_quotas(
        org_id,
        platform_id=auth.platform_id,
        limits=org.limits.model_dump(),
        job_store=job_store,
    )
    base = OrgResponse.from_org(org)
    return OrgDetailResponse(**base.model_dump(), quota=quota)


@router.patch("/{org_id}", response_model=OrgResponse)
def update_org(
    org_id: str,
    req: UpdateOrgRequest,
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> OrgResponse:
    """Patch an org's name / tier / metadata."""
    org = org_store.update(
        auth.platform_id, org_id,
        name=req.name, tier=req.tier, limits=req.limits, metadata=req.metadata,
    )
    if org is None:
        raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
    return OrgResponse.from_org(org)


@router.delete("/{org_id}", status_code=204)
def delete_org(
    org_id: str,
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> Response:
    """
    Remove the org's registry record.

    This does NOT delete the org's posters or assets from storage — it only
    de-registers the org so new poster/asset calls for it are rejected.
    """
    if not org_store.delete(auth.platform_id, org_id):
        raise HTTPException(status_code=404, detail=f"Org not found: {org_id}")
    return Response(status_code=204)
