"""Tests for prompt/keyart.build_keyart_prompt (background LoRA prompt).

The grammar mirrors the real training captions:
    <trigger>, <scene>, <c1> and <c2> palette, <m1> and <m2> mood,
    cinematic esports key art, highly detailed, <vibe>, <energy>
"""

from __future__ import annotations

import re

import pytest

from esports_poster_ai.prompt.keyart import (
    NEGATIVE_PROMPT,
    build_keyart_prompt,
)


def _input(*, game="league_of_legends", output_format="portrait_1080x1920", design=None) -> dict:
    return {
        "_meta": {
            "game": game,
            "poster_type": "gameday",
            "mode": "fresh",
            "output_format": output_format,
        },
        "design": design if design is not None else {
            "vibe": "dark_fantasy",
            "primary_color": "#8C1419",
            "energy": "intense",
        },
    }


def test_trigger_and_lora_per_game():
    lol = build_keyart_prompt(_input(game="league_of_legends"), seed=1)
    val = build_keyart_prompt(_input(game="valorant"), seed=1)
    assert lol.trigger == "lol_keyart" and lol.lora == "lol_keyart"
    assert val.trigger == "valo_keyart" and val.lora == "valo_keyart"


def test_prompt_starts_with_trigger():
    out = build_keyart_prompt(_input(), seed=7)
    assert out.prompt.startswith("lol_keyart, ")


def test_prompt_ends_with_raw_vibe_and_energy_tokens():
    # The single most important fix: vibe + energy are raw trailing tokens.
    out = build_keyart_prompt(
        _input(design={"vibe": "dark_fantasy", "energy": "explosive"}), seed=7
    )
    assert out.prompt.endswith(
        "cinematic esports key art, highly detailed, dark_fantasy, explosive"
    )


def test_palette_slot_uses_word_and_word_form():
    out = build_keyart_prompt(_input(), seed=3).prompt
    assert re.search(r", [^,]+ and [^,]+ palette, ", out)


def test_mood_slot_uses_two_adjectives():
    out = build_keyart_prompt(_input(), seed=3).prompt
    assert re.search(r", \w+ and \w+ mood, ", out)


def test_hex_primary_color_is_converted_to_a_word():
    # #8C1419 is a deep blood red -> nearest named color word, never a hex.
    out = build_keyart_prompt(
        _input(design={"vibe": "dark_fantasy", "primary_color": "#8C1419", "energy": "intense"}),
        seed=3,
    ).prompt
    assert "#" not in out
    assert "palette" in out


def test_word_primary_color_passes_through():
    out = build_keyart_prompt(
        _input(design={"vibe": "dark_fantasy", "primary_color": "blood red", "energy": "intense"}),
        seed=3,
    ).prompt
    assert "blood red and" in out


def test_no_primary_color_falls_back_to_vibe_palette():
    out = build_keyart_prompt(
        _input(game="valorant", design={"vibe": "cyberpunk", "energy": "explosive"}),
        seed=3,
    ).prompt
    assert "palette" in out and "#" not in out


def test_negative_prompt_leads_with_text_free_terms():
    out = build_keyart_prompt(_input(), seed=1)
    assert out.negative_prompt == NEGATIVE_PROMPT
    assert out.negative_prompt.startswith("text,")
    for term in ("watermark", "logo", "typography"):
        assert term in out.negative_prompt


def test_no_composition_or_text_phrasing_in_prompt():
    out = build_keyart_prompt(_input(), seed=9).prompt.lower()
    for banned in ("negative space", "empty zone", "watermark", "text", "logo"):
        assert banned not in out


def test_same_seed_is_deterministic():
    assert build_keyart_prompt(_input(), seed=42) == build_keyart_prompt(_input(), seed=42)


def test_different_seeds_can_vary_the_prompt():
    prompts = {build_keyart_prompt(_input(), seed=s).prompt for s in range(12)}
    assert len(prompts) > 1


def test_missing_seed_is_generated_and_reproducible():
    out = build_keyart_prompt(_input())
    assert isinstance(out.seed, int)
    assert build_keyart_prompt(_input(), seed=out.seed).prompt == out.prompt


@pytest.mark.parametrize(
    "fmt,dims",
    [
        ("portrait_1080x1920", (1080, 1920)),
        ("square_1080x1080", (1080, 1080)),
        ("landscape_1920x1080", (1920, 1080)),
    ],
)
def test_dimensions_track_output_format(fmt, dims):
    out = build_keyart_prompt(_input(output_format=fmt), seed=1)
    assert (out.width, out.height) == dims


def test_missing_design_uses_defaults_and_stays_valid():
    out = build_keyart_prompt(_input(design={}), seed=1)
    assert out.prompt.startswith("lol_keyart, ")
    assert out.prompt.endswith(f"highly detailed, {out.vibe}, {out.energy}")
    assert out.vibe == "cinematic" and out.energy == "balanced"


def test_unknown_game_raises():
    with pytest.raises(ValueError):
        build_keyart_prompt(_input(game="dota2"), seed=1)
