"""
Official game-logo assets.

A per-game brand mark (e.g. the League of Legends wordmark) is supplied to the
poster pipeline as a REFERENCE image, and the vision model is instructed to place
it based on the background it sees. This keeps the mark pixel-accurate (the image
model copies the real file) while the placement stays background-aware. Both the
prompt block and the reference-image collector read the logo through here, so
they can never disagree about whether a logo is present.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from esports_poster_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)

# game (as in `_meta.game`) -> project-root-relative logo path.
_GAME_LOGOS = {
    "league_of_legends": "assets/brand/lol/wordmark.png",
    # "valorant": "assets/brand/valorant/wordmark.png",  # add when trained/served
}


def game_logo_path(game: Optional[str], *, settings: Optional[Settings] = None) -> Optional[Path]:
    """
    Path to the official logo for `game`, or None when the overlay is disabled,
    the game has no configured logo, or the file is missing. The single gate both
    the prompt block and the reference collector consult.
    """
    s = settings or get_settings()
    if not s.brand_logo_enabled:
        return None
    rel = _GAME_LOGOS.get((game or "").strip().lower())
    if not rel:
        return None
    p = (s.project_root / rel).resolve()
    if not p.is_file():
        logger.warning("brand.logo_missing", extra={"game": game, "path": str(p)})
        return None
    return p


def game_logo_bytes(game: Optional[str], *, settings: Optional[Settings] = None) -> Optional[bytes]:
    """Read the official logo bytes for `game`, or None when unavailable."""
    p = game_logo_path(game, settings=settings)
    return p.read_bytes() if p else None


def has_game_logo(game: Optional[str], *, settings: Optional[Settings] = None) -> bool:
    return game_logo_path(game, settings=settings) is not None


__all__ = ["game_logo_path", "game_logo_bytes", "has_game_logo"]
