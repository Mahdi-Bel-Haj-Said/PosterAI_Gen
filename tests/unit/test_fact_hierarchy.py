"""
Fact hierarchy: the factual values must not all render at one shared size. The
hero-title rule is deliberately left intact — this covers only the ranking of
everything below it, and that the ranking reaches the image model.
"""

from __future__ import annotations

from esports_poster_ai.prompt.assembler import build_image_factual_footer, build_prompt


def _announcement():
    return {
        "_meta": {
            "game": "league_of_legends",
            "poster_type": "tournament_announcement",
            "mode": "fresh",
            "output_format": "landscape_1920x1080",
        },
        "tournament": {
            "name": "EMEA MASTERS",
            "start_date": "2026-08-11",
            "location": "France . Paris",
            "prize_pool": "50.000$",
            "teams_count": 32,
            "format": "Single Elimination",
            "tagline": "THE ROAD TO GLORY",
        },
        "design": {"vibe": "dark_fantasy", "energy": "intense"},
    }


def test_prompt_ranks_facts_into_three_weights():
    out = build_prompt(_announcement())
    assert "FACT HIERARCHY" in out
    for tier in ("HEADLINE FACT", "SUPPORTING FACTS", "MINOR FACTS"):
        assert tier in out


def test_hero_title_rule_is_left_intact():
    out = build_prompt(_announcement())
    assert "Must be the single largest text element on the entire poster" in out


def test_uniform_icon_row_is_forbidden():
    # The exact failure mode: five facts as equal icon+label cells.
    out = build_prompt(_announcement())
    assert "row of equal icon + label cells at one uniform size" in out


def test_output_template_carries_a_hierarchy_slot():
    # So the ranking survives into the gpt-image-2 prompt, not just GPT-4o's head.
    assert "FACT HIERARCHY:" in build_prompt(_announcement())


def test_footer_states_it_is_not_a_ranking():
    # The verbatim footer is the last thing the image model reads; without this
    # it re-flattens the facts into a peer list.
    footer = build_image_factual_footer(_announcement())
    assert "listed for ACCURACY, not importance" in footer
