"""
Typography-variety block.

Without this, every poster gets the SAME type: the static rules hard-code the
hero title to "ultra-bold, wide, all-caps" with one metallic/particle effect
recipe, and the creative copy to a brush-script italic — so all posters look
typographically identical (same 3 fonts, same effects).

This block samples a fresh typographic treatment per poster — a hero-title
typeface + material finish, and a distinct creative-copy (tagline) style — from
curated banks, and injects it as an OVERRIDE of those defaults. Orthogonal axes
(letter SHAPE × surface MATERIAL × tagline STYLE) multiply into a large space, so
consecutive posters read differently. Factual text stays clean/legible either way.

Sampled unseeded (fresh each build) so even re-rolls of the same brief vary.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional

# Hero-title letter SHAPES (the typeface silhouette). Curated to styles image
# models render CLEANLY and legibly — no blackletter/gothic, shattered/fractured,
# graffiti, or rounded faces, which come out messy and "AI-looking" as big title
# text. All all-caps: esports titles read best in caps and stay legible.
_TITLE_TYPEFACES = [
    "an ultra-bold, wide extended sans-serif, all-caps",
    "a tall, tightly-condensed heavy sans-serif, all-caps",
    "a sharp chiseled angular slab-serif, all-caps",
    "a clean geometric sci-fi / techno sans, all-caps",
    "a high-contrast elegant serif display with dramatic thick-thin strokes, all-caps",
    "a bold military stencil face, all-caps",
    "a strong art-deco geometric display, all-caps",
    "a wide brutalist heavy sans, all-caps",
]

# Hero-title surface MATERIALS / finishes (independent of shape). Clean finishes
# only — dropped glitch/datamosh (reads as broken).
_TITLE_FINISHES = [
    "polished metallic chrome",
    "brushed gold with fine grain",
    "cracked carved stone",
    "molten glowing energy",
    "neon tube glow",
    "frosted ice / crystalline facets",
    "burnished embossed metal relief",
    "holographic iridescent foil",
    "matte industrial concrete",
    "liquid molten-metal",
]

# Finishes that are themselves a light source. At chill / balanced energy they
# fight the reduced text-effect intensity — a "molten glowing energy" title
# reads heavy no matter how few particles cross it — so they are held back for
# the high-energy levels.
_GLOWING_FINISHES = {
    "molten glowing energy",
    "neon tube glow",
    "holographic iridescent foil",
    "liquid molten-metal",
}

_CALM_ENERGIES = {"chill", "balanced"}


# Creative copy (tagline / hype phrase) STYLES — must differ from the hero title.
# Dropped marker-scrawl and graffiti-tag (come out messy).
# FACTUAL text faces (dates, venue, prize pool, team names, scores). Named
# families rather than descriptions, because the image model renders a named
# mainstream face more consistently than "a clean sans".
#
# All four are high-legibility screen faces with a real bold weight — the
# constraint here is readability at small sizes over a busy background, so this
# bank is deliberately narrower in character than the hero-title banks. Rajdhani
# is the one with obvious esports/techno flavour; the other three are neutral
# workhorses that differ mainly in letter width and warmth.
_FACTUAL_TYPEFACES = [
    "Montserrat (geometric, wide, even-width caps)",
    "Poppins (geometric, circular bowls, friendly and open)",
    "Inter (neutral UI grotesque, tight apertures, very high legibility)",
    "Rajdhani (squarish techno face with flat sides — esports scoreboard feel)",
]


_TAGLINE_STYLES = [
    "a handwritten brush script",
    "a clean condensed italic sans",
    "a tall, thin, widely letter-spaced uppercase sans",
    "an elegant serif italic",
    "a bold stencil, all-caps",
    "a refined thin uppercase with generous tracking",
    "a fast, slanted speed-italic sans",
]


def build_typography_block(
    input_data: Dict[str, Any], *, rng: Optional[random.Random] = None
) -> str:
    """A per-poster typography direction that overrides the generic default type."""
    r = rng or random

    design = input_data.get("design") if isinstance(input_data, dict) else None
    energy = design.get("energy") if isinstance(design, dict) else None
    energy = (energy if isinstance(energy, str) else "").strip().lower() or "balanced"

    finishes = _TITLE_FINISHES
    if energy in _CALM_ENERGIES:
        finishes = [f for f in _TITLE_FINISHES if f not in _GLOWING_FINISHES]

    typeface = r.choice(_TITLE_TYPEFACES)
    finish = r.choice(finishes)
    tagline = r.choice(_TAGLINE_STYLES)
    factual = r.choice(_FACTUAL_TYPEFACES)
    return f"""
TYPOGRAPHY DIRECTION — vary the type so posters don't all look the same. This
OVERRIDES the default "ultra-bold wide all-caps + metallic" title and the default
brush-script tagline:
- HERO TITLE typeface: use {typeface}. Give the letters a {finish} finish/material.
  Keep it the largest, most legible text and integrated into the scene (light,
  texture, particles) as described above — but its SHAPE and MATERIAL must be the
  ones named here, NOT the generic chunky metallic block.
- CREATIVE COPY (tagline / sub-tagline / hype phrase) typeface: use {tagline},
  clearly distinct from BOTH the hero title and the factual text. Do NOT default
  to a brush script unless it is named here.
- Choose type that still suits the scene's mood; if a named style would clash
  badly with the vibe, adapt its execution but keep it clearly different from the
  usual look.
- FACTUAL TEXT (names, dates, scores, venue, prize pool, tournament, format):
  set it in {factual}. Use this ONE family for every factual value on the poster —
  vary only weight and size within it, never mix a second factual face.
  It stays clean and legible regardless: no particles, debris, or chromatic
  aberration on these glyphs, whatever the energy level.
""".strip()


__all__ = ["build_typography_block"]
