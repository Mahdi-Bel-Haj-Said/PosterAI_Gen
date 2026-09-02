"""
Text-effect intensity: the hero title's scene integration scales with the chosen
energy level. Before this, the seven integration effects were unconditional and
marked MANDATORY, so a `balanced` poster got the same particle-and-aberration
stack as an `explosive` one.
"""

from __future__ import annotations

import random

from esports_poster_ai.prompt.assembler import build_image_style_footer, build_prompt
from esports_poster_ai.prompt.blocks.typography import (
    _GLOWING_FINISHES,
    build_typography_block,
)


def _input(energy="balanced"):
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "gameday",
            "mode": "fresh",
            "output_format": "landscape_1920x1080",
        },
        "tournament": {"name": "VXG Tunisia"},
        "match": {
            "team1": {"name": "FNATIC", "logo_path": "assets/logos/FNC.png"},
            "team2": {"name": "T1", "logo_path": "assets/logos/T1.png"},
        },
        "design": {"vibe": "cinematic", "primary_color": "#7B2FF7", "energy": energy},
    }


def test_effects_are_scaled_not_mandatory():
    out = build_prompt(_input())
    assert "TEXT EFFECT INTENSITY" in out
    # The unconditional stack is gone.
    assert "MANDATORY text integration into the scene" not in out


def test_every_energy_level_has_a_rung():
    out = build_prompt(_input())
    for level in ("chill", "balanced", "intense", "explosive"):
        assert level in out


def test_calm_levels_forbid_the_heavy_effects():
    out = build_prompt(_input())
    assert "NO chromatic aberration" in out
    assert "NO particles or sparks crossing" in out


def test_style_footer_carries_the_intensity():
    # The footer bypasses GPT-4o's rewrite, so it has to restate the rule.
    footer = build_image_style_footer(_input())
    assert "Scale the TEXT effects to that energy" in footer


def test_calm_energy_never_draws_a_glowing_finish():
    r = random.Random(0)
    for _ in range(60):
        block = build_typography_block(_input("balanced"), rng=r)
        assert not any(f in block for f in _GLOWING_FINISHES)


def test_high_energy_keeps_the_full_finish_bank():
    r = random.Random(1)
    seen = set()
    for _ in range(300):
        block = build_typography_block(_input("explosive"), rng=r)
        seen.update(f for f in _GLOWING_FINISHES if f in block)
    assert seen, "explosive energy should still reach the glowing finishes"


def test_missing_energy_defaults_to_calm_finishes():
    data = _input()
    data["design"].pop("energy")
    r = random.Random(2)
    for _ in range(60):
        block = build_typography_block(data, rng=r)
        assert not any(f in block for f in _GLOWING_FINISHES)
