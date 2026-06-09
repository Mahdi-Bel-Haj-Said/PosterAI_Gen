"""
Sponsor-bar reservation block.

When `sponsors.enabled` is true, a sponsor bar is composited onto the poster by
Pillow AFTER the image model finishes. The image model must therefore leave a
clean horizontal strip for it — otherwise the bar lands on top of text or
logos. This block injects that instruction; it is omitted when sponsors are off.
"""

from __future__ import annotations

from typing import Any, Dict


_SPONSOR_RESERVATION = """
SPONSOR BAR RESERVATION — MANDATORY, overrides the fill / composition rules:
A sponsor bar will be composited onto the FINISHED poster afterward. You MUST
design the poster to leave a clean horizontal strip for it:
- Reserve the bottom 8-10% of the poster height as a RESERVED STRIP, full width.
- The reserved strip must contain NO text, NO logos, NO faces, and no important
  focal content. Background and subtle atmospheric extension are fine — the bar
  is semi-transparent and will sit over them.
- Keep the hero title, team names, score, dates, stream info, and every other
  text or logo element ABOVE the reserved strip — never inside it.
- This reservation overrides the 'fill all empty space' and composition-density
  rules for that strip only: the strip stays deliberately clear of content.
""".strip()


def build_sponsor_block(input_data: Dict[str, Any]) -> str:
    """Return the sponsor-bar reservation block when sponsors are enabled."""
    sponsors = input_data.get("sponsors")
    if not isinstance(sponsors, dict) or sponsors.get("enabled") is not True:
        return ""
    return _SPONSOR_RESERVATION


__all__ = ["build_sponsor_block"]
