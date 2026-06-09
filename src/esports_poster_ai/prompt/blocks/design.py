"""
Visual-style block — the fresh-mode design direction.

Built from the input JSON's `design` object (vibe preset, dominant color,
energy level). In consistency mode the Style DNA governs visual style
instead, so the assembler injects this block only when no DNA applies.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# Each vibe carries both a look and a COMPOSITION DENSITY directive — the
# density is what makes "minimal" actually produce a minimal poster instead of
# the maximalist default.
_VIBE_GUIDANCE = {
    "cyberpunk": "Cyberpunk — neon-lit, high-tech, electric, futuristic dystopia. "
                 "Composition: dense and energetic, glow and particles fill the frame.",
    "cinematic": "Cinematic — dramatic film-grade lighting, depth of field, epic "
                 "framing. Composition: balanced, with a strong focal hierarchy.",
    "dark_fantasy": "Dark fantasy — moody, mythic, ominous, painterly shadow and "
                    "detail. Composition: rich and atmospheric.",
    "cosmic": "Cosmic — deep space, nebulae, stellar glow, vast and surreal. "
              "Composition: expansive, with atmospheric depth.",
    "minimal": "Minimal — clean, restrained, refined. Composition: embrace generous "
               "NEGATIVE SPACE, few elements, sparse and subtle effects. Do NOT "
               "fill every zone — calm, uncluttered, intentionally empty areas are "
               "correct and required for this vibe.",
    "fire_energy": "Fire & energy — intense heat, embers, sparks, explosive motion. "
                   "Composition: dense and high-impact, filling the frame.",
}

_ENERGY_GUIDANCE = {
    "chill": "calm, relaxed pacing — soft contrast, gentle motion",
    "balanced": "balanced — moderate contrast and dynamic motion",
    "intense": "intense — high contrast, strong dynamic tension",
    "explosive": "explosive — maximum contrast, dramatic peak-action energy",
}


def build_design_block(design: Optional[Dict[str, Any]]) -> str:
    """
    Render the VISUAL STYLE block from the input's `design` object.

    Returns an empty string when no design fields are provided.
    """
    if not isinstance(design, dict):
        return ""

    lines = [
        "VISUAL STYLE (design direction — applies across the whole poster). "
        "These directives OVERRIDE the generic composition-density and "
        "text-integration defaults stated elsewhere in this prompt:"
    ]

    vibe = design.get("vibe")
    if isinstance(vibe, str) and vibe.strip():
        lines.append(f"- Vibe: {_VIBE_GUIDANCE.get(vibe, vibe)}")

    color = design.get("primary_color")
    if isinstance(color, str) and color.strip():
        lines.append(
            f"- Dominant color: {color} — make this the primary color of the poster, "
            f"or a close variation of it. Build the palette around it."
        )

    energy = design.get("energy")
    if isinstance(energy, str) and energy.strip():
        lines.append(f"- Energy level: {_ENERGY_GUIDANCE.get(energy, energy)}")

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


__all__ = ["build_design_block"]
