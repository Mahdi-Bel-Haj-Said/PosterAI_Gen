"""
Prompt assembler — builds the final prompt sent to the vision model.

The METADATA block is adapted to the poster type: a game_results poster gets
the series score + derived winner, a roster_reveal poster gets the player
list, a tournament poster gets the event details, and so on. Each builder
injects only the factual fields that apply to its poster type; null/empty
values are skipped silently.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from esports_poster_ai.prompt.blocks.assets import build_asset_block
from esports_poster_ai.prompt.blocks.consistency import build_consistency_block
from esports_poster_ai.prompt.blocks.design import build_design_block, resolve_color_mode
from esports_poster_ai.prompt.blocks.game_logo import build_game_logo_block
from esports_poster_ai.prompt.blocks.game_rules import build_game_rules_block
from esports_poster_ai.prompt.blocks.poster_type import POSTER_TYPE_BLOCKS
from esports_poster_ai.prompt.blocks.sponsors import build_sponsor_block
from esports_poster_ai.prompt.blocks.typography import build_typography_block
from esports_poster_ai.prompt.blocks.static import (
    BACKGROUND_ANALYSIS_BLOCK,
    FACTUAL_TEXT_BLOCK,
    OUTPUT_RULES_BLOCK,
)
from esports_poster_ai.prompt.router import route


def _is_non_empty_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _kv_lines(pairs: List[Tuple[str, Any]]) -> List[str]:
    """Render (label, value) pairs as '- label: value', skipping null/empty values."""
    out: List[str] = []
    for label, value in pairs:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        out.append(f"- {label}: {value}")
    return out


def _dict(parent: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Return parent[key] if it is a dict, else an empty dict."""
    v = parent.get(key) if isinstance(parent, dict) else None
    return v if isinstance(v, dict) else {}


def _stream_value(stream: Dict[str, Any]) -> Optional[str]:
    url = stream.get("url")
    if not _is_non_empty_str(url):
        return None
    platform = stream.get("platform")
    return f"{platform} · {url}" if _is_non_empty_str(platform) else url


def _match_time_value(match: Dict[str, Any]) -> Optional[str]:
    time_ = match.get("time")
    if not _is_non_empty_str(time_):
        return None
    tz = match.get("timezone")
    return f"{time_} {tz}" if _is_non_empty_str(tz) else time_


def _team_name(team: Dict[str, Any], fallback: str) -> str:
    return team.get("name") if _is_non_empty_str(team.get("name")) else fallback


# ---------------------------------------------------------------------------
# Per-poster-type METADATA builders. Each returns a list of rendered lines.
# ---------------------------------------------------------------------------


def _gameday_meta(input_data: Dict[str, Any]) -> List[str]:
    tournament = _dict(input_data, "tournament")
    match = _dict(input_data, "match")
    team1 = _dict(match, "team1")
    team2 = _dict(match, "team2")
    return _kv_lines(
        [
            ("Team 1", team1.get("name")),
            ("Team 2", team2.get("name")),
            ("Tournament", tournament.get("name")),
            ("Phase", tournament.get("phase")),
            ("Circuit", tournament.get("circuit")),
            ("Date", match.get("date")),
            ("Format", match.get("format")),
            ("Match Time", _match_time_value(match)),
            ("Stream", _stream_value(_dict(input_data, "stream"))),
        ]
    )


def _game_results_meta(input_data: Dict[str, Any]) -> List[str]:
    tournament = _dict(input_data, "tournament")
    match = _dict(input_data, "match")
    team1 = _dict(match, "team1")
    team2 = _dict(match, "team2")
    n1 = _team_name(team1, "Team 1")
    n2 = _team_name(team2, "Team 2")

    lines = _kv_lines(
        [
            ("Team 1", team1.get("name")),
            ("Team 2", team2.get("name")),
            ("Tournament", tournament.get("name")),
            ("Phase", tournament.get("phase")),
            ("Circuit", tournament.get("circuit")),
            ("Date", match.get("date")),
            ("Format", match.get("format")),
        ]
    )

    # Series score + derived winner (the single source of truth is the scores).
    s1, s2 = team1.get("score"), team2.get("score")
    if isinstance(s1, int) and isinstance(s2, int):
        lines.append(f"- Series Score: {n1} {s1} — {s2} {n2}")
        if s1 != s2:
            winner, loser = (n1, n2) if s1 > s2 else (n2, n1)
            lines.append(
                f"- Winner: {winner} — render as the winning team "
                f"(larger, brighter, elevated)"
            )
            lines.append(f"- Defeated: {loser} — render slightly smaller, cooler tone")

    # Valorant per-map results (distinct from the series score).
    maps = match.get("maps")
    if isinstance(maps, list):
        map_lines: List[str] = []
        for i, m in enumerate(maps, start=1):
            if not isinstance(m, dict):
                continue
            map_name = m.get("map_name")
            r1, r2 = m.get("rounds_team1"), m.get("rounds_team2")
            label = map_name if _is_non_empty_str(map_name) else f"Map {i}"
            if isinstance(r1, int) and isinstance(r2, int):
                map_lines.append(f"  - {label}: {n1} {r1} — {r2} {n2}")
            elif _is_non_empty_str(map_name):
                map_lines.append(f"  - {label}")
        if map_lines:
            lines.append("- Maps:")
            lines.extend(map_lines)

    # MVP (optional).
    mvp = _dict(input_data, "mvp")
    if mvp.get("enabled") is True and _is_non_empty_str(mvp.get("player_name")):
        mvp_str = str(mvp.get("player_name"))
        if _is_non_empty_str(mvp.get("agent_name")):
            mvp_str += f" ({mvp.get('agent_name')})"
        stat_label, stat_value = mvp.get("stat_label"), mvp.get("stat_value")
        if _is_non_empty_str(stat_label) and stat_value not in (None, ""):
            mvp_str += f" — {stat_label}: {stat_value}"
        lines.append(f"- MVP: {mvp_str}")

    return lines


def _roster_reveal_meta(input_data: Dict[str, Any]) -> List[str]:
    team = _dict(input_data, "team")
    roster = _dict(input_data, "roster")

    lines = _kv_lines(
        [
            ("Team", team.get("name")),
            ("Season", roster.get("season")),
            ("Head Coach", roster.get("head_coach")),
        ]
    )

    players = roster.get("players")
    if isinstance(players, list):
        player_lines: List[str] = []
        for i, player in enumerate(players, start=1):
            if not isinstance(player, dict):
                continue
            ign, role = player.get("ign"), player.get("role")
            if not _is_non_empty_str(ign) and not _is_non_empty_str(role):
                continue
            entry = ign if _is_non_empty_str(ign) else f"Player {i}"
            if _is_non_empty_str(role):
                entry += f" — {role}"
            if _is_non_empty_str(player.get("signature_agent")):
                entry += f" (signature agent: {player.get('signature_agent')})"
            if player.get("is_new_signing") is True:
                entry += " [NEW SIGNING]"
            player_lines.append(f"  - {entry}")
        if player_lines:
            lines.append("- Players:")
            lines.extend(player_lines)

        # Explicit reference-image → player mapping. The image list passed to
        # gpt-image-2 is ordered exactly like this; the prompt makes that
        # alignment a hard placement rule so photos and IGNs never swap.
        # This mirrors `_extract_input_images` in modes/fresh.py.
        mapping_lines: List[str] = []
        idx = 1
        if _is_non_empty_str(team.get("logo_path")):
            label = team.get("name") or "team"
            mapping_lines.append(f"  - Reference image #{idx}: TEAM LOGO ({label})")
            idx += 1
        for player in players:
            if not isinstance(player, dict):
                continue
            if not _is_non_empty_str(player.get("image_path")):
                continue
            ign = player.get("ign") or "—"
            role = player.get("role")
            tail = f" ({role})" if _is_non_empty_str(role) else ""
            mapping_lines.append(f"  - Reference image #{idx}: PLAYER PHOTO → {ign}{tail}")
            idx += 1
        if mapping_lines:
            lines.append(
                "- Roster photo mapping (strict 1:1 with reference image order — do NOT swap):"
            )
            lines.extend(mapping_lines)
            lines.append(
                "- PLACEMENT RULE: Each player photo MUST be placed in that player's "
                "own card slot. The IGN rendered beneath/beside a photo MUST match "
                "that photo. Never reuse one player's face for another. If a "
                "referenced photo is unavailable, leave the corresponding slot "
                "empty rather than substituting another player's face."
            )

        # Players without a provided photo must NOT get an invented face — the #1
        # roster failure is the model fabricating realistic headshots to fill empty
        # cards. Call them out explicitly and forbid it.
        valid_players = [
            p for p in players
            if isinstance(p, dict)
            and (_is_non_empty_str(p.get("ign")) or _is_non_empty_str(p.get("role")))
        ]
        no_photo = [
            (p.get("ign") or "a player")
            for p in valid_players
            if not _is_non_empty_str(p.get("image_path"))
        ]
        if no_photo:
            who = (
                "EVERY player"
                if len(no_photo) == len(valid_players)
                else "these players: " + ", ".join(no_photo)
            )
            lines.append(
                f"- NO-PHOTO PLAYERS — CRITICAL: {who} have NO photo supplied. Render "
                "each such player's card with the IGN + role as TEXT ONLY and NO "
                "portrait — at most a neutral, faceless silhouette or a monogram / "
                "initial placeholder in the photo area. Do NOT invent, generate, "
                "imagine, or hallucinate any human face, headshot, or player likeness "
                "for a player without a provided photo. A fabricated face is a hard "
                "failure — an empty/text-only card is correct."
            )

    return lines


def _tournament_announcement_meta(input_data: Dict[str, Any]) -> List[str]:
    t = _dict(input_data, "tournament")
    return _kv_lines(
        [
            ("Tournament", t.get("name")),
            ("Start Date", t.get("start_date")),
            ("Location", t.get("location")),
            ("Prize Pool", t.get("prize_pool")),
            ("Teams Competing", t.get("teams_count")),
            ("Format", t.get("format")),
            ("Circuit", t.get("circuit")),
            ("Tagline", t.get("tagline")),
            ("Sub-tagline", t.get("sub_tagline")),
        ]
    )


def _tournament_banner_meta(input_data: Dict[str, Any]) -> List[str]:
    t = _dict(input_data, "tournament")
    return _kv_lines(
        [
            ("Tournament", t.get("name")),
            ("Date Range", t.get("date_range")),
            ("Location", t.get("location")),
            ("Prize Pool", t.get("prize_pool")),
            ("Circuit", t.get("circuit")),
            ("Tagline", t.get("tagline")),
        ]
    )


_METADATA_BUILDERS = {
    "gameday": _gameday_meta,
    "game_results": _game_results_meta,
    "roster_reveal": _roster_reveal_meta,
    "tournament_announcement": _tournament_announcement_meta,
    "tournament_banner": _tournament_banner_meta,
}


def _build_metadata_block(input_data: Dict[str, Any]) -> str:
    """Build the METADATA block, adapted to the poster type."""
    meta = _dict(input_data, "_meta")
    header = _kv_lines(
        [("Game", meta.get("game")), ("Poster Type", meta.get("poster_type"))]
    )
    builder = _METADATA_BUILDERS.get(meta.get("poster_type"))
    body = builder(input_data) if builder else []
    return ("METADATA:\n" + "\n".join(header + body)).strip()


_IMAGE_FACTUAL_RULES = """\
RENDER RULES — HIGHEST PRIORITY, override anything above that conflicts:
- Every piece of text on this poster must come ONLY from the FACTUAL DATA
  listed above. Reproduce each score digit, name, and date character for
  character — exactly as written.
- Do NOT invent, add, complete, or "correct" any tournament name, team name,
  player name, location, date, time, score, or format. If a value is not in
  the FACTUAL DATA above, it does NOT appear anywhere on the poster.
- Do NOT use real-world knowledge about these teams, players, or tournament.
  Treat the logos purely as graphics.
- Any text beyond the FACTUAL DATA must be purely decorative (hero title,
  hype/result phrase) and must never look like a name, score, or date."""


def build_image_factual_footer(input_data: Dict[str, Any]) -> str:
    """
    Hard factual-constraint block appended DIRECTLY to the prompt sent to the
    image model.

    The image-generation prompt is written by GPT-4o, which can paraphrase or
    drop factual values. This footer re-injects the verbatim factual data plus
    a render-exactly rule onto the very prompt gpt-image-2 receives, so the
    facts bypass GPT-4o's rewrite (removes one telephone hop).
    """
    metadata = _build_metadata_block(input_data)
    factual = metadata.replace("METADATA:", "FACTUAL DATA (verbatim):", 1)
    return (
        "=== FACTUAL CONTENT — RENDER EXACTLY, INVENT NOTHING ===\n\n"
        f"{factual}\n\n"
        f"{_IMAGE_FACTUAL_RULES}"
    )


_IMAGE_STYLE_RULES = """\
STYLE RULES — apply to the WHOLE poster; override the source background's own
colors and mood wherever they conflict with the directives above:
- Color-grade the ENTIRE frame toward the dominant color above — not only the
  accents, glow, or text. Re-tint the background, lighting, and atmosphere so
  that hue clearly dominates the finished poster.
- Treat the vibe and energy above as the overall mood and composition density
  of the poster, not a minor accent.
- These are deliberate creative directions from the user. Do NOT fall back to
  the source background's original palette or mood because it looks safer."""

# Auto color mode: keep the background's own palette instead of forcing a hue.
_IMAGE_STYLE_RULES_AUTO = """\
STYLE RULES — apply to the WHOLE poster:
- Build the palette FROM the background image's own dominant colors: sample them
  and reuse them for the title, accents, glow, and overlays so the design feels
  unified with the background. Do NOT impose an external or single forced color,
  and do NOT re-tint the whole frame to a hue the background does not already have.
- Treat the vibe and energy above as the overall mood and composition density of
  the poster, not a minor accent."""


def _style_directive_lines(
    input_data: Dict[str, Any], style_dna: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Verbatim style directives for the image footer.

    Consistency mode (a Style DNA is present) speaks in palette + lighting +
    atmosphere; fresh mode speaks in the user's design vibe / color / energy.
    Mirrors the precedence the assembler uses for the in-prompt style block.
    """
    if isinstance(style_dna, dict) and style_dna:
        lines: List[str] = []
        palette = style_dna.get("palette")
        if isinstance(palette, list):
            hexes = ", ".join(c for c in palette if _is_non_empty_str(c))
            if hexes:
                lines.append(
                    f"- Dominant palette (use these as the poster's primary colors): {hexes}"
                )
        for label, key in (("Lighting", "lighting"), ("Atmosphere", "atmosphere"), ("Energy", "energy")):
            if _is_non_empty_str(style_dna.get(key)):
                lines.append(f"- {label}: {style_dna.get(key)}")
        return lines

    design = input_data.get("design") if isinstance(input_data, dict) else None
    if not isinstance(design, dict):
        return []
    lines = []
    if _is_non_empty_str(design.get("vibe")):
        lines.append(f"- Vibe: {design.get('vibe')}")
    if resolve_color_mode(design) == "auto":
        lines.append(
            "- Color: use the BACKGROUND image's own dominant colors as the poster's "
            "palette; do not force an external color"
        )
    elif _is_non_empty_str(design.get("primary_color")):
        lines.append(
            f"- Dominant color (make this the primary color of the WHOLE poster): "
            f"{design.get('primary_color')}"
        )
    if _is_non_empty_str(design.get("energy")):
        lines.append(f"- Energy: {design.get('energy')}")
    return lines


def build_image_style_footer(
    input_data: Dict[str, Any], style_dna: Optional[Dict[str, Any]] = None
) -> str:
    """
    Hard visual-style block appended DIRECTLY to the prompt the image model
    receives — the style counterpart to `build_image_factual_footer`.

    The user's design direction (dominant color, vibe, energy) only reaches
    gpt-image-2 through GPT-4o's rewrite, which — looking at the real source
    background — tends to describe the colors it sees and soften the requested
    ones. Re-stating the directives verbatim here bypasses that dilution and
    explicitly tells the edit pass to color-grade the whole frame, instead of
    leaving the dominant color as a mere accent on the original background.

    Returns an empty string when no style directives apply.
    """
    lines = _style_directive_lines(input_data, style_dna)
    if not lines:
        return ""
    body = "\n".join(lines)
    # Fresh mode with auto color → keep the background's palette; otherwise (or in
    # DNA mode) use the color-grade-to-dominant rules.
    design = input_data.get("design") if isinstance(input_data, dict) else None
    auto = not (isinstance(style_dna, dict) and style_dna) and resolve_color_mode(design) == "auto"
    rules = _IMAGE_STYLE_RULES_AUTO if auto else _IMAGE_STYLE_RULES
    return (
        "=== VISUAL STYLE — APPLY ACROSS THE WHOLE POSTER ===\n\n"
        f"{body}\n\n"
        f"{rules}"
    )


def build_prompt(input_data: Dict[str, Any], style_dna: Optional[Dict[str, Any]] = None) -> str:
    """
    Assemble the final prompt string in fixed order:

    1. BACKGROUND_ANALYSIS_BLOCK           — always
    2. METADATA block                      — always, adapted to poster_type
    3. FACTUAL_TEXT_BLOCK                   — always (verbatim-text hard rule)
    4. POSTER_TYPE_BLOCKS[poster_type]     — always
    5. GAME_RULES[game]                    — only when needs_game_rules
    6. asset_block                         — always
    7. visual-style block                  — consistency DNA, else design block
    8. sponsor-bar reservation              — only when sponsors.enabled
    9. OUTPUT_RULES_BLOCK                  — always
    """
    decisions = route(input_data, style_dna=style_dna)
    poster_type = decisions.get("poster_type")
    game = decisions.get("game")

    poster_type_block = POSTER_TYPE_BLOCKS.get(poster_type)
    if not poster_type_block:
        raise ValueError(f"Unknown poster_type: {poster_type!r}")

    parts: List[str] = []
    parts.append(BACKGROUND_ANALYSIS_BLOCK)
    parts.append(_build_metadata_block(input_data))
    parts.append(FACTUAL_TEXT_BLOCK)
    parts.append(poster_type_block)

    if decisions.get("needs_game_rules"):
        parts.append(build_game_rules_block(str(game)))

    parts.append(build_asset_block(input_data))

    # Visual style: when a Style DNA is supplied it takes precedence and is
    # injected as a hard constraint ("match my previous posters"). Otherwise
    # the user's fresh-mode design choices drive the style. Keyed on the
    # actual presence of a DNA — NOT on _meta.mode — so a loaded DNA always
    # reaches the prompt regardless of what the JSON's mode field says.
    style_block = ""
    if decisions.get("style_dna"):
        style_block = build_consistency_block(decisions.get("style_dna"))
    if not style_block:
        style_block = build_design_block(input_data.get("design"))
    if style_block:
        parts.append(style_block)

    # Official game logo: the vision model picks where the (reference-supplied)
    # game wordmark goes, based on the background.
    game_logo_block = build_game_logo_block(input_data)
    if game_logo_block:
        parts.append(game_logo_block)

    # Per-poster typography variety — FRESH mode only. In consistency mode the
    # Style DNA already carries the saved typography (see build_consistency_block),
    # so randomizing here would break the "keep the same look" guarantee.
    if not decisions.get("style_dna"):
        parts.append(build_typography_block(input_data))

    # Reserve a clean strip for the sponsor bar (composited post-generation).
    sponsor_block = build_sponsor_block(input_data)
    if sponsor_block:
        parts.append(sponsor_block)

    parts.append(OUTPUT_RULES_BLOCK)
    return "\n\n".join([p.strip() for p in parts if p and p.strip()])
