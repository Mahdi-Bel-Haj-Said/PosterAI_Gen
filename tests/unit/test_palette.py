"""Tests for style_dna.palette."""

from __future__ import annotations

from PIL import Image

from esports_poster_ai.style_dna.palette import color_temperature, extract_palette


def _two_color_image(top: tuple, bottom: tuple, width: int = 100, height: int = 100) -> Image.Image:
    img = Image.new("RGB", (width, height), top)
    bottom_band = Image.new("RGB", (width, height // 2), bottom)
    img.paste(bottom_band, (0, height // 2))
    return img


def test_extract_palette_returns_n_colors_for_diverse_image():
    img = Image.new("RGB", (50, 50))
    pixels = img.load()
    palette_input = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (128, 128, 128),
    ]
    for y in range(50):
        for x in range(50):
            pixels[x, y] = palette_input[(x + y) % len(palette_input)]

    result = extract_palette(img, n_colors=5)
    assert len(result) <= 5
    assert all(isinstance(h, str) and h.startswith("#") for h in result)


def test_extract_palette_returns_one_color_for_solid_image():
    img = Image.new("RGB", (50, 50), (255, 0, 0))
    result = extract_palette(img, n_colors=5)
    # Median-cut may emit a single useful color from a flat image.
    assert len(result) >= 1
    assert result[0] in {"#ff0000", "#fe0000"}  # quantization may shift by 1


def test_extract_palette_orders_by_frequency():
    # Image that is 90% red, 10% blue. Red should be first in the result.
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    blue_band = Image.new("RGB", (100, 10), (0, 0, 255))
    img.paste(blue_band, (0, 0))
    result = extract_palette(img, n_colors=3)
    assert result[0].startswith("#ff") or result[0].startswith("#fe")


def test_extract_palette_handles_rgba():
    img = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
    result = extract_palette(img, n_colors=3)
    assert len(result) >= 1


def test_extract_palette_caps_n_colors_at_16():
    img = Image.new("RGB", (50, 50), (100, 100, 100))
    result = extract_palette(img, n_colors=500)
    assert len(result) <= 16


def test_extract_palette_returns_empty_for_zero_colors():
    img = Image.new("RGB", (50, 50), (255, 0, 0))
    assert extract_palette(img, n_colors=0) == []


def test_color_temperature_warm_for_red_palette():
    assert color_temperature(["#ff5500", "#ff8800", "#cc4400"]) == "warm"


def test_color_temperature_cool_for_blue_palette():
    assert color_temperature(["#0055ff", "#1188ff", "#0044cc"]) == "cool"


def test_color_temperature_neutral_for_balanced_palette():
    # Roughly equal R and B should land on neutral.
    assert color_temperature(["#808080", "#7a7a7a", "#909090"]) == "neutral"


def test_color_temperature_empty_palette_is_neutral():
    assert color_temperature([]) == "neutral"


def test_color_temperature_tolerates_malformed_entries():
    # The malformed entry is skipped; the rest still classifies as warm.
    assert color_temperature(["#ff0000", "bogus", "#cc4400"]) == "warm"
