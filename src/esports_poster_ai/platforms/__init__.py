"""Platform (client) registry — provider <-> client commercial metadata."""

from esports_poster_ai.platforms.store import PlatformStore
from esports_poster_ai.platforms.economics import (
    economics_for,
    branding_for,
    features_for,
    quotas_for,
    platform_for,
)

__all__ = [
    "PlatformStore", "economics_for", "branding_for",
    "features_for", "quotas_for", "platform_for",
]
