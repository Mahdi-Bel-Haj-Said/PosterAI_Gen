"""
Platform record — a CLIENT of the API provider (the integrating customer that
holds an API key). This is the provider <-> client relationship, which is purely
commercial: a service type and a fee. Red Coins are an ORG-level concept (the
platform's own end-users) and deliberately do NOT live here.

`service_type`:
  * "hosted" — fully managed: our OpenAI keys, our R2 bucket, we hold the data.
  * "byok"   — bring-your-own-keys: the client's OpenAI key, their R2, their data;
               we provide the software/API layer only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ServiceType = Literal["hosted", "byok"]
DEFAULT_SERVICE_TYPE: ServiceType = "hosted"

# Quality tiers a client may offer their orgs.
ALL_QUALITIES = ["low", "medium", "high"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlatformEconomics(BaseModel):
    """
    Per-client (platform) Red Coins economics. Each client sets these during
    integration to control how THEY price and monetise their own orgs. Defaults
    reproduce the standard pricing, so a client that customises nothing behaves
    exactly as before.

    The token charge for a poster is:
        tokens_charged = round(base_cost_usd * quality_mult * poster_markup * tokens_per_usd)
    """

    model_config = ConfigDict(extra="ignore")

    # Exchange rate: how many Red Coins equal $1 of value. Higher = coins are
    # "cheaper" / finer-grained (e.g. 10000 -> a $0.10 poster costs 1000 coins);
    # lower -> coarser. This only changes the coin denomination, not the margin.
    tokens_per_usd: int = Field(default=10000, ge=1)

    # Margin multiplier applied to the real platform cost before converting to
    # coins. 2.0 = the org pays 2x what the poster costs the platform. This is
    # the client's profit-per-poster lever ("win more per poster").
    poster_markup: float = Field(default=2.0, ge=0.0)

    # Price (USD) for an org to top up 10,000 Red Coins, pay-as-you-go. Usually
    # a touch above the subscription-implied rate.
    topup_usd_per_10k: float = Field(default=0.80, ge=0.0)

    # Cost basis (USD) of a single MEDIUM-quality poster. For hosted clients this
    # is the provider's real cost; for BYOK the client may set their own basis
    # (they pay their own OpenAI/R2). Quality tiers scale off this.
    base_cost_per_poster_usd: float = Field(default=0.054, ge=0.0)

    # Monthly Red Coins granted to an org on each subscription tier.
    free_grant: int = Field(default=1500, ge=0)
    pro_grant: int = Field(default=30000, ge=0)
    kratos_grant: int = Field(default=100000, ge=0)

    # ---- derived helpers (single source of truth for the math) -------------
    def tokens_for_cost(self, cost_usd: float) -> int:
        """Red Coins to charge an org for a poster that cost `cost_usd`."""
        return max(1, round(float(cost_usd) * self.poster_markup * self.tokens_per_usd))

    def estimate_tokens(self, quality_mult: float) -> int:
        """Red Coins for one poster at the given quality multiplier."""
        return self.tokens_for_cost(self.base_cost_per_poster_usd * float(quality_mult))

    def grant_for(self, tier: str) -> int:
        return {"free": self.free_grant, "pro": self.pro_grant, "kratos": self.kratos_grant}.get(tier, self.free_grant)

    def topup_tokens_for_usd(self, usd: float) -> int:
        if self.topup_usd_per_10k <= 0:
            return 0
        return max(0, round(float(usd) / self.topup_usd_per_10k * 10000))


class PlatformBranding(BaseModel):
    """White-label appearance the client shows to THEIR orgs/end-users."""

    model_config = ConfigDict(extra="ignore")

    product_name: Optional[str] = None     # app name shown in the UI (e.g. "Acme Posters")
    coin_name: str = "Red Coins"           # full name of the token currency
    coin_symbol: str = "RC"                # short label shown next to amounts
    logo_url: Optional[str] = None         # client logo (URL)
    accent_color: Optional[str] = None     # primary brand color, hex (e.g. "#E83A57")
    ai_accent_color: Optional[str] = None  # secondary/AI accent, hex
    powered_by: bool = True                # show the "powered by <provider>" mark


class PlatformFeatures(BaseModel):
    """Which capabilities the client exposes to their orgs (sell tiers on these)."""

    model_config = ConfigDict(extra="ignore")

    consistency: bool = True               # Style DNA consistency mode
    refine: bool = True                    # refine / image-edit pass
    sponsor_bar: bool = True               # sponsor logo bar
    caption: bool = True                   # Gemini social captions
    social: bool = True                    # native social posting (Postiz)
    background_upload: bool = True         # let orgs upload their own background
    allowed_qualities: List[str] = Field(default_factory=lambda: list(ALL_QUALITIES))


class PlatformTier(BaseModel):
    """Per-tier overrides: what the client calls a tier and charges orgs for it.
    (The monthly Red Coins grant lives in PlatformEconomics.)"""

    model_config = ConfigDict(extra="ignore")

    label: Optional[str] = None            # display name, e.g. "Starter" instead of "Pro"
    price_usd: Optional[float] = None       # what the CLIENT charges their org for this tier


class PlatformQuotas(BaseModel):
    """Default rolling per-org caps on completed posters. None = service default."""

    model_config = ConfigDict(extra="ignore")

    day: Optional[int] = Field(default=None, ge=0)
    week: Optional[int] = Field(default=None, ge=0)
    month: Optional[int] = Field(default=None, ge=0)


class PlatformBYOK(BaseModel):
    """Bring-your-own-keys credentials, used when service_type == 'byok'. The
    client runs on their own OpenAI / Gemini / R2 — the provider stores these and
    the pipeline uses them for that client's jobs. Secrets are masked on read."""

    model_config = ConfigDict(extra="ignore")

    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket: Optional[str] = None


class Platform(BaseModel):
    """A client of the API provider."""

    model_config = ConfigDict(extra="ignore")

    platform_id: str
    name: Optional[str] = None
    service_type: ServiceType = DEFAULT_SERVICE_TYPE
    # What the client pays the provider per month (the money relationship). The
    # real billing provider plugs in later; this is the agreed figure for now.
    monthly_fee_usd: float = 0.0
    notes: Optional[str] = None

    # ---- Client-owned configuration (the client self-serves these) ----------
    economics: PlatformEconomics = Field(default_factory=PlatformEconomics)
    branding: PlatformBranding = Field(default_factory=PlatformBranding)
    features: PlatformFeatures = Field(default_factory=PlatformFeatures)
    quotas: PlatformQuotas = Field(default_factory=PlatformQuotas)
    byok: PlatformBYOK = Field(default_factory=PlatformBYOK)
    # Per-tier label + price overrides, keyed by tier id (free / pro / kratos).
    tiers: Dict[str, PlatformTier] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# Top-level config blocks the CLIENT may edit themselves (excludes commercial /
# entitlement fields like service_type and monthly_fee_usd, which the provider owns).
CLIENT_EDITABLE_BLOCKS = ("economics", "branding", "features", "quotas", "byok", "tiers")

__all__ = [
    "Platform", "PlatformEconomics", "PlatformBranding", "PlatformFeatures",
    "PlatformTier", "PlatformQuotas", "PlatformBYOK",
    "ServiceType", "DEFAULT_SERVICE_TYPE", "ALL_QUALITIES", "CLIENT_EDITABLE_BLOCKS",
]
