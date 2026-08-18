"""
Single source of truth for the sponsor-bar reserved strip.

Two parts of the pipeline size the sponsor bar:

  * the Pillow compositor (``stages/sponsor_bar.py``) draws the bar at exactly
    ``reserved_height_px`` (the BAR fraction) pinned to the bottom edge, and
  * the image prompt (``prompt/blocks/sponsors.py``) tells the model to leave a
    clean, EMPTY strip at the bottom — but a bit TALLER than the bar (bar +
    ``SPONSOR_PROMPT_BUFFER``).

The extra buffer is deliberate: the model only *roughly* honors the reserved
strip, and when it drifts a line of text downward that text lands on the bar.
By asking it to clear more than the bar occupies, minor drift stays in the empty
buffer ABOVE the bar instead of colliding with it. The buffer region is just
clean background (the bar sits in the lower part of the cleared strip), so a
slightly-too-tall reservation costs nothing but a little breathing room.
"""

from __future__ import annotations

from typing import Optional

# Reserved bottom strip as a fraction of poster HEIGHT, by orientation.
# Landscape posters are short, so a smaller fraction still yields a usable
# full-width bar; portrait posters are tall, so they need a larger fraction
# for the bar to read at all. This is the BAR height (what the compositor draws).
SPONSOR_RESERVED_FRACTION = {
    "landscape": 0.05,
    "square": 0.08,
    "portrait": 0.10,
}

# Extra fraction the PROMPT asks the model to clear on top of the bar height, as
# a safety margin against the model drifting text down into the bar. Only affects
# the instruction text — never the composited bar size.
SPONSOR_PROMPT_BUFFER = 0.04

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
    """Reserved-strip fraction as a whole-number percent (bar height only)."""
    return int(round(reserved_fraction_for_output_format(output_format) * 100))


def reserved_percent_for_prompt(output_format: Optional[str]) -> int:
    """
    Percent the PROMPT should tell the model to leave clear: the bar height PLUS
    the safety buffer. Larger than the composited bar on purpose, so the model
    drifting text downward doesn't land it on the bar (see module docstring).
    """
    frac = reserved_fraction_for_output_format(output_format) + SPONSOR_PROMPT_BUFFER
    return int(round(frac * 100))


def reserved_height_px(width: int, height: int) -> int:
    """Reserved-strip height in pixels for a poster of the given dimensions."""
    orientation = orientation_from_dims(width, height)
    return max(1, int(round(height * reserved_fraction(orientation))))


__all__ = [
    "SPONSOR_RESERVED_FRACTION",
    "SPONSOR_PROMPT_BUFFER",
    "orientation_from_dims",
    "orientation_from_output_format",
    "reserved_fraction",
    "reserved_fraction_for_output_format",
    "reserved_percent_for_output_format",
    "reserved_percent_for_prompt",
    "reserved_height_px",
]
