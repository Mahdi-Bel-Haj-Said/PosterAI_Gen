"""Tests for stages/background_select + background_judge (no network)."""

from __future__ import annotations

from esports_poster_ai.prompt.keyart import build_keyart_prompt
from esports_poster_ai.stages.background_judge import BackgroundScore, OpenAIBackgroundJudge
from esports_poster_ai.stages.background_select import (
    BackgroundGenerator,
    BackgroundJudge,
    generate_best_background,
)


def _prompt():
    return build_keyart_prompt(
        {"_meta": {"game": "league_of_legends"}, "design": {"vibe": "dark_fantasy", "energy": "intense"}},
        seed=1,
    )


class _FakeGen:
    def __init__(self):
        self.seeds = []

    def generate(self, prompt, *, seed):
        self.seeds.append(seed)
        return f"img-{seed}".encode()


class _FakeJudge:
    """Returns scores from a fixed list, in call order."""

    def __init__(self, scores):
        self.scores = list(scores)
        self.i = 0

    def score(self, image, *, prompt):
        s = self.scores[self.i % len(self.scores)]
        self.i += 1
        return s


def test_protocols_are_satisfied():
    assert isinstance(_FakeGen(), BackgroundGenerator)
    assert isinstance(_FakeJudge([1.0]), BackgroundJudge)


def test_best_of_2_picks_higher_score():
    gen, judge = _FakeGen(), _FakeJudge([0.3, 0.8])
    r = generate_best_background(_prompt(), generator=gen, judge=judge, n=2, seed=42)
    assert r.score == 0.8
    assert r.n_generated == 2 and r.attempts == 1
    # winner image corresponds to the 2nd generated seed
    assert r.image == f"img-{gen.seeds[1]}".encode() and r.seed == gen.seeds[1]


def test_no_judge_generates_single():
    gen = _FakeGen()
    r = generate_best_background(_prompt(), generator=gen, judge=None, seed=42)
    assert r.score is None and r.n_generated == 1 and r.attempts == 1
    assert len(gen.seeds) == 1


def test_retry_when_below_min_score():
    gen = _FakeGen()
    # batch1 best = 0.5 (< 0.9) -> retry; batch2 has 0.95 -> stop
    judge = _FakeJudge([0.3, 0.5, 0.95, 0.4])
    r = generate_best_background(
        _prompt(), generator=gen, judge=judge, n=2, retries=1, min_score=0.9, seed=42
    )
    assert r.score == 0.95
    assert r.n_generated == 4 and r.attempts == 2


def test_retry_stops_after_budget_even_if_below_threshold():
    gen = _FakeGen()
    judge = _FakeJudge([0.1, 0.2, 0.3, 0.4])  # never reaches 0.9
    r = generate_best_background(
        _prompt(), generator=gen, judge=judge, n=2, retries=1, min_score=0.9, seed=42
    )
    assert r.attempts == 2 and r.n_generated == 4
    assert r.score == 0.4  # best seen, returned anyway


def test_deterministic_with_seed():
    a = generate_best_background(_prompt(), generator=_FakeGen(), judge=_FakeJudge([0.3, 0.8]), n=2, seed=7)
    b = generate_best_background(_prompt(), generator=_FakeGen(), judge=_FakeJudge([0.3, 0.8]), n=2, seed=7)
    assert a.seed == b.seed and a.image == b.image


# --- judge -----------------------------------------------------------------
class _FakeOAClient:
    def __init__(self, score: BackgroundScore):
        self._score = score
        self.last = None

    def generate_structured(self, *, image, instructions, schema, **kw):
        self.last = (image, instructions)
        return self._score


def test_judge_returns_overall_when_text_free():
    client = _FakeOAClient(BackgroundScore(text_free=True, style_fit=8, composition=7, overall=8.5))
    judge = OpenAIBackgroundJudge(client=client)
    assert judge.score(b"img", prompt=_prompt()) == 8.5
    # style ends up in the rubric
    assert "dark_fantasy, intense" in client.last[1]


def test_judge_penalizes_text():
    client = _FakeOAClient(BackgroundScore(text_free=False, style_fit=9, composition=9, overall=9))
    judge = OpenAIBackgroundJudge(client=client)
    assert judge.score(b"img", prompt=_prompt()) == 9 * 0.2  # heavy penalty
