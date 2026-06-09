"""Tests for stages/sponsor_bar.detect_bar_config and color/brightness helpers."""

from __future__ import annotations

from PIL import Image

from esports_poster_ai.stages.sponsor_bar import (
    _choose_bar_color,
    _logos_mean_brightness,
    detect_bar_config,
)


def _solid(width: int, height: int, color: tuple) -> Image.Image:
    """Build a solid-color RGBA image."""
    if len(color) == 3:
        color = color + (255,)
    return Image.new("RGBA", (width, height), color)


def _vertical_split(width: int, height: int, top_color: tuple, bottom_color: tuple) -> Image.Image:
    """Build a poster with two solid halves stacked top/bottom."""
    img = Image.new("RGBA", (width, height), top_color + (255,))
    bottom = Image.new("RGBA", (width, height // 2), bottom_color + (255,))
    img.paste(bottom, (0, height - height // 2))
    return img


def test_logos_mean_brightness_ignores_transparent_pixels():
    # Fully transparent black image — visible pixel count is 0, returns neutral 128.0
    transparent = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    assert _logos_mean_brightness([transparent]) == 128.0


def test_logos_mean_brightness_white_logo_returns_high():
    white = _solid(10, 10, (255, 255, 255))
    assert _logos_mean_brightness([white]) > 240


def test_logos_mean_brightness_black_logo_returns_low():
    black = _solid(10, 10, (0, 0, 0))
    assert _logos_mean_brightness([black]) < 10


def test_choose_bar_color_returns_light_for_dark_logos():
    assert _choose_bar_color("#101010", logos_brightness=20.0) == "#e8e8e8"


def test_choose_bar_color_returns_region_for_bright_logos():
    assert _choose_bar_color("#101010", logos_brightness=200.0) == "#101010"


def test_choose_bar_color_returns_region_for_midtone_logos():
    # Per current heuristic: only logos_brightness < 80 swaps to light.
    assert _choose_bar_color("#202020", logos_brightness=128.0) == "#202020"


def test_detect_bar_config_position_is_always_bottom():
    # The bar is pinned to the bottom — the prompt reserves a bottom strip.
    poster = _solid(400, 800, (10, 10, 10))
    logos = [_solid(50, 50, (255, 255, 255))]
    assert detect_bar_config(poster, logos)["position"] == "bottom"


def test_detect_bar_config_stays_bottom_even_when_top_is_emptier():
    # Top half empty/dark, bottom half busy mid-grey — bar still goes bottom.
    poster = _vertical_split(400, 800, top_color=(0, 0, 0), bottom_color=(128, 128, 128))
    logos = [_solid(50, 50, (255, 255, 255))]
    assert detect_bar_config(poster, logos)["position"] == "bottom"


def test_detect_bar_config_returns_expected_keys():
    poster = _solid(400, 800, (10, 10, 10))
    logos = [_solid(50, 50, (255, 255, 255))]
    cfg = detect_bar_config(poster, logos)
    assert set(cfg.keys()) == {
        "position",
        "height",
        "background_color",
        "opacity",
        "padding_x",
        "padding_y",
    }
    assert cfg["height"] >= 56
    assert cfg["height"] <= 88
    assert 0.55 <= cfg["opacity"] <= 0.85
    assert cfg["background_color"].startswith("#")


def test_detect_bar_config_clamps_bar_height_for_huge_logos():
    poster = _solid(400, 800, (0, 0, 0))
    huge_logo = _solid(200, 500, (255, 255, 255))
    cfg = detect_bar_config(poster, [huge_logo])
    assert cfg["height"] <= 88
