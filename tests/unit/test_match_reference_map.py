"""
Reference-image mapping for match posters.

`_extract_input_images` compacts its list — anything without a path is skipped —
so the index of each reference shifts with whatever the user supplied. Two team
logos alone are unambiguous, but adding a tournament logo gave the image model a
third unlabelled graphic to guess at, and a team logo would come back merged,
misplaced, or missing. These tests pin the mapping to the real supply order.
"""

from __future__ import annotations

from esports_poster_ai.prompt.assembler import _build_metadata_block, build_prompt


def _gameday(tournament_logo=None, player=False, game="league_of_legends"):
    data = {
        "_meta": {
            "game": game,
            "poster_type": "gameday",
            "mode": "fresh",
            "output_format": "landscape_1920x1080",
        },
        "tournament": {"name": "VXG Tunisia"},
        "match": {
            "team1": {"name": "FNATIC", "logo_path": "assets/logos/FNC.png"},
            "team2": {"name": "T1", "logo_path": "assets/logos/T1.png"},
        },
        "design": {"vibe": "cinematic", "energy": "balanced"},
    }
    if tournament_logo:
        data["tournament"]["logo_path"] = tournament_logo
    if player:
        data["player_feature"] = {"enabled": True, "image_path": "assets/p.png"}
    return data


def test_team_logos_are_indexed_by_name():
    out = _build_metadata_block(_gameday())
    assert "Reference image #1: TEAM LOGO → FNATIC" in out
    assert "Reference image #2: TEAM LOGO → T1" in out


def test_tournament_logo_takes_slot_three_and_is_marked_not_a_team():
    out = _build_metadata_block(_gameday(tournament_logo="assets/vxg.png"))
    assert "Reference image #3: TOURNAMENT LOGO (VXG Tunisia) → NOT a team logo" in out


def test_adding_a_tournament_logo_does_not_move_the_team_logos():
    # The exact regression: team slots must stay #1 and #2.
    with_logo = _build_metadata_block(_gameday(tournament_logo="assets/vxg.png"))
    assert "Reference image #1: TEAM LOGO → FNATIC" in with_logo
    assert "Reference image #2: TEAM LOGO → T1" in with_logo
    assert "both teams keep their own full-size marks" in with_logo


def test_player_photo_follows_the_tournament_logo():
    out = _build_metadata_block(_gameday(tournament_logo="assets/vxg.png", player=True))
    assert "Reference image #4: FEATURED PLAYER PHOTO" in out


def test_game_wordmark_is_indexed_last():
    # modes/fresh.py appends it after every other reference.
    out = _build_metadata_block(_gameday(tournament_logo="assets/vxg.png", player=True))
    assert "Reference image #5: OFFICIAL GAME LOGO" in out


def test_indices_compact_when_assets_are_absent():
    # Valorant has no configured wordmark, and no tournament logo here, so the
    # mapping must stop at #2 rather than reserving empty slots.
    out = _build_metadata_block(_gameday(game="valorant"))
    assert "Reference image #2: TEAM LOGO → T1" in out
    assert "#3" not in out


def test_mapping_is_omitted_when_nothing_can_be_confused():
    data = _gameday(game="valorant")
    data["match"]["team2"].pop("logo_path")
    out = _build_metadata_block(data)
    assert "Reference image mapping" not in out


def test_mapping_reaches_the_assembled_prompt():
    assert "Reference image mapping" in build_prompt(_gameday(tournament_logo="a.png"))


def test_game_results_gets_the_mapping_too():
    data = _gameday(tournament_logo="assets/vxg.png")
    data["_meta"]["poster_type"] = "game_results"
    data["match"]["team1"]["score"] = 3
    data["match"]["team2"]["score"] = 1
    out = _build_metadata_block(data)
    assert "Reference image #3: TOURNAMENT LOGO" in out
    # The existing score/winner lines must survive alongside it.
    assert "Series Score" in out
