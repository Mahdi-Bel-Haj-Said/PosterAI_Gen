"""
`/v1/style-dnas/{tournament_id}` endpoints — manage the per-tournament
Style DNA used by consistency mode.

`POST` extracts a DNA from a completed poster's bytes (fetched from R2).
`GET` reads the current DNA. `PUT` replaces the draft with an edited DNA.
`POST /approve` promotes the draft. `DELETE` removes both objects.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import ValidationError
from typing_extensions import Literal

from esports_poster_ai.api.routes.posters import get_job_store
from esports_poster_ai.api.schemas import (
    ApproveStyleDNARequest,
    ExtractStyleDNARequest,
    StyleDNAResponse,
    UpdateStyleDNARequest,
)
from esports_poster_ai.domain.style_dna import StyleDNA
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.storage import get_storage
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


# ---------------------------------------------------------------- extract
@router.post("/{tournament_id}", status_code=201, response_model=StyleDNAResponse)
def extract_style_dna_endpoint(
    tournament_id: str,
    req: ExtractStyleDNARequest,
    job_store: JobStore = Depends(get_job_store),
) -> StyleDNAResponse:
    """
    Extract a Style DNA from a completed poster job and save it as draft.

    The source poster is fetched from R2 using the job's `storage_key`.
    """
    job = job_store.get(req.source_job_id)
    if job is None:
        raise HTTPException(
            status_code=404, detail=f"Source job not found: {req.source_job_id}"
        )
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
    save_draft(dna, req.org_id)
    logger.info(
        "api.style_dna.extracted",
        extra={"org_id": req.org_id, "tournament_id": tournament_id},
    )
    return _dna_response(dna)


# ---------------------------------------------------------------- read
@router.get("/{tournament_id}", response_model=StyleDNAResponse)
def get_style_dna(
    tournament_id: str,
    org_id: str = Query(..., description="Organization id."),
    status: Optional[DNAStatusFilter] = Query(
        None,
        description=(
            "Which DNA to return: `draft` or `approved`; default = active "
            "(approved if present, else draft)."
        ),
    ),
) -> StyleDNAResponse:
    """Get the tournament's current Style DNA."""
    if status == "draft":
        dna = load_draft(org_id, tournament_id)
    elif status == "approved":
        dna = load_approved(org_id, tournament_id)
    else:
        located = load_active(org_id, tournament_id)
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
) -> StyleDNAResponse:
    """
    Replace the draft Style DNA with the provided document (the 'edit by hand' step).

    An edited DNA always lands as a draft — re-approve it via `/approve`.
    The `tournament_id` in the body is overridden with the path parameter.
    """
    payload = dict(req.dna)
    payload["tournament_id"] = tournament_id
    payload["status"] = "draft"

    try:
        dna = StyleDNA.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=jsonable_encoder(e.errors()))

    save_draft(dna, req.org_id)
    return _dna_response(dna)


# ---------------------------------------------------------------- approve
@router.post("/{tournament_id}/approve", response_model=StyleDNAResponse)
def approve_style_dna(
    tournament_id: str,
    req: ApproveStyleDNARequest,
) -> StyleDNAResponse:
    """Promote the draft Style DNA to approved (and delete the draft)."""
    try:
        dna, _key = promote_draft_to_approved(req.org_id, tournament_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _dna_response(dna)


# ---------------------------------------------------------------- delete
@router.delete("/{tournament_id}", status_code=204)
def delete_style_dna(
    tournament_id: str,
    org_id: str = Query(..., description="Organization id."),
) -> Response:
    """Remove both the draft and approved Style DNA objects for this tournament."""
    delete_for_tournament(org_id, tournament_id)
    return Response(status_code=204)
