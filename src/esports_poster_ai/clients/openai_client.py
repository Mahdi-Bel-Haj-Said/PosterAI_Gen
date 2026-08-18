"""
Thin OpenAI wrapper.

Owns: API key loading, retry policy, structured logging with run_id,
and translation of transient errors into a single retryable exception class.

All OpenAI calls in the pipeline go through this module — stages never
import `openai` directly.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import uuid
from typing import List, Optional, Tuple, Type, TypeVar

from openai import (
    APIConnectionError,
    APIError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from PIL import Image
from pydantic import BaseModel, ValidationError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from esports_poster_ai.config import Settings, get_settings, require_openai_key
from esports_poster_ai.errors import BackgroundRejectedError

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


# Shown to the user when the vision model returns nothing usable even after
# retries. The prior copy asserted "copyrighted content" as the cause, but the
# analyzer (gpt-4o) intermittently returns an empty / refusal-shaped response for
# perfectly clean images — so we lead with the far more likely explanation (a
# transient hiccup → just retry) and keep the copyright note as a secondary hint
# that only really applies to user uploads.
_BACKGROUND_REJECTED_MSG = (
    "We couldn't generate this poster — the image analyzer returned an empty "
    "response for the background, even after several retries. This is almost "
    "always a temporary hiccup with the analyzer, not a problem with your image, "
    "so please try again. If you uploaded your own background and it keeps "
    "failing, check that it has no recognizable characters, team logos, or "
    "copyrighted artwork baked in."
)

_REFUSAL_PREFIXES = (
    "i'm sorry", "i am sorry", "sorry,", "i can't", "i cannot", "i can not",
    "i'm unable", "i am unable", "i won't", "i will not", "unfortunately, i",
)
_REFUSAL_SNIPPETS = (
    "can't assist", "cannot assist", "can't help with", "cannot help with",
    "unable to assist", "unable to help", "can't provide", "cannot provide",
)


# The prompt-stage model is told to output ONLY the image prompt, but gpt-4o
# often wraps it in a markdown code fence and/or a label line ("```",
# "BACKGROUND ANALYSIS:", "Here is the prompt:"). That preamble then leaks into
# the gpt-image-2 prompt and dilutes it. Strip it so the image model gets clean
# scene text.
_LEADING_LABEL_RE = re.compile(
    r"^\s*(?:here(?:'s| is)\b[^\n]*|sure\b[^\n]*|(?:image[- ]?)?(?:generation )?prompt"
    r"|background analysis|revised prompt|final prompt)\s*:\s*\n+",
    re.IGNORECASE,
)


def _strip_preamble(text: str) -> str:
    """Remove wrapping ``` fences and a leading label line; keep the prompt body.

    Falls back to the original text if stripping would empty it (never returns "").
    """
    t = (text or "").strip()
    t = re.sub(r"^```[^\n`]*\n", "", t)          # opening fence line (```/```lang)
    t = re.sub(r"\n?```[ \t]*$", "", t).strip()  # closing fence
    t = _LEADING_LABEL_RE.sub("", t, count=1).strip()
    return t or (text or "").strip()


def _looks_like_refusal(text: str) -> bool:
    """Heuristic: does the model's reply read like a content refusal, not a prompt?

    A real image-generation prompt is long, descriptive scene text; a refusal is
    short and apologetic. We only inspect the opening so a legitimate prompt that
    merely contains the word "cannot" later on isn't misflagged.
    """
    t = (text or "").strip().lower()
    if not t:
        return True
    if t.startswith(_REFUSAL_PREFIXES):
        return True
    head = t[:200]
    return any(s in head for s in _REFUSAL_SNIPPETS)


# Errors we consider transient and worth retrying.
RETRYABLE_ERRORS = (APIConnectionError, RateLimitError, InternalServerError, APIError)


def new_run_id() -> str:
    """Generate a short run id for log correlation."""
    return uuid.uuid4().hex[:12]


def _sniff_image(data: bytes) -> Tuple[str, str]:
    """Detect (mime_type, extension) from an image's magic bytes."""
    if data[:8].startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    # Default: treat as PNG. OpenAI also content-sniffs server-side.
    return "image/png", "png"


def _encode_image_to_data_url(image_bytes: bytes) -> str:
    mime, _ext = _sniff_image(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _named_buffer(image_bytes: bytes, fallback_name: str) -> io.BytesIO:
    """Wrap bytes in a BytesIO with a `.name` so the OpenAI SDK can form the upload."""
    _mime, ext = _sniff_image(image_bytes)
    buf = io.BytesIO(image_bytes)
    buf.name = f"{fallback_name}.{ext}"
    return buf


class OpenAIClient:
    """
    Wrapper around the OpenAI SDK.

    Instantiate once per process (or per request). Stage code receives
    an instance and calls high-level methods like `generate_prompt()` or
    `generate_poster()`.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings: Settings = settings or get_settings()
        require_openai_key(self.settings)
        self._client = OpenAI(api_key=self.settings.openai_api_key)

    # ---------------------------------------------------------------- prompt
    def generate_prompt(
        self,
        *,
        background_image: bytes,
        assembled_prompt: str,
        instructions: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        model: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> str:
        """
        Send the assembled prompt + background image to the vision model and
        return the image-generation prompt text.

        `instructions` is an optional system-level steer (the Responses API
        `instructions` field) — used to pin the model's role and force faithful
        carry-through of the style directives.
        """
        run_id = run_id or new_run_id()
        model = model or self.settings.openai_prompt_model
        max_output_tokens = max_output_tokens or self.settings.stage2_max_output_tokens

        if not background_image:
            raise ValueError("background_image is empty.")

        logger.info(
            "prompt_stage.start",
            extra={"run_id": run_id, "model": model, "max_output_tokens": max_output_tokens},
        )

        # The vision model INTERMITTENTLY returns an empty or refusal-shaped
        # response for a perfectly clean background (a non-deterministic gpt-4o
        # hiccup — the same input succeeds on the next call). A single empty
        # response is therefore NOT evidence of a bad background, so we retry the
        # whole call a few times before giving up, instead of failing the poster
        # on the first blank. (This is separate from `_call_responses`'s own
        # retry, which only covers transient API/network errors.)
        attempts = max(1, self.settings.openai_max_retries)
        last_head = ""
        for attempt in range(1, attempts + 1):
            text = self._call_responses(
                run_id=run_id,
                model=model,
                max_output_tokens=max_output_tokens,
                assembled_prompt=assembled_prompt,
                image_bytes=background_image,
                instructions=instructions,
            )
            if text and not _looks_like_refusal(text):
                cleaned = _strip_preamble(text)
                logger.info(
                    "prompt_stage.done",
                    extra={"run_id": run_id, "chars": len(cleaned), "attempt": attempt},
                )
                return cleaned
            last_head = (text or "")[:120]
            logger.warning(
                "prompt_stage.empty_or_refusal",
                extra={
                    "run_id": run_id,
                    "attempt": attempt,
                    "attempts": attempts,
                    "empty": not text,
                    "head": last_head,
                },
            )

        # Exhausted retries — surface an honest, actionable error (leads with
        # "transient, try again"; copyright is only a secondary hint for uploads).
        logger.warning(
            "prompt_stage.background_rejected",
            extra={"run_id": run_id, "attempts": attempts, "last_head": last_head},
        )
        raise BackgroundRejectedError(_BACKGROUND_REJECTED_MSG)

    # ---------------------------------------------------------------- image
    def generate_poster(
        self,
        *,
        background_image: bytes,
        input_images: List[bytes],
        prompt: str,
        size: str,
        quality: str = "medium",
        model: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Image.Image:
        """
        Call the image-generation model in editing mode with the background
        and the reference images (logos, player photos) as inputs. Returns a
        PIL Image (caller persists it).
        """
        run_id = run_id or new_run_id()
        model = model or self.settings.openai_image_model

        if not background_image:
            raise ValueError("background_image is empty.")

        logger.info(
            "image_stage.start",
            extra={
                "run_id": run_id,
                "model": model,
                "size": size,
                "quality": quality,
                "input_image_count": len(input_images),
            },
        )

        b64 = self._call_images_edit(
            run_id=run_id,
            model=model,
            background_image=background_image,
            input_images=input_images,
            prompt=prompt,
            size=size,
            quality=quality,
        )

        poster_bytes = base64.b64decode(b64)
        poster_image = Image.open(io.BytesIO(poster_bytes))
        logger.info("image_stage.done", extra={"run_id": run_id, "bytes": len(poster_bytes)})
        return poster_image

    # ---------------------------------------------------------------- structured output
    def generate_structured(
        self,
        *,
        image: bytes,
        instructions: str,
        schema: Type[T],
        max_output_tokens: int = 1500,
        model: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> T:
        """
        Vision call returning a Pydantic instance.

        We instruct the model to emit JSON only, parse the response, and
        validate against `schema`. On parse/validation failure we retry once
        with a stronger reminder before giving up. Transport errors are
        handled by the existing retry policy.
        """
        run_id = run_id or new_run_id()
        model = model or self.settings.openai_prompt_model

        if not image:
            raise ValueError("image is empty.")

        full_prompt = _wrap_with_json_schema(instructions, schema)

        logger.info(
            "structured.start",
            extra={"run_id": run_id, "model": model, "schema": schema.__name__},
        )

        # Attempt 1.
        text = self._call_responses(
            run_id=run_id,
            model=model,
            max_output_tokens=max_output_tokens,
            assembled_prompt=full_prompt,
            image_bytes=image,
        )
        parsed = _try_parse(text, schema)
        if parsed is not None:
            logger.info("structured.done", extra={"run_id": run_id, "attempt": 1})
            return parsed

        # Attempt 2 — explicit reminder.
        logger.warning(
            "structured.retry",
            extra={"run_id": run_id, "reason": "first attempt failed to parse"},
        )
        reminder = (
            "Your previous response did not parse as JSON matching the required "
            "schema. Return ONLY a single valid JSON object, no markdown fences, "
            "no preamble, no commentary.\n\n" + full_prompt
        )
        text = self._call_responses(
            run_id=run_id,
            model=model,
            max_output_tokens=max_output_tokens,
            assembled_prompt=reminder,
            image_bytes=image,
        )
        parsed = _try_parse(text, schema)
        if parsed is not None:
            logger.info("structured.done", extra={"run_id": run_id, "attempt": 2})
            return parsed

        raise RuntimeError(
            f"[{run_id}] Structured output could not be parsed after 2 attempts. "
            f"Last raw text: {text[:400]!r}"
        )

    # ---------------------------------------------------------------- internals
    def _retry_policy(self):
        s = self.settings
        return retry(
            reraise=True,
            stop=stop_after_attempt(s.openai_max_retries),
            wait=wait_exponential(
                multiplier=s.openai_initial_backoff_seconds,
                max=s.openai_max_backoff_seconds,
            ),
            retry=retry_if_exception_type(RETRYABLE_ERRORS),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )

    def _call_responses(
        self,
        *,
        run_id: str,
        model: str,
        max_output_tokens: int,
        assembled_prompt: str,
        image_bytes: bytes,
        instructions: Optional[str] = None,
    ) -> str:
        @self._retry_policy()
        def _do() -> str:
            kwargs = {
                "model": model,
                "max_output_tokens": max_output_tokens,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": assembled_prompt},
                            {
                                "type": "input_image",
                                "image_url": _encode_image_to_data_url(image_bytes),
                            },
                        ],
                    }
                ],
            }
            if instructions:
                kwargs["instructions"] = instructions
            resp = self._client.responses.create(**kwargs)
            return (getattr(resp, "output_text", None) or "").strip()

        try:
            return _do()
        except RETRYABLE_ERRORS as e:
            logger.error("prompt_stage.failed", extra={"run_id": run_id, "error": str(e)})
            raise

    def _call_images_edit(
        self,
        *,
        run_id: str,
        model: str,
        background_image: bytes,
        input_images: List[bytes],
        prompt: str,
        size: str,
        quality: str,
    ) -> str:
        @self._retry_policy()
        def _do() -> str:
            image_inputs = [_named_buffer(background_image, "background")]
            for i, ref_image in enumerate(input_images):
                image_inputs.append(_named_buffer(ref_image, f"reference_{i}"))

            response = self._client.images.edit(
                model=model,
                image=image_inputs,
                prompt=prompt,
                quality=quality,
                size=size,
            )
            return response.data[0].b64_json

        try:
            return _do()
        except RETRYABLE_ERRORS as e:
            logger.error("image_stage.failed", extra={"run_id": run_id, "error": str(e)})
            raise


def estimate_prompt_call_upper_bound_usd(
    *, max_output_tokens: int, assumed_input_tokens: int = 8000
) -> float:
    """
    Conservative per-call cost upper bound for the prompt stage.

    Pricing is approximate and should be updated if OpenAI pricing changes.
    """
    input_per_1m = 2.50
    output_per_1m = 10.00
    return (assumed_input_tokens / 1_000_000) * input_per_1m + (
        max_output_tokens / 1_000_000
    ) * output_per_1m


# ----------------------------------------------------------------------------
# JSON / structured-output helpers (free functions so they can be unit-tested
# without spinning up an OpenAI client).
# ----------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    """Remove leading/trailing ```json fences the model sometimes adds."""
    return _JSON_FENCE_RE.sub("", text).strip()


def _extract_first_json_object(text: str) -> Optional[str]:
    """
    Find the first balanced top-level JSON object in `text`.

    Returns the substring including the enclosing braces, or None if no
    balanced object is found. Tolerates leading prose or trailing commentary.
    """
    depth = 0
    start: Optional[int] = None
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    return text[start : i + 1]

    return None


def _try_parse(text: str, schema: Type[T]) -> Optional[T]:
    """Try to extract + parse + validate JSON from raw model text."""
    if not text:
        return None
    candidate = _strip_code_fences(text)
    obj_str = _extract_first_json_object(candidate) or candidate
    try:
        data = json.loads(obj_str)
    except json.JSONDecodeError:
        return None
    try:
        return schema.model_validate(data)
    except ValidationError:
        return None


def _wrap_with_json_schema(instructions: str, schema: Type[BaseModel]) -> str:
    """Append a JSON-schema reminder so the model knows the exact shape we want."""
    json_schema = json.dumps(schema.model_json_schema(), indent=2)
    return (
        f"{instructions}\n\n"
        f"Return a single JSON object matching this schema:\n\n"
        f"```json\n{json_schema}\n```\n\n"
        f"Return ONLY the JSON object — no preamble, no commentary, no markdown fences."
    )


__all__ = [
    "OpenAIClient",
    "estimate_prompt_call_upper_bound_usd",
    "new_run_id",
    "RETRYABLE_ERRORS",
    # exported for tests
    "_strip_code_fences",
    "_extract_first_json_object",
    "_try_parse",
]
