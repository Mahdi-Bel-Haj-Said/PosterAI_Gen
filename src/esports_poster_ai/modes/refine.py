"""
Refine mode — apply a user-supplied freeform edit to an existing poster.

Unlike fresh/consistency (which generate a poster from input data + a complex
assembled prompt), refine takes the *previous* poster as the editing canvas and
asks `gpt-image-2` for a small, targeted modification described in plain
English by the user (e.g. "make it darker", "change the font of secondary
info to be more dynamic", "add a subtle glow around the matchup").

Caveat — image models are unreliable text renderers (see the README's Known
gaps). Refine works best for VISUAL changes; for factual-text edits (time,
score, names) the user should regenerate from edited input data instead.

Input shape carried on `input_data`:
    {
      "_meta": { ... mode: "refine", output_format: "<same as parent>" ... },
      "refine": {
        "parent_storage_key": "defendr-poster-ai/.../posters/<id>.png",
        "user_prompt": "<freeform>"
      }
    }
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Union

from esports_poster_ai.clients.openai_client import OpenAIClient, new_run_id
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.stages.poster_generator import (
    PosterResult,
    generate_poster,
    save_poster,
)
from esports_poster_ai.storage import StorageKeys, get_storage
from esports_poster_ai.storage.base import Storage

logger = logging.getLogger(__name__)

StatusCallback = Optional[Callable[[str], None]]

# Prompt sent to gpt-image-2 in edit mode. The poster image itself is the only
# reference — the model treats it as the canvas to modify. We frame the change
# as MINIMAL and strict about preserving everything else, because the failure
# mode of these models is to redraw too much.
_REFINE_PROMPT_TEMPLATE = (
    "You are editing an existing finished poster. Apply the user's requested "
    "change below to this poster, then return the modified poster.\n\n"
    "STRICT RULES — keep the result coherent with the original:\n"
    "  • Preserve the overall layout, composition, framing, and crop.\n"
    "  • Preserve every piece of factual text NOT mentioned in the change "
    "(team names, scores, dates, times, tournament name, stream URL, "
    "sponsor logos, hashtags). Re-render them VERBATIM, character for "
    "character, in the same position.\n"
    "  • Preserve every team logo, player photo, and any other reference "
    "image already placed in the poster.\n"
    "  • If the user asks for a VISUAL change (darker, brighter, different "
    "atmosphere, different font feel, more particles, palette shift, etc.) "
    "apply it globally and tastefully.\n"
    "  • If the user asks for a FACTUAL text change (e.g. \"change time "
    "from 17:00 to 18:00\") apply it ONLY to the specified text; do not "
    "alter any other text, digit, or name.\n"
    "  • Do NOT invent new content, new logos, new players, or new "
    "sponsors. Do NOT rewrite team names, scores, or dates the user did "
    "not mention.\n\n"
    "USER CHANGE REQUEST:\n"
    "{user_prompt}"
)


def _build_refine_prompt(user_prompt: str) -> str:
    return _REFINE_PROMPT_TEMPLATE.format(user_prompt=(user_prompt or "").strip())


def run_refine(
    input_data: Dict[str, Any],
    *,
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    on_status: StatusCallback = None,
    client: Optional[OpenAIClient] = None,
    settings: Optional[Settings] = None,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
) -> PosterResult:
    """
    Refine the parent poster according to the user's freeform prompt.

    Reads `input_data["refine"]["parent_storage_key"]` and `["user_prompt"]`.
    Calls `gpt-image-2` in edit mode with the parent poster as the canvas and
    no additional reference inputs (logos etc. are already burned into the
    parent). Persists the result as a new poster under the same tournament.
    """
    s = settings or get_settings()
    run_id = new_run_id()

    def _emit(status: str) -> None:
        if on_status is not None:
            on_status(status)

    refine_cfg = input_data.get("refine") or {}
    parent_key = refine_cfg.get("parent_storage_key")
    user_prompt = refine_cfg.get("user_prompt") or ""

    if not isinstance(parent_key, str) or not parent_key.strip():
        raise ValueError("refine.parent_storage_key is required.")
    if not user_prompt.strip():
        raise ValueError("refine.user_prompt is required.")

    output_format = (input_data.get("_meta") or {}).get("output_format") or "portrait_1080x1920"
    quality = (input_data.get("_meta") or {}).get("quality") or "medium"

    logger.info(
        "refine.start",
        extra={
            "run_id": run_id,
            "org_id": str(org_id),
            "tournament_id": str(tournament_id),
            "parent_storage_key": parent_key,
        },
    )

    api = client or OpenAIClient(settings=s)
    st = storage or get_storage(s)

    _emit("generating_prompt")
    prompt = _build_refine_prompt(user_prompt)

    # Parent poster IS the canvas to edit. No extra reference images.
    parent_bytes = st.get_bytes(parent_key)

    _emit("generating_poster")
    poster_image = generate_poster(
        background_image=parent_bytes,
        prompt=prompt,
        input_images=[],
        output_format=output_format,
        quality=quality,
        client=api,
        settings=s,
        run_id=run_id,
    )

    result = save_poster(
        poster_image,
        org_id=org_id,
        tournament_id=tournament_id,
        storage=storage,
        keys=keys,
        settings=s,
        run_id=run_id,
    )

    logger.info(
        "refine.done",
        extra={
            "run_id": run_id,
            "local_path": str(result.local_path),
            "storage_key": result.storage_key,
        },
    )
    return result


__all__ = ["run_refine", "StatusCallback"]
