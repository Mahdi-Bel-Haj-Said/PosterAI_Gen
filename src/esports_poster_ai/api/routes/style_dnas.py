"""
`/v1/style-dnas/{tournament_id}` endpoints — manage the per-tournament
Style DNA used by consistency mode.

`POST` extracts a DNA from a completed poster's bytes (fetched from R2).
`GET` reads the current DNA. `PUT` replaces the draft with an edited DNA.
`POST /approve` promotes the draft. `DELETE` removes both objects.
"""

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import ValidationError
from typing_extensions import Literal

from esports_poster_ai.api.deps import AuthContext, get_auth_context, get_org_store
from esports_poster_ai.api.routes.posters import get_job_store
from esports_poster_ai.orgs.store import OrgStore
from esports_poster_ai.api.schemas import (
    ApproveStyleDNARequest,
    ExtractStyleDNARequest,
    StyleDNAListResponse,
    StyleDNAResponse,
    UpdateStyleDNARequest,
)
from esports_poster_ai.domain.style_dna import StyleDNA
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.storage import get_keys, get_storage
from esports_poster_ai.storage.base import StorageError
from esports_poster_ai.style_dna.extractor import extract_style_dna
from esports_poster_ai.style_dna.repository import (
    delete_for_tournament,
    load_active,
    load_approved,
    load_draft,
    promote_draft_to_approved,
    save_draft,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/style-dnas", tags=["style-dnas"])


DNAStatusFilter = Literal["draft", "approved", "active"]


def _source_poster_url(dna) -> Optional[str]:
    """Sign the source poster if it lives in object storage (CLI-era local paths are skipped)."""
    path = getattr(dna, "source_poster_path", None)
    if not path:
        return None
    storage = get_storage()
    try:
        if storage.exists(path):
            return storage.signed_url(path)
    except Exception:  # noqa: BLE001 — a missing/unsignable source must not break the response
        return None
    return None


def _dna_response(dna) -> StyleDNAResponse:
    return StyleDNAResponse.from_dna(dna, source_poster_url=_source_poster_url(dna))


# ---------------------------------------------------------------- list (org-wide)
@router.get("", response_model=StyleDNAListResponse)
def list_style_dnas(
    org_id: Optional[str] = Query(
        None, description="Organization id. Omit when authenticating with an API key."
    ),
    auth: AuthContext = Depends(get_auth_context),
) -> StyleDNAListResponse:
    """
    List every Style DNA an org has, one per tournament (active view).

    Scans the org's tournament prefix in object storage for `style-dna(.draft).json`
    objects and returns the active DNA (approved over draft) for each tournament.
    This is the direct API equivalent of the dashboard's "Style DNA library",
    which previously could only be reconstructed client-side from job history.
    """
    org_id = auth.require_org(org_id)
    storage = get_storage()
    keys = get_keys(platform_id=auth.platform_id)

    try:
        all_keys = storage.list_keys(keys.tournaments_prefix(org_id))
    except Exception:  # noqa: BLE001 — a storage hiccup yields an empty library, not a 500
        all_keys = []

    # Collect the distinct tournament ids that own a DNA object, then resolve
    # each to its active DNA so draft+approved for one tournament collapse to one row.
    tournament_ids = []
    seen = set()
    for key in all_keys:
        p = PurePosixPath(key)
        if p.name in ("style-dna.json", "style-dna.draft.json"):
            tid = p.parent.name
            if tid and tid not in seen:
                seen.add(tid)
                tournament_ids.append(tid)

    items = []
    for tid in sorted(tournament_ids):
        located = load_active(org_id, tid, keys=keys)
        if located is not None:
            items.append(_dna_response(located.dna))

    return StyleDNAListResponse(style_dnas=items, count=len(items))


# ---------------------------------------------------------------- extract
@router.post("/{tournament_id}", status_code=201, response_model=StyleDNAResponse)
def extract_style_dna_endpoint(
    tournament_id: str,
    req: ExtractStyleDNARequest,
    job_store: JobStore = Depends(get_job_store),
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> StyleDNAResponse:
    """
    Extract a Style DNA from a completed poster job and save it as draft.

    The source poster is fetched from R2 using the job's `storage_key`.
    """
    org_id = auth.require_org(req.org_id)
    auth.require_org_registered(org_id, org_store)
    job = job_store.get(req.source_job_id)
    if job is None:
        raise HTTPException(
            status_code=404, detail=f"Source job not found: {req.source_job_id}"
        )
    auth.assert_platform(job.platform_id)
    if job.status != "completed" or not job.storage_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source job is not a completed poster (status={job.status}); "
                "Style DNA can only be extracted from a completed poster."
            ),
        )

    try:
        poster_bytes = get_storage().get_bytes(job.storage_key)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"Source poster object not found: {job.storage_key}"
        ) from e
    except StorageError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    dna = extract_style_dna(
        poster_bytes=poster_bytes,
        tournament_id=tournament_id,
        source_reference=job.storage_key,
    )
    save_draft(dna, org_id, keys=get_keys(platform_id=auth.platform_id))
    logger.info(
        "api.style_dna.extracted",
        extra={"org_id": org_id, "tournament_id": tournament_id},
    )
    return _dna_response(dna)


# ---------------------------------------------------------------- read
@router.get("/{tournament_id}", response_model=StyleDNAResponse)
def get_style_dna(
    tournament_id: str,
    org_id: Optional[str] = Query(
        None, description="Organization id. Omit when authenticating with an API key."
    ),
    status: Optional[DNAStatusFilter] = Query(
        None,
        description=(
            "Which DNA to return: `draft` or `approved`; default = active "
            "(approved if present, else draft)."
        ),
    ),
    auth: AuthContext = Depends(get_auth_context),
) -> StyleDNAResponse:
    """Get the tournament's current Style DNA."""
    org_id = auth.require_org(org_id)
    keys = get_keys(platform_id=auth.platform_id)
    if status == "draft":
        dna = load_draft(org_id, tournament_id, keys=keys)
    elif status == "approved":
        dna = load_approved(org_id, tournament_id, keys=keys)
    else:
        located = load_active(org_id, tournament_id, keys=keys)
        dna = located.dna if located else None

    if dna is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Style DNA for tournament {tournament_id} (status={status or 'active'}).",
        )
    return _dna_response(dna)


# ---------------------------------------------------------------- update
@router.put("/{tournament_id}", response_model=StyleDNAResponse)
def update_style_dna(
    tournament_id: str,
    req: UpdateStyleDNARequest,
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> StyleDNAResponse:
    """
    Replace the draft Style DNA with the provided document (the 'edit by hand' step).

    An edited DNA always lands as a draft — re-approve it via `/approve`.
    The `tournament_id` in the body is overridden with the path parameter.
    """
    org_id = auth.require_org(req.org_id)
    auth.require_org_registered(org_id, org_store)
    payload = dict(req.dna)
    payload["tournament_id"] = tournament_id
    payload["status"] = "draft"

    try:
        dna = StyleDNA.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=jsonable_encoder(e.errors()))

    save_draft(dna, org_id, keys=get_keys(platform_id=auth.platform_id))
    return _dna_response(dna)


# ---------------------------------------------------------------- approve
@router.post("/{tournament_id}/approve", response_model=StyleDNAResponse)
def approve_style_dna(
    tournament_id: str,
    req: ApproveStyleDNARequest,
    auth: AuthContext = Depends(get_auth_context),
    org_store: OrgStore = Depends(get_org_store),
) -> StyleDNAResponse:
    """Promote the draft Style DNA to approved (and delete the draft)."""
    org_id = auth.require_org(req.org_id)
    auth.require_org_registered(org_id, org_store)
    try:
        dna, _key = promote_draft_to_approved(
            org_id, tournament_id, keys=get_keys(platform_id=auth.platform_id)
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _dna_response(dna)


# ---------------------------------------------------------------- delete
@router.delete("/{tournament_id}", status_code=204)
def delete_style_dna(
    tournament_id: str,
    org_id: Optional[str] = Query(
        None, description="Organization id. Omit when authenticating with an API key."
    ),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    """Remove both the draft and approved Style DNA objects for this tournament."""
    org_id = auth.require_org(org_id)
    delete_for_tournament(org_id, tournament_id, keys=get_keys(platform_id=auth.platform_id))
    return Response(status_code=204)
