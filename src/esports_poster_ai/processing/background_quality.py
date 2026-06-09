"""
Background-asset quality gate.

Applied at upload time (``POST /v1/assets`` with ``asset_type=background``),
this module guards two things:

  1. Minimum resolution — anything smaller than HD on the SHORTER edge is
     rejected with a typed error. The cost stack downstream is dominated by
     the image-generation call; a 640×480 JPEG that ends up as a poster
     canvas means the user paid for a generation that was visually weak from
     the start. Better to fail fast at upload.

  2. Maximum resolution — anything larger than ~2K on the LONGER edge is
     downscaled, aspect-preserving, before persistence. ``gpt-image-2``
     tokenizes input images by area; a 7680×4320 (8K) background uses ~16×
     the input tokens of a 1920×1080 background for no visible benefit
     (the model rasterizes onto a 1024 or 1536-wide canvas anyway).
     Capping at 2K keeps per-generation cost predictable without throwing
     away the artistic detail the user uploaded.

Thresholds are module constants so they're tunable in one place. The shape
mirrors ``processing/resize.py`` (logos / players) intentionally.

The downscale path also normalises the encoded format:
  * Inputs with transparency  -> PNG (alpha preserved).
  * Inputs without transparency -> JPEG quality 92 (smaller bytes, no
    visible quality loss from a single Lanczos downsample).

Rationale for the specific numbers
----------------------------------
  * ``BACKGROUND_MIN_SHORT_EDGE = 720`` — the bottom of the HD ladder.
    Accepts 1280×720, 1920×1080, 720×1280 (portrait HD), 1080×1080 (square),
    and anything above. Rejects 640×480 (VGA), 800×600 (SVGA), 1024×768
    (XGA) — none of which would survive a poster-grade composite.

  * ``BACKGROUND_MAX_LONG_EDGE = 2048`` — DCI 2K. Two-megapixel-ish, more
    than enough texture for the image-edit model to harvest, much cheaper
    in tokens than 4K (3840) or 8K (7680). 1920×1080 and 1080×1920 stay
    untouched; 3840×2160 becomes 2048×1152; 7680×4320 becomes 2048×1152.
"""

from __future__ import annotations

import io
import logging
from typing import Tuple

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# --- Public thresholds -------------------------------------------------------

BACKGROUND_MIN_SHORT_EDGE = 720
"""Reject any uploaded background whose shorter side is below this."""

BACKGROUND_MAX_LONG_EDGE = 2048
"""Downscale (aspect-preserving) any background whose longer side exceeds this."""


# --- Exceptions --------------------------------------------------------------


class BackgroundQualityError(ValueError):
    """Base class — anything wrong with the uploaded background bytes."""


class BackgroundTooSmallError(BackgroundQualityError):
    """The image is below the HD minimum and should not be accepted."""


class BackgroundUnreadableError(BackgroundQualityError):
    """The bytes couldn't be parsed as an image at all."""


# --- Helpers -----------------------------------------------------------------


def _scaled_size(w: int, h: int, max_long_edge: int) -> Tuple[int, int]:
    """
    Return the (w, h) that fits inside ``max_long_edge`` on the longer side
    while preserving aspect ratio. Pass-through if already within the cap.
    """
    longest = max(w, h)
    if longest <= max_long_edge:
        return (w, h)
    scale = max_long_edge / float(longest)
    return (max(1, round(w * scale)), max(1, round(h * scale)))


def _open_image_strict(image_bytes: bytes) -> Image.Image:
    """
    Decode ``image_bytes`` or raise BackgroundUnreadableError.

    Unlike the resize helper (which silently passes bytes through on a
    decode failure), the quality gate has to fail loudly — we cannot
    validate or downscale what we can't decode, and an unreadable upload
    should produce a clean 400 at the API edge, not slip into storage.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        return img
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BackgroundUnreadableError(
            f"Could not decode the uploaded file as an image: {exc}"
        ) from exc


# --- Public surface ----------------------------------------------------------


def validate_and_downscale_background(
    image_bytes: bytes,
    *,
    content_type_hint: str = "image/png",
    min_short_edge: int = BACKGROUND_MIN_SHORT_EDGE,
    max_long_edge: int = BACKGROUND_MAX_LONG_EDGE,
) -> Tuple[bytes, str]:
    """
    Validate then (if needed) downscale an uploaded background image.

    Returns ``(bytes, content_type)``:
      * unchanged input bytes + the supplied ``content_type_hint`` when the
        image already lies in the [min_short_edge, max_long_edge] window;
      * freshly-encoded bytes + the matching content-type (`image/png` if
        the source had alpha, `image/jpeg` otherwise) after a Lanczos
        downscale when ``max(w, h) > max_long_edge``.

    Raises
    ------
    BackgroundTooSmallError
        ``min(w, h) < min_short_edge``. Caller should map to HTTP 422.
    BackgroundUnreadableError
        The bytes are not a valid image. Caller should map to HTTP 400.

    Both exceptions subclass ``BackgroundQualityError`` for catch-all sites.
    """
    if not image_bytes:
        raise BackgroundUnreadableError("Empty image payload.")

    img = _open_image_strict(image_bytes)
    w, h = img.size

    # ---- Minimum-quality gate ----------------------------------------------
    if min(w, h) < min_short_edge:
        raise BackgroundTooSmallError(
            "Background must be at least "
            f"{min_short_edge}px on the shorter side "
            f"(uploaded {w}×{h}). Please upload an HD-or-better image so the "
            "model has enough detail to work with."
        )

    # ---- Downscale path ----------------------------------------------------
    new_w, new_h = _scaled_size(w, h, max_long_edge)
    if (new_w, new_h) == (w, h):
        # Already within the cap — pass-through, no re-encode.
        logger.debug(
            "background_quality.passthrough",
            extra={"size": (w, h), "min_short_edge": min_short_edge, "max_long_edge": max_long_edge},
        )
        return image_bytes, content_type_hint

    # Palette images lose data on resize unless we promote them first.
    if img.mode == "P":
        img = img.convert("RGBA")
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    has_alpha = "A" in resized.getbands()
    out = io.BytesIO()
    if has_alpha:
        resized.save(out, "PNG", optimize=True)
        out_ct = "image/png"
    else:
        if resized.mode != "RGB":
            resized = resized.convert("RGB")
        resized.save(out, "JPEG", quality=92, optimize=True)
        out_ct = "image/jpeg"

    encoded = out.getvalue()
    logger.info(
        "background_quality.downscaled",
        extra={
            "from_wh": (w, h),
            "to_wh": (new_w, new_h),
            "bytes_in": len(image_bytes),
            "bytes_out": len(encoded),
            "out_content_type": out_ct,
        },
    )
    return encoded, out_ct


__all__ = [
    "BACKGROUND_MIN_SHORT_EDGE",
    "BACKGROUND_MAX_LONG_EDGE",
    "BackgroundQualityError",
    "BackgroundTooSmallError",
    "BackgroundUnreadableError",
    "validate_and_downscale_background",
]
