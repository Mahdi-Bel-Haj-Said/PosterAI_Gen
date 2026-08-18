"""
Small-model text LLM adapter for key-art prompt building.

Implements the `PromptLLM` seam used by `prompt/keyart_builder.py`, backed by the
SAME OpenAI key as the rest of the pipeline but a cheap small model
(`settings.openai_prompt_builder_model`, default `gpt-4o-mini`). Prompt work is
~$0.001/call, so this stays negligible next to image generation.

Text-only (no image), via the Responses API: `system` -> `instructions`,
`user` -> `input`. Transient errors use the same retry policy as the main client.
The key/client are created lazily, so a missing key raises only at call time —
`keyart_builder.build_prompt` catches that and falls back to the bank prompt, so
an unconfigured key simply degrades to the free `economy` tier.
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from esports_poster_ai.clients.openai_client import RETRYABLE_ERRORS
from esports_poster_ai.config import Settings, get_settings, require_openai_key

logger = logging.getLogger(__name__)


class OpenAIPromptLLM:
    """`PromptLLM` implementation on a cheap OpenAI text model."""

    def __init__(self, settings: Optional[Settings] = None, model: Optional[str] = None) -> None:
        self.settings: Settings = settings or get_settings()
        self.model: str = model or self.settings.openai_prompt_builder_model
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            key = require_openai_key(self.settings)  # raises if missing -> caught upstream
            self._client = OpenAI(api_key=key)
        return self._client

    def complete(self, *, system: str, user: str, max_output_tokens: int = 300) -> str:
        client = self._get_client()

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.settings.openai_max_retries),
            wait=wait_exponential(
                multiplier=self.settings.openai_initial_backoff_seconds,
                max=self.settings.openai_max_backoff_seconds,
            ),
            retry=retry_if_exception_type(RETRYABLE_ERRORS),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        def _do() -> str:
            resp = client.responses.create(
                model=self.model,
                instructions=system,
                input=user,
                max_output_tokens=max_output_tokens,
            )
            return (getattr(resp, "output_text", None) or "").strip()

        return _do()


__all__ = ["OpenAIPromptLLM"]
