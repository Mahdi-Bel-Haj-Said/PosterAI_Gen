"""
A `game_results` poster must carry a FINISHED series score.

`clampScore` in the wizard (and any integrator's own form) can only stop a score
being *impossible* — no team above the win target, no series longer than N games.
That still admits scores which are merely undecided: 2-0 or 2-2 in a Bo5 are
perfectly legal mid-series, but cannot be a final result. The pipeline would
happily render one, publishing an authoritative poster for a match that has not
been decided.

These cases pin the rule at the API boundary, where it protects every caller
rather than only the wizard.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from esports_poster_ai.domain.inputs import PosterInput


def _results_doc(fmt: str, score_a, score_b, poster_type: str = "game_results") -> dict:
    return {
        "_meta": {"game": "valorant", "poster_type": poster_type},
        "match": {
            "format": fmt,
            "team1": {"name": "Team A", "score": score_a},
            "team2": {"name": "Team B", "score": score_b},
        },
    }


# (format, score_a, score_b) — every way a series can legitimately end.
DECIDED = [
    ("bo1", 1, 0), ("bo1", 0, 1),
    ("bo3", 2, 0), ("bo3", 2, 1), ("bo3", 0, 2), ("bo3", 1, 2),
    ("bo5", 3, 0), ("bo5", 3, 1), ("bo5", 3, 2),
    ("bo5", 0, 3), ("bo5", 1, 3), ("bo5", 2, 3),
]

UNDECIDED_OR_IMPOSSIBLE = [
    ("bo5", 2, 0),   # the reported bug: not enough wins to take a Bo5
    ("bo5", 2, 2),   # the reported bug: a tie is not an outcome
    ("bo5", 0, 0),
    ("bo5", 1, 1),
    ("bo5", 3, 3),   # both at the target
    ("bo5", 4, 0),   # past the target
    ("bo3", 1, 0),
    ("bo3", 1, 1),
    ("bo3", 2, 2),
    ("bo3", 3, 0),   # a Bo3 ends at 2
    ("bo1", 0, 0),
    ("bo1", 1, 1),
    ("bo1", 2, 0),
]


@pytest.mark.parametrize("fmt,a,b", DECIDED)
def test_decided_series_is_accepted(fmt: str, a: int, b: int) -> None:
    poster = PosterInput.model_validate(_results_doc(fmt, a, b))
    assert poster.match is not None
    assert poster.match.team1 is not None and poster.match.team2 is not None
    assert (poster.match.team1.score, poster.match.team2.score) == (a, b)


@pytest.mark.parametrize("fmt,a,b", UNDECIDED_OR_IMPOSSIBLE)
def test_undecided_series_is_rejected(fmt: str, a: int, b: int) -> None:
    with pytest.raises(ValidationError):
        PosterInput.model_validate(_results_doc(fmt, a, b))


def test_negative_scores_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PosterInput.model_validate(_results_doc("bo5", -1, 3))


# --- the validator must stay silent everywhere it does not apply -------------
#
# It runs on every PosterInput, including ones built by the express endpoint and
# by integrators who send partial data. Firing outside `game_results` — or on a
# document that simply has not filled the scores in yet — would break callers
# that were never wrong.

def test_gameday_poster_may_carry_an_undecided_score() -> None:
    """A gameday poster is about an upcoming match; 2-0 is not its business."""
    PosterInput.model_validate(_results_doc("bo5", 2, 0, poster_type="gameday"))


def test_unknown_format_is_not_second_guessed() -> None:
    """Nothing to validate against, so accept rather than invent a rule."""
    PosterInput.model_validate(_results_doc("bo7", 2, 0))
    PosterInput.model_validate(_results_doc("", 2, 0))


def test_missing_scores_are_allowed() -> None:
    PosterInput.model_validate(
        {
            "_meta": {"game": "valorant", "poster_type": "game_results"},
            "match": {"format": "bo5", "team1": {"name": "A"}, "team2": {"name": "B"}},
        }
    )


def test_missing_match_block_is_allowed() -> None:
    PosterInput.model_validate(
        {"_meta": {"game": "valorant", "poster_type": "game_results"}}
    )
