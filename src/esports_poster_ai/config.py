"""
Central application settings.

Loaded once from environment variables (and `.env` if present).
All modules that need configuration should import `get_settings()` rather than
reading `os.environ` directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root = repo root. From this file: parents[0]=esports_poster_ai,
# parents[1]=src, parents[2]=repo root.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All runtime configuration in one place."""

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_prompt_model: str = Field(
        default="gpt-4o",
        description="Model used in the prompt-generation stage (vision-capable).",
    )
    openai_image_model: str = Field(
        default="gpt-image-2",
        description="Model used in the poster-generation stage.",
    )

    # RunPod (reserved for the deferred SD background stage)
    runpod_api_key: str = Field(default="")
    runpod_endpoint_id: str = Field(default="")

    # Cloudflare R2 (S3-compatible object storage)
    r2_access_key_id: str = Field(default="", description="R2 API token Access Key ID.")
    r2_secret_access_key: str = Field(default="", description="R2 API token Secret Access Key.")
    r2_endpoint: str = Field(
        default="",
        description="R2 S3 API endpoint, e.g. https://<account_id>.r2.cloudflarestorage.com",
    )
    r2_bucket: str = Field(default="", description="R2 bucket name (shared with Defendr).")
    r2_key_prefix: str = Field(
        default="defendr-poster-ai",
        description="Top-level key prefix for all objects this service writes to the shared bucket.",
    )
    r2_public_url: str = Field(
        default="",
        description="Optional public base URL (r2.dev or custom domain). Blank = use presigned URLs.",
    )

    # Async job pipeline — Redis (queue) + MongoDB (job store).
    # Dev: local containers. Prod: Defendr's instances, namespaced.
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for the RQ job queue.",
    )
    mongodb_url: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URL for the job store.",
    )
    mongodb_db: str = Field(
        default="defendr_poster_ai",
        description="MongoDB database name owned by this service (own DB, never Defendr's).",
    )

    # HTTP API
    api_host: str = Field(default="0.0.0.0", description="Host the HTTP API binds to.")
    api_port: int = Field(default=8000, description="Port the HTTP API binds to.")
    public_base_url: str = Field(
        default="http://localhost:8000",
        description=(
            "Publicly reachable base URL of this API. Used to build absolute "
            "share landing-page URLs (/p/{job_id}) embedded in Twitter/OG tags. "
            "Override in production with the real domain (no trailing slash)."
        ),
    )

    # Gemini — used to generate social captions for completed posters. The free
    # tier of gemini-2.5-flash is sufficient (captions are ~100 tokens out, well
    # under any free-tier cap). Leave the key blank to disable caption endpoints.
    gemini_api_key: str = Field(default="", description="Google AI Studio API key.")
    gemini_caption_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model used by the caption-generation stage.",
    )

    # Postiz — self-hosted social posting aggregator. Handles OAuth + per-platform
    # API calls for Twitter, Facebook, Instagram, LinkedIn, etc. We talk to it via
    # its Public API. Leave the key blank to disable the /v1/social/* endpoints.
    postiz_base_url: str = Field(
        default="http://localhost:4007",
        description=(
            "Base URL of your Postiz instance (self-hosted) or https://api.postiz.com "
            "for cloud. We append /public/v1 internally. No trailing slash."
        ),
    )
    postiz_api_key: str = Field(
        default="",
        description=(
            "Public API key generated in the Postiz UI (Settings → Public API). "
            "When blank, native-post endpoints return 503."
        ),
    )
    max_asset_size_mb: int = Field(
        default=10, description="Hard cap on a single asset upload (MB)."
    )
    admin_token: str = Field(
        default="",
        description=(
            "Bearer token for admin-only endpoints (API key management). "
            "When unset, admin endpoints refuse all requests."
        ),
    )
    api_key_required: bool = Field(
        default=False,
        description=(
            "When True, every org-scoped endpoint requires a valid "
            "'Authorization: Bearer <api-key>' and pins org_id from that key. "
            "When False (dev default), requests may pass org_id directly and a "
            "key is optional — present keys are still validated and enforced. "
            "Flip to True before exposing the API beyond localhost."
        ),
    )
    cost_per_poster_usd: float = Field(
        default=0.054,
        description="Estimated end-to-end cost of one completed poster (billing trail).",
    )

    # Default per-org rate limits, rolling windows. Each org can override these
    # in the MongoDB `org_limits` collection; if the doc is missing the defaults
    # apply. Failed jobs do not count toward usage.
    quota_day_default: int = Field(
        default=3,
        description="Default cap on posters per rolling 24h window.",
    )
    quota_week_default: int = Field(
        default=15,
        description="Default cap on posters per rolling 7-day window.",
    )
    quota_month_default: int = Field(
        default=30,
        description="Default cap on posters per rolling 30-day window.",
    )

    # Budget guards
    stage2_budget_usd: float = Field(
        default=0.10,
        description="Hard cap on the per-call upper-bound cost estimate for the prompt stage.",
    )
    stage2_max_output_tokens: int = Field(default=2000)

    # OpenAI retry policy
    openai_max_retries: int = Field(default=3)
    openai_initial_backoff_seconds: float = Field(default=1.0)
    openai_max_backoff_seconds: float = Field(default=16.0)

    # Logging
    log_level: str = Field(default="INFO")

    # Filesystem (kept here so stages can resolve paths consistently in CLI mode).
    project_root: Path = PROJECT_ROOT
    backgrounds_dir: Path = PROJECT_ROOT / "backgrounds"
    outputs_dir: Path = PROJECT_ROOT / "outputs"
    styles_dir: Path = PROJECT_ROOT / "styles"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached)."""
    return Settings()


def require_openai_key(settings: Optional[Settings] = None) -> str:
    """
    Fail fast with a clear error if the OpenAI key is missing.

    Stages should call this at entry rather than reaching into Settings
    themselves, so the error message is consistent everywhere.
    """
    s = settings or get_settings()
    if not s.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file at the project root."
        )
    return s.openai_api_key
