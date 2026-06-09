"""
Background removal for uploaded assets (logos, sponsor logos, player photos).

Uses `rembg` with the small `u2netp` model — CPU-friendly (~1-2s per image,
4.7 MB model downloaded on first use) and robust across both clean logos and
busy player photos. The pipeline stays storage-backed: input is bytes, output
is PNG bytes ready for `Storage.put_bytes`.

Two short-circuits keep upload latency tight:
  1. If the input already has meaningful alpha transparency, we assume the
     user uploaded a clean PNG and return the bytes unchanged.
  2. If `rembg` fails for any reason (model load issue, malformed input),
     we log and return the original bytes — the upload must never fail
     because of background removal.

The model session is loaded lazily and cached for the process lifetime so
the FastAPI worker pays the ~1s warm-up only once.
"""

from __future__ import annotations

import io
import logging
from threading import Lock
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# Default model: small, CPU-friendly, decent across logos and photos.
DEFAULT_MODEL = "u2netp"

# An alpha sample with more than this fraction of "see-through" pixels counts
# as a meaningful transparent background -> skip the model.
_ALPHA_PROBE_TRANSPARENT_THRESHOLD = 0.02   # 2% of pixels meaningfully transparent
_ALPHA_PROBE_SAMPLE_SIZE = 128              # downsample for the probe (cheap)

_session_lock = Lock()
_session_cache: dict = {}


def _get_session(model_name: str):
    """Lazy, cached `rembg` session — pay model-load cost once per worker."""
    with _session_lock:
        sess = _session_cache.get(model_name)
        if sess is None:
            from rembg import new_session  # local import keeps import cost lazy

            sess = new_session(model_name)
            _session_cache[model_name] = sess
            logger.info("bg_removal.session_loaded", extra={"model": model_name})
        return sess


def has_meaningful_alpha(image_bytes: bytes) -> bool:
    """
    True if the image already has a real transparent background.

    Downsamples to a small probe so we don't iterate millions of pixels for
    nothing. "Meaningful" means a non-trivial fraction of the pixels are at
    least partially transparent — i.e. the user actually pre-removed the bg.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:  # noqa: BLE001 — malformed input is the caller's problem
        return False

    if "A" not in img.getbands():
        return False

    img = img.convert("RGBA")
    img.thumbnail((_ALPHA_PROBE_SAMPLE_SIZE, _ALPHA_PROBE_SAMPLE_SIZE))
    alphas = img.getchannel("A").getdata()
    n = len(alphas)
    if n == 0:
        return False

    transparent = sum(1 for a in alphas if a < 250)
    return (transparent / n) >= _ALPHA_PROBE_TRANSPARENT_THRESHOLD


def remove_background(
    image_bytes: bytes,
    *,
    model: str = DEFAULT_MODEL,
    skip_if_already_transparent: bool = True,
) -> bytes:
    """
    Return PNG bytes with the background removed.

    Args:
        image_bytes: Raw input bytes (PNG / JPEG / WEBP).
        model:      `rembg` model name. Default `u2netp` (small, CPU-friendly).
        skip_if_already_transparent: If True (default) and the input already
            has meaningful alpha, return the bytes unchanged.

    Returns:
        PNG bytes. On any error, returns `image_bytes` unchanged after logging.
    """
    if not image_bytes:
        return image_bytes

    if skip_if_already_transparent and has_meaningful_alpha(image_bytes):
        logger.info("bg_removal.skip", extra={"reason": "already transparent"})
        return image_bytes

    try:
        from rembg import remove  # lazy import to keep module-load cost low

        session = _get_session(model)
        out = remove(image_bytes, session=session)
        # `rembg.remove` returns PNG bytes (RGBA). Validate by re-opening.
        with Image.open(io.BytesIO(out)) as result:
            result.verify()
        return out
    except Exception as e:  # noqa: BLE001 — upload must not fail on this
        logger.warning(
            "bg_removal.failed",
            extra={"reason": str(e), "model": model},
        )
        return image_bytes


__all__ = ["remove_background", "has_meaningful_alpha", "DEFAULT_MODEL"]
