"""Tests for prompt/router.route."""

from __future__ import annotations

from esports_poster_ai.prompt.router import route


def _meta(poster_type: str, game: str = "league_of_legends", mode: str = "fresh") -> dict:
    return {"_meta": {"poster_type": poster_type, "game": game, "mode": mode}}


def test_route_extracts_meta_fields():
    decisions = route(_meta("gameday", game="valorant", mode="consistency"))
    assert decisions["poster_type"] == "gameday"
    assert decisions["game"] == "valorant"
    assert decisions["mode"] == "consistency"


def test_route_needs_game_rules_for_game_results():
    assert route(_meta("game_results"))["needs_game_rules"] is True


def test_route_needs_game_rules_for_roster_reveal():
    assert route(_meta("roster_reveal"))["needs_game_rules"] is True


def test_route_does_not_need_game_rules_for_gameday():
    assert route(_meta("gameday"))["needs_game_rules"] is False


def test_route_does_not_need_game_rules_for_tournament_types():
    assert route(_meta("tournament_announcement"))["needs_game_rules"] is False
    assert route(_meta("tournament_banner"))["needs_game_rules"] is False


def test_route_passes_through_style_dna():
    dna = {"palette": ["#FF0000"]}
    assert route(_meta("gameday"), style_dna=dna)["style_dna"] is dna


def test_route_handles_missing_meta_gracefully():
    decisions = route({})
    assert decisions["poster_type"] is None
    assert decisions["game"] is None
    assert decisions["needs_game_rules"] is False
