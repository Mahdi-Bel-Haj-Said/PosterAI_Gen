"""Post-processing helpers (background removal, reference-image resize, etc.)."""

from esports_poster_ai.processing.background_quality import (
    BACKGROUND_MAX_LONG_EDGE,
    BACKGROUND_MIN_SHORT_EDGE,
    BackgroundQualityError,
    BackgroundTooSmallError,
    BackgroundUnreadableError,
    validate_and_downscale_background,
)
from esports_poster_ai.processing.background_removal import (
    has_meaningful_alpha,
    remove_background,
)
from esports_poster_ai.processing.resize import (
    LOGO_MAX_DIM,
    PLAYER_MAX_DIM,
    resize_for_reference,
)

__all__ = [
    "remove_background",
    "has_meaningful_alpha",
    "resize_for_reference",
    "LOGO_MAX_DIM",
    "PLAYER_MAX_DIM",
    "validate_and_downscale_background",
    "BACKGROUND_MIN_SHORT_EDGE",
    "BACKGROUND_MAX_LONG_EDGE",
    "BackgroundQualityError",
    "BackgroundTooSmallError",
    "BackgroundUnreadableError",
]
