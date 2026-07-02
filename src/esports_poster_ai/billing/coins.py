"""
Red Coins — the user-facing token economy.

Final users never see dollars. Every price is expressed in *Red Coins* (tokens).
The platform's real per-poster cost is marked up and converted to tokens so the
platform keeps an average ~2x margin:

    tokens_charged = round(platform_cost_usd * POSTER_MARKUP * TOKENS_PER_USD)

Example: a poster that costs the platform $0.05 -> 0.05 * 2 * 10000 = 1000 tokens
(worth $0.10 of value to the user).

Coins arrive two ways:
  * a monthly subscription grant per tier (see SUBSCRIPTION_TIERS), and
  * pay-as-you-go top-ups at TOPUP_USD_PER_10K dollars per 10,000 tokens.

This module is the single source of truth for all token math.
"""

from __future__ import annotations

from esports_poster_ai.billing.tiers import (
    DEFAULT_TIER,
    SUBSCRIPTION_TIERS,
    SubscriptionTier,
)

# 1 USD of value == 10,000 tokens.
TOKENS_PER_USD = 10_000
# Platform margin: a poster is billed at this multiple of its real cost.
POSTER_MARKUP = 2.0
# Top-up price: how many USD to buy 10,000 tokens (slightly richer than the
# subscription rate, on purpose).
TOPUP_USD_PER_10K = 0.80

# Per-quality image cost multiplier (mirrors the wizard/quality feature), applied
# to the base per-poster cost to get the platform cost for a given quality.
QUALITY_COST_MULTIPLIER = {"low": 0.25, "medium": 1.0, "high": 4.0}


def tokens_for_cost_usd(cost_usd: float) -> int:
    """Red Coins to charge for a poster that cost the platform `cost_usd`."""
    return max(1, round(float(cost_usd) * POSTER_MARKUP * TOKENS_PER_USD))


def quality_multiplier(quality: str | None) -> float:
    return QUALITY_COST_MULTIPLIER.get((quality or "medium"), 1.0)


def poster_cost_usd(base_cost_usd: float, quality: str | None) -> float:
    """Platform cost for one poster at the given quality."""
    return float(base_cost_usd) * quality_multiplier(quality)


def estimate_tokens(base_cost_usd: float, quality: str | None) -> int:
    """Red Coins a poster at the given quality will cost the user."""
    return tokens_for_cost_usd(poster_cost_usd(base_cost_usd, quality))


def monthly_grant_for_tier(tier: SubscriptionTier | str | None) -> int:
    info = SUBSCRIPTION_TIERS.get(tier) or SUBSCRIPTION_TIERS[DEFAULT_TIER]
    return info.monthly_token_grant


def topup_tokens_for_usd(usd: float) -> int:
    """How many tokens a top-up of `usd` dollars buys."""
    return max(0, round(float(usd) / TOPUP_USD_PER_10K * 10_000))


def topup_usd_for_tokens(tokens: int) -> float:
    """Dollar price to top up `tokens` tokens."""
    return round(max(0, int(tokens)) / 10_000 * TOPUP_USD_PER_10K, 2)


__all__ = [
    "TOKENS_PER_USD",
    "POSTER_MARKUP",
    "TOPUP_USD_PER_10K",
    "QUALITY_COST_MULTIPLIER",
    "tokens_for_cost_usd",
    "quality_multiplier",
    "poster_cost_usd",
    "estimate_tokens",
    "monthly_grant_for_tier",
    "topup_tokens_for_usd",
    "topup_usd_for_tokens",
]
