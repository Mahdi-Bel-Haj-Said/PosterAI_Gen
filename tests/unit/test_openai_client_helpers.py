"""
Tests for the JSON-parsing helpers exposed by clients/openai_client.

These functions are pure and tested without spinning up an OpenAIClient.
"""

from __future__ import annotations

from pydantic import BaseModel

from esports_poster_ai.clients.openai_client import (
    _extract_first_json_object,
    _strip_code_fences,
    _try_parse,
)


class _Toy(BaseModel):
    a: int
    b: str


def test_strip_code_fences_removes_json_fence():
    text = '```json\n{"a": 1, "b": "x"}\n```'
    assert _strip_code_fences(text).strip() == '{"a": 1, "b": "x"}'


def test_strip_code_fences_removes_bare_fence():
    text = '```\n{"a": 1}\n```'
    assert _strip_code_fences(text).strip() == '{"a": 1}'


def test_strip_code_fences_leaves_clean_text_alone():
    text = '{"a": 1, "b": "x"}'
    assert _strip_code_fences(text) == text


def test_extract_first_json_object_finds_first_balanced_object():
    text = 'noise {"a": 1, "b": "x"} more noise'
    assert _extract_first_json_object(text) == '{"a": 1, "b": "x"}'


def test_extract_first_json_object_handles_nested_braces():
    text = '{"a": 1, "b": {"c": 2}}'
    assert _extract_first_json_object(text) == text


def test_extract_first_json_object_handles_braces_in_strings():
    text = '{"a": 1, "b": "has } in it"}'
    assert _extract_first_json_object(text) == text


def test_extract_first_json_object_returns_none_when_unbalanced():
    assert _extract_first_json_object("{ no close brace") is None


def test_extract_first_json_object_returns_none_when_no_object():
    assert _extract_first_json_object("just text") is None


def test_try_parse_returns_validated_instance():
    parsed = _try_parse('{"a": 1, "b": "x"}', _Toy)
    assert parsed is not None
    assert parsed.a == 1
    assert parsed.b == "x"


def test_try_parse_handles_markdown_wrapped_json():
    parsed = _try_parse('```json\n{"a": 1, "b": "x"}\n```', _Toy)
    assert parsed is not None


def test_try_parse_handles_text_around_json():
    parsed = _try_parse('Here is your output: {"a": 1, "b": "x"}. Done.', _Toy)
    assert parsed is not None


def test_try_parse_returns_none_on_invalid_json():
    assert _try_parse("not json at all", _Toy) is None


def test_try_parse_returns_none_on_validation_failure():
    # Valid JSON, wrong shape.
    assert _try_parse('{"a": "not_an_int", "b": "x"}', _Toy) is None


def test_try_parse_returns_none_on_empty_input():
    assert _try_parse("", _Toy) is None
