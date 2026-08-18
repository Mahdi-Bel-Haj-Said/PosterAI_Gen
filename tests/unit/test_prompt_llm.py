"""Tests for clients/prompt_llm.OpenAIPromptLLM (no network — client injected)."""

from __future__ import annotations

from esports_poster_ai.clients.prompt_llm import OpenAIPromptLLM
from esports_poster_ai.config import Settings
from esports_poster_ai.prompt.keyart import build_keyart_prompt
from esports_poster_ai.prompt.keyart_builder import PromptLLM, build_prompt


# --- fake OpenAI SDK surface (responses.create -> obj with .output_text) -----
class _FakeResp:
    def __init__(self, text):
        self.output_text = text


class _FakeResponses:
    def __init__(self, text):
        self._text = text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResp(self._text)


class _FakeClient:
    def __init__(self, text):
        self.responses = _FakeResponses(text)


def _llm_with_fake(text):
    llm = OpenAIPromptLLM(settings=Settings(openai_api_key="test-key"))
    llm._client = _FakeClient(text)  # inject, bypass real network/key
    return llm


def test_adapter_satisfies_prompt_llm_protocol():
    assert isinstance(_llm_with_fake("x"), PromptLLM)


def test_adapter_uses_small_model_and_maps_system_user():
    llm = _llm_with_fake("  a caption  ")
    out = llm.complete(system="SYS", user="USR")
    assert out == "a caption"  # stripped
    kw = llm._client.responses.last_kwargs
    assert kw["model"] == "gpt-4o-mini"  # the small default
    assert kw["instructions"] == "SYS"
    assert kw["input"] == "USR"


def test_adapter_model_override():
    llm = OpenAIPromptLLM(settings=Settings(openai_api_key="k"), model="gpt-5-mini")
    llm._client = _FakeClient("ok")
    llm.complete(system="s", user="u")
    assert llm._client.responses.last_kwargs["model"] == "gpt-5-mini"


def test_adapter_drives_balanced_tier_end_to_end():
    valid = (
        "lol_keyart, a vast fog-wrapped ruined keep under a bleeding crimson sky, "
        "blood red and charcoal palette, ominous and grim mood, "
        "cinematic esports key art, highly detailed, dark_fantasy, intense"
    )
    inp = {
        "_meta": {"game": "league_of_legends", "output_format": "landscape_1920x1080"},
        "design": {"vibe": "dark_fantasy", "energy": "intense"},
    }
    out = build_prompt(inp, tier="balanced", seed=7, llm=_llm_with_fake(valid))
    assert out.prompt == valid


def test_missing_key_degrades_to_bank_via_builder():
    # No key -> require_openai_key raises inside complete -> builder falls back.
    llm = OpenAIPromptLLM(settings=Settings(openai_api_key=""))
    inp = {
        "_meta": {"game": "league_of_legends", "output_format": "landscape_1920x1080"},
        "design": {"vibe": "cinematic", "energy": "balanced"},
    }
    out = build_prompt(inp, tier="balanced", seed=3, llm=llm)
    assert out.prompt == build_keyart_prompt(inp, seed=3).prompt  # bank fallback
