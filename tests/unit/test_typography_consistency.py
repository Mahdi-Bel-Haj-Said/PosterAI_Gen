"""
Typography + consistency mode.

Fresh mode randomizes the type (for variety). Consistency mode must NOT — it
reproduces the Style DNA's saved typography so a series looks the same. These
tests pin that split and the DNA's typography plumbing.
"""

from __future__ import annotations

from esports_poster_ai.prompt.assembler import build_prompt
from esports_poster_ai.prompt.blocks.consistency import build_consistency_block

# Unique to the random per-poster typography block (not the static references).
_RANDOM_MARK = "HERO TITLE typeface: use"

_BASE = {
    "_meta": {"game": "league_of_legends", "poster_type": "tournament_announcement"},
    "design": {"vibe": "dark_fantasy", "energy": "intense"},
}


def _dna(typography="tall condensed chrome title, brush-script tagline"):
    return {
        "palette": ["#123456"], "lighting": "rim glow", "atmosphere": "dark",
        "particle_effects": "embers", "energy": "intense", "sd_style_keywords": "dark,neon",
        "typography": typography,
    }


def test_fresh_mode_randomizes_typography():
    p = build_prompt(_BASE)
    assert _RANDOM_MARK in p                 # variety block present
    assert "CONSISTENCY MODE" not in p


def test_consistency_mode_drops_random_typography_and_uses_dna():
    p = build_prompt(_BASE, style_dna=_dna())
    assert _RANDOM_MARK not in p             # no randomization in a series
    assert "CONSISTENCY MODE" in p
    assert "tall condensed chrome title" in p  # the saved typography is applied


def test_consistency_block_includes_typography_line():
    block = build_consistency_block(_dna("chiseled slab, neon glow; italic tagline"))
    assert "Typography:" in block
    assert "chiseled slab, neon glow" in block


def test_consistency_block_omits_typography_when_absent():
    # Old DNA saved before typography capture — no typography line, no crash.
    block = build_consistency_block(_dna(typography=""))
    assert "Typography:" not in block
