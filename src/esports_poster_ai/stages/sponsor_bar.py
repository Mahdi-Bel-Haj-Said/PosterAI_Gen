"""
Automatic sponsor bar overlay.

Composites a sponsor bar INSIDE the poster canvas (no resize). All logos
are RGBA with transparency preserved.

NOTE — doc drift with project_overview.md:
The doc describes a WCAG binary search on opacity in [0.20, 0.60]. The
actual implementation uses a simpler dark-logos-on-light-bar heuristic and
sets opacity in [0.55, 0.85] based on region brightness. The code is the
source of truth; the doc should be updated next pass.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

from esports_poster_ai.sponsors_layout import reserved_height_px

logger = logging.getLogger(__name__)


def _load_logos(logos_cfg: List[dict]) -> List[Image.Image]:
    """
    Load sponsor logos from config; bad entries are skipped with a warning.

    Each entry is a dict carrying either:
      - ``bytes``: raw image bytes (API runs — logos come from object storage), or
      - ``path``:  a local filesystem path (CLI runs).
    Bytes take precedence so the pipeline can stay storage-backed end-to-end.
    """
    logos: List[Image.Image] = []
    for item in logos_cfg or []:
        if not isinstance(item, dict):
            logger.warning("sponsors.skip", extra={"reason": "bad entry"})
            continue

        data = item.get("bytes")
        if data:
            try:
                logos.append(Image.open(BytesIO(data)).convert("RGBA"))
            except Exception as e:  # noqa: BLE001
                logger.warning("sponsors.skip", extra={"reason": "open bytes failed", "error": str(e)})
            continue

        path = item.get("path")
        if not path:
            logger.warning("sponsors.skip", extra={"reason": "no path/bytes"})
            continue

        p = Path(path)
        if not p.exists():
            logger.warning("sponsors.skip", extra={"reason": "not found", "path": str(p)})
            continue

        try:
            logos.append(Image.open(p).convert("RGBA"))
        except Exception as e:  # noqa: BLE001
            logger.warning("sponsors.skip", extra={"reason": "open failed", "path": str(p), "error": str(e)})

    return logos


def _logos_mean_brightness(logos: list) -> float:
    """
    Mean brightness of all non-transparent pixels across all logos.
    Pixels with alpha < 10 are ignored. Returns 128.0 if no visible pixels.
    """
    total, count = 0.0, 0
    for logo in logos:
        for r, g, b, a in logo.getdata():
            if a >= 10:
                total += (r + g + b) / 3
                count += 1
    return total / count if count > 0 else 128.0


def _choose_bar_color(region_hex: str, logos_brightness: float) -> str:
    """
    Pick a bar background that contrasts with the logos.

    - logos_brightness < 80  → dark/black logos → return light bar "#e8e8e8"
    - otherwise              → return the sampled region color unchanged
    """
    if logos_brightness < 80:
        return "#e8e8e8"
    return region_hex


def _mean_brightness(region: Image.Image) -> float:
    rgb = region.convert("RGB")
    stat = ImageStat.Stat(rgb)
    mean = stat.mean[:3]
    return float(sum(mean) / 3.0)


def _sample_and_darken(region: Image.Image, darken_factor: float = 0.30) -> str:
    """Sample region average color and darken each channel by `darken_factor`."""
    avg = region.convert("RGB").resize((1, 1), resample=Image.Resampling.LANCZOS)
    r, g, b = avg.getpixel((0, 0))
    r = int(r * darken_factor)
    g = int(g * darken_factor)
    b = int(b * darken_factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_to_rgba(hex_color: str, opacity: float) -> Tuple[int, int, int, int]:
    s = (hex_color or "").strip().lstrip("#")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    a = int(max(0.0, min(opacity, 1.0)) * 255)
    return (r, g, b, a)


def _scale_logos(logos: List[Image.Image], max_logo_height: int) -> List[Image.Image]:
    out: List[Image.Image] = []
    for logo in logos:
        if logo.height > max_logo_height and logo.height > 0:
            ratio = max_logo_height / float(logo.height)
            new_w = int(logo.width * ratio)
            resized = logo.resize((max(new_w, 1), max_logo_height), resample=Image.Resampling.LANCZOS)
            out.append(resized.convert("RGBA"))
        else:
            out.append(logo.convert("RGBA"))
    return out


def _build_linear_bar_gradient(
    width: int, height: int, base_rgb: Tuple[int, int, int], opacity: float
) -> Image.Image:
    """Horizontal gradient: edges lighter + more transparent, center darker."""
    r0, g0, b0 = base_rgb

    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = gradient.load()

    half = max(width / 2.0, 1.0)
    edge_lighten = 1.18
    center_darken = 0.75

    center_alpha = int(max(0.0, min(opacity, 1.0)) * 255)
    edge_alpha = int(center_alpha * 0.1)  # 90% transparent at edges

    for x in range(width):
        t = abs((x + 0.5) - half) / half

        factor = center_darken + (edge_lighten - center_darken) * t

        rr = max(0, min(255, int(r0 * factor)))
        gg = max(0, min(255, int(g0 * factor)))
        bb = max(0, min(255, int(b0 * factor)))

        a = int(center_alpha - (center_alpha - edge_alpha) * t)

        for y in range(height):
            px[x, y] = (rr, gg, bb, a)

    return gradient


def _is_black_logo(logo: Image.Image) -> bool:
    visible = 0
    dark = 0
    total_luma = 0.0
    for r, g, b, a in logo.getdata():
        if a < 12:
            continue
        visible += 1
        luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
        total_luma += luma
        if luma < 65:
            dark += 1

    if visible == 0:
        return False

    mean_luma = total_luma / visible
    dark_ratio = dark / float(visible)
    return mean_luma < 85 and dark_ratio > 0.60


def _style_logo_with_effects(logo: Image.Image, logo_opacity: float = 0.90) -> Image.Image:
    """Apply 90% logo opacity + soft drop shadow + subtle glow (or white outline for black logos)."""
    src = logo.convert("RGBA")
    alpha = src.getchannel("A").point(
        lambda p: int(max(0, min(255, p * max(0.0, min(logo_opacity, 1.0)))))
    )
    src = src.copy()
    src.putalpha(alpha)

    padding = 8
    shadow_offset = (0, 3)
    canvas_w = src.width + padding * 2
    canvas_h = src.height + padding * 2 + shadow_offset[1]
    out = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    shadow_alpha = src.getchannel("A").point(lambda p: int(p * 0.45))
    shadow = Image.new("RGBA", src.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    out.alpha_composite(shadow, (padding + shadow_offset[0], padding + shadow_offset[1]))

    alpha_channel = src.getchannel("A")
    black_logo = _is_black_logo(src)

    if black_logo:
        dilated = alpha_channel.filter(ImageFilter.MaxFilter(3))
        outline_mask = ImageChops.subtract(dilated, alpha_channel).filter(ImageFilter.GaussianBlur(1))
        outline_mask = outline_mask.point(lambda p: int(p * 0.85))
        outline = Image.new("RGBA", src.size, (255, 255, 255, 0))
        outline.putalpha(outline_mask)
        out.alpha_composite(outline, (padding, padding))

        halo_alpha = dilated.filter(ImageFilter.GaussianBlur(1)).point(lambda p: int(p * 0.20))
        halo = Image.new("RGBA", src.size, (255, 255, 255, 0))
        halo.putalpha(halo_alpha)
        out.alpha_composite(halo, (padding, padding))
    else:
        glow_alpha = alpha_channel.point(lambda p: int(p * 0.18))
        glow = Image.new("RGBA", src.size, (255, 255, 255, 0))
        glow.putalpha(glow_alpha)
        glow = glow.filter(ImageFilter.GaussianBlur(2))
        out.alpha_composite(glow, (padding, padding))

    out.alpha_composite(src, (padding, padding))
    return out


def _build_bar_surface(
    poster_w: int,
    bar_height: int,
    bg_color_hex: str,
    opacity: float,
    scaled_logos: List[Image.Image],
    padding_x: int,
    padding_y: int,
) -> Image.Image:
    bar = Image.new("RGBA", (poster_w, bar_height), (0, 0, 0, 0))

    bg_rgba = _hex_to_rgba(bg_color_hex, opacity)
    bg = _build_linear_bar_gradient(
        width=poster_w,
        height=bar_height,
        base_rgb=(bg_rgba[0], bg_rgba[1], bg_rgba[2]),
        opacity=opacity,
    )
    bar.alpha_composite(bg)

    styled_logos = [_style_logo_with_effects(logo, logo_opacity=0.90) for logo in scaled_logos]
    n = len(styled_logos)
    if n == 0:
        return bar

    logo_gap = max(32, int(poster_w * 0.04))

    total_logos_width = sum(logo.width for logo in styled_logos)
    total_group_width = total_logos_width + logo_gap * (n - 1)

    x = (poster_w - total_group_width) // 2

    draw = ImageDraw.Draw(bar, "RGBA")
    divider_color = (255, 255, 255, 72)

    glow_layer = Image.new("RGBA", bar.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer, "RGBA")

    for i, logo in enumerate(styled_logos):
        logo_y = (bar_height - logo.height) // 2
        bar.alpha_composite(logo, (x, logo_y))

        if i < n - 1:
            divider_x = x + logo.width + (logo_gap // 2)

            glow_draw.line(
                [(divider_x, padding_y), (divider_x, bar_height - padding_y)],
                fill=(255, 255, 255, 100),
                width=3,
            )

            draw.line(
                [(divider_x, padding_y), (divider_x, bar_height - padding_y)],
                fill=divider_color,
                width=1,
            )

        x += logo.width + logo_gap

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(2))
    bar.alpha_composite(glow_layer)

    return bar


def detect_bar_config(poster: Image.Image, logos: List[Image.Image]) -> dict:
    """
    Pick how to draw the sponsor bar.

    The bar always sits at the BOTTOM of the poster: when sponsors are enabled,
    the image prompt reserves a clean bottom strip for it (see
    prompt/blocks/sponsors.py), so the bar placement is pinned to match.

    Returns a dict: position, height, background_color, opacity, padding_x, padding_y.
    """
    w, h = poster.size

    region_h = max(1, int(h * 0.15))
    bottom_region = poster.crop((0, h - region_h, w, h))
    position = "bottom"

    # Bar height = the reserved fraction the prompt told the model to clear
    # (orientation-based: landscape 5% / square 8% / portrait 10%). Logos scale
    # to fit inside it. This pins the bar to the exact strip the image model
    # left empty, so the two always line up. See sponsors_layout.py.
    bar_height = reserved_height_px(w, h)
    padding_y = max(8, int(bar_height * 0.22))

    winning_region = bottom_region
    bg_color_hex = _sample_and_darken(winning_region, darken_factor=0.30)
    logos_brightness = _logos_mean_brightness(logos)
    bg_color_hex = _choose_bar_color(bg_color_hex, logos_brightness)

    mean_b = _mean_brightness(winning_region)
    opacity = 0.55 + (mean_b / 255.0) * 0.30
    opacity = max(0.55, min(opacity, 0.85))
    opacity = round(opacity, 2)

    padding_x = max(24, int(w * 0.03))

    return {
        "position": position,
        "height": bar_height,
        "background_color": bg_color_hex,
        "opacity": opacity,
        "padding_x": padding_x,
        "padding_y": padding_y,
    }


def add_sponsor_bar(poster: Image.Image, sponsors_config: dict) -> Image.Image:
    """
    Composite a sponsor bar inside the poster canvas.

    Args:
        poster: Source poster image.
        sponsors_config: {"enabled": bool, "logos": [{"path": "..."}, ...]}

    Returns:
        New opaque RGB poster with the bar drawn, or the original poster
        unchanged if sponsors are disabled / no valid logos.
    """
    if not (sponsors_config or {}).get("enabled", False):
        return poster

    logos_cfg = (sponsors_config or {}).get("logos", [])
    logos = _load_logos(logos_cfg)
    if not logos:
        logger.warning("sponsors.disabled", extra={"reason": "no valid logos"})
        return poster

    cfg = detect_bar_config(poster, logos)
    logger.info("sponsors.config", extra=cfg)

    max_logo_h = max(1, cfg["height"] - (cfg["padding_y"] * 2))
    scaled = _scale_logos(logos, max_logo_h)

    n = len(scaled)
    logo_gap = max(32, int(poster.width * 0.04))
    effect_extra_w_per_logo = 16
    total_w = sum(img.width for img in scaled) + (effect_extra_w_per_logo * n)
    total_group_w = total_w + logo_gap * max(0, n - 1)
    if total_group_w > poster.width and total_w > 0:
        max_total_logo_w = max(1, poster.width - logo_gap * max(0, n - 1))
        ratio = max_total_logo_w / float(total_w)
        resized: List[Image.Image] = []
        for img in scaled:
            new_w = max(1, int(img.width * ratio))
            new_h = max(1, int(img.height * ratio))
            resized.append(img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS).convert("RGBA"))
        scaled = resized

    bar_surface = _build_bar_surface(
        poster_w=poster.width,
        bar_height=cfg["height"],
        bg_color_hex=cfg["background_color"],
        opacity=cfg["opacity"],
        scaled_logos=scaled,
        padding_x=cfg["padding_x"],
        padding_y=cfg["padding_y"],
    )

    result = poster.convert("RGBA").copy()
    # The bar is pinned to the bottom — the prompt reserves a bottom strip.
    y = result.height - cfg["height"]
    result.paste(bar_surface, (0, y), bar_surface)

    # Flatten to RGB: pasting the semi-transparent bar drops the destination
    # alpha below 255 in the bar region. The blended RGB is correct, but a
    # partially transparent PNG shows a checkerboard in viewers. A poster is a
    # final, fully opaque deliverable — discard the alpha channel.
    return result.convert("RGB")
