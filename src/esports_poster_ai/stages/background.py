"""
Background stage — resolves the base canvas image for the poster.

Three sources are supported, picked in priority order from `input_data`:

  1. **User upload** (`background.source == "custom"` or just `image_path`):
     read the bytes the user supplied. The path may be a local file (CLI
     runs) or an R2 storage key from `POST /v1/assets` (API runs).

  2. **AI-generated** (`background.source == "generated"`): call the fine-tuned
     Stable Diffusion model on Runpod. This is the long-term plan and is
     deferred — the stub raises `NotImplementedError` with a clear message
     so misconfigured callers fail loudly.

  3. **System pool** (default): pick a static image from the local
     `backgrounds/` directory. Same behavior the pipeline has had since
     day one; remains as the safety net.

The single public entry point is `select_background(input_data, ...)`.
Callers (CLI and worker) never need to know about the source resolution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.storage import get_storage
from esports_poster_ai.storage.base import Storage, StorageError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- public API
def select_background(
    input_data: Optional[Dict[str, Any]] = None,
    *,
    backgrounds_dir: Optional[Path] = None,
    project_root: Optional[Path] = None,
    settings: Optional[Settings] = None,
) -> bytes:
    """
    Return the background image bytes for this poster.

    Source resolution (first match wins, then falls through to the pool):

    1. `input_data.background.image_path` set (with `source` either `"custom"`
       or unset) → read those bytes from local fs or R2.
    2. `input_data.background.source == "generated"` → AI-generate via the
       fine-tuned SD model on Runpod (currently a stub).
    3. Otherwise → pick the first image alphabetically from the local
       `backgrounds/` pool (system default).

    A missing user-supplied path falls through to the pool with a warning so a
    stale storage key never breaks a run.
    """
    s = settings or get_settings()
    bg = (input_data or {}).get("background") or {}
    source = (bg.get("source") or "").strip().lower() or None
    image_path = bg.get("image_path")

    # 1. User upload (explicit "custom" or implied by image_path)
    if image_path and source != "generated":
        data = _read_user_background(
            image_path,
            project_root=project_root or s.project_root,
            storage=get_storage(s),
        )
        if data is not None:
            logger.info("background.selected_user", extra={"path": image_path})
            return data
        logger.warning(
            "background.user_missing",
            extra={"reason": "not found in local fs or storage", "path": image_path},
        )
        # fall through to defaults

    # 2. AI-generated via Runpod (deferred — see _generate_with_runpod)
    if source == "generated":
        logger.info("background.requesting_generated")
        return _generate_with_runpod(input_data or {}, settings=s)

    # 3. System pool (current behavior)
    return _select_from_pool(backgrounds_dir or s.backgrounds_dir)


# ---------------------------------------------------------------- source 1: user
def _read_user_background(
    image_path: str,
    *,
    project_root: Path,
    storage: Storage,
) -> Optional[bytes]:
    """Read user-supplied bytes. Tries local fs first, then the configured storage."""
    if not isinstance(image_path, str) or not image_path.strip():
        return None

    p = Path(image_path)
    candidate = p if p.is_absolute() else (project_root / p).resolve()
    if candidate.is_file():
        return candidate.read_bytes()

    # Fall back to object storage — covers R2 keys from /v1/assets
    try:
        return storage.get_bytes(image_path)
    except FileNotFoundError:
        return None
    except StorageError as e:
        logger.warning("background.storage_error", extra={"path": image_path, "error": str(e)})
        return None


# ---------------------------------------------------------------- source 2: Runpod (stub)
def _generate_with_runpod(input_data: Dict[str, Any], *, settings: Settings) -> bytes:
    """
    Generate a background with the fine-tuned Stable Diffusion model on Runpod.

    DEFERRED — not yet implemented. When wiring this in:

      1. Verify `settings.runpod_api_key` and `settings.runpod_endpoint_id` are set.
      2. Derive a prompt from `input_data`:
            - `_meta.game`           → game-flavored vibe (LoL / VAL aesthetics)
            - `design.vibe`          → cyberpunk / cinematic / dark_fantasy / …
            - `design.primary_color` → dominant hue for the palette
            - `design.energy`        → chill / balanced / intense / explosive
            - `_meta.output_format`  → portrait / square / landscape size hint
         Render this into a Stable-Diffusion-style prompt.
      3. POST to `https://api.runpod.ai/v2/{endpoint_id}/run` with the prompt,
         poll `.../status/{request_id}` until COMPLETED, fetch the image bytes
         (Runpod usually returns a presigned URL or a base64 payload — depends
         on the worker config).
      4. Apply a content-hash cache (sha256 of prompt + width × height) so
         identical inputs reuse the same background across reruns. Useful for
         "regenerate this exact poster" UX.

    Implementation lives here so the rest of the pipeline never changes —
    just the body of this function gets filled in.
    """
    if not settings.runpod_api_key or not settings.runpod_endpoint_id:
        raise RuntimeError(
            "AI-generated background requires RUNPOD_API_KEY and "
            "RUNPOD_ENDPOINT_ID to be set. Configure them in .env, then "
            "implement the Runpod call in stages/background._generate_with_runpod."
        )
    # NOTE: when wired, replace this raise with the real Runpod call.
    raise NotImplementedError(
        "AI-generated backgrounds (fine-tuned SD via Runpod) are not implemented yet. "
        "Use background.source='custom' (user upload) or omit it (system pool)."
    )


# ---------------------------------------------------------------- pool listing
_POOL_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def list_pool(
    backgrounds_dir: Optional[Path] = None,
    *,
    settings: Optional[Settings] = None,
) -> list[str]:
    """
    Return the file names in the local system background pool, sorted.

    The single source of truth for "which system backgrounds exist". Exposed so
    the HTTP API (`GET /v1/backgrounds`) can advertise the pool to integrators
    without reaching into the filesystem itself. Missing directory → empty list.
    """
    s = settings or get_settings()
    bg_dir = backgrounds_dir or s.backgrounds_dir
    if not bg_dir.exists():
        return []
    return sorted(
        p.name for p in bg_dir.iterdir() if p.suffix.lower() in _POOL_SUFFIXES
    )


# ---------------------------------------------------------------- source 3: system pool
def _select_from_pool(bg_dir: Path) -> bytes:
    """Pick the first image alphabetically from the local backgrounds pool."""
    if not bg_dir.exists():
        raise FileNotFoundError(f"Backgrounds directory not found: {bg_dir}")

    candidates = sorted(
        p for p in bg_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if not candidates:
        raise FileNotFoundError(f"No background images found in: {bg_dir}")

    chosen = candidates[0].resolve()
    logger.info("background.selected_pool", extra={"path": str(chosen)})
    return chosen.read_bytes()


__all__ = ["select_background", "list_pool"]
