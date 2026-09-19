"""
Layout blocks — how the poster's elements are arranged.

`build_layout_block` SAMPLES one of ten named composition patterns and hands it
to the vision model as a decision already made, picking the pool from the poster
format and how much content the brief carries.

It used to present all ten as a menu and let the model choose. That produced the
same failure the roster arrangements had: given a free choice the model converges
on one safe answer, so posters kept coming back in the same stacked-band
arrangement despite ten patterns being on offer. Choosing here spends the model's
judgement on executing the pattern against the background instead of picking it.

`build_roster_arrangement_block` does the same job one level down, for the five
player photos on a roster reveal. The poster-type block used to say "player
cards", so every roster came back as five rectangles; this samples a fresh
arrangement per poster from a curated bank instead.

Both choices are named in the output prompt, so they travel through to
gpt-image-2 instead of living only in the vision model's head.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional

from esports_poster_ai.sponsors_layout import orientation_from_output_format

_ORIENTATION_LABEL = {
    "portrait": "portrait (tall)",
    "square": "square",
    "landscape": "landscape (wide)",
}

# The ten patterns, each paired with the brief size it actually serves.
#
# These used to be presented as a menu for the vision model to choose from, and
# the result was the same failure the roster arrangements had: offered a free
# choice, the model converges on one safe answer, so nearly every poster came
# back as the same stacked-band composition. The pattern is now SAMPLED HERE and
# handed over as a decision already made — the model's judgement is spent on
# executing it against the background, not on picking it.
_HERO_SUPPORTING = (
    "HERO + SUPPORTING — one dominant element; everything else clearly smaller "
    "and secondary, arranged around it."
)
_DIAGONAL = (
    "DIAGONAL ACTION — content flows along a strong diagonal axis, corner toward "
    "corner; speed and motion."
)
_CENTER_FOCAL = (
    "CENTER-FOCAL — one commanding element dead centre, the rest arranged "
    "symmetrically around it."
)
_BENTO = (
    "MODULAR (BENTO) GRID — content divided into clean rectangular cells of "
    "varying size."
)
_RADIAL = (
    "RADIAL (CIRCULAR) — elements arranged in a ring, or radiating outward from "
    "a central point."
)
_PROGRESSIVE = (
    "PROGRESSIVE (TIMELINE / LIST) — elements sequenced along one axis in a "
    "deliberate reading order."
)
_COLLISION = (
    "COLLISION (OVERLAPPING) — layers deliberately overlap and interlock; depth "
    "built by occlusion."
)
_NEGATIVE_SPACE = (
    "NEGATIVE-SPACE HERO — a single element held in a large, intentionally empty "
    "field."
)
_BROKEN_GRID = (
    "BROKEN GRID (ASYMMETRICAL) — an underlying grid deliberately broken; offset, "
    "off-balance tension."
)
_REPETITION = (
    "REPETITION (PATTERNED) — one motif repeated at rhythm across the frame, "
    "varying scale or opacity."
)

# Patterns that can carry a lot of separate values without turning into soup.
_HEAVY_PATTERNS = [_BENTO, _PROGRESSIVE, _BROKEN_GRID, _COLLISION, _HERO_SUPPORTING]
# Patterns that need room to breathe — wrong for a brief with ten facts in it.
_SPARSE_PATTERNS = [_NEGATIVE_SPACE, _CENTER_FOCAL, _HERO_SUPPORTING, _RADIAL, _DIAGONAL]
# Everything, for briefs in the middle.
_ALL_PATTERNS = [
    _HERO_SUPPORTING, _DIAGONAL, _CENTER_FOCAL, _BENTO, _RADIAL,
    _PROGRESSIVE, _COLLISION, _NEGATIVE_SPACE, _BROKEN_GRID, _REPETITION,
]


def _content_weight(input_data: Dict[str, Any]) -> int:
    """
    Roughly how many separate things this poster has to place.

    Used only to pick a sensible pattern pool: a five-player roster with
    sponsors must not be handed Negative-Space Hero, and a bare two-team
    gameday must not be handed a Bento Grid with nothing to put in the cells.
    """
    if not isinstance(input_data, dict):
        return 0

    weight = 0
    match = input_data.get("match")
    if isinstance(match, dict):
        weight += sum(1 for k in ("team1", "team2") if isinstance(match.get(k), dict))
        weight += sum(
            1 for k in ("date", "time", "format", "timezone") if match.get(k)
        )
    roster = input_data.get("roster")
    if isinstance(roster, dict) and isinstance(roster.get("players"), list):
        # Each player is two things to place: a portrait and an IGN attached to it.
        weight += 2 * len(roster["players"])
    event = input_data.get("event")
    if isinstance(event, dict):
        weight += sum(1 for v in event.values() if v)
    sponsors = input_data.get("sponsors")
    if isinstance(sponsors, dict) and sponsors.get("enabled"):
        weight += len(sponsors.get("logos") or [])
    for key in ("tournament", "stream"):
        block = input_data.get(key)
        if isinstance(block, dict):
            weight += sum(1 for v in block.values() if v)
    return weight


def build_layout_block(
    input_data: Dict[str, Any], *, rng: Optional[random.Random] = None
) -> str:
    """Pick the composition pattern for this poster and hand it over as decided."""
    meta = input_data.get("_meta") if isinstance(input_data, dict) else None
    fmt = meta.get("output_format") if isinstance(meta, dict) else None
    orientation = orientation_from_output_format(fmt)
    label = _ORIENTATION_LABEL.get(orientation, orientation)

    poster_type = meta.get("poster_type") if isinstance(meta, dict) else None
    weight = _content_weight(input_data)

    if poster_type == "roster_reveal":
        # Five portraits and five IGNs, however bare the rest of the brief is.
        # Negative-Space Hero cannot hold that, whatever the weight says.
        pool = _HEAVY_PATTERNS
    elif weight >= 9:
        pool = _HEAVY_PATTERNS
    elif weight <= 4:
        pool = _SPARSE_PATTERNS
    else:
        pool = _ALL_PATTERNS

    r = rng or random
    pattern = r.choice(pool)

    return f"""
STEP 2.5 — THE LAYOUT PATTERN FOR THIS POSTER (already chosen — use it):
This poster is {label}. Its composition pattern is:

CHOSEN PATTERN: {pattern}

- Use THIS pattern. It has been selected for this poster's format and for how
  much content the METADATA and ASSETS actually carry. Do not substitute a
  different one because another feels safer, and never blend two patterns.
- Adapt it to the background you can see: work with the subject's position and
  the empty zones you found, scaling and shifting elements so the pattern fits
  the real image. Adapting it is expected; abandoning it is not.
- Name this pattern in the LAYOUT section of your output prompt, so it carries
  through to the image model.
- The pattern governs PLACEMENT only. It never overrides the verbatim-text rules,
  the sponsor-strip reservation, the fact hierarchy, or the visual-style
  directives.
- ONE exception: if this pattern genuinely cannot hold the required content
  without hiding or shrinking a factual value below legibility, fall back to
  HERO + SUPPORTING and say in the LAYOUT section that you did, and why.
""".strip()


# Roster arrangements. Curated to shapes an image model renders cleanly, and
# deliberately varied in silhouette so consecutive rosters do not read the same.
# The classic grid stays in the bank — it is a legitimate look, just no longer
# the only one. Sampled unseeded, so a re-roll of the same brief varies too.
_ROSTER_ARRANGEMENTS = [
    "STAGGERED WEDGE — the featured player front and centre and the largest; two "
    "players flanking slightly further back and smaller; the last two outermost "
    "and smaller still. Heads sit at descending heights so the group reads as a V.",

    "OVERLAPPING LINE-UP — all five as background-free cutouts standing "
    "shoulder-to-shoulder in one band, each overlapping its neighbour so they "
    "interlock. No frames, boxes, or dividers of any kind.",

    "ANGLED SHARDS — each portrait sits inside a slanted, non-rectangular shard "
    "or ribbon. The shards tilt the same way and interlock like broken glass or "
    "torn strips. Edges are angled, never square.",

    "HERO + SUPPORTING FOUR — one player rendered large as the poster's main "
    "subject; the other four noticeably smaller in a compact cluster or narrow "
    "strip to one side, clearly secondary to them.",

    "DIAGONAL CASCADE — the five step diagonally across the frame, corner toward "
    "corner, each scaled slightly differently so the group has depth and motion.",

    "ARC FORMATION — the five arranged along a gentle curve or fan, curving "
    "around the team logo or the hero title rather than sitting on a straight line.",

    "VERTICAL SLIVERS — five tall, narrow vertical panels side by side, one "
    "player each, separated by thin angled gaps of light rather than card borders "
    "or outlines.",

    "CLASSIC CARD GRID — five clean rectangular player cards in an even row or "
    "grid, each with its own frame. The traditional look.",
]


def build_roster_arrangement_block(
    input_data: Dict[str, Any], *, rng: Optional[random.Random] = None
) -> str:
    """Sample how the roster's player photos are arranged on this poster.

    Returns "" for every poster type except roster_reveal.
    """
    meta = input_data.get("_meta") if isinstance(input_data, dict) else None
    if not isinstance(meta, dict) or meta.get("poster_type") != "roster_reveal":
        return ""

    r = rng or random
    arrangement = r.choice(_ROSTER_ARRANGEMENTS)

    return f"""
ROSTER ARRANGEMENT — how the player photos are laid out on THIS poster:
Use this arrangement: {arrangement}

- This OVERRIDES any default "five player cards in a row". Unless the arrangement
  named above is the card grid, the players do NOT sit in rectangular cards, boxes,
  or framed panels.
- Adapt the arrangement to the format and to the background you can see: keep the
  players clear of the main subject and inside the usable space. You may change
  their order, spacing, and scale to make it fit, and you may crop portraits to
  head-and-shoulders or waist-up framing.
- Every rule about WHICH photo belongs to WHICH player still applies exactly:
  the arrangement changes the shape of the presentation, never the identity
  mapping, and never invents a face for a player with no photo supplied.
- Each player's IGN stays clearly attached to that player wherever the
  arrangement places them.
- State the arrangement you used in the LAYOUT section of your output prompt.
""".strip()


__all__ = ["build_layout_block", "build_roster_arrangement_block"]
