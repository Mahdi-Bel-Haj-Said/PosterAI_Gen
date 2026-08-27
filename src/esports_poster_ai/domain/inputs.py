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

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
# Image-model render quality. Drives the gpt-image-2 `quality` param and the
# per-poster cost (low is cheapest, high is sharpest + most expensive).
Quality = Literal["low", "medium", "high"]

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
    quality: Quality = "medium"


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
    # "dominant" → force primary_color across the poster (default).
    # "auto"     → derive the palette from the background image instead.
    color_mode: Optional[str] = None


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

    @model_validator(mode="after")
    def _series_score_must_be_decided(self) -> "PosterInput":
        """
        A results poster states an outcome, so its score must be a FINISHED
        series: exactly one team on the win target, the other below it.

        Scores like 2-0 or 2-2 in a Bo5 are legal mid-series but cannot be a
        final result, and the pipeline would render them as one — an authoritative
        poster announcing a match that has not been decided. Validated here rather
        than only in the wizard so an integrator's own frontend cannot post one.

        Only enforced when there is something to check: results posters that
        actually carry both scores and a recognised format.
        """
        if self.meta.poster_type != "game_results" or self.match is None:
            return self

        fmt = (self.match.format or "").strip().lower()
        target = _SERIES_WIN_TARGET.get(fmt)
        if target is None:
            return self  # unknown/blank format — nothing to validate against

        t1, t2 = self.match.team1, self.match.team2
        if t1 is None or t2 is None or t1.score is None or t2.score is None:
            return self

        a, b = t1.score, t2.score
        if a < 0 or b < 0:
            raise ValueError("Series scores cannot be negative.")

        hi, lo = max(a, b), min(a, b)
        label = fmt.upper()

        if hi != target or lo >= target:
            raise ValueError(
                f"{a}-{b} is not a finished {label}: the winner must reach "
                f"exactly {target} and the loser stay below it."
            )
        if a + b > _SERIES_MAX_GAMES[fmt]:
            raise ValueError(
                f"A {label} runs at most {_SERIES_MAX_GAMES[fmt]} games, "
                f"but {a}-{b} totals {a + b}."
            )
        return self




# Games a team must win to take a best-of-N series, and the most games it can
# run to. Bo1 -> 1 of 1, Bo3 -> 2 of 3, Bo5 -> 3 of 5.
_SERIES_WIN_TARGET = {"bo1": 1, "bo3": 2, "bo5": 3}
_SERIES_MAX_GAMES = {"bo1": 1, "bo3": 3, "bo5": 5}


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
    "Quality",
    "VibePreset",
    "DesignEnergy",
]
