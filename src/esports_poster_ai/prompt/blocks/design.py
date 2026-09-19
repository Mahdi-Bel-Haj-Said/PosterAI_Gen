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
                 "Composition: dense and energetic, built from neon glow and "
                 "particles — how much of the frame they cover is set by the "
                 "effect budget below, not by the vibe.",
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
                   "Composition: dense and high-impact — how much of the frame the "
                   "embers and sparks cover is set by the effect budget below, not "
                   "by the vibe.",
}

# Energy describes how much DRAMA the scene carries, never how much clutter.
#
# "high contrast" and "maximum contrast" used to be the whole description, and
# the model read them as licence to raise contrast and effect density across the
# entire frame — so intense and explosive posters came back as uniform noise with
# the text fighting sparks for attention. The drama is now explicitly directed at
# ONE focal area, with the rest of the frame kept calm enough to read.
_ENERGY_GUIDANCE = {
    "chill": "calm, relaxed pacing — soft contrast, gentle motion",
    "balanced": "balanced — moderate contrast and dynamic motion",
    "intense": (
        "intense — strong dynamic tension and deep contrast CONCENTRATED on the "
        "focal area. Intensity comes from the drama of a few strong elements, not "
        "from adding more of them or raising contrast everywhere"
    ),
    "explosive": (
        "explosive — peak-action drama: big motion, violent light, a scene at its "
        "loudest moment. This is still ONE dramatic focal point, not a frame full "
        "of competing effects. Deep shadow and bright highlight belong around that "
        "focus; the rest of the frame stays calmer so the poster still reads at a "
        "glance"
    ),
}


# How MUCH effect the scene carries, as opposed to what KIND.
#
# The vibe descriptions above set density in absolute terms — "particles fill the
# frame" for cyberpunk, "filling the frame" for fire & energy — with no reference
# to the energy level, and the VISUAL STYLE block outranks the generic density
# defaults. So a cyberpunk poster was told to fill the frame whether the brief
# asked for chill or explosive, and energy only ever scaled the TITLE's effects.
# That is where frame-wide noise came from, including at intense.
#
# The vibe still decides the CHARACTER of the effects; these decide the AMOUNT.
# Stated as rough coverage rather than adjectives, because "dense" and "restrained"
# are what produced the problem.
_ENERGY_EFFECT_BUDGET = {
    "chill": (
        "effects touch roughly a TENTH of the frame, one effect type only. The "
        "great majority of the image stays clean and uninterrupted"
    ),
    "balanced": (
        "effects touch roughly a QUARTER of the frame, at most two effect types. "
        "Most of the image stays clear"
    ),
    "intense": (
        "effects touch at most about FORTY PERCENT of the frame, at most three "
        "effect types, and they CLUSTER around the focal area rather than "
        "spreading evenly. At least a third of the frame stays visually calm — "
        "this is not a licence to cover the image in sparks and arcs"
    ),
    "explosive": (
        "effects touch at most about SIXTY PERCENT of the frame, still gathered "
        "around ONE focal concentration rather than spread edge to edge. At least "
        "a fifth of the frame stays visually calm"
    ),
}


def energy_effect_budget(energy: Optional[str]) -> str:
    """How much of the frame effects may cover at this energy, or "" if unknown.

    Exposed because the image model needs it too: the footer used to pass only
    the bare word ("Energy: intense"), which carries the label without any of
    the constraint, and density is decided by the pass that draws the frame.
    """
    if not isinstance(energy, str):
        return ""
    return _ENERGY_EFFECT_BUDGET.get(energy.strip().lower(), "")


def resolve_color_mode(design: Optional[Dict[str, Any]]) -> str:
    """
    Return the effective color mode: "dominant" or "auto".

    - Explicit `design.color_mode` wins ("dominant" | "auto").
    - Otherwise back-compat: a set `primary_color` implies "dominant"; nothing
      set implies "auto" (let the poster take the background's own colors).
    """
    if not isinstance(design, dict):
        return "auto"
    mode = (design.get("color_mode") or "").strip().lower()
    if mode in ("dominant", "auto"):
        return mode
    color = design.get("primary_color")
    return "dominant" if isinstance(color, str) and color.strip() else "auto"


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

    if resolve_color_mode(design) == "auto":
        lines.append(
            "- Color: DERIVE the poster's palette from the BACKGROUND image — build the "
            "design around the background's own dominant colors. Do NOT impose an "
            "external or single forced color."
        )
    else:
        color = design.get("primary_color")
        if isinstance(color, str) and color.strip():
            lines.append(
                f"- Dominant color: {color} — make this the primary color of the poster, "
                f"or a close variation of it. Build the palette around it."
            )

    energy = design.get("energy")
    if isinstance(energy, str) and energy.strip():
        lines.append(f"- Energy level: {_ENERGY_GUIDANCE.get(energy, energy)}")
        budget = _ENERGY_EFFECT_BUDGET.get(energy.strip().lower())
        if budget:
            lines.append(f"- Effect budget: {budget}")

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


__all__ = ["build_design_block", "resolve_color_mode"]
