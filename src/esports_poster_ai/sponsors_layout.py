"""
Single source of truth for the sponsor-bar reserved strip.

Two parts of the pipeline must agree on how much room the sponsor bar takes:

  * the image prompt (``prompt/blocks/sponsors.py``) tells the model to leave a
    clean, EMPTY strip of this fraction at the bottom of the poster, and
  * the Pillow compositor (``stages/sponsor_bar.py``) draws the bar at exactly
    the same fraction afterward.

If those two numbers drift, the model clears one amount and the bar fills
another — leaving a visible gap (the model's reserved zone peeking out above a
shorter bar). Keeping the fraction here, keyed by orientation, guarantees they
line up. Tweak the percentages in one place.
"""

from __future__ import annotations

from typing import Optional

# Reserved bottom strip as a fraction of poster HEIGHT, by orientation.
# Landscape posters are short, so a smaller fraction still yields a usable
# full-width bar; portrait posters are tall, so they need a larger fraction
# for the bar to read at all.
SPONSOR_RESERVED_FRACTION = {
    "landscape": 0.05,
    "square": 0.08,
    "portrait": 0.10,
}

_DEFAULT_ORIENTATION = "portrait"


def orientation_from_dims(width: int, height: int) -> str:
    """Classify a poster by its pixel dimensions."""
    if width > height:
        return "landscape"
    if width < height:
        return "portrait"
    return "square"


def orientation_from_output_format(output_format: Optional[str]) -> str:
    """Classify from the input `_meta.output_format` literal.

    Matches on substring so it tolerates the `*_1080x1920` suffixes. Falls back
    to portrait (the most common format) when unknown/missing.
    """
    f = (output_format or "").lower()
    if "landscape" in f:
        return "landscape"
    if "square" in f:
        return "square"
    if "portrait" in f:
        return "portrait"
    return _DEFAULT_ORIENTATION


def reserved_fraction(orientation: str) -> float:
    """Reserved-strip fraction for an orientation name."""
    return SPONSOR_RESERVED_FRACTION.get(
        orientation, SPONSOR_RESERVED_FRACTION[_DEFAULT_ORIENTATION]
    )


def reserved_fraction_for_output_format(output_format: Optional[str]) -> float:
    """Reserved-strip fraction derived from an `_meta.output_format` value."""
    return reserved_fraction(orientation_from_output_format(output_format))


def reserved_percent_for_output_format(output_format: Optional[str]) -> int:
    """Reserved-strip fraction as a whole-number percent (for the prompt text)."""
    return int(round(reserved_fraction_for_output_format(output_format) * 100))


def reserved_height_px(width: int, height: int) -> int:
    """Reserved-strip height in pixels for a poster of the given dimensions."""
    orientation = orientation_from_dims(width, height)
    return max(1, int(round(height * reserved_fraction(orientation))))


__all__ = [
    "SPONSOR_RESERVED_FRACTION",
    "orientation_from_dims",
    "orientation_from_output_format",
    "reserved_fraction",
    "reserved_fraction_for_output_format",
    "reserved_percent_for_output_format",
    "reserved_height_px",
]
