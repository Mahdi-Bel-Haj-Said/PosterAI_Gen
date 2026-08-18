"""Tests for the StyleDNA Pydantic schema + helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from esports_poster_ai.domain.style_dna import (
    CURRENT_SCHEMA_VERSION,
    StyleDNA,
    StyleDNASemantic,
)


def _minimal_dna() -> StyleDNA:
    return StyleDNA(
        tournament_id="ewc_2025",
        palette=["#FF5C00"],
        lighting="neon backlit",
        atmosphere="dark electric",
        particle_effects="sparks",
        energy="intense",
        sd_style_keywords="cyberpunk",
    )


def test_dna_defaults_to_draft_status():
    dna = _minimal_dna()
    assert dna.status == "draft"


def test_dna_to_prompt_dict_returns_consistency_block_shape():
    dna = _minimal_dna()
    prompt_dict = dna.to_prompt_dict()
    assert set(prompt_dict.keys()) == {
        "palette",
        "lighting",
        "atmosphere",
        "particle_effects",
        "energy",
        "sd_style_keywords",
        "typography",
    }


def test_dna_approve_sets_status_and_timestamp():
    dna = _minimal_dna()
    approved = dna.approve()
    assert approved.status == "approved"
    assert approved.approved_at is not None
    # Original instance not mutated.
    assert dna.status == "draft"
    assert dna.approved_at is None


def test_dna_rejects_invalid_energy():
    with pytest.raises(ValidationError):
        StyleDNA(tournament_id="x", energy="berserk")  # type: ignore[arg-type]


def test_dna_rejects_invalid_color_temperature():
    with pytest.raises(ValidationError):
        StyleDNA(tournament_id="x", color_temperature="lukewarm")  # type: ignore[arg-type]


def test_dna_schema_version_defaults_to_current():
    dna = _minimal_dna()
    assert dna.schema_version == CURRENT_SCHEMA_VERSION


def test_dna_allows_extra_fields_for_forward_compat():
    StyleDNA(tournament_id="x", custom_future_field="anything")  # should not raise


def test_dna_semantic_required_fields():
    # All five semantic fields must be present.
    with pytest.raises(ValidationError):
        StyleDNASemantic.model_validate({"lighting": "x"})


def test_dna_semantic_rejects_invalid_energy():
    with pytest.raises(ValidationError):
        StyleDNASemantic.model_validate({
            "lighting": "a",
            "atmosphere": "b",
            "particle_effects": "c",
            "energy": "wild",
            "sd_style_keywords": "d",
        })
