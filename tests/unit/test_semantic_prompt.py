"""Tests for the semantic-extraction prompt template (no OpenAI calls)."""

from __future__ import annotations

from esports_poster_ai.style_dna.semantic import build_semantic_prompt


def test_prompt_contains_content_blacklist():
    prompt = build_semantic_prompt(["#FF5C00", "#0A0A1A"])
    assert "team names" in prompt.lower()
    assert "score" in prompt.lower()
    assert "tournament names" in prompt.lower()


def test_prompt_injects_palette_csv():
    prompt = build_semantic_prompt(["#FF5C00", "#0A0A1A"])
    assert "#FF5C00" in prompt
    assert "#0A0A1A" in prompt


def test_prompt_handles_empty_palette():
    prompt = build_semantic_prompt([])
    assert "palette extraction returned no colors" in prompt.lower()


def test_prompt_mentions_required_fields():
    prompt = build_semantic_prompt(["#FF5C00"])
    for field in ("lighting", "atmosphere", "particle_effects", "energy", "sd_style_keywords"):
        assert field in prompt


def test_prompt_lists_valid_energy_values():
    prompt = build_semantic_prompt(["#FF5C00"])
    for value in ("chill", "balanced", "intense", "explosive"):
        assert value in prompt
