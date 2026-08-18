"""
The prompt (vision) stage must RETRY an empty / refusal-shaped response instead
of instantly failing the poster.

gpt-4o intermittently returns an empty or apologetic reply for a perfectly clean
background — the same input succeeds on the next call. Before this, one blank
response raised BackgroundRejectedError ("...copyrighted content...") and killed
the poster. These tests pin the retry-until-success behavior (no network — the
low-level `_call_responses` is stubbed).
"""

from __future__ import annotations

import pytest

from esports_poster_ai.clients.openai_client import OpenAIClient
from esports_poster_ai.config import Settings
from esports_poster_ai.errors import BackgroundRejectedError


def _client(**overrides) -> OpenAIClient:
    return OpenAIClient(Settings(openai_api_key="test-key", **overrides))


def test_retries_empty_then_succeeds():
    c = _client(openai_max_retries=3)
    calls = {"n": 0}

    def fake(**_kw):
        calls["n"] += 1
        return "" if calls["n"] < 2 else "A sweeping cosmic vista of drifting nebulae"

    c._call_responses = fake
    out = c.generate_prompt(background_image=b"img", assembled_prompt="brief")
    assert out.startswith("A sweeping")
    assert calls["n"] == 2  # first blank, second good


def test_retries_refusal_shaped_then_succeeds():
    c = _client(openai_max_retries=3)
    seq = iter(["I'm sorry, I can't help with that.", "A dramatic esports arena at dusk"])
    c._call_responses = lambda **_kw: next(seq)
    out = c.generate_prompt(background_image=b"img", assembled_prompt="brief")
    assert out.startswith("A dramatic")


def test_raises_after_exhausting_retries():
    c = _client(openai_max_retries=2)
    calls = {"n": 0}

    def fake(**_kw):
        calls["n"] += 1
        return ""  # always blank

    c._call_responses = fake
    with pytest.raises(BackgroundRejectedError):
        c.generate_prompt(background_image=b"img", assembled_prompt="brief")
    assert calls["n"] == 2  # exactly openai_max_retries attempts, then give up


def test_message_no_longer_asserts_copyright_as_primary_cause():
    # The user-facing copy should lead with "try again", not blame copyright.
    from esports_poster_ai.clients.openai_client import _BACKGROUND_REJECTED_MSG

    assert "try again" in _BACKGROUND_REJECTED_MSG.lower()
    assert not _BACKGROUND_REJECTED_MSG.lower().startswith("we couldn't use this background")


# --- preamble stripping: gpt-4o wraps the prompt in fences / labels ----------
def test_strip_removes_fence_and_analysis_label():
    from esports_poster_ai.clients.openai_client import _strip_preamble

    raw = "```\nBACKGROUND ANALYSIS:\nA cosmic vista of nebulae and stars.\n```"
    assert _strip_preamble(raw) == "A cosmic vista of nebulae and stars."


def test_strip_handles_unterminated_fence():
    from esports_poster_ai.clients.openai_client import _strip_preamble

    assert _strip_preamble("```\nA dark forest, moody lighting.") == "A dark forest, moody lighting."


def test_strip_removes_here_is_the_prompt_label():
    from esports_poster_ai.clients.openai_client import _strip_preamble

    assert _strip_preamble("Here is the image prompt:\nA neon city at night.") == "A neon city at night."


def test_strip_leaves_a_clean_prompt_untouched():
    from esports_poster_ai.clients.openai_client import _strip_preamble

    clean = "A sweeping desert under a golden sun, distant ruins."
    assert _strip_preamble(clean) == clean


def test_strip_never_returns_empty():
    from esports_poster_ai.clients.openai_client import _strip_preamble

    assert _strip_preamble("```\n```")  # falls back to the original, non-empty


def test_generate_prompt_returns_cleaned_text():
    c = _client(openai_max_retries=2)
    c._call_responses = lambda **_kw: "```\nBACKGROUND ANALYSIS:\nA stormy coastline at dusk.\n```"
    assert c.generate_prompt(background_image=b"img", assembled_prompt="brief") == "A stormy coastline at dusk."
