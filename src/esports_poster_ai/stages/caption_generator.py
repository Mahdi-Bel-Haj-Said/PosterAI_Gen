"""
Caption-generation stage.

Given a completed poster Job, produce a short social-media caption that's
plausible to post directly to Twitter / Facebook / Instagram / LinkedIn
without manual editing. The stage:

  1. Pulls structured facts out of ``job.input_data`` — TEAMS, TOURNAMENT,
     PLAYERS, MVP, SCORE, MAPS, VENUE, PRIZE POOL — these are AUTHORITATIVE.
     The LLM never invents them; it just chooses prose around them.
  2. Auto-builds a list of REACH HASHTAGS (game-canonical + tournament +
     team short names + esports universals) so the model can pick from a
     curated set instead of inventing tags that don't exist.
  3. Injects a game-specific VOCABULARY hint (LoL or Valorant lingo) plus
     esports universals, so captions sound like a fan wrote them — not a
     marketing tool.
  4. Calls Gemini with a tight system prompt + three poster-type-distinct
     few-shot examples.
  5. Trims the model output and returns the caption string. Persistence
     is the caller's job.

Design block excluded by intent
-------------------------------
``input_data.design`` (vibe, primary_color, energy) is *not* read here.
Those drive the IMAGE, not the social copy — pasting "intense cyberpunk
mood" into a tweet reads like AI slop.

Why not per-platform variants?
------------------------------
For v1 we still generate a single caption that's reasonable everywhere.
Twitter is the tightest container (280 chars) so we target that. Easy to
add a ``platform`` parameter later if Instagram wants a longer body and
LinkedIn a different tone.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from esports_poster_ai.clients.gemini_client import generate_text
from esports_poster_ai.domain.job import Job

logger = logging.getLogger(__name__)


# ---- vocabularies -----------------------------------------------------------
# These feed the prompt as inspiration — the model picks what fits. Keep each
# entry short (1-2 words) so the LLM can drop them into a sentence naturally.

_GAME_LEXICON: Dict[str, Dict[str, Any]] = {
    "league_of_legends": {
        "label": "League of Legends",
        # Authentic LoL terminology a fan would actually use.
        "vocabulary": [
            "draft phase", "side selection", "mid-lane diff", "jungle pathing",
            "ADC carry", "support roam", "top island", "gank", "baron buff",
            "dragon soul", "rift herald", "teamfight", "objective control",
            "vision war", "scaling team", "early-game pressure", "throne",
            "summoner's rift", "nexus push", "tower dive",
        ],
        # Always-relevant hashtags for the game.
        "base_hashtags": ["#LeagueOfLegends", "#LoL", "#LoLEsports"],
        # Recognisable league/tournament hashtags. The LLM picks the one(s)
        # that match the tournament name.
        "league_hashtags": [
            "#LEC", "#LCS", "#LCK", "#LPL", "#PCS", "#CBLOL", "#LLA",
            "#Worlds", "#MSI", "#EWC", "#EsportsWorldCup",
        ],
    },
    "valorant": {
        "label": "VALORANT",
        "vocabulary": [
            "agent comp", "map veto", "attack side", "defense side",
            "pistol round", "eco round", "thrifty", "force buy", "full buy",
            "spike plant", "spike defuse", "retake", "clutch", "1v3", "1v4",
            "ace", "headshot", "lurker", "entry frag", "operator pick",
            "double up", "executor", "agent pool",
        ],
        "base_hashtags": ["#VALORANT", "#VCT"],
        "league_hashtags": [
            "#VCTAmericas", "#VCTEMEA", "#VCTPacific", "#VCTChina",
            "#VALORANTChampions", "#VCTMasters", "#GameChangers",
        ],
    },
}

# Universal esports terms a caption can lean on regardless of game.
_ESPORTS_VOCABULARY: List[str] = [
    "clutch", "scrim", "GG WP", "GG", "throw", "comeback", "dynasty",
    "rivalry", "showdown", "playoff run", "gauntlet", "domination",
    "statement win", "upset", "underdog", "favourite", "champion",
    "crown", "throne", "hype", "fire", "let's go", "locked in",
]


# ---- fact extraction --------------------------------------------------------


_POSTER_TYPE_LABEL = {
    "gameday": "match day announcement",
    "roster_reveal": "roster reveal",
    "tournament_announcement": "tournament announcement",
    "tournament_banner": "tournament banner",
    "game_results": "match result",
}


def _stringify_team(team: Optional[Dict[str, Any]]) -> str:
    """Return 'FNATIC (FNC)' or just 'FNATIC' if no short name."""
    if not isinstance(team, dict):
        return ""
    name = (team.get("name") or "").strip()
    short = (team.get("short_name") or "").strip()
    if name and short and short.lower() != name.lower():
        return f"{name} ({short})"
    return name or short


def _is_nonempty(value: Any) -> bool:
    """Loose truthiness — keeps zero scores (a legitimate result)."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _resolve_input_data(job: Job) -> Dict[str, Any]:
    """
    Return the input_data that actually carries facts.

    Refine-mode jobs only carry ``{_meta, refine: {parent_job_id, ...}}`` —
    the teams, score, MVP, etc. live on the PARENT job. Walk back so a
    refined poster's caption gets the same facts the original would.
    Falls through to ``job.input_data`` for non-refine jobs (the normal case).
    """
    raw: Dict[str, Any] = job.input_data or {}
    refine = raw.get("refine") or {}
    parent_id = refine.get("parent_job_id")
    if not parent_id:
        return raw

    # Lazy import — avoids a circular import between stages and jobs.store.
    from esports_poster_ai.jobs.store import JobStore

    try:
        parent = JobStore().get(parent_id)
    except Exception:  # noqa: BLE001 — best-effort lookup
        parent = None
    if parent is None or not parent.input_data:
        return raw

    # Merge: keep child's _meta (poster_type/game came from there), borrow
    # everything else from the parent.
    merged = dict(parent.input_data)
    if raw.get("_meta"):
        merged["_meta"] = raw["_meta"]
    return merged


def _build_facts(job: Job) -> Dict[str, Any]:
    """
    Pull every caption-relevant field out of the resolved input_data.

    Per poster_type we extract a different shape:
      * gameday        : teams, schedule, stream, optional player_feature flag
      * game_results   : teams + scores, derived winner, MVP, valorant maps
      * roster_reveal  : team + ordered player list (IGN + role + new flag)
      * tournament_*   : tournament name + phase + tagline + venue + prize pool
    """
    d: Dict[str, Any] = _resolve_input_data(job)
    meta = d.get("_meta") or {}
    poster_type = meta.get("poster_type") or "gameday"
    game = meta.get("game") or ""

    tournament = d.get("tournament") or {}
    facts: Dict[str, Any] = {
        "game": game,
        "poster_type": poster_type,
        "tournament": tournament.get("name") or job.tournament_id or "",
        "phase": tournament.get("phase"),
    }

    if poster_type in ("gameday", "game_results"):
        match = d.get("match") or {}
        team1 = match.get("team1") or {}
        team2 = match.get("team2") or {}
        facts["team1"] = _stringify_team(team1)
        facts["team2"] = _stringify_team(team2)
        facts["team1_short"] = (team1.get("short_name") or "").strip()
        facts["team2_short"] = (team2.get("short_name") or "").strip()
        facts["team1_score"] = team1.get("score")
        facts["team2_score"] = team2.get("score")
        facts["format"] = match.get("format")
        facts["date"] = match.get("date")
        facts["time"] = match.get("time")
        facts["timezone"] = match.get("timezone")

        # Derived winner — only when both scores are numeric and distinct.
        s1, s2 = facts["team1_score"], facts["team2_score"]
        if isinstance(s1, int) and isinstance(s2, int) and s1 != s2:
            facts["winner"] = facts["team1_short"] if s1 > s2 else facts["team2_short"]
            facts["loser"] = facts["team2_short"] if s1 > s2 else facts["team1_short"]

        # Stream (gameday only typically — but it's harmless on results).
        stream = d.get("stream") or {}
        facts["stream_platform"] = stream.get("platform")
        facts["stream_url"] = stream.get("url")

        # MVP (game_results, when enabled).
        mvp = d.get("mvp") or {}
        if mvp.get("enabled"):
            facts["mvp_player"] = mvp.get("player_name")
            facts["mvp_agent"] = mvp.get("agent_name")  # Valorant only
            label = mvp.get("stat_label")
            value = mvp.get("stat_value")
            if label and value:
                facts["mvp_stat"] = f"{label}: {value}"

        # Valorant per-map results.
        maps = match.get("maps") or []
        clean_maps = []
        for m in maps:
            if not isinstance(m, dict):
                continue
            name = (m.get("map_name") or "").strip()
            r1 = m.get("rounds_team1")
            r2 = m.get("rounds_team2")
            if name and isinstance(r1, int) and isinstance(r2, int):
                clean_maps.append({"map": name, "rounds": f"{r1}-{r2}"})
        if clean_maps:
            facts["maps"] = clean_maps

    elif poster_type == "roster_reveal":
        team = d.get("team") or {}
        facts["team_name"] = team.get("name") or ""
        roster = d.get("roster") or {}
        facts["season"] = roster.get("season")
        facts["head_coach"] = roster.get("head_coach")
        players_raw = roster.get("players") or []
        facts["players"] = [
            {
                "ign": (p.get("ign") or "").strip(),
                "role": (p.get("role") or "").strip(),
                "new": bool(p.get("is_new_signing")),
            }
            for p in players_raw
            if isinstance(p, dict) and p.get("ign")
        ]
        facts["has_new_signings"] = any(p["new"] for p in facts["players"])

    elif poster_type in ("tournament_announcement", "tournament_banner"):
        facts["start_date"] = tournament.get("start_date")
        facts["location"] = tournament.get("location")
        facts["prize_pool"] = tournament.get("prize_pool")
        facts["teams_count"] = tournament.get("teams_count")
        facts["format"] = tournament.get("format")
        facts["tagline"] = tournament.get("tagline")
        facts["sub_tagline"] = tournament.get("sub_tagline")

    return facts


# ---- hashtag suggestions ----------------------------------------------------


_TAG_SAFE_RE = re.compile(r"[^A-Za-z0-9]+")


def _slugify_tag(value: str) -> Optional[str]:
    """Turn 'EWC 2026' into '#EWC2026'. Returns None if nothing remains."""
    if not value:
        return None
    slug = _TAG_SAFE_RE.sub("", value)
    if not slug:
        return None
    return f"#{slug}"


def _suggested_hashtags(facts: Dict[str, Any]) -> List[str]:
    """
    Build a deduped, ordered list of relevant hashtags from facts.

    Order matters — the LLM tends to pick from the top of the list, so we put
    the most-recognisable tags (game-canonical, tournament) first, then
    team-affinity tags (#FNC, #FNCWIN), then esports generics.
    """
    seen: set[str] = set()
    out: List[str] = []

    def _push(tag: Optional[str]) -> None:
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)

    game = facts.get("game", "")
    lex = _GAME_LEXICON.get(game, {})

    # 1. Game canonical
    for t in lex.get("base_hashtags", []):
        _push(t)

    # 2. Tournament tag — built from name, plus any matching league hashtag.
    tname = facts.get("tournament") or ""
    if tname:
        _push(_slugify_tag(tname))
        for ltag in lex.get("league_hashtags", []):
            # Match e.g. "EWC" inside "EWC 2026" or "LEC" inside "LEC Summer 2026".
            short = ltag.lstrip("#")
            if short and short.lower() in tname.lower():
                _push(ltag)

    # 3. Per-team tags (only on match-type posters where team_short exists).
    poster_type = facts.get("poster_type")
    if poster_type in ("gameday", "game_results"):
        winner = facts.get("winner")
        for team_short in (facts.get("team1_short"), facts.get("team2_short")):
            if not team_short:
                continue
            _push(_slugify_tag(team_short))
            # Win tags only on the team that actually won (for results) or on
            # both sides (for gameday — bait both fanbases).
            if poster_type == "game_results":
                if team_short.upper() == (winner or "").upper():
                    _push(f"#{_TAG_SAFE_RE.sub('', team_short)}WIN")
            else:
                _push(f"#{_TAG_SAFE_RE.sub('', team_short)}WIN")
    elif poster_type == "roster_reveal":
        # Tag the team itself if it has a slug-able name.
        _push(_slugify_tag(facts.get("team_name") or ""))

    # 4. Esports generics — always at the bottom; safe filler.
    _push("#Esports")
    _push("#Gaming")

    return out


# ---- facts block formatter --------------------------------------------------


def _format_facts_block(facts: Dict[str, Any]) -> str:
    """
    Render the facts as a labelled list the LLM can read without confusion.

    Per-type fields only show when present — we never emit "Score: None" or
    similar; missing data is silently omitted so the model isn't tempted to
    backfill it with junk.
    """
    lines: List[str] = []
    pt = facts.get("poster_type", "")
    label = _POSTER_TYPE_LABEL.get(pt, pt)
    lines.append(f"Poster type: {label}")

    game = facts.get("game")
    if game:
        game_label = _GAME_LEXICON.get(game, {}).get("label") or game.replace("_", " ").title()
        lines.append(f"Game: {game_label}")

    if facts.get("tournament"):
        line = f"Tournament: {facts['tournament']}"
        if _is_nonempty(facts.get("phase")):
            line += f" — {facts['phase']}"
        lines.append(line)

    if pt in ("gameday", "game_results"):
        if facts.get("team1") and facts.get("team2"):
            lines.append(f"Match: {facts['team1']} vs {facts['team2']}")
        if _is_nonempty(facts.get("format")):
            lines.append(f"Format: {facts['format']}")

        # Score line (results) — uses short names for compactness.
        s1, s2 = facts.get("team1_score"), facts.get("team2_score")
        if isinstance(s1, int) and isinstance(s2, int):
            ts1 = facts.get("team1_short") or facts.get("team1", "T1")
            ts2 = facts.get("team2_short") or facts.get("team2", "T2")
            lines.append(f"Score: {ts1} {s1}-{s2} {ts2}")
        if facts.get("winner"):
            lines.append(f"Winner: {facts['winner']}")

        # Schedule (gameday).
        when_parts = [facts.get("date"), facts.get("time"), facts.get("timezone")]
        when = " ".join(x for x in when_parts if _is_nonempty(x)).strip()
        if when:
            lines.append(f"When: {when}")

        if _is_nonempty(facts.get("stream_url")):
            platform = facts.get("stream_platform") or "stream"
            lines.append(f"Watch on {platform}: {facts['stream_url']}")

        # MVP block (results, optional).
        if facts.get("mvp_player"):
            mvp_line = f"MVP: {facts['mvp_player']}"
            if facts.get("mvp_agent"):
                mvp_line += f" on {facts['mvp_agent']}"
            if facts.get("mvp_stat"):
                mvp_line += f" ({facts['mvp_stat']})"
            lines.append(mvp_line)

        # Valorant per-map (results).
        if facts.get("maps"):
            map_lines = ", ".join(f"{m['map']} {m['rounds']}" for m in facts["maps"])
            lines.append(f"Maps: {map_lines}")

    elif pt == "roster_reveal":
        if facts.get("team_name"):
            lines.append(f"Team: {facts['team_name']}")
        if _is_nonempty(facts.get("season")):
            lines.append(f"Season: {facts['season']}")
        if _is_nonempty(facts.get("head_coach")):
            lines.append(f"Head coach: {facts['head_coach']}")
        if facts.get("players"):
            roster_line = ", ".join(
                f"{p['ign']} ({p['role']})" + (" — new" if p["new"] else "")
                for p in facts["players"]
            )
            lines.append(f"Roster: {roster_line}")
        if facts.get("has_new_signings"):
            lines.append("Note: roster includes new signings — call that out.")

    elif pt in ("tournament_announcement", "tournament_banner"):
        if _is_nonempty(facts.get("start_date")):
            lines.append(f"Start date: {facts['start_date']}")
        if _is_nonempty(facts.get("location")):
            lines.append(f"Location: {facts['location']}")
        if _is_nonempty(facts.get("prize_pool")):
            lines.append(f"Prize pool: {facts['prize_pool']}")
        if _is_nonempty(facts.get("teams_count")):
            lines.append(f"Teams competing: {facts['teams_count']}")
        if _is_nonempty(facts.get("format")):
            lines.append(f"Format: {facts['format']}")
        if _is_nonempty(facts.get("tagline")):
            lines.append(f"Tagline: {facts['tagline']}")
        if _is_nonempty(facts.get("sub_tagline")):
            lines.append(f"Sub-tagline: {facts['sub_tagline']}")

    return "\n".join(lines)


def _vocabulary_block(facts: Dict[str, Any]) -> str:
    """Suggest 6-8 game-specific + esports terms to the model as flavor."""
    game = facts.get("game", "")
    game_lex = _GAME_LEXICON.get(game, {})
    game_terms = game_lex.get("vocabulary", [])[:10]
    universal = _ESPORTS_VOCABULARY[:10]
    lines = []
    if game_terms:
        lines.append(f"GAME LINGO ({game_lex.get('label', game)}): " + ", ".join(game_terms))
    lines.append("ESPORTS UNIVERSALS: " + ", ".join(universal))
    return "\n".join(lines)


# ---- system prompt + few-shots ---------------------------------------------


_SYSTEM_INSTRUCTIONS = """\
You write punchy social-media captions for esports posters that real fans would
write — not marketing copy. Your job:

REQUIREMENTS (non-negotiable)
- Output ONE caption. No options, no preamble, no "Here's your caption:".
- Use the FACTS verbatim — team names, scores, MVPs, dates. Never invent.
- If teams + score are in the facts, the score MUST appear in the caption.
- If a tournament name is in the facts, the tournament MUST appear (full name,
  abbreviation, or a slug-able variant — your call).
- Pick 3-6 hashtags from SUGGESTED HASHTAGS. Do NOT make up new hashtags.
- Total length under 240 characters so it fits Twitter.

STYLE
- 1 to 3 short lines of prose, then the hashtags on a final line.
- Use emojis sparingly (max 2 across the whole caption). Picks: 🔥 ⚔️ 👑 🎯 🎮 💀
  for hype/win, 🚨 ⏳ 👀 for announcements.
- Energetic but not cringe. Lean on terms from VOCABULARY when they fit
  naturally — they make the caption read like a fan wrote it, not a tool.
- Universal tone: should read fine on Twitter, Instagram, and Facebook.
- Do NOT include the words "AI-generated" or "POSTER/AI".
- Do NOT mention design choices (no "cyberpunk", "intense vibe", etc.).

FEW-SHOT EXAMPLES
================

FACTS:
Poster type: match day announcement
Game: League of Legends
Tournament: EWC 2026 — Quarterfinals
Match: FNATIC (FNC) vs T1 (T1)
When: 17:00 CET
Watch on Twitch: twitch.tv/caedrel
SUGGESTED HASHTAGS: #LeagueOfLegends #LoL #LoLEsports #EWC2026 #EWC #FNC #FNCWIN #T1 #T1WIN #Esports

CAPTION:
The rivalry resumes. ⚔️
FNC vs T1 — EWC 2026 Quarterfinals
17:00 CET · twitch.tv/caedrel
#EWC2026 #LoLEsports #FNCWIN #T1WIN

FACTS:
Poster type: match result
Game: League of Legends
Tournament: EWC 2026
Match: JSK vs GNG
Format: Bo5
Score: JSK 3-1 GNG
Winner: JSK
SUGGESTED HASHTAGS: #LeagueOfLegends #LoL #LoLEsports #EWC2026 #EWC #JSK #JSKWIN #GNG #Esports

CAPTION:
JSK 3-1 GNG. 🔥
Statement win on the Rift — quarterfinal scaling team takes the series.
#JSKWIN #EWC2026 #LoLEsports

FACTS:
Poster type: match result
Game: VALORANT
Tournament: VCT 2026 — EMEA Stage 2
Match: FNATIC (FNC) vs Team Liquid (TL)
Score: FNC 2-1 TL
Winner: FNC
MVP: Boaster on Sova (ACS: 287)
Maps: Ascent 13-9, Sunset 7-13, Lotus 13-11
SUGGESTED HASHTAGS: #VALORANT #VCT #VCTEMEA #VCT2026 #FNC #FNCWIN #TL #Esports

CAPTION:
FNC over TL, 2-1. Lotus closes it 13-11. 🎯
Boaster's Sova went off — 287 ACS executor performance.
#VCTEMEA #FNCWIN #VALORANT

FACTS:
Poster type: roster reveal
Game: League of Legends
Team: Karmine Corp
Season: 2026
Roster: Cabochard (Top) — new, Yike (Jungle), Vladi (Mid), Caliste (Bot), Targamas (Support) — new
Note: roster includes new signings — call that out.
SUGGESTED HASHTAGS: #LeagueOfLegends #LoL #LoLEsports #LEC #KarmineCorp #Esports

CAPTION:
The 2026 roster is locked in. 🎮
Cabochard. Yike. Vladi. Caliste. Targamas.
Two new signings, one mission. The grind starts now.
#LEC #LoLEsports #KCorp

FACTS:
Poster type: tournament announcement
Game: League of Legends
Tournament: EWC 2026
Start date: July 8, 2026
Location: Riyadh, Saudi Arabia
Prize pool: $2,000,000
Teams competing: 16
Tagline: One throne. One champion.
SUGGESTED HASHTAGS: #LeagueOfLegends #LoL #LoLEsports #EWC2026 #EWC #Esports

CAPTION:
One throne. One champion. 👑
EWC 2026 · Riyadh · July 8.
16 teams. $2M on the line.
#EWC2026 #LoLEsports
"""


def _build_prompt(job: Job) -> str:
    facts = _build_facts(job)
    tags = _suggested_hashtags(facts)
    vocab = _vocabulary_block(facts)
    return (
        f"{_SYSTEM_INSTRUCTIONS}\n\n"
        f"NOW WRITE THE CAPTION FOR THESE FACTS\n"
        f"====================================\n\n"
        f"FACTS:\n{_format_facts_block(facts)}\n"
        f"SUGGESTED HASHTAGS: {' '.join(tags) if tags else '(none)'}\n\n"
        f"VOCABULARY (use when natural):\n{vocab}\n\n"
        f"CAPTION:\n"
    )


# ---- post-processing --------------------------------------------------------


_LEADING_LABEL_RE = re.compile(r"^(caption|here'?s|here is)[:\s\-—]+", re.IGNORECASE)


def _clean_caption(raw: str) -> str:
    """
    Strip the noise Gemini sometimes prefixes ("Caption:", smart quotes around
    the whole block, etc.) and bound the length.
    """
    text = raw.strip()
    # Drop wrapping triple-backticks if the model decided to "code-block" it.
    if text.startswith("```"):
        text = text.strip("`").strip()
    # Drop any leading "Caption:" / "Here's your caption" preamble.
    text = _LEADING_LABEL_RE.sub("", text).strip()
    # Drop wrapping quotes.
    if len(text) >= 2 and text[0] in "\"'“”" and text[-1] in "\"'“”":
        text = text[1:-1].strip()
    # Hard cap — Twitter is the tightest at 280 chars; stay under for safety.
    if len(text) > 280:
        text = text[:277].rstrip() + "…"
    return text


# ---- public surface ---------------------------------------------------------


def generate_caption_for_job(job: Job) -> str:
    """
    Produce a single social caption for ``job``. Caller persists.

    Raises GeminiError on transport / API failures so the route layer can
    convert to a clean 502.
    """
    prompt = _build_prompt(job)
    # 300 output tokens is plenty for a 240-char caption + a hashtag line; the
    # extra headroom is for the model's planning tokens. temperature 0.85 keeps
    # output lively without going random.
    raw = generate_text(prompt, temperature=0.85, max_output_tokens=300)
    caption = _clean_caption(raw)
    logger.info(
        "caption.generated",
        extra={"job_id": job.job_id, "length": len(caption)},
    )
    return caption


__all__ = ["generate_caption_for_job"]
