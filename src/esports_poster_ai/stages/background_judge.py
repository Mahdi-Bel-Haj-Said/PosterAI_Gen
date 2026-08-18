"""
GPT-4o Vision judge for generated backgrounds — the concrete `BackgroundJudge`.

Scores a candidate background on style-fit, composition (overlay-friendliness),
and text-free-ness, then returns a single float the selection loop maximizes.
Text is folded into the rubric (rather than a separate OCR pass): an image with
readable text/logos is heavily penalized, so the loop naturally picks the clean
one — cheap insurance since the base Qwen-Image model *can* render text even
though the LoRA never trained on any.

Uses the existing `OpenAIClient.generate_structured` vision call — no new
infrastructure. The client is injectable for testing (no network).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from esports_poster_ai.clients.openai_client import OpenAIClient
from esports_poster_ai.config import Settings
from esports_poster_ai.prompt.keyart import KeyartPrompt


class BackgroundScore(BaseModel):
    """Structured judge output for one background."""

    text_free: bool = Field(
        description="True if the image contains NO readable text, letters, numbers, or logos."
    )
    style_fit: float = Field(ge=0, le=10, description="Match to the requested vibe/energy and LoL key-art look.")
    composition: float = Field(ge=0, le=10, description="Clean, striking, overlay-friendly background.")
    overall: float = Field(ge=0, le=10, description="Overall quality as a poster background.")


_RUBRIC = """\
You are judging a generated esports KEY-ART BACKGROUND for a League of Legends
poster. No text or logos are composited yet — the background should be pure
environment/atmosphere.

Requested style: {style}

Score it (0-10 each):
- style_fit: does it match the requested vibe/energy and look like painterly,
  cinematic LoL key art?
- composition: is it a clean, striking background with room for overlays (not
  cluttered edge to edge, no distracting central clutter)?
- overall: overall quality as a poster background.
And judge:
- text_free: does it contain ANY readable text, letters, numbers, or logos?
  Return true ONLY if it is completely free of text/logos.

Return the scores."""

# Multiplier applied to `overall` when the image is NOT text-free — pushes any
# text-containing candidate below a clean one without a separate OCR gate.
_TEXT_PENALTY = 0.2


class OpenAIBackgroundJudge:
    """`BackgroundJudge` backed by GPT-4o Vision structured output."""

    def __init__(
        self,
        client: Optional[OpenAIClient] = None,
        *,
        settings: Optional[Settings] = None,
    ) -> None:
        self._client = client or OpenAIClient(settings)

    def score(self, image: bytes, *, prompt: KeyartPrompt) -> float:
        style = f"{prompt.vibe}, {prompt.energy}"
        result = self._client.generate_structured(
            image=image,
            instructions=_RUBRIC.format(style=style),
            schema=BackgroundScore,
            max_output_tokens=300,
        )
        return float(result.overall if result.text_free else result.overall * _TEXT_PENALTY)


__all__ = ["OpenAIBackgroundJudge", "BackgroundScore"]
