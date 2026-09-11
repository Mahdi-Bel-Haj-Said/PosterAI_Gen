"""
Central application settings.

Loaded once from environment variables (and `.env` if present).
All modules that need configuration should import `get_settings()` rather than
reading `os.environ` directly.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_project_root(start: Optional[Path] = None) -> Path:
    """
    Locate the repo root, whichever way the package was installed.

    This used to be `Path(__file__).resolve().parents[2]`, which is only correct
    while the package sits in `src/`. A plain `pip install .` copies it into
    `site-packages`, where the same arithmetic lands on `<venv>/lib/pythonX.Y`
    and every data directory resolves inside the virtualenv — the pipeline then
    dies on a missing `backgrounds/` that is present all along. That is a
    deployment failure with no obvious cause, so the root is now discovered by
    looking for a marker rather than by counting directories.

    Order: explicit override, then the nearest ancestor holding `pyproject.toml`
    (which covers both the `src/` layout and a venv living inside the repo),
    then the working directory when it looks like the project — systemd sets
    `WorkingDirectory` to the install root.
    """
    override = os.getenv("EPAI_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()

    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent

    cwd = Path.cwd().resolve()
    if (cwd / "pyproject.toml").is_file() or (cwd / "backgrounds").is_dir():
        return cwd

    # Nothing identifiable. Keep the historical answer so a source checkout
    # behaves exactly as before rather than failing in a new way.
    return here.parents[2] if len(here.parents) > 2 else here.parent


PROJECT_ROOT: Path = _detect_project_root()


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
    openai_caption_model: str = Field(
        default="gpt-4o-mini",
        description=(
            "Small, cheap text model for social captions (~100 tokens out). "
            "Captions moved here from Gemini, whose API geo-blocks callers by "
            "IP and is unreachable from some hosts regardless of configuration."
        ),
    )
    openai_prompt_builder_model: str = Field(
        default="gpt-4o-mini",
        description=(
            "Small, cheap text model for key-art background prompt enrichment / "
            "generation (keyart_builder balanced/premium tiers). ~$0.001 per call."
        ),
    )

    # RunPod (reserved for the deferred SD background stage)
    runpod_api_key: str = Field(default="")
    runpod_endpoint_id: str = Field(default="")

    # Pre-generated background bank (R2). Backgrounds are generated offline in
    # batches and served instantly (delete-on-serve); a refill tops the bank back
    # up when any combo runs low. See the `esports_poster_ai.bank` package.
    bg_bank_prefix: str = Field(
        default="Bg_bank_lol",
        description=(
            "Top-level R2 folder holding the pre-generated background bank. "
            "LoL-specific (the LoRA is LoL-trained); a Valorant bank would use its own."
        ),
    )
    bg_bank_target_per_combo: int = Field(
        default=6,
        description="Desired number of ready backgrounds per (energy, vibe) combo.",
    )
    bg_bank_refill_threshold: int = Field(
        default=2,
        description=(
            "When any combo drops to <= this many remaining, one refill job tops "
            "every combo back up to the target."
        ),
    )
    bg_bank_image_size: int = Field(
        default=1536,
        description=(
            "Square edge (px) of each bank background render. 1536 is the target "
            "(sharper than 1024); confirm the serverless worker's GPU has the VRAM "
            "for it with one test image before a full fill — drop to 1024 if it OOMs."
        ),
    )
    bg_bank_steps: int = Field(default=30, description="Diffusion steps for bank renders.")
    bg_bank_guidance: float = Field(default=5.0, description="CFG guidance for bank renders.")
    bg_bank_refill_lock_ttl_seconds: int = Field(
        default=1800,
        description="Safety TTL on the refill lock (auto-releases if a refill crashes).",
    )
    bg_bank_fill_concurrency: int = Field(
        default=3,
        description=(
            "How many generation jobs to keep in RunPod's queue at once during a "
            "fill. Keeping the queue non-empty stops the serverless worker from "
            "scaling to zero between images (which would cold-reload the 20B model "
            "each time). Requires the endpoint's Max Workers = 1 so extra queued "
            "jobs don't spin up additional (cold-starting) workers."
        ),
    )
    bg_bank_auto_refill_enabled: bool = Field(
        default=True,
        description=(
            "Master switch for the automatic bank refill. When a served combo "
            "drops to <= the threshold, a refill is spawned as a DETACHED process "
            "(so it never blocks poster generation on the job worker). Set false "
            "to disable auto-refill entirely — e.g. while testing, or when you fill "
            "the bank manually with `bank.seed --fill`."
        ),
    )
    bg_bank_job_max_wait_seconds: int = Field(
        default=3600,
        description=(
            "How long the durable refill waits for ONE background job (queued on "
            "RunPod, waiting for a free GPU) before it cancels and RETRIES it. The "
            "refill never skips — it retries until the bank is filled — so this just "
            "bounds how long a single attempt waits before a fresh one is submitted."
        ),
    )
    bg_bank_job_ttl_ms: int = Field(
        default=3600000,
        description=(
            "RunPod job execution-policy TTL (ms): how long RunPod keeps a submitted "
            "job QUEUED waiting for a GPU before dropping it. Set generous so jobs "
            "survive a GPU shortage; if RunPod drops one, the durable refill resubmits."
        ),
    )

    # Official game-logo overlay. When on, an LoL poster gets the official
    # League of Legends wordmark supplied to the pipeline as a reference image,
    # and the vision model is told to place it based on the background — so a
    # viewer instantly knows the game. Set false to disable the overlay.
    brand_logo_enabled: bool = Field(
        default=True,
        description="Add the official game logo (LoL wordmark) as a reference + placement instruction.",
    )

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
    cors_allow_origins: str = Field(
        default="*",
        description=(
            "Comma-separated list of origins allowed to call this API from a "
            "browser, or '*' for any. '*' is a DEV-ONLY default — it exists so "
            "the reference SPA works from any port. In the Defendr integration "
            "the browser never calls this API directly (Defendr's backend "
            "proxies everything), so production should set this to an empty "
            "string, which blocks all cross-origin browser access."
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

    # Webhooks — push notifications to a platform's callback URL on job
    # completion/failure. OFF by default: with this false the emit hook is a
    # no-op and nothing about the existing pipeline changes.
    webhooks_enabled: bool = Field(
        default=False,
        description="Master switch for outbound webhooks. False = no webhooks fire.",
    )
    webhook_timeout_seconds: float = Field(
        default=5.0, description="Per-attempt HTTP timeout when POSTing to a client URL."
    )
    webhook_max_attempts: int = Field(
        default=5, description="Max delivery attempts before a webhook is dead-lettered."
    )
    webhook_backoff_base_seconds: float = Field(
        default=10.0,
        description="Base for exponential backoff between delivery retries (base * 2**(attempt-1)).",
    )
    webhook_allow_insecure_urls: bool = Field(
        default=False,
        description=(
            "Dev-only escape hatch: when true, http:// and private/loopback hosts "
            "are accepted as callback URLs (e.g. to test against webhook.site over "
            "http or a local listener). Keep false in production (HTTPS + SSRF guard)."
        ),
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
    # Real training captions used as RAG exemplars for the premium prompt tier
    # (keyart_builder.load_caption_store). Missing dir -> premium falls back.
    keyart_captions_dir: Path = PROJECT_ROOT / "Prompts"

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
