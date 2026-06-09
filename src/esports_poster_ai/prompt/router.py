"""
Router for prompt assembly decisions.

Reads the input JSON and returns which blocks to inject. Pure function — no
filesystem access, no model calls.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def route(input_data: Dict[str, Any], style_dna: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Decide which prompt blocks to inject.

    Args:
        input_data: Parsed JSON dict from a file under `inputs/`.
        style_dna: Optional Style DNA dict (consistency mode).

    Returns:
        Routing decisions consumed by the assembler.
    """
    meta = input_data.get("_meta", {}) if isinstance(input_data, dict) else {}
    poster_type = meta.get("poster_type")

    return {
        "game": meta.get("game"),
        "poster_type": poster_type,
        "mode": meta.get("mode"),
        "needs_game_rules": poster_type in {"game_results", "roster_reveal"},
        "style_dna": style_dna,
    }
