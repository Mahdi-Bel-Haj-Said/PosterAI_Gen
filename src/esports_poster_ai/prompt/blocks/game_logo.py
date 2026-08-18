"""
Official game-logo placement block.

When an official game logo is available (see `brand.py`), it is supplied to the
image model as a reference image, and THIS block tells the vision model
(gpt-4o) — which can actually see the background — to choose the best spot for it
and state that placement in the image prompt. That gives background-aware
placement with a pixel-accurate mark (the image model copies the provided file
rather than drawing the logo from memory). Omitted when no logo is available.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from esports_poster_ai.brand import has_game_logo
from esports_poster_ai.config import Settings, get_settings

_GAME_LABEL = {"league_of_legends": "League of Legends", "valorant": "Valorant"}


def build_game_logo_block(
    input_data: Dict[str, Any], *, settings: Optional[Settings] = None
) -> str:
    """Return the game-logo placement instruction, or "" when no logo applies."""
    s = settings or get_settings()
    meta = input_data.get("_meta") if isinstance(input_data, dict) else None
    game = (meta or {}).get("game") if isinstance(meta, dict) else None
    if not has_game_logo(game, settings=s):
        return ""

    label = _GAME_LABEL.get((game or "").strip().lower(), "game")
    return f"""
OFFICIAL GAME LOGO — MANDATORY: one of the reference input images is the official
{label} logo (a metallic gold wordmark on a transparent background). You MUST
instruct the image model to place this EXACT provided logo onto the poster so a
viewer instantly recognizes the game.
- YOU choose the placement, based on the background you can see. Pick a calm,
  uncluttered area with enough contrast for a GOLD wordmark to stay legible
  (avoid bright, busy, or already-golden regions where it would disappear).
- The logo must NOT overlap the hero title, team names, scores, dates, or any
  other text/logo, and must stay ABOVE the reserved sponsor strip at the bottom.
  Good spots are usually the upper third — top-centre, a top corner, or a clean
  band near the top.
- Keep it crisp, undistorted, correct aspect ratio, and MODEST in size: a clearly
  readable brand mark, roughly 20–35% of the poster width, not dominating the art.
- Reproduce the provided logo FAITHFULLY — do not redraw, restyle, recolor,
  re-letter, translate, or add effects to it. It is an official trademark.
- State the chosen position explicitly in your output prompt (e.g. "place the
  provided League of Legends gold wordmark logo in the upper-left, over the dark
  sky, clear of the title") so the image model renders it exactly there.
""".strip()


__all__ = ["build_game_logo_block"]
