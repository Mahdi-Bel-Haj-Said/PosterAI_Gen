"""
Official game-logo overlay: the LoL wordmark is supplied as a reference image and
the vision model is told to place it. These tests cover the gating (LoL only, and
only when enabled) and that the logo actually reaches the reference images.
"""

from __future__ import annotations

from esports_poster_ai.brand import game_logo_bytes, game_logo_path, has_game_logo
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.modes.fresh import _extract_input_images
from esports_poster_ai.prompt.assembler import build_prompt
from esports_poster_ai.prompt.blocks.game_logo import build_game_logo_block


def _lol(poster_type="tournament_announcement"):
    return {
        "_meta": {"game": "league_of_legends", "poster_type": poster_type, "mode": "fresh",
                  "output_format": "portrait_1080x1920", "quality": "medium"},
        "tournament": {"name": "Summer Clash"},
        "design": {"vibe": "dark_fantasy", "energy": "intense"},
    }


def test_block_present_for_league_of_legends():
    assert "OFFICIAL GAME LOGO" in build_game_logo_block(_lol())


def test_block_absent_for_unconfigured_game():
    # Valorant has no logo configured yet → no block, no reference.
    assert build_game_logo_block({"_meta": {"game": "valorant"}}) == ""


def test_block_absent_when_disabled():
    off = Settings(brand_logo_enabled=False)
    assert build_game_logo_block(_lol(), settings=off) == ""


def test_assembled_prompt_includes_logo_instruction_for_lol():
    assert "OFFICIAL GAME LOGO" in build_prompt(_lol())


def test_logo_asset_resolves_and_loads():
    assert game_logo_path("league_of_legends") is not None
    assert game_logo_bytes("league_of_legends")
    assert has_game_logo("league_of_legends") is True


def test_no_logo_for_unknown_or_unconfigured_game():
    assert game_logo_path("starcraft") is None
    assert has_game_logo("valorant") is False


def test_logo_is_added_to_reference_images():
    imgs = _extract_input_images(_lol(), get_settings().project_root)
    # No team/tournament logo_path supplied here → the ONLY reference is the wordmark.
    assert len(imgs) == 1
