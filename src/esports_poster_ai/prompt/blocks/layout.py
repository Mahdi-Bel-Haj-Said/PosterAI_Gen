"""
Layout blocks — how the poster's elements are arranged.

`build_layout_block` hands the vision model a menu of ten named composition
patterns and makes it commit to exactly ONE, chosen from the poster format, how
much content the brief carries, and where the background is busy or empty.
Without it the model composes ad hoc, and because the output template maps
content into TOP / MIDDLE / BOTTOM bands, nearly every poster came back as the
same stacked-band arrangement.

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

_PATTERNS = """\
1. Hero + Supporting — one dominant element; everything else clearly smaller and secondary around it.
2. Diagonal Action — content flows along a strong diagonal axis, corner toward corner; speed and motion.
3. Center-Focal — one commanding element dead centre, the rest arranged symmetrically around it.
4. Modular (Bento) Grid — content divided into clean rectangular cells of varying size.
5. Radial (Circular) — elements arranged in a ring, or radiating outward from a central point.
6. Progressive (Timeline / List) — elements sequenced along one axis in a deliberate reading order.
7. Collision (Overlapping) — layers deliberately overlap and interlock; depth built by occlusion.
8. Negative-Space Hero — a single element held in a large, intentionally empty field.
9. Broken Grid (Asymmetrical) — an underlying grid deliberately broken; offset, off-balance tension.
10. Repetition (Patterned) — one motif repeated at rhythm across the frame, varying scale or opacity."""


def build_layout_block(input_data: Dict[str, Any]) -> str:
    """Return the layout-pattern selection block for this poster."""
    meta = input_data.get("_meta") if isinstance(input_data, dict) else None
    fmt = meta.get("output_format") if isinstance(meta, dict) else None
    orientation = orientation_from_output_format(fmt)
    label = _ORIENTATION_LABEL.get(orientation, orientation)

    return f"""
STEP 2.5 — CHOOSE THE LAYOUT PATTERN (pick exactly ONE):
This poster is {label}. Choose the single pattern below that best fits (a) that
format, (b) how much content the METADATA and ASSETS above actually require, and
(c) the subject position and empty zones you found in the background.

{_PATTERNS}

- Content-heavy briefs (full rosters, map lists, many logos) suit Bento Grid,
  Progressive, or Broken Grid; sparse briefs suit Negative-Space Hero,
  Center-Focal, or Hero + Supporting; a background with one strong off-centre
  subject suits Hero + Supporting, Diagonal Action, or Collision.
- Commit to it: every element you place must follow the chosen pattern, and you
  must name that pattern in the LAYOUT section of your output prompt. Never blend
  two patterns.
- The pattern governs PLACEMENT only. It never overrides the verbatim-text rules,
  the sponsor-strip reservation, or the visual-style directives.
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
