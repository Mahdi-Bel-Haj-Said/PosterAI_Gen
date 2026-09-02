"""
Layout-pattern selection: the vision model must commit to ONE of ten named
composition patterns, chosen from the poster format, the amount of content, and
the background. These tests cover the block itself (all ten patterns offered,
the orientation stated) and that it reaches the assembled prompt in both modes.
"""

from __future__ import annotations

import pytest

from esports_poster_ai.prompt.assembler import build_prompt
from esports_poster_ai.prompt.blocks.layout import build_layout_block


def _gameday(output_format="portrait_1080x1920"):
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "gameday",
            "mode": "fresh",
            "output_format": output_format,
        },
        "tournament": {"name": "EWC 2025"},
        "match": {
            "team1": {"name": "FNATIC", "logo_path": "assets/logos/FNC.png"},
            "team2": {"name": "T1", "logo_path": "assets/logos/T1.png"},
        },
        "design": {"vibe": "cyberpunk", "energy": "intense"},
    }


def test_block_offers_all_ten_patterns():
    out = build_layout_block(_gameday())
    for name in (
        "Hero + Supporting",
        "Diagonal Action",
        "Center-Focal",
        "Modular (Bento) Grid",
        "Radial (Circular)",
        "Progressive (Timeline / List)",
        "Collision (Overlapping)",
        "Negative-Space Hero",
        "Broken Grid (Asymmetrical)",
        "Repetition (Patterned)",
    ):
        assert name in out


def test_block_demands_exactly_one_pattern():
    out = build_layout_block(_gameday())
    assert "pick exactly ONE" in out
    assert "Never blend" in out


@pytest.mark.parametrize(
    "output_format,expected",
    [
        ("portrait_1080x1920", "portrait (tall)"),
        ("square_1080x1080", "square"),
        ("landscape_1920x1080", "landscape (wide)"),
    ],
)
def test_block_states_the_poster_format(output_format, expected):
    assert expected in build_layout_block(_gameday(output_format))


def test_missing_output_format_falls_back_to_portrait():
    assert "portrait (tall)" in build_layout_block({"_meta": {}})


def test_assembled_prompt_carries_the_pattern_menu_and_output_slot():
    out = build_prompt(_gameday())
    assert "STEP 2.5 — CHOOSE THE LAYOUT PATTERN" in out
    # The chosen pattern must be named in the output prompt, so it survives
    # through to gpt-image-2 rather than staying in the vision model's head.
    assert "LAYOUT PATTERN:" in out


def test_present_in_consistency_mode_too():
    # Layout is not carried by the Style DNA, so the choice still has to be made.
    dna = {"palette": ["#101820", "#FF5C00"], "lighting": "hard rim light"}
    out = build_prompt(_gameday(), style_dna=dna)
    assert "STEP 2.5 — CHOOSE THE LAYOUT PATTERN" in out
