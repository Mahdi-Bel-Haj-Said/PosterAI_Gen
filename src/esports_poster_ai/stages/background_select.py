"""
Best-of-N background selection.

Given a resolved `KeyartPrompt`, generate N candidate backgrounds (each with its
own diffusion seed), score them with a judge, and return the winner. Optionally
retry a batch if the best candidate is below a quality threshold.

This is the quality backstop of the background path: variety comes from the
prompt builder, but this loop is what guarantees the *served* background is the
best of a few — catching the occasional weak composition (and, via the judge's
rubric, any stray text — see `background_judge.py`).

Seams (dependency-injected, provider-agnostic, no network in tests):
- `BackgroundGenerator.generate(prompt, seed) -> bytes` — the model call. Wired to
  RunPod Serverless later (in `_generate_with_runpod`); a persistent pod is NOT
  used for serving (per-second serverless billing).
- `BackgroundJudge.score(image, prompt) -> float` — higher is better. See
  `OpenAIBackgroundJudge` for the concrete GPT-4o Vision implementation.

If no judge is supplied, a single image is generated and returned (economy path).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Protocol, runtime_checkable

from esports_poster_ai.prompt.keyart import KeyartPrompt


@runtime_checkable
class BackgroundGenerator(Protocol):
    """Generate one background image (bytes) for a prompt at a given diffusion seed."""

    def generate(self, prompt: KeyartPrompt, *, seed: int) -> bytes: ...


@runtime_checkable
class BackgroundJudge(Protocol):
    """Score a candidate background — higher is better."""

    def score(self, image: bytes, *, prompt: KeyartPrompt) -> float: ...


@dataclass(frozen=True)
class BackgroundResult:
    """The winning background + provenance (for reproducibility / caching)."""

    image: bytes
    seed: int  # the diffusion seed that produced the winner
    score: Optional[float]  # None when generated without a judge
    n_generated: int  # total candidates generated across all attempts
    attempts: int  # how many batches were run (1 + retries used)


def generate_best_background(
    prompt: KeyartPrompt,
    *,
    generator: BackgroundGenerator,
    judge: Optional[BackgroundJudge] = None,
    n: int = 2,
    retries: int = 1,
    min_score: Optional[float] = None,
    seed: Optional[int] = None,
) -> BackgroundResult:
    """
    Generate `n` candidates, judge them, and return the best.

    - `n`: candidates per batch (default 2 — the best value/cost sweet spot).
    - `retries`: extra batches allowed if the best candidate is below `min_score`.
    - `min_score`: retry threshold; None = always keep the best of the first batch.
    - `seed`: seeds the *diffusion seed* sequence for reproducibility. None →
      fresh random seeds (so two users never collide). The winner's `seed` is
      returned, so any served background can be regenerated exactly.

    Without a `judge`, generates a single image (no selection) and returns it.
    """
    rng = random.Random(seed)

    if judge is None:
        s = rng.randrange(2**31)
        return BackgroundResult(
            image=generator.generate(prompt, seed=s),
            seed=s,
            score=None,
            n_generated=1,
            attempts=1,
        )

    best_score: Optional[float] = None
    best_image: Optional[bytes] = None
    best_seed: int = 0
    total = 0
    attempts = 0

    for _ in range(max(1, retries + 1)):
        attempts += 1
        for _ in range(max(1, n)):
            s = rng.randrange(2**31)
            image = generator.generate(prompt, seed=s)
            total += 1
            sc = judge.score(image, prompt=prompt)
            if best_score is None or sc > best_score:
                best_score, best_image, best_seed = sc, image, s
        if min_score is None or best_score >= min_score:
            break

    assert best_image is not None  # at least one candidate always generated
    return BackgroundResult(
        image=best_image,
        seed=best_seed,
        score=best_score,
        n_generated=total,
        attempts=attempts,
    )


__all__ = [
    "BackgroundGenerator",
    "BackgroundJudge",
    "BackgroundResult",
    "generate_best_background",
]
