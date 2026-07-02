"""
Sponsor-bar reservation block.

When `sponsors.enabled` is true, a sponsor bar is composited onto the poster by
Pillow AFTER the image model finishes. The image model must therefore leave a
clean horizontal strip for it — otherwise the bar lands on top of text or
logos. This block injects that instruction; it is omitted when sponsors are off.
"""

from __future__ import annotations

from typing import Any, Dict

from esports_poster_ai.sponsors_layout import reserved_percent_for_output_format


def _reservation_text(pct: int) -> str:
    """Render the reservation block for an exact reserved percentage.

    The percentage is the SAME value the Pillow compositor uses for the bar
    height (see `sponsors_layout.py`), so the strip the model clears and the
    bar that lands on it line up exactly.
    """
    return f"""
SPONSOR BAR RESERVATION — MANDATORY, overrides the fill / composition rules:
A separate step composites the real sponsor logos onto the FINISHED poster
afterward, as a full-width bar pinned to the very bottom edge that occupies
EXACTLY the bottom {pct}% of the poster height. Your ONLY job here is to leave
that bottom {pct}% as clean, EMPTY space. Do NOT design, draw, decorate, or
frame this strip yourself.
- Treat the bottom {pct}% of the poster height as an EMPTY RESERVED STRIP, full width.
- The strip must read as clean negative space — just a soft, slightly darker and
  calmer continuation of the existing background. Nothing sits inside it.
- Do NOT draw a bar, panel, box, frame, border, outline, divider line, separator,
  corner brackets, ornaments, UI chrome, placeholder boxes, icons, or any sponsor
  logos inside the strip. No "container" or "tray" graphic of ANY kind.
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
    pct = reserved_percent_for_output_format(output_format)
    return _reservation_text(pct)


__all__ = ["build_sponsor_block"]
