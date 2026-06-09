"""
Fresh mode orchestration: background -> prompt -> poster -> persist.

The image model owns logo placement (no separate PIL re-stamp pass). The
sponsor bar is opt-in via the input JSON's `sponsors.enabled` flag. The
finished poster is saved to both the local outputs dir and object storage.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from esports_poster_ai.clients.openai_client import OpenAIClient, new_run_id
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.inputs import PosterInput
from esports_poster_ai.processing import LOGO_MAX_DIM, PLAYER_MAX_DIM, resize_for_reference
from esports_poster_ai.stages.background import select_background
from esports_poster_ai.stages.poster_generator import PosterResult, generate_poster, save_poster
from esports_poster_ai.stages.prompt_generator import generate_image_prompt
from esports_poster_ai.stages.sponsor_bar import add_sponsor_bar
from esports_poster_ai.storage import StorageKeys, get_storage
from esports_poster_ai.storage.base import Storage, StorageError

logger = logging.getLogger(__name__)

# Optional progress callback — the async worker passes one that writes each
# status transition to the job store; the CLI runs without it.
StatusCallback = Optional[Callable[[str], None]]


def _resolve_path(root: Path, maybe_path: Any) -> Optional[Path]:
    if not isinstance(maybe_path, str) or not maybe_path.strip():
        return None
    p = Path(maybe_path)
    return p if p.is_absolute() else (root / p).resolve()


def _read_image(root: Path, maybe_path: Any) -> Optional[bytes]:
    """
    Resolve an image from the input JSON and read its bytes.

    The pipeline is dual-mode: CLI runs reference local files like
    `assets/logos/T1.png`; API runs reference R2 storage keys like
    `defendr-poster-ai/orgs/1/assets/team-logos/{asset_id}.png`. Try local
    first (cheap), then fall back to the configured storage backend.
    """
    if not isinstance(maybe_path, str) or not maybe_path.strip():
        return None

    p = _resolve_path(root, maybe_path)
    if p is not None and p.is_file():
        return p.read_bytes()

    # Fall back to object storage — covers R2 keys uploaded via /v1/assets.
    try:
        return get_storage().get_bytes(maybe_path)
    except FileNotFoundError:
        logger.warning("logo.skip", extra={"reason": "not found", "path": maybe_path})
        return None
    except StorageError as e:
        logger.warning("logo.skip", extra={"reason": f"storage error: {e}", "path": maybe_path})
        return None


def _extract_input_images(input_data: Dict[str, Any], project_root: Path) -> List[bytes]:
    """
    Read the reference images to pass into the image-edit call, per poster type:
    team/tournament logos plus, optionally, player photos.

    - gameday / game_results: both team logos + the featured player image
      (when `player_feature.enabled` is true).
    - roster_reveal: the team logo + each roster player's photo (when provided).
    - tournament_*: the tournament logo.

    Each candidate carries its own resize cap (logo vs player) so input tokens
    to `gpt-image-2` stay predictable without throwing away the asset stored
    in R2. Aspect ratio is preserved by the resizer.
    """
    meta = input_data.get("_meta", {})
    poster_type = meta.get("poster_type")
    candidates: List[Tuple[Any, int]] = []  # (path-or-storage-key, max_dim)

    if poster_type in {"gameday", "game_results"}:
        match = input_data.get("match") or {}
        candidates.append(((match.get("team1") or {}).get("logo_path"), LOGO_MAX_DIM))
        candidates.append(((match.get("team2") or {}).get("logo_path"), LOGO_MAX_DIM))
        # Tournament logo is a real reference input for match posters too, so the
        # model places the actual logo instead of fabricating one from the name.
        candidates.append(((input_data.get("tournament") or {}).get("logo_path"), LOGO_MAX_DIM))
        player = input_data.get("player_feature") or {}
        if isinstance(player, dict) and player.get("enabled") is True:
            candidates.append((player.get("image_path"), PLAYER_MAX_DIM))
    elif poster_type == "roster_reveal":
        candidates.append(((input_data.get("team") or {}).get("logo_path"), LOGO_MAX_DIM))
        roster = input_data.get("roster") or {}
        for player in roster.get("players") or []:
            if isinstance(player, dict):
                candidates.append((player.get("image_path"), PLAYER_MAX_DIM))
    else:
        candidates.append(((input_data.get("tournament") or {}).get("logo_path"), LOGO_MAX_DIM))

    images: List[bytes] = []
    for path, cap in candidates:
        raw = _read_image(project_root, path)
        if raw:
            images.append(resize_for_reference(raw, cap))
    return images


def _resolve_sponsor_logos(input_data: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    """
    Read sponsor logo bytes so add_sponsor_bar can composite them.

    Sponsor logo paths in the input JSON are either local files (CLI runs) or
    R2 storage keys (API runs). `_read_image` handles both, so the resolved
    config carries raw `bytes` rather than filesystem paths — keeping the
    pipeline storage-backed end-to-end.
    """
    sponsors = input_data.get("sponsors")
    if not isinstance(sponsors, dict):
        return {"enabled": False, "logos": []}

    resolved_logos: List[Dict[str, bytes]] = []
    for item in sponsors.get("logos") or []:
        if not isinstance(item, dict):
            continue
        data = _read_image(project_root, item.get("path"))
        if data:
            resolved_logos.append({"bytes": data})

    return {"enabled": bool(sponsors.get("enabled", False)), "logos": resolved_logos}


def run_fresh(
    input_data: Dict[str, Any],
    *,
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    style_dna: Optional[Dict[str, Any]] = None,
    on_status: StatusCallback = None,
    client: Optional[OpenAIClient] = None,
    settings: Optional[Settings] = None,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
) -> PosterResult:
    """
    Run the pipeline end-to-end.

    Args:
        input_data: The parsed poster input JSON (a dict). Callers load the
            file; this function does not touch the filesystem for input.
        org_id: Tenant identifier (poster is stored under this org).
        tournament_id: Tournament identifier (poster is stored under it).
        style_dna: Optional Style DNA dict (consistency mode). Injected into
            the prompt as a hard visual constraint when provided.
        on_status: Optional callback invoked with each pipeline status
            (`generating_prompt`, `generating_poster`, `applying_sponsor_bar`).
            The async worker uses it to record progress; the CLI omits it.
        client: Optional pre-built OpenAIClient.
        settings / storage / keys: Optional overrides (mostly for tests).

    Returns:
        A `PosterResult` (local path + storage key + signed URL).
    """
    s = settings or get_settings()
    run_id = new_run_id()

    def _emit(status: str) -> None:
        if on_status is not None:
            on_status(status)

    logger.info(
        "fresh.start",
        extra={
            "run_id": run_id,
            "org_id": str(org_id),
            "tournament_id": str(tournament_id),
            "has_style_dna": style_dna is not None,
        },
    )

    # Validate the meta block strictly; the rest is intentionally loose.
    PosterInput.model_validate(input_data)

    project_root = s.project_root
    api = client or OpenAIClient(settings=s)

    # The background stage owns all source selection — user upload (local or
    # R2), AI-generated (Runpod, deferred), or the local pool. See
    # stages/background.py for the priority order.
    background_image = select_background(
        input_data=input_data, project_root=project_root, settings=s
    )

    _emit("generating_prompt")
    prompt = generate_image_prompt(
        background_image=background_image,
        input_data=input_data,
        style_dna=style_dna,
        client=api,
        settings=s,
        run_id=run_id,
    )

    output_format = (input_data.get("_meta") or {}).get("output_format") or "portrait_1080x1920"
    input_images = _extract_input_images(input_data, project_root)

    _emit("generating_poster")
    poster_image = generate_poster(
        background_image=background_image,
        prompt=prompt,
        input_images=input_images,
        output_format=output_format,
        client=api,
        settings=s,
        run_id=run_id,
    )

    # Optional sponsor bar pass (composited on the in-memory image).
    sponsors_cfg = _resolve_sponsor_logos(input_data, project_root)
    if sponsors_cfg["enabled"] and sponsors_cfg["logos"]:
        _emit("applying_sponsor_bar")
        poster_image = add_sponsor_bar(poster_image, sponsors_cfg)
        logger.info("fresh.sponsor_bar_applied", extra={"run_id": run_id})

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
        "fresh.done",
        extra={"run_id": run_id, "local_path": str(result.local_path), "storage_key": result.storage_key},
    )
    return result
