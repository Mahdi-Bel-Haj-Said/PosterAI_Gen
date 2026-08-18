"""
Sponsor-bar reservation block.

When `sponsors.enabled` is true, a sponsor bar is composited onto the poster by
Pillow AFTER the image model finishes. The image model must therefore leave a
clean horizontal strip for it — otherwise the bar lands on top of text or
logos. This block injects that instruction; it is omitted when sponsors are off.
"""

from __future__ import annotations

from typing import Any, Dict

from esports_poster_ai.sponsors_layout import reserved_percent_for_prompt


def _reservation_text(pct: int) -> str:
    """Render the reservation block for the reserved percentage.

    `pct` is the BAR height plus a safety buffer (see `sponsors_layout.py`), so
    the model clears a little more than the bar occupies and minor downward text
    drift stays above the bar instead of colliding with it.
    """
    return f"""
SPONSOR BAR RESERVATION — MANDATORY, overrides the fill / composition rules:
⚠️ HARD RULE #1 — NO TEXT OR LOGOS IN THE BOTTOM {pct}%: the hero title, team
names, "VS", score, dates, times, tournament name, stream handles, and EVERY
other text or logo element MUST sit entirely ABOVE the bottom {pct}% of the
poster height. Not one character, digit, or logo may enter that bottom band —
it is the single most important rule here. Push all text UP so the lowest line
still leaves the bottom {pct}% completely clear.

A separate step composites the real sponsor logos onto the FINISHED poster
afterward, as a full-width bar pinned to the very bottom edge. Your ONLY job here
is to leave the bottom {pct}% as clean, EMPTY space. Do NOT design, draw,
decorate, or frame this strip yourself.
- Treat the bottom {pct}% of the poster height as an EMPTY RESERVED STRIP, full width.
- The strip must read as clean negative space — just a soft, slightly darker and
  calmer continuation of the existing background. Nothing sits inside it. It is NOT
  a surface, a platform, or an object — it is only empty background.
- Do NOT draw ANY distinct object in the strip: no bar, panel, box, frame, border,
  outline, divider, separator, corner brackets, ornaments, UI/HUD chrome, placeholder
  boxes, icons, or sponsor logos. NO "container", "tray", "stage", "platform",
  "pedestal", "plinth", "podium", "dais", or "riser" of ANY kind — and NO glowing,
  neon, or holographic shape, rounded-rectangle, capsule, pill, hexagon, or beveled
  panel to "hold" or "present" the logos.
- ⚠️ COMMON MISTAKE TO AVOID: do NOT build a glowing/neon sponsor "stage", lit
  pedestal, or framed logo tray along the bottom. This is the single most common
  error — there must be NO such element. Only plain, calm background reaches the
  bottom edge.
- Do NOT render any text, labels, or words in the strip (no "SPONSORS", no captions).
- Do NOT mark the strip off with a visible edge or line — it should blend smoothly
  with the rest of the poster, simply kept free of content. The compositing step
  adds its own subtle bar; anything you draw there will clash with it and look messy.
- Keep the hero title, team names, score, dates, stream info, and every other text
  or logo element ABOVE the strip — never inside it.
- This reservation overrides the 'fill all empty space' and composition-density
  rules for that strip only: the strip stays deliberately clear and uncluttered.
""".strip()


def build_sponsor_block(input_data: Dict[str, Any]) -> str:
    """Return the sponsor-bar reservation block when sponsors are enabled.

    The reserved percentage is derived from the poster's output format so it
    matches the bar the compositor draws (landscape < square < portrait).
    """
    sponsors = input_data.get("sponsors")
    if not isinstance(sponsors, dict) or sponsors.get("enabled") is not True:
        return ""

    meta = input_data.get("_meta") if isinstance(input_data, dict) else None
    output_format = meta.get("output_format") if isinstance(meta, dict) else None
    pct = reserved_percent_for_prompt(output_format)
    return _reservation_text(pct)


__all__ = ["build_sponsor_block"]
