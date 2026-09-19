"""
Layout-pattern selection: ONE of ten named composition patterns is chosen HERE
and handed to the vision model as decided, rather than offered as a menu.

The menu version is what these tests used to cover. It was replaced because
offering the choice produced the same failure the roster arrangements had — the
model kept returning the same safe composition, so posters looked alike despite
ten patterns being available. The tests below therefore cover the properties that
actually matter now: exactly one pattern is named, it comes from the known ten,
consecutive builds differ, and a content-heavy brief never draws a pattern that
cannot hold it.
"""

from __future__ import annotations

import random

import pytest

from esports_poster_ai.prompt.assembler import build_prompt
from esports_poster_ai.prompt.blocks.layout import build_layout_block

PATTERN_NAMES = (
    "HERO + SUPPORTING",
    "DIAGONAL ACTION",
    "CENTER-FOCAL",
    "MODULAR (BENTO) GRID",
    "RADIAL (CIRCULAR)",
    "PROGRESSIVE (TIMELINE / LIST)",
    "COLLISION (OVERLAPPING)",
    "NEGATIVE-SPACE HERO",
    "BROKEN GRID (ASYMMETRICAL)",
    "REPETITION (PATTERNED)",
)

# Patterns that cannot carry five portraits plus five IGNs.
SPARSE_ONLY = ("NEGATIVE-SPACE HERO", "REPETITION (PATTERNED)")


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


def _roster():
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "roster_reveal",
            "mode": "fresh",
            "output_format": "portrait_1080x1920",
        },
        "team": {"name": "FNATIC"},
        "roster": {"players": [{"ign": f"P{i}"} for i in range(5)]},
        "design": {"vibe": "cyberpunk", "energy": "intense"},
    }


def _chosen(text):
    """The pattern on the CHOSEN PATTERN line.

    Parsed from that line specifically, not by scanning the whole block: the
    fallback sentence also names a pattern, so a plain substring search reports
    two and always finds the fallback first.
    """
    line = next(l for l in text.splitlines() if l.startswith("CHOSEN PATTERN:"))
    return next(name for name in PATTERN_NAMES if name in line)


def _named_patterns(text):
    return [name for name in PATTERN_NAMES if name in text]


def test_block_names_a_single_chosen_pattern():
    out = build_layout_block(_gameday())
    lines = [l for l in out.splitlines() if l.startswith("CHOSEN PATTERN:")]
    assert len(lines) == 1, f"expected one CHOSEN PATTERN line, got {lines}"
    assert len(_named_patterns(lines[0])) == 1


def test_named_pattern_is_one_of_the_ten():
    assert _chosen(build_layout_block(_gameday())) in PATTERN_NAMES


def test_the_choice_is_presented_as_already_made():
    out = build_layout_block(_gameday())
    assert "already chosen" in out
    assert "never blend two patterns" in out.lower()


def test_patterns_vary_across_builds():
    """The regression guard: posters kept coming back in one composition."""
    seen = {_chosen(build_layout_block(_gameday())) for _ in range(60)}
    assert len(seen) > 1, f"pattern never varied across 60 builds: {seen}"


def test_a_roster_never_draws_a_pattern_that_cannot_hold_it():
    for _ in range(60):
        chosen = _chosen(build_layout_block(_roster()))
        assert chosen not in SPARSE_ONLY, f"roster drew {chosen}"


def test_selection_is_reproducible_with_a_seeded_rng():
    a = build_layout_block(_gameday(), rng=random.Random(7))
    b = build_layout_block(_gameday(), rng=random.Random(7))
    assert a == b


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


def test_assembled_prompt_carries_the_pattern_and_output_slot():
    out = build_prompt(_gameday())
    assert "STEP 2.5 — THE LAYOUT PATTERN FOR THIS POSTER" in out
    assert len(_named_patterns(out)) >= 1
    # The chosen pattern must be named in the output prompt, so it survives
    # through to gpt-image-2 rather than staying in the vision model's head.
    assert "LAYOUT PATTERN:" in out


def test_present_in_consistency_mode_too():
    # Layout is not carried by the Style DNA, so the choice still has to be made.
    dna = {"palette": ["#101820", "#FF5C00"], "lighting": "hard rim light"}
    out = build_prompt(_gameday(), style_dna=dna)
    assert "STEP 2.5 — THE LAYOUT PATTERN FOR THIS POSTER" in out
