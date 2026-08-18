"""Tests for the bank combo space."""

from __future__ import annotations

from esports_poster_ai.bank.combos import (
    ENERGIES,
    VIBES,
    all_combos,
    combo_from_slug,
    combo_or_none,
)


def test_there_are_exactly_24_unique_combos():
    combos = all_combos()
    assert len(combos) == 24
    assert len(ENERGIES) == 4 and len(VIBES) == 6
    assert len({c.slug for c in combos}) == 24


def test_slug_format():
    c = all_combos()[0]
    assert c.slug == f"{c.energy}_{c.vibe}"
    assert c.slug == "chill_cyberpunk"  # declaration order of the enums


def test_combo_from_slug_round_trips():
    for c in all_combos():
        assert combo_from_slug(c.slug) == c


def test_combo_from_slug_rejects_unknown():
    assert combo_from_slug("nope_nope") is None
    assert combo_from_slug("chill_notavibe") is None


def test_combo_or_none_validates_both_axes():
    assert combo_or_none("chill", "cyberpunk") is not None
    assert combo_or_none("chill", "bogus") is None
    assert combo_or_none("bogus", "cyberpunk") is None
    assert combo_or_none(None, None) is None


def test_input_data_shape_feeds_the_prompt_builder():
    data = combo_or_none("intense", "dark_fantasy").input_data()
    assert data["_meta"]["game"] == "league_of_legends"
    assert data["design"] == {"vibe": "dark_fantasy", "energy": "intense"}
