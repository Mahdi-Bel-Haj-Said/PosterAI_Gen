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
from esports_poster_ai.prompt.assembler import build_image_factual_footer, build_prompt

logger = logging.getLogger(__name__)


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
        run_id=run_id,
    )

    # Append the verbatim factual data + render rules directly onto the prompt
    # the image model receives — bypassing GPT-4o's paraphrase.
    footer = build_image_factual_footer(input_data)
    return f"{gpt4o_prompt}\n\n{footer}"
