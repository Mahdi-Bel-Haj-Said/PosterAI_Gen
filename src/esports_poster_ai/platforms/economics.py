"""
Resolve the Red Coins economics for a given client (platform).

Every billing decision (estimate, charge, grant, top-up) goes through here, so a
client's custom rates take effect everywhere with no other code change. A client
that never customised anything gets `PlatformEconomics()` defaults — identical to
the old hardcoded behaviour.
"""

from __future__ import annotations

from typing import Optional

from esports_poster_ai.domain.platform import (
    Platform,
    PlatformBranding,
    PlatformEconomics,
    PlatformFeatures,
    PlatformQuotas,
)
from esports_poster_ai.platforms.store import PlatformStore

_DEFAULT_ECON = PlatformEconomics()
_DEFAULT_BRANDING = PlatformBranding()
_DEFAULT_FEATURES = PlatformFeatures()
_DEFAULT_QUOTAS = PlatformQuotas()


def platform_for(platform_id: Optional[str]) -> Optional[Platform]:
    try:
        return PlatformStore().get(platform_id)
    except Exception:  # noqa: BLE001 — never 500 on a config lookup
        return None


def economics_for(platform_id: Optional[str]) -> PlatformEconomics:
    """Return the platform's economics config, or defaults if none is set."""
    rec = platform_for(platform_id)
    return rec.economics if (rec and rec.economics) else _DEFAULT_ECON


def branding_for(platform_id: Optional[str]) -> PlatformBranding:
    rec = platform_for(platform_id)
    return rec.branding if (rec and rec.branding) else _DEFAULT_BRANDING


def features_for(platform_id: Optional[str]) -> PlatformFeatures:
    rec = platform_for(platform_id)
    return rec.features if (rec and rec.features) else _DEFAULT_FEATURES


def quotas_for(platform_id: Optional[str]) -> PlatformQuotas:
    rec = platform_for(platform_id)
    return rec.quotas if (rec and rec.quotas) else _DEFAULT_QUOTAS


__all__ = ["platform_for", "economics_for", "branding_for", "features_for", "quotas_for"]
