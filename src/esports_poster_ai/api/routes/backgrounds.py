"""
`GET /v1/backgrounds` — advertise the system background pool.

The wizard offers three background sources (system pool / custom upload /
AI-generated). The custom-upload path already has an API (`/v1/assets` with
`asset_type=backgrounds`), but the *system pool* the pipeline falls back to was
only knowable by reading the server's filesystem. This endpoint exposes it so
an integrator can render the same "pick a system background" choice the UI does.

Two sources are merged:
  * the local `backgrounds/` pool the pipeline picks from today (no URL — the
    files live on the API host, not in object storage), and
  * any objects under the shared `system/backgrounds/` prefix in object storage
    (signed URLs), which is where a curated pool will live once migrated.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from esports_poster_ai.api.deps import AuthContext, get_auth_context
from esports_poster_ai.stages.background import list_pool
from esports_poster_ai.storage import get_keys, get_storage

router = APIRouter(prefix="/v1/backgrounds", tags=["backgrounds"])


class BackgroundItem(BaseModel):
    """One available system background."""

    name: str
    source: str = Field(
        description="Where it lives: 'system_pool' (local pool) or 'r2_system' (object storage)."
    )
    signed_url: Optional[str] = Field(
        default=None,
        description="Signed URL when the background lives in object storage; "
        "null for the local pool (served from the API host, not a bucket).",
    )


class BackgroundListResponse(BaseModel):
    backgrounds: List[BackgroundItem]
    count: int


@router.get("", response_model=BackgroundListResponse)
def list_backgrounds(
    auth: AuthContext = Depends(get_auth_context),
) -> BackgroundListResponse:
    """
    List the shared system backgrounds available to every org.

    Not org-scoped (these are shared system assets), but still gated by
    `get_auth_context` so the endpoint locks down with everything else when
    `API_KEY_REQUIRED=true`.
    """
    items: List[BackgroundItem] = [
        BackgroundItem(name=name, source="system_pool") for name in list_pool()
    ]

    # Forward-compatible: surface any curated pool already in object storage.
    try:
        storage = get_storage()
        keys = get_keys()
        for key in storage.list_keys(keys.backgrounds_prefix()):
            name = PurePosixPath(key).name
            if not name:
                continue
            items.append(
                BackgroundItem(
                    name=name,
                    source="r2_system",
                    signed_url=storage.signed_url(key),
                )
            )
    except Exception:  # noqa: BLE001 — a storage hiccup shouldn't hide the local pool
        pass

    return BackgroundListResponse(backgrounds=items, count=len(items))
