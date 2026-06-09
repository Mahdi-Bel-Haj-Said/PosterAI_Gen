"""
Reference-image resizing for the image-edit call.

Each reference image fed to `gpt-image-2` is tokenized by area (roughly:
`85 + 170 × ceil(w/512) × ceil(h/512)` at $10/1M input tokens). Capping the
longest side keeps input cost predictable without throwing away the original
asset stored in R2 — the resize is done in-memory, just before the call.

Two caps, exposed as constants so they're tweakable in one place:

  - LOGO_MAX_DIM    (team / tournament logos): 512 px on the longest side.
                    Flat brand marks don't need more detail than that.
  - PLAYER_MAX_DIM  (featured / roster player photos): 1024 px on the longest
                    side. Faces need real pixels to render recognizably.

Aspect ratio is preserved — a 1024×680 input becomes 512×340 (logos) or
stays 1024×680 (players), never a square. Below the cap we pass the bytes
through unchanged.

Sponsor logos do NOT go through this helper because sponsors are composited
locally by `stages/sponsor_bar.add_sponsor_bar` (Pillow), never sent to the
image model.
"""

from __future__ import annotations

import io
import logging
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)

LOGO_MAX_DIM = 512
PLAYER_MAX_DIM = 1024


def _scaled_size(w: int, h: int, max_dim: int) -> Tuple[int, int]:
    """Compute the new (w, h) that fits inside `max_dim` while keeping ratio."""
    longest = max(w, h)
    if longest <= max_dim:
        return (w, h)
    scale = max_dim / float(longest)
    return (max(1, round(w * scale)), max(1, round(h * scale)))


def resize_for_reference(image_bytes: bytes, max_dim: int) -> bytes:
    """
    Resize an image so its longest side is at most `max_dim`, preserving aspect ratio.

    If the image is already at or below the cap, the original bytes are
    returned unchanged. On any decoding/encoding failure, returns the input
    bytes — a resize hiccup must never break the generation call.

    Output format is chosen to preserve fidelity:
      - Inputs with transparency (RGBA) -> PNG (alpha preserved).
      - Inputs without transparency      -> JPEG quality 92 (smaller bytes,
        no visible quality loss after a single downsample).
    """
    if not image_bytes or max_dim <= 0:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()  # decode now so format/mode are populated
    except Exception as e:  # noqa: BLE001
        logger.warning("resize.skip", extra={"reason": f"open failed: {e}"})
        return image_bytes

    w, h = img.size
    new_w, new_h = _scaled_size(w, h, max_dim)
    if (new_w, new_h) == (w, h):
        return image_bytes  # already within the cap

    try:
        # Normalize palette images so the resample step doesn't drop data.
        if img.mode == "P":
            img = img.convert("RGBA")

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        has_alpha = "A" in resized.getbands()
        out = io.BytesIO()
        if has_alpha:
            resized.save(out, "PNG", optimize=True)
        else:
            if resized.mode != "RGB":
                resized = resized.convert("RGB")
            resized.save(out, "JPEG", quality=92, optimize=True)

        logger.info(
            "resize.applied",
            extra={
                "from_wh": (w, h),
                "to_wh": (new_w, new_h),
                "max_dim": max_dim,
                "bytes_in": len(image_bytes),
                "bytes_out": out.tell(),
            },
        )
        return out.getvalue()
    except Exception as e:  # noqa: BLE001
        logger.warning("resize.skip", extra={"reason": f"resize failed: {e}"})
        return image_bytes


__all__ = ["resize_for_reference", "LOGO_MAX_DIM", "PLAYER_MAX_DIM"]
