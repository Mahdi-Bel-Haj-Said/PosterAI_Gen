"""Tests for storage.keys — the object key builder."""

from __future__ import annotations

import pytest

from esports_poster_ai.storage.keys import AssetType, StorageKeys


def test_asset_keys_are_org_level():
    k = StorageKeys(prefix="defendr-poster-ai")
    assert k.asset(1, AssetType.TEAM_LOGO, "fnc") == (
        "defendr-poster-ai/orgs/1/assets/team-logos/fnc.png"
    )
    assert k.asset(1, AssetType.PLAYER_IMAGE, "faker", ext="webp") == (
        "defendr-poster-ai/orgs/1/assets/player-images/faker.webp"
    )
    assert k.asset(2, AssetType.SPONSOR_LOGO, "redbull") == (
        "defendr-poster-ai/orgs/2/assets/sponsor-logos/redbull.png"
    )
    assert k.asset(2, AssetType.TOURNAMENT_LOGO, "ewc") == (
        "defendr-poster-ai/orgs/2/assets/tournament-logos/ewc.png"
    )


def test_style_dna_keys_are_tournament_level():
    k = StorageKeys(prefix="defendr-poster-ai")
    assert k.style_dna(7, "ewc_2025") == (
        "defendr-poster-ai/orgs/7/tournaments/ewc_2025/style-dna.json"
    )
    assert k.style_dna_draft(7, "ewc_2025") == (
        "defendr-poster-ai/orgs/7/tournaments/ewc_2025/style-dna.draft.json"
    )


def test_poster_keys_are_tournament_level():
    k = StorageKeys(prefix="defendr-poster-ai")
    assert k.poster(7, "ewc_2025", "abc123") == (
        "defendr-poster-ai/orgs/7/tournaments/ewc_2025/posters/abc123.png"
    )


def test_listing_prefixes():
    k = StorageKeys(prefix="defendr-poster-ai")
    assert k.posters_prefix(9, "worlds") == (
        "defendr-poster-ai/orgs/9/tournaments/worlds/posters/"
    )
    assert k.tournaments_prefix(9) == "defendr-poster-ai/orgs/9/tournaments/"
    assert k.assets_prefix(9, AssetType.TEAM_LOGO) == (
        "defendr-poster-ai/orgs/9/assets/team-logos/"
    )


def test_background_key_is_shared():
    k = StorageKeys(prefix="defendr-poster-ai")
    assert k.background("3.jpg") == "defendr-poster-ai/system/backgrounds/3.jpg"


def test_ids_accept_int_and_str():
    k = StorageKeys()
    assert k.poster(1, 42, "p").startswith(
        "defendr-poster-ai/orgs/1/tournaments/42/"
    )
    assert k.poster("org-xyz", "t-abc", "p").startswith(
        "defendr-poster-ai/orgs/org-xyz/tournaments/t-abc/"
    )


def test_ext_normalized():
    k = StorageKeys()
    assert k.asset(1, AssetType.TEAM_LOGO, "fnc", ext=".PNG").endswith("fnc.png")
    assert k.poster(1, "t", "p", ext="JPG").endswith("p.jpg")


def test_prefix_must_not_be_empty():
    with pytest.raises(ValueError):
        StorageKeys(prefix="   ")


@pytest.mark.parametrize("bad", ["", "  ", "a/b", "a\\b", "..", "."])
def test_rejects_unsafe_org_id(bad):
    k = StorageKeys()
    with pytest.raises(ValueError):
        k.poster(bad, "t", "p")


@pytest.mark.parametrize("bad", ["", "  ", "a/b", "a\\b", "..", "."])
def test_rejects_unsafe_tournament_id(bad):
    k = StorageKeys()
    with pytest.raises(ValueError):
        k.poster(1, bad, "p")
    with pytest.raises(ValueError):
        k.style_dna(1, bad)


def test_default_prefix():
    assert StorageKeys().prefix == "defendr-poster-ai"
