"""
Scenario tests — exercise the full range of *user inputs* end-to-end through
the deterministic core of the pipeline: validate (PosterInput) -> route -> build
the prompt + factual footer.

These complement the per-feature unit tests in test_domain_inputs / test_router /
test_assembler by treating each realistic user input as a whole *scenario*:

  * every input fixture shipped under inputs/ (the real CLI/API inputs),
  * the full game x poster_type x output_format matrix,
  * the edge cases a real user actually hits — winner / loser / tie scores,
    0 / 1 / 5-player rosters, sponsors on/off, consistency with/without a DNA,
    blank "template" inputs, and Valorant per-map results,
  * and the invalid inputs that must fail fast at the boundary.

No network and no OpenAI calls — same constraints as the rest of tests/unit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from esports_poster_ai.domain.inputs import PosterInput
from esports_poster_ai.prompt.assembler import build_image_factual_footer, build_prompt
from esports_poster_ai.prompt.router import route

# --------------------------------------------------------------------------- #
# Shared vocab — kept in lockstep with domain/inputs.py Literals.
# --------------------------------------------------------------------------- #

GAMES = ["league_of_legends", "valorant"]
POSTER_TYPES = [
    "gameday",
    "game_results",
    "roster_reveal",
    "tournament_announcement",
    "tournament_banner",
]
OUTPUT_FORMATS = [
    "portrait_1080x1920",
    "square_1080x1080",
    "landscape_1920x1080",
]

# tests/unit/ -> tests/ -> repo root -> inputs/
INPUTS_DIR = Path(__file__).resolve().parents[2] / "inputs"
INPUT_FILES = sorted(INPUTS_DIR.rglob("*.json"))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _scenario_input(
    *,
    game: str = "league_of_legends",
    poster_type: str = "gameday",
    output_format: str = "portrait_1080x1920",
    mode: str = "fresh",
    **overrides: Any,
) -> Dict[str, Any]:
    """A generic, fully-valid user input usable for any poster_type.

    Carries every section a real input might have; the assembler skips the
    sections that don't apply to a given poster_type, so one builder covers the
    whole matrix. Override any top-level key via kwargs.
    """
    base: Dict[str, Any] = {
        "_meta": {
            "game": game,
            "poster_type": poster_type,
            "mode": mode,
            "output_format": output_format,
        },
        "tournament": {
            "name": "Esports World Cup 2025",
            "phase": "Playoffs",
            "prize_pool": "$1,000,000",
            "teams_count": 16,
            "start_date": "2025-07-15",
            "date_range": "Jul 15 — Aug 24",
            "location": "Riyadh",
        },
        "match": {
            "team1": {"name": "Team Alpha", "short_name": "ALP", "logo_path": "assets/a.png"},
            "team2": {"name": "Team Bravo", "short_name": "BRV", "logo_path": "assets/b.png"},
            "date": "2025-07-20",
            "time": "17:00",
            "timezone": "CET",
            "format": "bo5",
        },
        "stream": {"platform": "Twitch", "url": "twitch.tv/example"},
        "team": {"name": "Team Alpha", "logo_path": "assets/a.png"},
        "roster": {
            "season": "2025 Summer",
            "players": [
                {"ign": "Alpha1", "role": "Top"},
                {"ign": "Alpha2", "role": "Jungle"},
                {"ign": "Alpha3", "role": "Mid"},
                {"ign": "Alpha4", "role": "Bot"},
                {"ign": "Alpha5", "role": "Support"},
            ],
        },
        "design": {"vibe": "cyberpunk", "primary_color": "#7B2FFF", "energy": "intense"},
    }
    base.update(overrides)
    return base


def _factual_data_section(footer: str) -> str:
    """The verbatim-data portion of the image footer, before the static rules."""
    return footer.split("RENDER RULES", 1)[0]


def _assert_no_placeholder_leak(text: str) -> None:
    """No null/None values and no unresolved {placeholder} tokens leak into the
    factual data the image model is told to render verbatim."""
    assert "None" not in text, f"leaked Python None into factual data:\n{text}"
    assert "null" not in text, f"leaked JSON null into factual data:\n{text}"
    assert "{" not in text and "}" not in text, f"unresolved placeholder:\n{text}"


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1. Every shipped input fixture is a real user scenario.
# --------------------------------------------------------------------------- #


def test_input_fixtures_are_discovered():
    """Guard against a silently-empty parametrize set (e.g. moved fixtures)."""
    assert INPUT_FILES, f"no input fixtures found under {INPUTS_DIR}"


@pytest.mark.parametrize(
    "fixture", INPUT_FILES, ids=[p.relative_to(INPUTS_DIR).as_posix() for p in INPUT_FILES]
)
def test_fixture_validates_routes_and_assembles(fixture: Path):
    data = _load(fixture)

    # Validates at the boundary exactly as the CLI / API would.
    pi = PosterInput.model_validate(data)
    assert pi.meta.game in GAMES
    assert pi.meta.poster_type in POSTER_TYPES
    assert pi.meta.output_format in OUTPUT_FORMATS

    # Routes consistently with _meta.
    decisions = route(data)
    assert decisions["poster_type"] == pi.meta.poster_type
    assert decisions["game"] == pi.meta.game

    # Assembles a non-trivial prompt without raising.
    prompt = build_prompt(data)
    assert isinstance(prompt, str) and len(prompt) > 200
    assert f"Game: {pi.meta.game}" in prompt
    assert f"Poster Type: {pi.meta.poster_type}" in prompt

    # And the verbatim factual footer never leaks null/None/placeholders —
    # several fixtures are blank "templates" (empty names, null fields).
    _assert_no_placeholder_leak(_factual_data_section(build_image_factual_footer(data)))


# --------------------------------------------------------------------------- #
# 2. Full game x poster_type x output_format matrix.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("game", GAMES)
@pytest.mark.parametrize("poster_type", POSTER_TYPES)
@pytest.mark.parametrize("output_format", OUTPUT_FORMATS)
def test_full_matrix_validates_and_assembles(game: str, poster_type: str, output_format: str):
    data = _scenario_input(game=game, poster_type=poster_type, output_format=output_format)

    pi = PosterInput.model_validate(data)
    assert pi.meta.output_format == output_format

    needs_rules = poster_type in {"game_results", "roster_reveal"}
    assert route(data)["needs_game_rules"] is needs_rules

    prompt = build_prompt(data)
    assert f"Game: {game}" in prompt
    assert f"Poster Type: {poster_type}" in prompt
    # Game rules block appears exactly for the two poster types that need it.
    assert ("GAME-SPECIFIC RULES" in prompt) is needs_rules
    _assert_no_placeholder_leak(_factual_data_section(build_image_factual_footer(data)))


# --------------------------------------------------------------------------- #
# 3. game_results — series score, derived winner, tie, and missing scores.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "s1, s2, winner, loser",
    [
        (3, 1, "Team Alpha", "Team Bravo"),  # team1 wins
        (2, 3, "Team Bravo", "Team Alpha"),  # team2 wins
        (3, 0, "Team Alpha", "Team Bravo"),  # sweep
    ],
)
def test_game_results_derives_winner_from_scores(s1: int, s2: int, winner: str, loser: str):
    data = _scenario_input(poster_type="game_results")
    data["match"]["team1"]["score"] = s1
    data["match"]["team2"]["score"] = s2
    out = build_prompt(data)
    assert f"Series Score: Team Alpha {s1} — {s2} Team Bravo" in out
    assert f"Winner: {winner}" in out
    assert f"Defeated: {loser}" in out


def test_game_results_tie_has_score_but_no_winner():
    data = _scenario_input(poster_type="game_results")
    data["match"]["team1"]["score"] = 2
    data["match"]["team2"]["score"] = 2
    out = build_prompt(data)
    assert "Series Score: Team Alpha 2 — 2 Team Bravo" in out
    assert "Winner:" not in out
    assert "Defeated:" not in out


def test_game_results_missing_scores_emit_no_score_line():
    data = _scenario_input(poster_type="game_results")  # no score fields
    out = build_prompt(data)
    assert "Series Score" not in out
    assert "Winner:" not in out


def test_game_results_valorant_per_map_results():
    data = _scenario_input(game="valorant", poster_type="game_results")
    data["match"]["team1"]["score"] = 2
    data["match"]["team2"]["score"] = 1
    data["match"]["maps"] = [
        {"map_name": "Haven", "rounds_team1": 13, "rounds_team2": 7},
        {"map_name": "Ascent", "rounds_team1": 11, "rounds_team2": 13},
        {"map_name": "Split", "rounds_team1": 13, "rounds_team2": 9},
    ]
    out = build_prompt(data)
    assert "Haven: Team Alpha 13 — 7 Team Bravo" in out
    assert "Ascent: Team Alpha 11 — 13 Team Bravo" in out
    assert "Split: Team Alpha 13 — 9 Team Bravo" in out


# --------------------------------------------------------------------------- #
# 4. roster_reveal — the 0 / 1 / 5 player counts the wizard allows.
# --------------------------------------------------------------------------- #


def _roster_players(n: int) -> List[Dict[str, Any]]:
    roles = ["Top", "Jungle", "Mid", "Bot", "Support"]
    return [{"ign": f"Player{i + 1}", "role": roles[i]} for i in range(n)]


@pytest.mark.parametrize("count", [0, 1, 5])
def test_roster_reveal_supported_player_counts(count: int):
    """The wizard restricts rosters to 0, 1, or 5 photos; the assembler must
    render each count gracefully (never crash, no leaks)."""
    data = _scenario_input(poster_type="roster_reveal")
    data["team"] = {"name": "Team Alpha"}
    data["roster"] = {"season": "2025 Summer", "players": _roster_players(count)}

    out = build_prompt(data)
    assert "Team: Team Alpha" in out
    if count == 0:
        assert "- Players:" not in out
    else:
        for i in range(count):
            assert f"Player{i + 1}" in out
    _assert_no_placeholder_leak(_factual_data_section(build_image_factual_footer(data)))


# --------------------------------------------------------------------------- #
# 5. Sponsors on/off and consistency with/without a Style DNA.
# --------------------------------------------------------------------------- #


def test_sponsors_enabled_reserves_a_bar():
    data = _scenario_input(sponsors={"enabled": True, "logos": [{"path": "s1.png"}]})
    assert "SPONSOR BAR RESERVATION" in build_prompt(data)


@pytest.mark.parametrize("sponsors", [None, {"enabled": False, "logos": []}])
def test_sponsors_disabled_reserves_no_bar(sponsors):
    data = _scenario_input()
    if sponsors is None:
        data.pop("sponsors", None)
    else:
        data["sponsors"] = sponsors
    assert "SPONSOR BAR RESERVATION" not in build_prompt(data)


def test_consistency_dna_replaces_design_block():
    data = _scenario_input(mode="consistency")
    dna = {"palette": ["#FF0000"], "lighting": "neon", "atmosphere": "dark"}
    out = build_prompt(data, style_dna=dna)
    assert "CONSISTENCY MODE — STYLE DNA CONSTRAINTS" in out


def test_consistency_without_dna_falls_back_to_design_block():
    data = _scenario_input(mode="consistency")
    out = build_prompt(data, style_dna=None)
    assert "CONSISTENCY MODE" not in out
    assert "VISUAL STYLE" in out


# --------------------------------------------------------------------------- #
# 6. Invalid user inputs must fail fast at the validation boundary.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "patch",
    [
        {"_meta": {"game": "dota2"}},
        {"_meta": {"poster_type": "victory_screen"}},
        {"_meta": {"output_format": "square_2048x2048"}},
        {"_meta": {"mode": "remix"}},
        {"design": {"vibe": "vaporwave"}},
        {"design": {"energy": "ultra"}},
    ],
    ids=["bad-game", "bad-poster-type", "bad-format", "bad-mode", "bad-vibe", "bad-energy"],
)
def test_invalid_enum_values_rejected(patch: Dict[str, Any]):
    data = _scenario_input()
    for section, fields in patch.items():
        data[section].update(fields)
    with pytest.raises(ValidationError):
        PosterInput.model_validate(data)


def test_missing_meta_block_rejected():
    data = _scenario_input()
    del data["_meta"]
    with pytest.raises(ValidationError):
        PosterInput.model_validate(data)


def test_assembler_rejects_unknown_poster_type_defense_in_depth():
    """Validation is the front line; the assembler still refuses a poster_type
    it has no block for rather than emitting a malformed prompt."""
    data = _scenario_input()
    data["_meta"]["poster_type"] = "not_a_real_type"  # bypasses model_validate
    with pytest.raises(ValueError):
        build_prompt(data)
