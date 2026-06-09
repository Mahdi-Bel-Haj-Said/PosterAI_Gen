"""Request / response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from esports_poster_ai.domain.api_key import ApiKey
from esports_poster_ai.domain.asset import Asset
from esports_poster_ai.domain.job import Job
from esports_poster_ai.domain.style_dna import StyleDNA


class CreatePosterRequest(BaseModel):
    """Body of `POST /v1/posters`."""

    org_id: str = Field(description="Organization (tenant) identifier.")
    tournament_id: str = Field(description="Tournament identifier.")
    input: Dict[str, Any] = Field(
        description="The poster input JSON document (validated as PosterInput; "
        "the generation mode is read from its _meta.mode)."
    )


class RefinePosterRequest(BaseModel):
    """Body of `POST /v1/posters/{job_id}/refine` — apply a freeform edit to a poster."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Freeform edit instruction (e.g. 'make it darker', "
        "'change time from 17:00 to 18:00', 'use a more dynamic font').",
    )


class JobResponse(BaseModel):
    """A job's status and result."""

    job_id: str
    status: str
    mode: str
    org_id: str
    tournament_id: str
    created_at: datetime
    updated_at: datetime
    poster_id: Optional[str] = None
    storage_key: Optional[str] = None
    signed_url: Optional[str] = None
    caption: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_job(cls, job: Job, signed_url: Optional[str] = None) -> "JobResponse":
        return cls(
            job_id=job.job_id,
            status=job.status,
            mode=job.mode,
            org_id=job.org_id,
            tournament_id=job.tournament_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
            poster_id=job.poster_id,
            storage_key=job.storage_key,
            signed_url=signed_url,
            caption=getattr(job, "caption", None),
            error=job.error,
        )


class JobListResponse(BaseModel):
    """A page of jobs."""

    jobs: List[JobResponse]
    count: int


class HealthResponse(BaseModel):
    """Service health."""

    status: str
    mongodb: str
    redis: str


# ----------------------------------------------------------------- assets


class AssetResponse(BaseModel):
    """An uploaded asset (logo, player photo, sponsor logo, tournament logo)."""

    asset_id: str
    org_id: str
    asset_type: str
    filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    name: Optional[str] = None
    team: Optional[str] = None
    created_at: datetime
    signed_url: Optional[str] = None

    @classmethod
    def from_asset(cls, asset: Asset, signed_url: Optional[str] = None) -> "AssetResponse":
        return cls(
            asset_id=asset.asset_id,
            org_id=asset.org_id,
            asset_type=str(asset.asset_type),
            filename=asset.filename,
            storage_key=asset.storage_key,
            content_type=asset.content_type,
            size_bytes=asset.size_bytes,
            name=asset.name,
            team=asset.team,
            created_at=asset.created_at,
            signed_url=signed_url,
        )


class AssetListResponse(BaseModel):
    assets: List[AssetResponse]
    count: int


# ----------------------------------------------------------------- style DNA


class ExtractStyleDNARequest(BaseModel):
    """Body of `POST /v1/style-dnas/{tournament_id}` — extract from a completed poster job."""

    org_id: str
    source_job_id: str = Field(
        description="job_id of a completed poster job to extract the DNA from."
    )


class UpdateStyleDNARequest(BaseModel):
    """Body of `PUT /v1/style-dnas/{tournament_id}` — replace the draft DNA."""

    org_id: str
    dna: Dict[str, Any] = Field(
        description="Full Style DNA document (validated as StyleDNA in the route)."
    )


class ApproveStyleDNARequest(BaseModel):
    org_id: str


class StyleDNAResponse(BaseModel):
    """A Style DNA document."""

    tournament_id: str
    status: str
    palette: List[str]
    color_temperature: str
    lighting: str
    atmosphere: str
    particle_effects: str
    energy: str
    sd_style_keywords: str
    source_poster_path: Optional[str] = None
    source_poster_url: Optional[str] = Field(
        default=None,
        description="Signed URL of the poster this DNA was extracted from, when it lives in storage.",
    )
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None

    @classmethod
    def from_dna(
        cls, dna: StyleDNA, source_poster_url: Optional[str] = None
    ) -> "StyleDNAResponse":
        return cls(
            tournament_id=dna.tournament_id,
            status=dna.status,
            palette=dna.palette,
            color_temperature=dna.color_temperature,
            lighting=dna.lighting,
            atmosphere=dna.atmosphere,
            particle_effects=dna.particle_effects,
            energy=dna.energy,
            sd_style_keywords=dna.sd_style_keywords,
            source_poster_path=dna.source_poster_path,
            source_poster_url=source_poster_url,
            created_at=dna.created_at,
            approved_at=dna.approved_at,
        )


# ----------------------------------------------------------------- api keys


class IssueApiKeyRequest(BaseModel):
    org_id: str
    name: Optional[str] = Field(
        default=None, description="Optional human label (e.g. 'Defendr production')."
    )


class IssuedApiKeyResponse(BaseModel):
    """Returned ONCE on creation — includes the plaintext key. Save it now."""

    key_id: str
    org_id: str
    name: Optional[str] = None
    key_prefix: str
    key: str = Field(description="Plaintext API key — shown only at creation. Save it.")
    created_at: datetime
    warning: str = "Save this key now. It will not be shown again."


class ApiKeyResponse(BaseModel):
    """Subsequent reads — no plaintext, only metadata."""

    key_id: str
    org_id: str
    name: Optional[str] = None
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked: bool
    revoked_at: Optional[datetime] = None

    @classmethod
    def from_api_key(cls, api_key: ApiKey) -> "ApiKeyResponse":
        return cls(
            key_id=api_key.key_id,
            org_id=api_key.org_id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            revoked=api_key.revoked,
            revoked_at=api_key.revoked_at,
        )


class ApiKeyListResponse(BaseModel):
    keys: List[ApiKeyResponse]
    count: int


# ----------------------------------------------------------------- usage


class UsageResponse(BaseModel):
    """Usage / cost report for an org over an optional time window."""

    org_id: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    total_jobs: int
    completed: int
    failed: int
    queued: int
    counts_by_status: Dict[str, int]
    estimated_cost_usd: float


__all__ = [
    "CreatePosterRequest",
    "RefinePosterRequest",
    "JobResponse",
    "JobListResponse",
    "HealthResponse",
    "AssetResponse",
    "AssetListResponse",
    "ExtractStyleDNARequest",
    "UpdateStyleDNARequest",
    "ApproveStyleDNARequest",
    "StyleDNAResponse",
    "IssueApiKeyRequest",
    "IssuedApiKeyResponse",
    "ApiKeyResponse",
    "ApiKeyListResponse",
    "UsageResponse",
]
