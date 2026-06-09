"""
Tests for processing/background_quality — upload-time quality gate for
user-uploaded background images.

Two behaviors under test:
  1. Reject anything below HD (min(w, h) < 720).
  2. Aspect-preserving downscale anything above 2K (max(w, h) > 2048).

We use synthetic in-memory PIL images instead of fixture files so the suite
stays self-contained and fast.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from esports_poster_ai.processing.background_quality import (
    BACKGROUND_MAX_LONG_EDGE,
    BACKGROUND_MIN_SHORT_EDGE,
    BackgroundTooSmallError,
    BackgroundUnreadableError,
    validate_and_downscale_background,
)


# ---- helpers ---------------------------------------------------------------


def _png_bytes(size: tuple[int, int], mode: str = "RGB", color=(40, 40, 40)) -> bytes:
    """Encode a solid-color image at the requested size as PNG."""
    img = Image.new(mode, size, color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _jpeg_bytes(size: tuple[int, int], color=(40, 40, 40)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _decode_size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


# ---- minimum-resolution gate -----------------------------------------------


@pytest.mark.parametrize(
    "size",
    [
        (640, 480),    # VGA — well below 720
        (800, 600),    # SVGA — well below
        (1280, 700),   # HD-ish but short edge 700 < 720
        (700, 1280),   # portrait counterpart of the above
        (719, 1080),   # one pixel below threshold — boundary guard
        (500, 500),    # square sub-HD
    ],
)
def test_below_hd_short_edge_is_rejected(size):
    data = _png_bytes(size)
    with pytest.raises(BackgroundTooSmallError):
        validate_and_downscale_background(data)


@pytest.mark.parametrize(
    "size",
    [
        (1280, 720),    # HD lower bound (boundary)
        (720, 1280),    # portrait HD
        (1024, 768),    # XGA — short edge 768 > 720, accepted
        (1920, 1080),   # FHD landscape
        (1080, 1920),   # FHD portrait
        (1080, 1080),   # square FHD
        (720, 720),     # square HD lower bound
    ],
)
def test_at_or_above_hd_short_edge_is_accepted(size):
    data = _png_bytes(size)
    out, ct = validate_and_downscale_background(data)
    # At/under the 2K cap so it should be a clean pass-through.
    assert out == data
    assert ct == "image/png"


# ---- downscale gate --------------------------------------------------------


def test_2k_landscape_passes_through():
    """An image whose long edge equals the cap is left untouched."""
    data = _png_bytes((2048, 1080))
    out, _ct = validate_and_downscale_background(data)
    assert out == data


def test_4k_landscape_downscales_to_2k_keeping_aspect():
    """3840×2160 (16:9) → ~2048×1152, aspect preserved within 1px."""
    data = _png_bytes((3840, 2160))
    out, ct = validate_and_downscale_background(data)
    assert out != data
    w, h = _decode_size(out)
    assert max(w, h) == BACKGROUND_MAX_LONG_EDGE
    # Source aspect = 16:9 = 1.777…  Allow ±0.01 to absorb integer rounding.
    assert abs((w / h) - (3840 / 2160)) < 0.01
    # No transparency in the source → JPEG re-encode.
    assert ct == "image/jpeg"


def test_8k_portrait_downscales_to_2k_keeping_aspect():
    """4320×7680 (9:16 portrait) — the long edge is the height now."""
    data = _png_bytes((4320, 7680))
    out, _ct = validate_and_downscale_background(data)
    w, h = _decode_size(out)
    assert max(w, h) == BACKGROUND_MAX_LONG_EDGE
    assert h > w  # orientation preserved
    assert abs((w / h) - (4320 / 7680)) < 0.01


def test_oversized_square_downscales_to_cap():
    """An exact square > cap → square at the cap."""
    data = _png_bytes((3000, 3000))
    out, _ct = validate_and_downscale_background(data)
    w, h = _decode_size(out)
    assert (w, h) == (BACKGROUND_MAX_LONG_EDGE, BACKGROUND_MAX_LONG_EDGE)


def test_downscale_preserves_alpha_as_png():
    """RGBA source must come back as PNG (alpha would be lost in JPEG)."""
    data = _png_bytes((4000, 2000), mode="RGBA", color=(40, 40, 40, 128))
    out, ct = validate_and_downscale_background(data)
    assert ct == "image/png"
    # PNG magic header — quick sanity check the encoder picked PNG.
    assert out.startswith(b"\x89PNG")


def test_downscale_jpeg_source_returns_jpeg():
    """Opaque JPEG source should be re-encoded as JPEG (smaller, no alpha)."""
    data = _jpeg_bytes((4000, 2250))
    out, ct = validate_and_downscale_background(data)
    assert ct == "image/jpeg"
    assert out[:2] == b"\xff\xd8"  # JPEG SOI marker


# ---- error surface --------------------------------------------------------


def test_empty_payload_is_unreadable():
    with pytest.raises(BackgroundUnreadableError):
        validate_and_downscale_background(b"")


def test_garbage_bytes_are_unreadable():
    with pytest.raises(BackgroundUnreadableError):
        validate_and_downscale_background(b"not an image at all")


# ---- overridable thresholds -----------------------------------------------


def test_custom_thresholds_apply():
    """Caller can tighten / loosen the gates per call without monkey-patching."""
    data = _png_bytes((1000, 800))
    # Tighter floor — 800 short edge is now below the gate.
    with pytest.raises(BackgroundTooSmallError):
        validate_and_downscale_background(data, min_short_edge=900)
    # Tighter cap — long edge 1000 > 600, should downscale.
    out, _ct = validate_and_downscale_background(data, max_long_edge=600)
    w, h = _decode_size(out)
    assert max(w, h) == 600


def test_threshold_constants_are_sensible():
    """Loud regression guard — if someone bumps the numbers, this test trips."""
    assert BACKGROUND_MIN_SHORT_EDGE == 720
    assert BACKGROUND_MAX_LONG_EDGE == 2048
