"""
Style DNA repository — storage-backed.

A tournament has at most two DNA objects in storage:

    .../orgs/{org_id}/tournaments/{tournament_id}/style-dna.json         # approved
    .../orgs/{org_id}/tournaments/{tournament_id}/style-dna.draft.json   # draft

Loading rules:
- `load_approved` returns the approved DNA if its object exists.
- `load_draft` returns the draft DNA if its object exists.
- `load_active` returns approved if present, otherwise draft (flagging which),
  otherwise None.

DNA documents are written by the extractor as drafts, reviewed, then promoted
to approved via `promote_draft_to_approved`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.domain.style_dna import DNAStatus, StyleDNA
from esports_poster_ai.storage import StorageKeys, get_keys, get_storage
from esports_poster_ai.storage.base import Storage

logger = logging.getLogger(__name__)


@dataclass
class StyleDNALocation:
    """Where a loaded DNA came from and what status it had in storage."""

    dna: StyleDNA
    status: DNAStatus
    key: str


def _resolve(
    storage: Optional[Storage], keys: Optional[StorageKeys], settings: Optional[Settings]
) -> Tuple[Storage, StorageKeys]:
    s = settings or get_settings()
    return (storage or get_storage(s), keys or get_keys(s))


def _serialize(dna: StyleDNA) -> bytes:
    # `mode="json"` so datetimes serialize to ISO strings.
    return json.dumps(
        dna.model_dump(mode="json"), indent=2, ensure_ascii=False
    ).encode("utf-8")


def _load(storage: Storage, key: str) -> Optional[StyleDNA]:
    try:
        data = storage.get_bytes(key)
    except FileNotFoundError:
        return None
    return StyleDNA.model_validate(json.loads(data))


# ---------------------------------------------------------------- save
def save_draft(
    dna: StyleDNA,
    org_id: Union[str, int],
    *,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
) -> str:
    """Persist `dna` as the tournament's draft DNA. Returns the storage key."""
    storage, keys = _resolve(storage, keys, settings)
    if dna.status != "draft":
        dna = dna.model_copy(update={"status": "draft"})
    key = keys.style_dna_draft(org_id, dna.tournament_id)
    storage.put_bytes(key, _serialize(dna), content_type="application/json")
    logger.info("dna.draft_saved", extra={"key": key, "tournament_id": dna.tournament_id})
    return key


def save_approved(
    dna: StyleDNA,
    org_id: Union[str, int],
    *,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
) -> str:
    """Persist `dna` as the tournament's approved DNA. Returns the storage key."""
    storage, keys = _resolve(storage, keys, settings)
    if dna.status != "approved":
        dna = dna.approve()
    key = keys.style_dna(org_id, dna.tournament_id)
    storage.put_bytes(key, _serialize(dna), content_type="application/json")
    logger.info("dna.approved_saved", extra={"key": key, "tournament_id": dna.tournament_id})
    return key


# ---------------------------------------------------------------- load
def load_approved(
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    *,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
) -> Optional[StyleDNA]:
    storage, keys = _resolve(storage, keys, settings)
    return _load(storage, keys.style_dna(org_id, tournament_id))


def load_draft(
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    *,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
) -> Optional[StyleDNA]:
    storage, keys = _resolve(storage, keys, settings)
    return _load(storage, keys.style_dna_draft(org_id, tournament_id))


def load_active(
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    *,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
) -> Optional[StyleDNALocation]:
    """
    Return the DNA that should currently be applied for this tournament.

    Approved wins over draft. Returns None if neither object exists.
    """
    storage, keys = _resolve(storage, keys, settings)

    approved_key = keys.style_dna(org_id, tournament_id)
    approved = _load(storage, approved_key)
    if approved is not None:
        return StyleDNALocation(dna=approved, status="approved", key=approved_key)

    draft_key = keys.style_dna_draft(org_id, tournament_id)
    draft = _load(storage, draft_key)
    if draft is not None:
        return StyleDNALocation(dna=draft, status="draft", key=draft_key)

    return None


# ---------------------------------------------------------------- promote
def promote_draft_to_approved(
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    *,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
) -> Tuple[StyleDNA, str]:
    """
    Promote a tournament's draft DNA to approved.

    Writes the approved object, deletes the draft. Raises FileNotFoundError
    if no draft exists.
    """
    storage, keys = _resolve(storage, keys, settings)

    draft = load_draft(org_id, tournament_id, storage=storage, keys=keys)
    if draft is None:
        raise FileNotFoundError(
            f"No draft Style DNA for org={org_id!r} tournament={tournament_id!r}. "
            f"Run extraction first."
        )

    approved = draft.approve()
    approved_key = save_approved(approved, org_id, storage=storage, keys=keys)
    storage.delete(keys.style_dna_draft(org_id, tournament_id))
    return approved, approved_key


# ---------------------------------------------------------------- delete
def delete_for_tournament(
    org_id: Union[str, int],
    tournament_id: Union[str, int],
    *,
    storage: Optional[Storage] = None,
    keys: Optional[StorageKeys] = None,
    settings: Optional[Settings] = None,
) -> Dict[str, bool]:
    """
    Remove both the draft and approved Style DNA objects for a tournament.

    Returns a dict reporting which (if any) existed and were deleted.
    Deletes are idempotent — missing objects are a no-op.
    """
    storage, keys = _resolve(storage, keys, settings)

    approved_key = keys.style_dna(org_id, tournament_id)
    draft_key = keys.style_dna_draft(org_id, tournament_id)

    had_approved = storage.exists(approved_key)
    had_draft = storage.exists(draft_key)

    storage.delete(approved_key)
    storage.delete(draft_key)

    if had_approved or had_draft:
        logger.info(
            "dna.deleted",
            extra={
                "tournament_id": str(tournament_id),
                "approved_removed": had_approved,
                "draft_removed": had_draft,
            },
        )
    return {"approved": had_approved, "draft": had_draft}


__all__ = [
    "StyleDNALocation",
    "load_approved",
    "load_draft",
    "load_active",
    "save_draft",
    "save_approved",
    "promote_draft_to_approved",
    "delete_for_tournament",
]
