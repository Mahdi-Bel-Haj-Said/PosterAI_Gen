"""
Thin Gemini REST client for caption generation.

We don't pull in the google-generativeai SDK — the surface we need is a
single :generateContent POST, and httpx (already a dependency for the
Postiz client) handles it in ~30 lines without an extra dep tree.

The free tier of `gemini-2.5-flash` is comfortable for captions: a single
call returns ~100 output tokens, well under the per-minute and per-day
quotas.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from esports_poster_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(RuntimeError):
    """Raised on Gemini network / 4xx / 5xx failures."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def generate_text(
    prompt: str,
    *,
    settings: Optional[Settings] = None,
    temperature: float = 0.85,
    max_output_tokens: int = 240,
    timeout_seconds: float = 20.0,
) -> str:
    """
    Call Gemini and return the plain-text response.

    Raises GeminiError if the key isn't configured or the API misbehaves.
    Returns the trimmed first candidate's text — captions are short and we
    never want multiple variants from a single call.
    """
    s = settings or get_settings()
    if not s.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is not set.")

    url = f"{_API_ROOT}/models/{s.gemini_caption_model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            # Gemini 2.5 Flash defaults to "thinking" mode, where the model
            # spends a chunk of its output token budget on reasoning tokens
            # the caller never sees. For short, structured output like a
            # caption that's all loss — captions came back truncated mid-
            # sentence ("...3-1 in the") because thinking ate the budget.
            # thinkingBudget=0 disables it entirely; the model goes straight
            # to producing the visible caption.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, params={"key": s.gemini_api_key}, json=body)
    except httpx.HTTPError as exc:
        raise GeminiError(f"Gemini request failed: {exc}") from exc

    if resp.status_code >= 400:
        preview = resp.text[:500] if resp.text else "<empty body>"
        raise GeminiError(
            f"Gemini {resp.status_code}: {preview}", status_code=resp.status_code
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise GeminiError("Gemini returned non-JSON body.") from exc

    candidates = data.get("candidates") or []
    if not candidates:
        # Common cause: safety-filter block. Surface the reason if Gemini gave one.
        block = data.get("promptFeedback", {}).get("blockReason")
        raise GeminiError(f"Gemini returned no candidates (blockReason={block}).")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text_chunks = [p.get("text", "") for p in parts if isinstance(p, dict)]
    text = "".join(text_chunks).strip()
    if not text:
        raise GeminiError("Gemini returned an empty caption.")
    return text


__all__ = ["GeminiError", "generate_text"]
