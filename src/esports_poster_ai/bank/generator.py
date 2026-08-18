"""
BankGenerator — turn a combo into background image bytes.

For each image it:
1. asks the key-art prompt builder (premium tier: LLM + RAG, degrading safely to
   the deterministic bank sampler) for a fresh, unique, environment-focused
   caption for the combo — a new caption seed each call, so the images in a
   combo differ; and
2. renders it on the RunPod Serverless endpoint at 1024x1024, `guidance=5`,
   30 steps, with a **varied diffusion seed** per image.

Upload is done by the caller (`BankStore`) — option (B), the external
orchestrator uploads. The endpoint today returns one base64 PNG per call
(~10s warm), so we loop one image per call; that keeps us far under the 600s
endpoint execution timeout and makes the ~40-images-per-request chunking
constraint moot. If a future worker renders many images per call and writes
straight to R2 (option A), only `generate_one` / the seam below changes.

Both the LLM and the model-call generator are dependency-injected, so this is
unit-testable with no network.
"""

from __future__ import annotations

import logging
import random
from dataclasses import replace
from typing import Optional

from esports_poster_ai.bank.combos import Combo
from esports_poster_ai.config import Settings, get_settings
from esports_poster_ai.prompt.keyart import KeyartPrompt
from esports_poster_ai.prompt.keyart_builder import (
    CaptionStore,
    PromptLLM,
    build_prompt,
    load_caption_store,
)
from esports_poster_ai.stages.background_select import BackgroundGenerator

logger = logging.getLogger(__name__)


class BankGenerator:
    """Generate ready-to-serve bank backgrounds for a combo."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        generator: Optional[BackgroundGenerator] = None,
        llm: Optional[PromptLLM] = None,
        store: Optional[CaptionStore] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._generator = generator or self._default_generator()
        self._llm = llm if llm is not None else self._default_llm()
        self._store = store if store is not None else load_caption_store(self._settings)

    def _default_generator(self) -> BackgroundGenerator:
        from esports_poster_ai.clients.runpod_client import RunpodBackgroundGenerator

        # A cold endpoint loads the 20B model before the first image (~6 min),
        # then serves ~10s/image warm. The poll deadline must comfortably clear
        # that cold start or the first image of a batch would spuriously time out;
        # 15 min gives generous headroom. Batching all combos into one refill means
        # only that first image pays the cold start — the rest are warm.
        return RunpodBackgroundGenerator(
            self._settings,
            steps=self._settings.bg_bank_steps,
            guidance=self._settings.bg_bank_guidance,
            poll_interval_s=5.0,
            timeout_s=900.0,
        )

    def _default_llm(self) -> Optional[PromptLLM]:
        # Only wire the LLM when a key is configured; otherwise premium/balanced
        # tiers degrade to the in-distribution bank sampler (still valid prompts).
        if not self._settings.openai_api_key:
            return None
        from esports_poster_ai.clients.prompt_llm import OpenAIPromptLLM

        return OpenAIPromptLLM(self._settings)

    # ------------------------------------------------------------------ API
    def build_prompt_for(self, combo: Combo, *, seed: Optional[int] = None) -> KeyartPrompt:
        """A unique key-art prompt for the combo, sized to the bank's square canvas."""
        kp = build_prompt(
            combo.input_data(),
            tier="premium",
            seed=seed,
            llm=self._llm,
            store=self._store,
        )
        size = self._settings.bg_bank_image_size
        return replace(kp, width=size, height=size)

    def generate_one(self, combo: Combo) -> bytes:
        """Render one background for the combo (fresh caption + fresh diffusion seed)."""
        prompt = self.build_prompt_for(combo)  # seed=None → unique caption
        diffusion_seed = random.randrange(2**31)  # varied per image
        logger.info(
            "bank.generate", extra={"combo": combo.slug, "seed": diffusion_seed}
        )
        return self._generator.generate(prompt, seed=diffusion_seed)


__all__ = ["BankGenerator"]
