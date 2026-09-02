"""
Conditional prompt blocks based on which assets exist in the input JSON.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _get(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _is_non_empty_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def build_asset_block(input_data: Dict[str, Any]) -> str:
    """
    Inspect input JSON and return instructions only for assets that actually exist.

    This function does NOT access the filesystem; it relies solely on JSON fields.
    """
    poster_type = _get(input_data, ["_meta", "poster_type"])

    lines: List[str] = []
    lines.append("ASSETS AVAILABLE (conditional instructions):")

    # Team logos for match-based poster types
    team1_logo = _get(input_data, ["match", "team1", "logo_path"])
    team2_logo = _get(input_data, ["match", "team2", "logo_path"])
    if poster_type in {"gameday", "game_results"}:
        if _is_non_empty_str(team1_logo):
            lines.append("- Team 1 logo available: integrate into Team 1 zone.")
        else:
            lines.append("- Team 1 logo missing: do not invent a logo; reserve the zone and keep it minimal.")

        if _is_non_empty_str(team2_logo):
            lines.append("- Team 2 logo available: integrate into Team 2 zone.")
        else:
            lines.append("- Team 2 logo missing: treat as single-team poster (no VS layout).")

    # Tournament logo where applicable
    tournament_logo = _get(input_data, ["tournament", "logo_path"])
    if tournament_logo is not None:
        if _is_non_empty_str(tournament_logo):
            lines.append(
                "- Tournament logo available: the real logo is supplied as a "
                "reference image. Reproduce it EXACTLY as given (no redraw, "
                "restyle, recolor, re-letter, or added effects) and place it near "
                "the tournament name without overpowering the hero title."
            )
        else:
            lines.append("- Tournament logo not provided: use stylized tournament text only.")

    # Stream block
    stream_url = _get(input_data, ["stream", "url"])
    if stream_url is None:
        pass
    elif _is_non_empty_str(stream_url):
        lines.append("- Stream URL provided: include stream platform + URL exactly as text.")
    else:
        lines.append("- Stream URL empty: omit the stream block entirely.")

    # Player feature (gameday)
    player_enabled = _get(input_data, ["player_feature", "enabled"])
    player_image = _get(input_data, ["player_feature", "image_path"])
    if player_enabled is True and _is_non_empty_str(player_image):
        lines.append(
            "- Featured player image PROVIDED: a player photo is among the reference "
            "images. Render the player as a LARGE, prominent hero subject in the "
            "foreground — a main visual focus of the poster, not a small accent. "
            "Freely resize, crop, or re-frame the photo to fit the poster's "
            "format and composition. Scene-light them to match the background; "
            "preserve their likeness."
        )
    elif player_enabled is True:
        lines.append("- Player feature enabled but image missing: do not invent a face; fill the player zone with atmosphere.")
    elif player_enabled is False:
        lines.append("- No player feature: fill any potential player zone with background-consistent atmospheric effects.")

    # Roster reveal player cards
    if poster_type == "roster_reveal":
        players = _get(input_data, ["roster", "players"])
        if isinstance(players, list):
            with_photo = sum(1 for p in players if isinstance(p, dict) and _is_non_empty_str(p.get("image_path")))
            with_flag = sum(1 for p in players if isinstance(p, dict) and _is_non_empty_str(p.get("nationality_flag_path")))
            lines.append(f"- Roster players: {len(players)} entries. Photos provided for {with_photo}. Flags provided for {with_flag}.")

    # MVP section
    mvp_enabled = _get(input_data, ["mvp", "enabled"])
    if mvp_enabled is True:
        lines.append("- MVP enabled: include MVP block (player name + stat) if fields are provided.")
    elif mvp_enabled is False:
        lines.append("- MVP disabled: omit MVP block entirely.")

    return "\n".join(lines).strip()
