"""
Consistency-mode prompt injection (Style DNA). Empty for fresh mode.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_consistency_block(style_dna: Optional[Dict[str, Any]]) -> str:
    """Build the consistency-mode block if a Style DNA dict is provided."""
    if not style_dna:
        return ""

    palette = style_dna.get("palette")
    lighting = style_dna.get("lighting")
    atmosphere = style_dna.get("atmosphere")
    particle_effects = style_dna.get("particle_effects")
    energy = style_dna.get("energy")
    sd_style_keywords = style_dna.get("sd_style_keywords")
    typography = style_dna.get("typography")

    lines = [
        "CONSISTENCY MODE — STYLE DNA CONSTRAINTS:",
        "This poster belongs to a tournament series. You MUST respect these visual",
        "constraints. They override any creative decisions you would otherwise make.",
        "",
    ]

    if palette:
        palette_str = (
            ", ".join(str(c) for c in palette)
            if isinstance(palette, (list, tuple))
            else str(palette)
        )
        lines.append(
            f"Color palette: {palette_str} — use ONLY these colors for all new elements"
        )
    if lighting:
        lines.append(
            f"Lighting style: {lighting} — match exactly, do not introduce new light sources"
        )
    if atmosphere:
        lines.append(f"Atmosphere: {atmosphere}")
    if particle_effects:
        lines.append(
            f"Particle effects: {particle_effects} — extend from background, "
            "do not introduce new types"
        )
    if energy:
        lines.append(f"Energy level: {energy}")
    if typography:
        lines.append(
            f"Typography: {typography} — render the hero title and the tagline / "
            "creative copy in THIS exact type style and finish. Do NOT vary the "
            "fonts, letter shapes, or text effects; matching type is essential to "
            "the series looking consistent."
        )
    if sd_style_keywords:
        lines.append(f"Style keywords: {sd_style_keywords}")

    return "\n".join(lines).strip()
