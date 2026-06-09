"""
Poster-generation stage.

`generate_poster` runs the image-generation editing call and returns a PIL
image. `save_poster` persists a finished poster to both the local outputs
directory and object storage (R2), under a tournament-scoped key.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
from uuid import uuid4

from PIL import Image

from esports_poster_ai.clients.openai_client import OpenAIClient, new_run_id
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.storage import StorageKeys, get_keys, get_storage
from esports_poster_ai.storage.base import Storage

logger = logging.getLogger(__name__)


_SIZE_FOR_FORMAT = {
    "portrait_1080x1920": "1024x1792",
    "square_1080x1080": "1024x1024",
    "landscape_1920x1080": "1792x1024",
    "landscape_1920x1080px": "1792x1024",
}


def _size_for(output_format: str) -> str:
    return _SIZE_FOR_FORMAT.get(output_format, "1024x1792")


@dataclass
class PosterResult:
    """Where a generated poster landed."""

    poster_id: str
    local_path: Path
    storage_key: str
    signed_url: str


def generate_poster(
    *,
    background_image: bytes,
    prompt: str,
    input_images: List[bytes],
    output_format: str,
    quality: str = "medium",
    client: Optional[OpenAIClient] = None,
    settings: Optional[Settings] = None,
    run_id: Optional[str] = None,
) -> Image.Image:
    """
    Run the image-generation editing call and return the poster image.

    `input_images` are the reference images (team/tournament logos and any
    player photos) handed to the editing model alongside the background.
    """
    s = settings or get_settings()
    run_id = run_id or new_run_id()

    api = client or OpenAIClient(settings=s)
    return api.generate_poster(
        background_image=background_image,
        input_images=input_images,
        prompt=prompt,
        size=_size_for(output_format),
        quality=quality,
        run_id=run_id,
    )


def save_poster(
    image: Image.Image,
    *,
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    outputs_dir: Optional[Path] = None,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
    run_id: Optional[str] = None,
) -> PosterResult:
    """
    Persist a finished poster to the local outputs dir AND to object storage.

    Returns a `PosterResult` with the local path, the storage key, and a
    signed URL for the stored object.
    """
    s = settings or get_settings()
    run_id = run_id or new_run_id()
    storage = storage or get_storage(s)
    keys = keys or get_keys(s)

    poster_id = f"poster_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"

    # A poster is a final, fully opaque deliverable. Flatten any alpha channel
    # so viewers never render a transparency checkerboard over the image.
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    png_bytes = buf.getvalue()

    # Local copy.
    out_root = (outputs_dir or s.outputs_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    local_path = (out_root / f"{poster_id}.png").resolve()
    local_path.write_bytes(png_bytes)

    # Object storage.
    key = keys.poster(org_id, tournament_id, poster_id)
    storage.put_bytes(key, png_bytes, content_type="image/png")
    url = storage.signed_url(key)

    logger.info(
        "poster.saved",
        extra={"run_id": run_id, "local_path": str(local_path), "storage_key": key},
    )
    return PosterResult(
        poster_id=poster_id,
        local_path=local_path,
        storage_key=key,
        signed_url=url,
    )


__all__ = ["PosterResult", "generate_poster", "save_poster"]
