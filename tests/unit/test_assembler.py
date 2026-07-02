"""Tests for prompt/assembler.build_prompt."""

from __future__ import annotations

import pytest

from esports_poster_ai.prompt.assembler import (
    build_image_factual_footer,
    build_image_style_footer,
    build_prompt,
)


def _gameday_input(**overrides) -> dict:
    base = {
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
        "stream": {"platform": "Twitch", "url": "twitch.tv/caedrel"},
        "design": {"vibe": "cyberpunk", "primary_color": "#FF5C00", "energy": "intense"},
    }
    base.update(overrides)
    return base


def test_build_prompt_includes_static_blocks_for_gameday():
    out = build_prompt(_gameday_input())
    assert "BACKGROUND ANALYSIS" in out  # from static block
    assert "POSTER GENERATION INSTRUCTIONS" in out
    assert "IF GAMEDAY:" in out  # from poster_type block


def test_build_prompt_includes_factual_text_rule():
    out = build_prompt(_gameday_input())
    assert "FACTUAL TEXT IS VERBATIM" in out
    assert "INVENT NOTHING" in out


def test_sponsor_reservation_only_when_sponsors_enabled():
    # No sponsors block -> no reservation.
    out = build_prompt(_gameday_input())
    assert "SPONSOR BAR RESERVATION" not in out

    # sponsors.enabled false -> no reservation.
    inp = _gameday_input()
    inp["sponsors"] = {"enabled": False, "logos": []}
    assert "SPONSOR BAR RESERVATION" not in build_prompt(inp)

    # sponsors.enabled true -> reservation injected.
    inp2 = _gameday_input()
    inp2["sponsors"] = {"enabled": True, "logos": [{"path": "a.png"}]}
    out2 = build_prompt(inp2)
    assert "SPONSOR BAR RESERVATION" in out2
    assert "reserved strip" in out2.lower()


def test_build_prompt_excludes_game_rules_for_gameday():
    # game_rules block only injected for game_results / roster_reveal
    out = build_prompt(_gameday_input())
    assert "GAME-SPECIFIC RULES" not in out


def test_build_prompt_includes_game_rules_for_game_results():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "game_results"
    out = build_prompt(inp)
    assert "GAME-SPECIFIC RULES" in out


def test_build_prompt_omits_null_metadata_lines():
    inp = _gameday_input()
    inp["tournament"]["phase"] = None
    inp["match"]["format"] = None
    out = build_prompt(inp)
    assert "- Phase:" not in out
    assert "- Format:" not in out


def test_build_prompt_includes_match_time_with_timezone():
    out = build_prompt(_gameday_input())
    assert "Match Time: 17:00 CET" in out


def test_build_prompt_omits_match_time_when_empty():
    inp = _gameday_input()
    inp["match"]["time"] = ""
    out = build_prompt(inp)
    assert "Match Time:" not in out


def test_build_prompt_includes_consistency_block_only_when_dna_present():
    inp = _gameday_input()
    inp["_meta"]["mode"] = "consistency"
    dna = {"palette": ["#FF0000"], "lighting": "neon", "atmosphere": "dark"}
    out = build_prompt(inp, style_dna=dna)
    assert "CONSISTENCY MODE — STYLE DNA CONSTRAINTS" in out

    out_no_dna = build_prompt(inp, style_dna=None)
    assert "CONSISTENCY MODE" not in out_no_dna


def test_build_prompt_raises_on_unknown_poster_type():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "not_a_real_type"
    with pytest.raises(ValueError):
        build_prompt(inp)


def test_build_prompt_assets_block_flags_missing_team_logo():
    inp = _gameday_input()
    inp["match"]["team1"]["logo_path"] = ""
    out = build_prompt(inp)
    assert "Team 1 logo missing" in out


def test_build_prompt_assets_block_includes_stream_when_url_present():
    out = build_prompt(_gameday_input())
    assert "Stream URL provided" in out


def test_build_prompt_assets_block_omits_stream_when_empty_string():
    inp = _gameday_input()
    inp["stream"]["url"] = ""
    out = build_prompt(inp)
    assert "Stream URL empty" in out


# --- poster-type-adaptive METADATA block ---------------------------------


def test_game_results_injects_series_score_and_winner():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "game_results"
    inp["match"]["team1"]["score"] = 2
    inp["match"]["team2"]["score"] = 3
    out = build_prompt(inp)
    assert "Series Score: FNATIC 2 — 3 T1" in out
    assert "Winner: T1" in out
    assert "Defeated: FNATIC" in out


def test_game_results_omits_score_when_absent():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "game_results"
    out = build_prompt(inp)
    assert "Series Score" not in out
    assert "Winner:" not in out


def test_game_results_injects_valorant_maps():
    inp = _gameday_input()
    inp["_meta"]["game"] = "valorant"
    inp["_meta"]["poster_type"] = "game_results"
    inp["match"]["team1"]["score"] = 2
    inp["match"]["team2"]["score"] = 1
    inp["match"]["maps"] = [
        {"map_name": "Haven", "rounds_team1": 13, "rounds_team2": 7},
        {"map_name": "Ascent", "rounds_team1": 11, "rounds_team2": 13},
    ]
    out = build_prompt(inp)
    assert "Haven: FNATIC 13 — 7 T1" in out
    assert "Ascent: FNATIC 11 — 13 T1" in out


def test_game_results_injects_mvp_when_enabled():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "game_results"
    inp["mvp"] = {
        "enabled": True,
        "player_name": "Faker",
        "stat_label": "KDA",
        "stat_value": "8.5",
    }
    out = build_prompt(inp)
    assert "MVP: Faker — KDA: 8.5" in out


def test_roster_reveal_injects_players():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "roster_reveal"
    inp["team"] = {"name": "FNATIC"}
    inp["roster"] = {
        "season": "2025 Summer",
        "players": [
            {"ign": "Razork", "role": "Jungle", "is_new_signing": True},
            {"ign": "Humanoid", "role": "Mid"},
        ],
    }
    out = build_prompt(inp)
    assert "Team: FNATIC" in out
    assert "Razork — Jungle [NEW SIGNING]" in out
    assert "Humanoid — Mid" in out


def test_tournament_announcement_injects_event_fields():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "tournament_announcement"
    inp["tournament"] = {
        "name": "EWC 2025",
        "prize_pool": "$1,000,000",
        "teams_count": 16,
    }
    out = build_prompt(inp)
    assert "Prize Pool: $1,000,000" in out
    assert "Teams Competing: 16" in out


# --- visual style: design block vs consistency DNA ------------------------


def test_design_block_injected_in_fresh_mode():
    out = build_prompt(_gameday_input())
    assert "VISUAL STYLE" in out
    assert "Cyberpunk" in out  # vibe preset guidance
    assert "#FF5C00" in out  # dominant color


def test_design_block_replaced_by_dna_in_consistency_mode():
    inp = _gameday_input()
    inp["_meta"]["mode"] = "consistency"
    dna = {"palette": ["#FF0000"], "lighting": "neon", "atmosphere": "dark"}
    out = build_prompt(inp, style_dna=dna)
    assert "CONSISTENCY MODE — STYLE DNA CONSTRAINTS" in out
    assert "VISUAL STYLE (design direction" not in out


def test_image_factual_footer_carries_verbatim_data_and_rules():
    inp = _gameday_input()
    inp["_meta"]["poster_type"] = "game_results"
    inp["match"]["team1"]["score"] = 2
    inp["match"]["team2"]["score"] = 3
    footer = build_image_factual_footer(inp)
    assert "RENDER EXACTLY, INVENT NOTHING" in footer
    assert "FACTUAL DATA (verbatim):" in footer
    assert "Series Score: FNATIC 2 — 3 T1" in footer
    assert "INVENT NOTHING" in footer or "Do NOT invent" in footer


def test_image_style_footer_carries_design_directives_verbatim():
    # Fresh mode: the footer re-states the user's design so the dominant color /
    # vibe / energy bypass GPT-4o's rewrite and reach gpt-image-2 directly.
    inp = _gameday_input()
    inp["design"] = {"vibe": "cyberpunk", "primary_color": "#FFD24B", "energy": "explosive"}
    footer = build_image_style_footer(inp)
    assert "VISUAL STYLE — APPLY ACROSS THE WHOLE POSTER" in footer
    assert "#FFD24B" in footer
    assert "cyberpunk" in footer
    assert "explosive" in footer
    # The whole-frame color-grade instruction is the actual fix for the bug.
    assert "color-grade the ENTIRE frame" in footer.lower() or "ENTIRE frame" in footer


def test_image_style_footer_prefers_dna_palette_in_consistency_mode():
    inp = _gameday_input()
    dna = {"palette": ["#FF0000", "#220011"], "lighting": "neon", "atmosphere": "smoky"}
    footer = build_image_style_footer(inp, style_dna=dna)
    assert "#FF0000" in footer and "#220011" in footer
    assert "neon" in footer
    assert "smoky" in footer


def test_image_style_footer_empty_when_no_design():
    inp = _gameday_input()
    inp.pop("design", None)
    assert build_image_style_footer(inp) == ""


def test_design_block_used_in_consistency_mode_when_no_dna():
    inp = _gameday_input()
    inp["_meta"]["mode"] = "consistency"
    out = build_prompt(inp, style_dna=None)
    assert "VISUAL STYLE" in out


def test_style_dna_applied_regardless_of_meta_mode():
    # Regression: a supplied DNA must reach the prompt even when the JSON's
    # _meta.mode says "fresh" (the CLI / API decide consistency separately).
    inp = _gameday_input()  # _meta.mode defaults to "fresh"
    dna = {"palette": ["#FF0000"], "lighting": "neon", "atmosphere": "dark"}
    out = build_prompt(inp, style_dna=dna)
    assert "CONSISTENCY MODE — STYLE DNA CONSTRAINTS" in out
    assert "VISUAL STYLE (design direction" not in out
