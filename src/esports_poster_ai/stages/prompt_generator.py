"""
Prompt-generation stage.

The vision model receives the assembled prompt + background image and
produces the final image-generation prompt for the poster stage.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from esports_poster_ai.clients.openai_client import (
    OpenAIClient,
    estimate_prompt_call_upper_bound_usd,
    new_run_id,
)
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.prompt.assembler import (
    build_image_factual_footer,
    build_image_style_footer,
    build_prompt,
)

logger = logging.getLogger(__name__)


# System steering for the prompt stage. Without it, GPT-4o is handed an
# image-model instruction set plus the real background and tends to describe
# the scene it sees — softening the user's requested color/vibe/energy. This
# pins its role and makes faithful style carry-through a hard requirement.
PROMPT_STAGE_INSTRUCTIONS = (
    "You are a prompt engineer for an esports-poster image model (gpt-image-2) "
    "running in EDIT mode on the provided background image. Your job is to turn "
    "the structured brief below into a single, vivid image-generation prompt.\n"
    "Hard requirements:\n"
    "- Faithfully carry through EVERY directive in the VISUAL STYLE section "
    "(fresh mode) or the CONSISTENCY MODE / STYLE DNA CONSTRAINTS section "
    "(consistency mode) — the dominant color or DNA palette, vibe/lighting, and "
    "energy. Instruct the model to color-grade the WHOLE frame toward those "
    "colors, not just accents or text, even when that means overriding the "
    "source background's existing palette.\n"
    "- Preserve all factual text (team names, scores, dates, tournament) exactly "
    "as given; never invent names, scores, or logos.\n"
    "- Output ONLY the image-generation prompt — no preamble, no commentary, no "
    "markdown."
)


def generate_image_prompt(
    *,
    background_image: bytes,
    input_data: Dict[str, Any],
    style_dna: Optional[Dict[str, Any]] = None,
    client: Optional[OpenAIClient] = None,
    settings: Optional[Settings] = None,
    run_id: Optional[str] = None,
) -> str:
    """
    Assemble the prompt, enforce the budget guard, call GPT-4o, and return the
    final prompt for the image model.

    The returned prompt is GPT-4o's written image prompt with a verbatim
    factual footer appended. The footer re-states the exact factual data and a
    render-exactly rule directly to gpt-image-2, so the facts are not lost to
    GPT-4o's paraphrase.
    """
    s = settings or get_settings()
    run_id = run_id or new_run_id()

    assembled = build_prompt(input_data, style_dna=style_dna)

    upper = estimate_prompt_call_upper_bound_usd(
        max_output_tokens=s.stage2_max_output_tokens,
        assumed_input_tokens=8000,
    )
    if upper > s.stage2_budget_usd:
        raise RuntimeError(
            f"[{run_id}] Prompt stage blocked by budget guard: "
            f"upper bound ${upper:.4f} > budget ${s.stage2_budget_usd:.2f}. "
            "Lower stage2_max_output_tokens or raise stage2_budget_usd."
        )

    api = client or OpenAIClient(settings=s)
    gpt4o_prompt = api.generate_prompt(
        background_image=background_image,
        assembled_prompt=assembled,
        instructions=PROMPT_STAGE_INSTRUCTIONS,
        run_id=run_id,
    )

    # Append the verbatim footers directly onto the prompt the image model
    # receives — bypassing GPT-4o's paraphrase. The factual footer pins names /
    # scores / dates; the style footer pins the dominant color / vibe / energy
    # and forces a whole-frame color grade instead of a mere accent.
    factual_footer = build_image_factual_footer(input_data)
    style_footer = build_image_style_footer(input_data, style_dna=style_dna)
    parts = [gpt4o_prompt, factual_footer]
    if style_footer:
        parts.append(style_footer)
    return "\n\n".join(parts)
