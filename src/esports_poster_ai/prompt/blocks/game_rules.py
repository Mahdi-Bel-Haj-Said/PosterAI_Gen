"""
Game-specific rules — injected only for game_results / roster_reveal posters.

These rules describe how to FORMAT data that the metadata actually provides.
They must never instruct rendering data the input schema does not carry
(e.g. per-game durations), or the image model will invent it.
"""

GAME_RULES = {
    "league_of_legends": {
        "score_format": (
            'Series score as two numbers separated by a dash, e.g. "2 — 1" or '
            '"3 — 0" — render exactly the score given in the metadata.'
        ),
        "result_detail": (
            "Show only the series score between the two teams. LoL series are "
            "counted in games, not maps — render no map names, and no per-game "
            "breakdown or durations unless the metadata explicitly provides them."
        ),
        "mvp_stats": "typically KDA, Kills, or CS per minute",
        "roles": "Top / Jungle / Mid / Bot / Support",
        "game_specific_donts": (
            "Do not show map names — LoL uses game numbers, not maps. "
            "Do not invent per-game durations or scores."
        ),
    },
    "valorant": {
        "score_format": (
            'Series score as two numbers, e.g. "2 — 1" — the number of maps each '
            "team won. If the metadata lists per-map results, show the per-map "
            'round scores in a row below, e.g. "Haven 13 — 7 · Ascent 11 — 13".'
        ),
        "result_detail": (
            "Show the series score, plus a map-by-map row ONLY for the maps "
            "present in the metadata. Do not add or invent maps or round scores."
        ),
        "mvp_stats": "typically ACS, Kills, HS%, or KAST",
        "roles": "Duelist / Initiator / Controller / Sentinel / Flex",
        "game_specific_donts": (
            "Do not show game durations — Valorant uses round scores per map. "
            "Do not invent maps or round scores."
        ),
    },
}


def build_game_rules_block(game: str) -> str:
    """Build the game rules block for the given game key."""
    rules = GAME_RULES.get(game)
    if not rules:
        return ""

    return (
        "GAME-SPECIFIC RULES (formatting only — never render a score, stat, "
        "duration, or map that the metadata does not contain):\n"
        f"- Score format: {rules.get('score_format')}\n"
        f"- Result detail: {rules.get('result_detail')}\n"
        f"- MVP stat (only if an MVP stat is provided): {rules.get('mvp_stats')}\n"
        f"- Roster roles: {rules.get('roles')}\n"
        f"- Game-specific DO NOT: {rules.get('game_specific_donts')}"
    ).strip()
