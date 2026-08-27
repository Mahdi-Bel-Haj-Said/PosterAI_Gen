"""
Consistency mode orchestration.

A tournament organizer generates the first poster (with no DNA on file yet —
behavior is identical to fresh mode), approves it, and then extracts a Style
DNA from that approved poster. From then on, every subsequent poster in the
series is generated with the DNA injected as a hard visual constraint.

This module handles the *generation* side. Extraction and approval are
exposed separately (style_dna.extractor + style_dna.repository) and reached
from the CLI via --extract-dna / --approve-dna.

Resolution order when running consistency mode:

1. If an approved DNA exists -> use it.
2. Else if a draft DNA exists -> use it but warn (not yet reviewed).
3. Else -> fall back to fresh-mode behavior and warn (this run is effectively
   producing the first poster of a new series).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from esports_poster_ai.clients.openai_client import OpenAIClient
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.modes.fresh import StatusCallback, run_fresh
from esports_poster_ai.stages.poster_generator import PosterResult
from esports_poster_ai.storage import StorageKeys
from esports_poster_ai.storage.base import Storage
from esports_poster_ai.style_dna.repository import load_active

logger = logging.getLogger(__name__)


def run_consistency(
    input_data: Dict[str, Any],
    tournament_id: Union[str, int],
    *,
    org_id: Union[str, int],
    on_status: StatusCallback = None,
    client: Optional[OpenAIClient] = None,
    settings: Optional[Settings] = None,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
) -> PosterResult:
    """
    Run the pipeline in consistency mode for `org_id` / `tournament_id`.

    `input_data` is the parsed poster input JSON (a dict). `keys` (platform-aware
    when an API job supplies it) governs where the poster is written AND where the
    Style DNA is read from, so both stay under the same platform namespace.
    Returns the `PosterResult` for the generated poster.
    """
    s = settings or get_settings()
    located = load_active(org_id, tournament_id, settings=s, storage=storage, keys=keys)

    style_dna_dict = None
    if located is None:
        logger.warning(
            "consistency.no_dna",
            extra={
                "org_id": str(org_id),
                "tournament_id": str(tournament_id),
                # NOT "message": logging reserves that name on LogRecord and
                # raises KeyError when `extra` tries to shadow it.
                "hint": (
                    "No Style DNA found for this tournament. Running as fresh. "
                    "After approving this poster, extract a DNA with "
                    "--extract-dna --source-poster <path> --tournament-id "
                    f"{tournament_id}."
                ),
            },
        )
    elif located.status == "draft":
        logger.warning(
            "consistency.using_draft",
            extra={
                "tournament_id": str(tournament_id),
                "key": located.key,
                "hint": (
                    "Using a DRAFT Style DNA. Promote it with --approve-dna "
                    "once the style is reviewed."
                ),
            },
        )
        style_dna_dict = located.dna.to_prompt_dict()
    else:
        logger.info(
            "consistency.using_approved",
            extra={"tournament_id": str(tournament_id), "key": located.key},
        )
        style_dna_dict = located.dna.to_prompt_dict()

    return run_fresh(
        input_data,
        org_id=org_id,
        tournament_id=tournament_id,
        style_dna=style_dna_dict,
        on_status=on_status,
        client=client,
        settings=s,
        storage=storage,
        keys=keys,
    )
