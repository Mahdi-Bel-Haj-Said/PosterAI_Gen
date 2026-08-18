"""Tests for prompt/keyart_builder — tiered builder with bank fallback."""

from __future__ import annotations

from esports_poster_ai.config import get_settings
from esports_poster_ai.prompt.keyart import build_keyart_prompt
from esports_poster_ai.prompt.keyart_builder import (
    VibeFilterStore,
    build_prompt,
    load_caption_store,
)


def _input(vibe="dark_fantasy", energy="intense"):
    return {
        "_meta": {"game": "league_of_legends", "output_format": "landscape_1920x1080"},
        "design": {"vibe": vibe, "energy": energy},
    }


# --- fake LLMs (no network) -------------------------------------------------
class _EchoLLM:
    def __init__(self, out):
        self.out = out
        self.calls = 0

    def complete(self, *, system, user):
        self.calls += 1
        return self.out


class _RaisingLLM:
    def complete(self, *, system, user):
        raise RuntimeError("boom")


_VALID = (
    "lol_keyart, a vast enriched haunted valley shrouded in cold drifting mist and "
    "ruined towers, deep teal and charcoal palette, ominous and grim mood, "
    "cinematic esports key art, highly detailed, dark_fantasy, intense"
)
_INVALID = "a woman with red hair playing chess, no structure at all"


def test_economy_returns_bank_prompt():
    out = build_prompt(_input(), tier="economy", seed=7)
    assert out == build_keyart_prompt(_input(), seed=7)


def test_balanced_without_llm_falls_back_to_bank():
    out = build_prompt(_input(), tier="balanced", seed=7, llm=None)
    assert out == build_keyart_prompt(_input(), seed=7)


def test_balanced_with_valid_enrichment_uses_it():
    out = build_prompt(_input(), tier="balanced", seed=7, llm=_EchoLLM(_VALID))
    assert out.prompt == _VALID
    # metadata (lora/trigger/vibe/energy/dims/seed) preserved from the bank base
    assert out.vibe == "dark_fantasy" and out.energy == "intense"
    assert out.lora == "lol_keyart" and (out.width, out.height) == (1920, 1080)


def test_balanced_with_invalid_enrichment_falls_back():
    out = build_prompt(_input(), tier="balanced", seed=7, llm=_EchoLLM(_INVALID))
    assert out.prompt == build_keyart_prompt(_input(), seed=7).prompt


def test_llm_error_falls_back_to_bank():
    out = build_prompt(_input(), tier="balanced", seed=7, llm=_RaisingLLM())
    assert out.prompt == build_keyart_prompt(_input(), seed=7).prompt


def test_premium_with_store_and_valid_llm():
    store = VibeFilterStore([_VALID, _VALID])
    out = build_prompt(_input(), tier="premium", seed=7, llm=_EchoLLM(_VALID), store=store)
    assert out.prompt == _VALID


def test_premium_without_store_still_works():
    out = build_prompt(_input(), tier="premium", seed=7, llm=_EchoLLM(_VALID), store=None)
    assert out.prompt == _VALID


def test_quality_alias_maps_to_tier():
    # "medium" -> balanced; with no llm it falls back to bank (economy behaviour)
    out = build_prompt(_input(), tier="medium", seed=7, llm=None)
    assert out.prompt == build_keyart_prompt(_input(), seed=7).prompt


def test_unknown_tier_raises():
    import pytest

    with pytest.raises(ValueError):
        build_prompt(_input(), tier="ultra", seed=7, llm=_EchoLLM(_VALID))


def test_load_caption_store_from_configured_dir():
    # The repo ships the real captions under settings.keyart_captions_dir (Prompts/).
    store = load_caption_store(get_settings())
    assert store is not None
    got = store.retrieve("dark_fantasy", "intense", 3)
    assert 1 <= len(got) <= 3
    assert all(c.startswith("lol_keyart,") for c in got)


def test_load_caption_store_missing_dir_returns_none(tmp_path):
    from esports_poster_ai.config import Settings

    s = Settings(keyart_captions_dir=tmp_path / "does_not_exist")
    assert load_caption_store(s) is None


def test_vibe_filter_store_retrieves_by_vibe():
    caps = [
        "lol_keyart, scene a, teal and charcoal palette, grim and eerie mood, cinematic esports key art, highly detailed, dark_fantasy, intense",
        "lol_keyart, scene b, gold and black palette, epic and grand mood, cinematic esports key art, highly detailed, cinematic, balanced",
        "lol_keyart, scene c, violet and navy palette, vast and surreal mood, cinematic esports key art, highly detailed, cosmic, chill",
    ]
    store = VibeFilterStore(caps)
    got = store.retrieve("dark_fantasy", "intense", 5)
    assert len(got) == 1 and got[0].endswith("dark_fantasy, intense")


def test_enriched_prompt_always_validates_or_falls_back():
    # a valid-but-slightly-different enrichment is accepted; garbage is rejected
    for out_str, expect_enriched in [(_VALID, True), (_INVALID, False)]:
        out = build_prompt(_input(), tier="balanced", seed=1, llm=_EchoLLM(out_str))
        if expect_enriched:
            assert out.prompt == out_str
        else:
            assert out.prompt == build_keyart_prompt(_input(), seed=1).prompt
