"""
Tournament-logo fidelity.

The tournament logo is supplied as a real reference image, but the prompt used to
say only "Apply scene lighting" and never that the mark must be reproduced as
given — so the image model restyled it. The official game wordmark already had
faithful-reproduction language; this brings the tournament logo in line.
"""

from __future__ import annotations

from esports_poster_ai.prompt.assembler import build_prompt
from esports_poster_ai.prompt.blocks.assets import build_asset_block


def _gameday(tournament_logo="assets/logos/vxg.png"):
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "gameday",
            "mode": "fresh",
            "output_format": "landscape_1920x1080",
        },
        "tournament": {"name": "VXG Tunisia", "logo_path": tournament_logo},
        "match": {
            "team1": {"name": "FNATIC", "logo_path": "assets/logos/FNC.png"},
            "team2": {"name": "T1", "logo_path": "assets/logos/T1.png"},
        },
        "design": {"vibe": "cinematic", "energy": "balanced"},
    }


def test_restyling_licence_is_gone():
    out = build_prompt(_gameday())
    assert "Smaller than team logos. Apply scene lighting." not in out


def test_tournament_logo_must_be_reproduced_exactly():
    out = build_prompt(_gameday())
    assert "Reproduce it EXACTLY as given" in out
    assert "not artwork to reinterpret" in out


def test_brightness_match_is_still_allowed():
    # It must not read as pasted on — the logo just must not be redrawn.
    out = build_prompt(_gameday())
    assert "brightness match only" in out


def test_asset_block_repeats_the_rule_when_a_logo_is_supplied():
    block = build_asset_block(_gameday())
    assert "Reproduce it EXACTLY as given" in block


def test_asset_block_unchanged_when_no_logo_supplied():
    block = build_asset_block(_gameday(tournament_logo=""))
    assert "use stylized tournament text only" in block
    assert "Reproduce it EXACTLY" not in block


def test_global_do_not_covers_every_provided_logo():
    out = build_prompt(_gameday())
    assert "ANY provided logo (team, tournament, or game wordmark)" in out


def test_team_logo_scene_integration_is_left_intact():
    # Team logos already render acceptably — that guidance must not regress.
    out = build_prompt(_gameday())
    assert "Apply subtle rim glow matching" in out
