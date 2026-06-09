"""Tests for style_dna.repository — storage-backed save / load / promote."""

from __future__ import annotations

import pytest

from esports_poster_ai.domain.style_dna import StyleDNA
from esports_poster_ai.storage.keys import StorageKeys
from esports_poster_ai.storage.local import LocalStorage
from esports_poster_ai.style_dna import repository as repo

ORG = "1"
TID = "ewc_2025"


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(root=tmp_path)


@pytest.fixture
def keys():
    return StorageKeys(prefix="defendr-poster-ai")


def _make_dna(tournament_id: str = TID, status: str = "draft") -> StyleDNA:
    return StyleDNA(
        tournament_id=tournament_id,
        status=status,  # type: ignore[arg-type]
        palette=["#FF5C00", "#0A0A1A", "#7B2FFF"],
        color_temperature="warm",
        lighting="neon backlit",
        atmosphere="dark electric",
        particle_effects="orange sparks",
        energy="intense",
        sd_style_keywords="cyberpunk arena, neon",
    )


def test_save_draft_and_load_draft_roundtrips(storage, keys):
    dna = _make_dna()
    key = repo.save_draft(dna, ORG, storage=storage, keys=keys)
    assert key == "defendr-poster-ai/orgs/1/tournaments/ewc_2025/style-dna.draft.json"

    loaded = repo.load_draft(ORG, TID, storage=storage, keys=keys)
    assert loaded is not None
    assert loaded.tournament_id == TID
    assert loaded.palette == dna.palette
    assert loaded.status == "draft"


def test_save_approved_writes_canonical_key(storage, keys):
    key = repo.save_approved(_make_dna(status="approved"), ORG, storage=storage, keys=keys)
    assert key == "defendr-poster-ai/orgs/1/tournaments/ewc_2025/style-dna.json"


def test_promote_draft_to_approved(storage, keys):
    repo.save_draft(_make_dna(), ORG, storage=storage, keys=keys)

    approved, approved_key = repo.promote_draft_to_approved(
        ORG, TID, storage=storage, keys=keys
    )
    assert approved.status == "approved"
    assert approved.approved_at is not None
    assert approved_key.endswith("style-dna.json")
    assert storage.exists(approved_key)

    # Draft object should be gone.
    assert not storage.exists(keys.style_dna_draft(ORG, TID))


def test_promote_draft_raises_when_no_draft_exists(storage, keys):
    with pytest.raises(FileNotFoundError):
        repo.promote_draft_to_approved(ORG, "nonexistent", storage=storage, keys=keys)


def test_load_active_prefers_approved_over_draft(storage, keys):
    repo.save_draft(_make_dna(), ORG, storage=storage, keys=keys)
    repo.save_approved(_make_dna(status="approved"), ORG, storage=storage, keys=keys)

    located = repo.load_active(ORG, TID, storage=storage, keys=keys)
    assert located is not None
    assert located.status == "approved"
    assert located.key.endswith("style-dna.json")


def test_load_active_returns_draft_when_only_draft_exists(storage, keys):
    repo.save_draft(_make_dna(), ORG, storage=storage, keys=keys)
    located = repo.load_active(ORG, TID, storage=storage, keys=keys)
    assert located is not None
    assert located.status == "draft"
    assert located.key.endswith("style-dna.draft.json")


def test_load_active_returns_none_when_nothing_exists(storage, keys):
    assert repo.load_active(ORG, "nothing_here", storage=storage, keys=keys) is None


def test_save_draft_normalizes_status_to_draft(storage, keys):
    dna = _make_dna(status="approved")  # mismatched on purpose
    repo.save_draft(dna, ORG, storage=storage, keys=keys)
    loaded = repo.load_draft(ORG, TID, storage=storage, keys=keys)
    assert loaded is not None
    assert loaded.status == "draft"


def test_save_approved_sets_approved_at(storage, keys):
    repo.save_approved(_make_dna(status="draft"), ORG, storage=storage, keys=keys)
    loaded = repo.load_approved(ORG, TID, storage=storage, keys=keys)
    assert loaded is not None
    assert loaded.status == "approved"
    assert loaded.approved_at is not None


def test_dna_of_different_tournaments_are_isolated(storage, keys):
    repo.save_approved(
        _make_dna(tournament_id="ewc_2025", status="approved"), ORG, storage=storage, keys=keys
    )
    repo.save_approved(
        _make_dna(tournament_id="worlds_2025", status="approved"), ORG, storage=storage, keys=keys
    )
    assert repo.load_approved(ORG, "ewc_2025", storage=storage, keys=keys) is not None
    assert repo.load_approved(ORG, "worlds_2025", storage=storage, keys=keys) is not None
    assert repo.load_approved(ORG, "other", storage=storage, keys=keys) is None
