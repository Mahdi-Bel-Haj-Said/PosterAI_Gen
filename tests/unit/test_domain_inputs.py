"""Tests for domain/inputs Pydantic models — strict Meta, loose elsewhere."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from esports_poster_ai.domain.inputs import PosterInput


def _valid_minimal() -> dict:
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "gameday",
            "mode": "fresh",
            "output_format": "portrait_1080x1920",
        },
        "tournament": {"name": "EWC 2025"},
        "match": {
            "team1": {"name": "FNATIC", "logo_path": "assets/logos/FNC.png"},
            "team2": {"name": "T1", "logo_path": "assets/logos/T1.png"},
            "time": "17:00",
            "timezone": "CET",
        },
        "design": {"vibe": "cyberpunk", "primary_color": "#FF5C00", "energy": "intense"},
    }


def test_meta_accepts_valid_values():
    PosterInput.model_validate(_valid_minimal())


def test_meta_rejects_invalid_game():
    d = _valid_minimal()
    d["_meta"]["game"] = "dota2"
    with pytest.raises(ValidationError):
        PosterInput.model_validate(d)


def test_meta_rejects_invalid_poster_type():
    d = _valid_minimal()
    d["_meta"]["poster_type"] = "victory_screen"
    with pytest.raises(ValidationError):
        PosterInput.model_validate(d)


def test_meta_rejects_invalid_output_format():
    d = _valid_minimal()
    d["_meta"]["output_format"] = "square_2048x2048"
    with pytest.raises(ValidationError):
        PosterInput.model_validate(d)


def test_meta_defaults_mode_to_fresh():
    d = _valid_minimal()
    del d["_meta"]["mode"]
    pi = PosterInput.model_validate(d)
    assert pi.meta.mode == "fresh"


def test_extra_top_level_fields_are_allowed():
    d = _valid_minimal()
    d["custom_marketing_field"] = {"campaign": "summer"}
    PosterInput.model_validate(d)  # should not raise


def test_design_accepts_valid_vibe_and_energy():
    d = _valid_minimal()
    d["design"] = {"vibe": "dark_fantasy", "primary_color": "#102030", "energy": "explosive"}
    PosterInput.model_validate(d)


def test_design_rejects_invalid_vibe():
    d = _valid_minimal()
    d["design"]["vibe"] = "vaporwave"
    with pytest.raises(ValidationError):
        PosterInput.model_validate(d)


def test_design_rejects_invalid_energy():
    d = _valid_minimal()
    d["design"]["energy"] = "ultra"
    with pytest.raises(ValidationError):
        PosterInput.model_validate(d)


def test_roster_field_is_accepted_loosely():
    d = _valid_minimal()
    d["_meta"]["poster_type"] = "roster_reveal"
    d["team"] = {"name": "FNC", "logo_path": "x.png"}
    d["roster"] = {
        "season": "Summer 2025",
        "players": [
            {"ign": "Caps", "role": "Mid", "image_path": None, "is_new_signing": False}
        ],
    }
    PosterInput.model_validate(d)
