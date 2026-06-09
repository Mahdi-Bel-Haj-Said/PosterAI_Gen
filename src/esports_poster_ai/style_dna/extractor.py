"""
Style DNA extractor — orchestrates palette + semantic extraction into a
complete StyleDNA document.

Accepts the approved poster as raw `bytes` so it works equally for a local
file (CLI) or an object fetched from R2 (HTTP API). It:

1. Extracts the palette programmatically (cheap, deterministic).
2. Derives color temperature from the palette.
3. Calls the vision model for the semantic fields (one OpenAI request),
   pre-supplying the palette to ground the description.
4. Assembles a `StyleDNA` instance with metadata.

It does *not* persist the result — that's the repository's job.
"""

from __future__ import annotations

import io
import logging
from typing import Optional

from PIL import Image

from esports_poster_ai.clients.openai_client import OpenAIClient, new_run_id
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.style_dna import (
    CURRENT_SCHEMA_VERSION,
    StyleDNA,
)
from esports_poster_ai.style_dna.palette import color_temperature, extract_palette
from esports_poster_ai.style_dna.semantic import extract_semantic

logger = logging.getLogger(__name__)


def extract_style_dna(
    *,
    poster_bytes: bytes,
    tournament_id: str,
    source_reference: Optional[str] = None,
    palette_size: int = 5,
    client: Optional[OpenAIClient] = None,
    settings: Optional[Settings] = None,
    run_id: Optional[str] = None,
) -> StyleDNA:
    """
    Build a full `StyleDNA` from an approved poster's bytes.

    Args:
        poster_bytes: Raw bytes of the approved poster image.
        tournament_id: ID to embed in the DNA (used as the storage key).
        source_reference: Optional string identifying where the bytes came
            from (a local path for CLI, a storage key for the API). Stored
            on the DNA as `source_poster_path` for traceability.
        palette_size: Number of dominant colors to extract programmatically.
        client / settings / run_id: Optional overrides.

    Returns:
        A draft-status `StyleDNA`. Caller decides whether to save / promote.
    """
    s = settings or get_settings()
    run_id = run_id or new_run_id()

    if not poster_bytes:
        raise ValueError("poster_bytes is empty.")

    logger.info(
        "dna.extract.start",
        extra={
            "run_id": run_id,
            "tournament_id": tournament_id,
            "source": source_reference,
            "bytes": len(poster_bytes),
        },
    )

    # 1. Programmatic palette + temperature.
    with Image.open(io.BytesIO(poster_bytes)) as img:
        palette = extract_palette(img, n_colors=palette_size)
    temperature = color_temperature(palette)

    # 2. Semantic fields via the vision model.
    api = client or OpenAIClient(settings=s)
    semantic = extract_semantic(
        poster_image=poster_bytes,
        palette=palette,
        client=api,
        run_id=run_id,
    )

    # 3. Assemble.
    dna = StyleDNA(
        schema_version=CURRENT_SCHEMA_VERSION,
        tournament_id=tournament_id,
        status="draft",
        source_poster_path=source_reference,
        palette=palette,
        color_temperature=temperature,
        lighting=semantic.lighting,
        atmosphere=semantic.atmosphere,
        particle_effects=semantic.particle_effects,
        energy=semantic.energy,
        sd_style_keywords=semantic.sd_style_keywords,
    )

    logger.info(
        "dna.extract.done",
        extra={
            "run_id": run_id,
            "tournament_id": tournament_id,
            "palette_count": len(palette),
            "color_temperature": temperature,
            "energy": dna.energy,
        },
    )
    return dna


__all__ = ["extract_style_dna"]
