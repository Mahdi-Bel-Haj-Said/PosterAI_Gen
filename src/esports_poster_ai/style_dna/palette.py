"""
Programmatic palette extraction.

Deterministic, free, fast. The vision model is bad at this — when asked to
list "5 dominant colors with hex codes" it gives approximations that drift
across runs. Median-cut quantization gives exact values, sorted by actual
frequency in the image.
"""

from __future__ import annotations

from typing import List, Tuple

from PIL import Image

from esports_poster_ai.domain.style_dna import ColorTemperature


# Resize cap for quantization input. Larger images don't make the palette
# better — they just make the call slower. 256x256 is plenty for posters.
_RESIZE_MAX = 256


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    s = hex_color.strip().lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def extract_palette(image: Image.Image, n_colors: int = 5) -> List[str]:
    """
    Extract dominant colors from a poster image.

    Args:
        image: PIL image. Any mode; will be converted to RGB internally.
        n_colors: Number of colors to return. Capped at 16 for sanity.

    Returns:
        Hex color strings sorted by descending frequency. The list may have
        fewer entries than `n_colors` for very flat images.
    """
    if n_colors <= 0:
        return []
    n_colors = min(int(n_colors), 16)

    rgb = image.convert("RGB")
    work = rgb.copy()
    work.thumbnail((_RESIZE_MAX, _RESIZE_MAX), Image.Resampling.LANCZOS)

    quantized = work.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)

    # `getpalette` is a flat [r, g, b, r, g, b, ...] list. We slice to the
    # actual number of palette entries used.
    raw_palette = quantized.getpalette() or []
    palette = [
        (raw_palette[i], raw_palette[i + 1], raw_palette[i + 2])
        for i in range(0, n_colors * 3, 3)
        if i + 2 < len(raw_palette)
    ]

    # `getcolors` returns [(count, palette_index), ...] sorted by index.
    # We re-sort by descending count so the first entry is the most-used color.
    counts = quantized.getcolors(maxcolors=n_colors * 4) or []
    counts_sorted = sorted(counts, key=lambda c: -c[0])

    seen: set = set()
    hex_palette: List[str] = []
    for _count, idx in counts_sorted:
        if 0 <= idx < len(palette) and idx not in seen:
            seen.add(idx)
            hex_palette.append(_rgb_to_hex(palette[idx]))

    # Fallback if `getcolors` somehow missed entries.
    for i, rgb_tuple in enumerate(palette):
        if i not in seen and len(hex_palette) < n_colors:
            hex_palette.append(_rgb_to_hex(rgb_tuple))

    return hex_palette[:n_colors]


def color_temperature(palette: List[str]) -> ColorTemperature:
    """
    Classify the palette as warm / cool / neutral.

    Uses the average of (R - B) across palette entries. Thresholds are
    intentionally conservative so mixed palettes land on "neutral" rather
    than being forced to one side.
    """
    if not palette:
        return "neutral"

    total = 0
    for hex_color in palette:
        try:
            r, _g, b = _hex_to_rgb(hex_color)
        except (ValueError, IndexError):
            continue
        total += r - b

    avg = total / max(len(palette), 1)

    if avg > 30:
        return "warm"
    if avg < -30:
        return "cool"
    return "neutral"


__all__ = ["extract_palette", "color_temperature"]
