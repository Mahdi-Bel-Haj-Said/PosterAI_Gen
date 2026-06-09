"""
Pydantic input models.

Pragmatic schema: the `_meta` block is strictly typed (Literals) so typos in
game / poster_type / mode / output_format fail fast at the boundary. The rest
of the document is loosely typed — optional nested models for the common
fields, extras allowed — because the input shape varies per poster_type and
forcing a full discriminated union for every variant is more rigor than this
codebase needs today.

Use `PosterInput.model_validate(json_dict)` at the entry point. Internal
modules still consume the underlying dict via `.model_dump(by_alias=True)`
when the existing block builders expect dicts; over time those builders
should be migrated to consume the typed objects directly.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


Game = Literal["league_of_legends", "valorant"]
PosterType = Literal[
    "gameday",
    "game_results",
    "roster_reveal",
    "tournament_announcement",
    "tournament_banner",
]
Mode = Literal["fresh", "consistency", "refine"]
OutputFormat = Literal[
    "portrait_1080x1920",
    "square_1080x1080",
    "landscape_1920x1080",
]

# Visual-style presets surfaced in the input UI's "Visual style" step.
VibePreset = Literal[
    "cyberpunk",
    "cinematic",
    "dark_fantasy",
    "cosmic",
    "minimal",
    "fire_energy",
]
# Energy vocabulary — kept identical to the Style DNA energy enum so fresh-mode
# design choices and consistency-mode DNA speak the same language.
DesignEnergy = Literal["chill", "balanced", "intense", "explosive"]


class _Loose(BaseModel):
    """Base model that allows extra keys (for forward-compat with input docs)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Meta(_Loose):
    game: Game
    poster_type: PosterType
    mode: Mode = "fresh"
    output_format: OutputFormat = "portrait_1080x1920"


class Team(_Loose):
    name: Optional[str] = None
    short_name: Optional[str] = None
    logo_path: Optional[str] = None
    score: Optional[int] = None  # series score (game_results)


class Match(_Loose):
    team1: Optional[Team] = None
    team2: Optional[Team] = None
    date: Optional[str] = None
    time: Optional[str] = None
    timezone: Optional[str] = None
    format: Optional[str] = None
    maps: Optional[List[Any]] = None  # valorant per-map results (game_results)


class Tournament(_Loose):
    name: Optional[str] = None
    logo_path: Optional[str] = None
    phase: Optional[str] = None
    circuit: Optional[str] = None  # valorant


class Stream(_Loose):
    platform: Optional[str] = None
    url: Optional[str] = None


class PlayerFeature(_Loose):
    enabled: bool = False
    image_path: Optional[str] = None


class SponsorLogo(_Loose):
    path: str


class Sponsors(_Loose):
    enabled: bool = False
    logos: List[SponsorLogo] = Field(default_factory=list)


class Design(_Loose):
    vibe: Optional[VibePreset] = None
    primary_color: Optional[str] = None
    energy: Optional[DesignEnergy] = None


class PosterInput(_Loose):
    """Top-level input document."""

    meta: Meta = Field(alias="_meta")
    tournament: Optional[Tournament] = None
    match: Optional[Match] = None
    stream: Optional[Stream] = None
    player_feature: Optional[PlayerFeature] = None
    org: Optional[Any] = None
    sponsors: Optional[Sponsors] = None
    design: Optional[Design] = None

    # roster_reveal-specific (kept loose — full schema deferred)
    team: Optional[Any] = None
    roster: Optional[Any] = None

    # results-specific
    mvp: Optional[Any] = None

    # tournament_announcement / tournament_banner-specific
    event: Optional[Any] = None


def to_block_dict(poster_input: PosterInput) -> dict:
    """
    Render the typed input back into the dict shape that the existing prompt
    block builders consume. Uses `by_alias=True` so `_meta` is emitted with
    its underscore prefix.
    """
    return poster_input.model_dump(by_alias=True, exclude_none=False)


__all__ = [
    "PosterInput",
    "Meta",
    "Team",
    "Match",
    "Tournament",
    "Stream",
    "PlayerFeature",
    "Sponsors",
    "SponsorLogo",
    "Design",
    "to_block_dict",
    "Game",
    "PosterType",
    "Mode",
    "OutputFormat",
    "VibePreset",
    "DesignEnergy",
]
