"""
Storage key builder.

The ONLY place object keys are formed. Every key the service writes is
namespaced under a single top-level prefix so the bucket can be shared with
Defendr without collisions.

Scheme:

    # org-level — brand asset library, reused across all the org's tournaments
    {prefix}/orgs/{org_id}/assets/team-logos/{asset_id}.{ext}
    {prefix}/orgs/{org_id}/assets/player-images/{asset_id}.{ext}
    {prefix}/orgs/{org_id}/assets/sponsor-logos/{asset_id}.{ext}
    {prefix}/orgs/{org_id}/assets/tournament-logos/{asset_id}.{ext}

    # tournament-level — each tournament has its own visual identity + posters
    {prefix}/orgs/{org_id}/tournaments/{tournament_id}/style-dna.json
    {prefix}/orgs/{org_id}/tournaments/{tournament_id}/style-dna.draft.json
    {prefix}/orgs/{org_id}/tournaments/{tournament_id}/posters/{poster_id}.{ext}

    # shared system data — not org-scoped
    {prefix}/system/backgrounds/{name}

`org_id` and `tournament_id` are opaque identifiers supplied by the caller
(static values today, real Defendr ids once the API ships).
"""

from __future__ import annotations

from enum import Enum
from typing import Union


class AssetType(str, Enum):
    """Asset kinds the pipeline reads, one folder each under assets/."""

    TEAM_LOGO = "team-logos"
    PLAYER_IMAGE = "player-images"
    SPONSOR_LOGO = "sponsor-logos"
    TOURNAMENT_LOGO = "tournament-logos"
    # User-uploaded backgrounds. Override the system pool when the input JSON
    # has `background.image_path` pointing at one of these.
    BACKGROUND = "backgrounds"


def _segment(value: Union[str, int], field: str) -> str:
    """
    Validate a single path segment.

    Rejects empty values and anything that could escape the key namespace
    (slashes, backslashes, parent refs). This matters because `org_id` and
    `tournament_id` will eventually arrive from an HTTP request.
    """
    s = str(value).strip()
    if not s:
        raise ValueError(f"{field} must not be empty.")
    if "/" in s or "\\" in s or s in {".", ".."}:
        raise ValueError(f"{field} contains an invalid path segment: {value!r}")
    return s


def _ext(ext: str) -> str:
    return ext.strip().lstrip(".").lower()


class StorageKeys:
    """Builds namespaced object keys. Construct once from settings."""

    def __init__(self, prefix: str = "defendr-poster-ai") -> None:
        self.prefix = prefix.strip().strip("/")
        if not self.prefix:
            raise ValueError("Storage key prefix must not be empty.")

    # ---------------------------------------------------------------- roots
    def _org_root(self, org_id: Union[str, int]) -> str:
        return f"{self.prefix}/orgs/{_segment(org_id, 'org_id')}"

    def _tournament_root(
        self, org_id: Union[str, int], tournament_id: Union[str, int]
    ) -> str:
        return (
            f"{self._org_root(org_id)}/tournaments/"
            f"{_segment(tournament_id, 'tournament_id')}"
        )

    # ---------------------------------------------------------------- assets (org-level)
    def asset(
        self,
        org_id: Union[str, int],
        asset_type: AssetType,
        asset_id: str,
        ext: str = "png",
    ) -> str:
        """Key for an uploaded asset (team/player/sponsor/tournament image)."""
        return (
            f"{self._org_root(org_id)}/assets/{asset_type.value}/"
            f"{_segment(asset_id, 'asset_id')}.{_ext(ext)}"
        )

    def assets_prefix(self, org_id: Union[str, int], asset_type: AssetType) -> str:
        """Listing prefix for one asset folder of an org."""
        return f"{self._org_root(org_id)}/assets/{asset_type.value}/"

    # ---------------------------------------------------------------- style DNA (tournament-level)
    def style_dna(
        self, org_id: Union[str, int], tournament_id: Union[str, int]
    ) -> str:
        """Key for a tournament's approved Style DNA."""
        return f"{self._tournament_root(org_id, tournament_id)}/style-dna.json"

    def style_dna_draft(
        self, org_id: Union[str, int], tournament_id: Union[str, int]
    ) -> str:
        """Key for a tournament's draft (not yet approved) Style DNA."""
        return f"{self._tournament_root(org_id, tournament_id)}/style-dna.draft.json"

    # ---------------------------------------------------------------- posters (tournament-level)
    def poster(
        self,
        org_id: Union[str, int],
        tournament_id: Union[str, int],
        poster_id: str,
        ext: str = "png",
    ) -> str:
        """Key for a generated poster within a tournament."""
        return (
            f"{self._tournament_root(org_id, tournament_id)}/posters/"
            f"{_segment(poster_id, 'poster_id')}.{_ext(ext)}"
        )

    def posters_prefix(
        self, org_id: Union[str, int], tournament_id: Union[str, int]
    ) -> str:
        """Listing prefix for one tournament's poster history."""
        return f"{self._tournament_root(org_id, tournament_id)}/posters/"

    def tournaments_prefix(self, org_id: Union[str, int]) -> str:
        """Listing prefix for all of an org's tournaments."""
        return f"{self._org_root(org_id)}/tournaments/"

    # ---------------------------------------------------------------- shared
    def background(self, name: str) -> str:
        """Key for a shared system background (not org-scoped)."""
        return f"{self.prefix}/system/backgrounds/{_segment(name, 'name')}"


__all__ = ["AssetType", "StorageKeys"]
