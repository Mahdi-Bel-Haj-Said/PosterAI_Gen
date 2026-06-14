"""
`/v1/assets` endpoints — the org's brand library.

Upload writes the bytes to R2 (`orgs/{org_id}/assets/{type}/{asset_id}.{ext}`)
and the metadata to the MongoDB `assets` collection. List / get / delete read
the metadata and resolve the storage layer for signed URLs and removal.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.api.schemas import AssetListResponse, AssetResponse
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.assets.store import AssetStore
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.asset import Asset
from esports_poster_ai.processing import (
    BackgroundTooSmallError,
    BackgroundUnreadableError,
    remove_background,
    validate_and_downscale_background,
)
from esports_poster_ai.storage import get_keys, get_storage
from esports_poster_ai.storage.base import Storage
from esports_poster_ai.storage.keys import AssetType

# Asset types where background removal is on by default — flat brand-mark
# logos and player portraits both composite better with a transparent bg.
_BG_REMOVAL_DEFAULT_ON = {
    AssetType.TEAM_LOGO,
    AssetType.SPONSOR_LOGO,
    AssetType.PLAYER_IMAGE,
    AssetType.TOURNAMENT_LOGO,
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/assets", tags=["assets"])


def get_asset_store() -> AssetStore:
    """FastAPI dependency providing an AssetStore. Overridable in tests."""
    return AssetStore()


_EXT_FOR_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}


def _extension_for(content_type: str, filename: Optional[str]) -> str:
    if content_type in _EXT_FOR_MIME:
        return _EXT_FOR_MIME[content_type]
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "png"


def _asset_to_response(asset: Asset, storage: Storage) -> AssetResponse:
    """Build an AssetResponse, attaching a signed R2 URL."""
    signed_url = storage.signed_url(asset.storage_key)
    return AssetResponse.from_asset(asset, signed_url=signed_url)


# ---------------------------------------------------------------- create
@router.post("", status_code=201, response_model=AssetResponse)
def upload_asset(
    org_id: Optional[str] = Form(
        None,
        description="Organization id this asset belongs to. Omit when "
        "authenticating with an API key (taken from the key).",
    ),
    asset_type: AssetType = Form(..., description="Asset folder type."),
    name: Optional[str] = Form(None, description="Optional human label (e.g. 'FNATIC logo')."),
    team: Optional[str] = Form(
        None,
        description="Owning team (team-logos / player-images). For team-logos this is unique: "
        "uploading a new logo for a team replaces the previous one.",
    ),
    remove_bg: Optional[bool] = Form(
        None,
        alias="remove_background",
        description="Remove the image background before storing. Defaults to ON "
        "for team/sponsor/tournament logos and player images; OFF otherwise. "
        "Already-transparent inputs are passed through unchanged.",
    ),
    file: UploadFile = File(..., description="Image file (PNG / JPEG / WEBP)."),
    store: AssetStore = Depends(get_asset_store),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> AssetResponse:
    """Upload an asset image. Returns the asset's id, storage key, and a signed URL."""
    org_id = auth.require_org(org_id)
    auth.require_org_registered(org_id, org_store)
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")

    max_bytes = get_settings().max_asset_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds max upload size of {get_settings().max_asset_size_mb} MB.",
        )

    content_type = (file.content_type or "").lower() or "image/png"
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, detail=f"Unsupported content type: {content_type}"
        )

    # Background-quality gate. Applied only to user-uploaded backgrounds —
    # logos and player photos have their own resize step at generation time,
    # and sponsor logos are composited locally so size doesn't drive cost.
    #
    #  * Reject min(w, h) < 720  -> 422 (visual quality too low to spend
    #    generation tokens on).
    #  * Downscale max(w, h) > 2048 to fit, aspect-preserving (cap input-
    #    token cost when the user drops in 4K / 8K wallpapers).
    if asset_type == AssetType.BACKGROUND:
        try:
            content, content_type = validate_and_downscale_background(
                content, content_type_hint=content_type
            )
        except BackgroundTooSmallError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except BackgroundUnreadableError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    team = (team or "").strip() or None

    # Background removal — default ON for logo/portrait asset types, off
    # otherwise. The processor short-circuits on already-transparent inputs
    # and falls back to the original bytes on any failure.
    apply_bg_removal = remove_bg if remove_bg is not None else (asset_type in _BG_REMOVAL_DEFAULT_ON)
    if apply_bg_removal:
        processed = remove_background(content)
        if processed is not content:
            content = processed
            content_type = "image/png"   # rembg returns RGBA PNG

    ext = _extension_for(content_type, file.filename)
    asset_id = uuid4().hex
    storage_key = get_keys(platform_id=auth.platform_id).asset(org_id, asset_type, asset_id, ext)

    storage = get_storage()
    storage.put_bytes(storage_key, content, content_type=content_type)

    # One logo per team: replacing a team's logo removes the previous one(s).
    if asset_type == AssetType.TEAM_LOGO and team:
        for prior in store.list_for_org(
            org_id, asset_type=AssetType.TEAM_LOGO, team=team, limit=100,
            platform_id=auth.platform_id,
        ):
            try:
                storage.delete(prior.storage_key)
            except Exception:  # noqa: BLE001 — stale metadata cleanup must still proceed
                pass
            store.delete(prior.asset_id)

    asset = store.create(
        org_id=org_id,
        asset_type=asset_type,
        asset_id=asset_id,
        filename=file.filename or "",
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=len(content),
        name=name,
        team=team,
        platform_id=auth.platform_id,
    )
    logger.info("api.asset.uploaded", extra={"asset_id": asset_id, "storage_key": storage_key, "team": team})
    return _asset_to_response(asset, storage)


# ---------------------------------------------------------------- read
@router.get("", response_model=AssetListResponse)
def list_assets(
    org_id: Optional[str] = Query(
        None, description="Organization id. Omit when authenticating with an API key."
    ),
    asset_type: Optional[AssetType] = Query(None, description="Filter by asset folder."),
    team: Optional[str] = Query(None, description="Filter by owning team (case-insensitive)."),
    limit: int = Query(50, ge=1, le=200),
    store: AssetStore = Depends(get_asset_store),
    auth: AuthContext = Depends(get_auth_context),
) -> AssetListResponse:
    """List an org's assets, most recent first."""
    org_id = auth.require_org(org_id)
    assets = store.list_for_org(
        org_id, asset_type=asset_type, team=team, limit=limit, platform_id=auth.platform_id
    )
    storage = get_storage()
    return AssetListResponse(
        assets=[_asset_to_response(a, storage) for a in assets],
        count=len(assets),
    )


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: str,
    store: AssetStore = Depends(get_asset_store),
    auth: AuthContext = Depends(get_auth_context),
) -> AssetResponse:
    """Get an asset's metadata + a signed URL."""
    asset = store.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    auth.assert_platform(asset.platform_id)
    return _asset_to_response(asset, get_storage())


# ---------------------------------------------------------------- delete
@router.delete("/{asset_id}", status_code=204)
def delete_asset(
    asset_id: str,
    store: AssetStore = Depends(get_asset_store),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    """Remove an asset from R2 and its metadata row."""
    asset = store.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    auth.assert_platform(asset.platform_id)

    get_storage().delete(asset.storage_key)
    store.delete(asset_id)
    return Response(status_code=204)
