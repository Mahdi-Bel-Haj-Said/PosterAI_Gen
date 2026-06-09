"""
Semantic Style DNA extraction via GPT-4o Vision.

The model receives the approved poster and the already-extracted palette
and returns a small structured JSON of semantic fields (lighting,
atmosphere, particle effects, energy, style keywords).

Why the palette is supplied to the model: vision models are weak at exact
color extraction but strong at semantic description. Pre-supplying the
palette frees the model from a job it's bad at and grounds the semantic
description in concrete values it can reference.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from esports_poster_ai.clients.openai_client import OpenAIClient, new_run_id
from esports_poster_ai.domain.style_dna import StyleDNASemantic

logger = logging.getLogger(__name__)


_BASE_INSTRUCTIONS = """\
You are a visual style analyzer for esports posters. You will be shown a finished
poster. Your job is to extract the VISUAL STYLE — and ONLY the visual style — for
reuse across other posters in the same tournament series.

CRITICAL — DO NOT include any content-specific information in your output:
- Do NOT mention team names, organization names, player names, or any text on the poster
- Do NOT mention tournament names or phase identifiers
- Do NOT mention scores, dates, times, or any numerical values shown on the poster
- Do NOT describe specific people, characters, or champions by identity
- Do NOT name specific logos
- If you notice text in the image, treat its presence as styling information only
  (e.g. "bold neon hero title with chromatic aberration") — never quote the words

What you SHOULD describe in one short sentence each:
- `lighting`: lighting style, light sources, rim light, glow, lens flare, etc.
- `atmosphere`: overall mood and atmosphere of the scene
- `particle_effects`: particle / energy / smoke / spark effects, or "none" if absent
- `energy`: one of "chill" | "balanced" | "intense" | "explosive"
- `sd_style_keywords`: 4-8 comma-separated style tags suitable for a Stable
  Diffusion prompt (e.g. "cyberpunk arena, neon orange purple, dark dramatic,
  high contrast"). Style only — never content.

The dominant color palette has already been extracted programmatically:
PALETTE: {palette_csv}

Use these colors as the reference when describing lighting and atmosphere. Do
not introduce other colors in your description.
"""


def build_semantic_prompt(palette: List[str]) -> str:
    """Render the extraction prompt with the palette injected."""
    palette_csv = ", ".join(palette) if palette else "(palette extraction returned no colors)"
    return _BASE_INSTRUCTIONS.format(palette_csv=palette_csv)


def extract_semantic(
    *,
    poster_image: bytes,
    palette: List[str],
    client: OpenAIClient,
    run_id: Optional[str] = None,
) -> StyleDNASemantic:
    """
    Call the vision model and return validated semantic fields.

    Args:
        poster_image: Raw bytes of the approved poster image.
        palette: Programmatically extracted palette (hex strings) for grounding.
        client: A live `OpenAIClient` instance.
        run_id: Optional run id for log correlation.

    Returns:
        Validated `StyleDNASemantic` instance.
    """
    run_id = run_id or new_run_id()
    instructions = build_semantic_prompt(palette)

    logger.info(
        "dna.semantic.start",
        extra={"run_id": run_id, "palette_len": len(palette)},
    )

    result = client.generate_structured(
        image=poster_image,
        instructions=instructions,
        schema=StyleDNASemantic,
        max_output_tokens=600,
        run_id=run_id,
    )

    logger.info("dna.semantic.done", extra={"run_id": run_id, "energy": result.energy})
    return result


__all__ = ["extract_semantic", "build_semantic_prompt"]
