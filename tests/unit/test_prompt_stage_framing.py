"""
The vision stage frames an AI-generated (bank) background as original fantasy art
so gpt-4o stops occasionally declining it — but ONLY for `source == "generated"`,
never for user uploads (where the "no real people / original art" claim may be
false).
"""

from __future__ import annotations

from esports_poster_ai.stages import prompt_generator as pg
from esports_poster_ai.stages.prompt_generator import (
    GENERATED_BG_FRAMING,
    PROMPT_STAGE_INSTRUCTIONS,
    _instructions_for,
    generate_image_prompt,
)


def test_framing_added_for_generated_background():
    ins = _instructions_for({"background": {"source": "generated"}})
    assert GENERATED_BG_FRAMING in ins
    assert PROMPT_STAGE_INSTRUCTIONS in ins


def test_framing_not_added_for_user_upload():
    ins = _instructions_for({"background": {"source": "custom", "image_path": "x.png"}})
    assert GENERATED_BG_FRAMING not in ins
    assert ins == PROMPT_STAGE_INSTRUCTIONS


def test_framing_not_added_when_no_background():
    assert _instructions_for({}) == PROMPT_STAGE_INSTRUCTIONS
    assert _instructions_for({"background": {}}) == PROMPT_STAGE_INSTRUCTIONS


class _FakeClient:
    def __init__(self):
        self.instructions = None

    def generate_prompt(self, *, background_image, assembled_prompt, instructions, run_id=None):
        self.instructions = instructions
        return "A vivid cosmic vista of drifting nebulae"


def test_generate_image_prompt_wires_framing_for_generated():
    client = _FakeClient()
    input_data = {
        "_meta": {"game": "league_of_legends", "poster_type": "tournament_announcement",
                  "mode": "fresh", "output_format": "portrait_1080x1920", "quality": "medium"},
        "background": {"source": "generated"},
        "tournament": {"name": "Summer Clash"},
        "design": {"vibe": "cosmic", "energy": "intense"},
    }
    out = generate_image_prompt(background_image=b"img", input_data=input_data, client=client)
    assert GENERATED_BG_FRAMING in client.instructions
    assert out.startswith("A vivid cosmic vista")


def test_generate_image_prompt_no_framing_for_upload():
    client = _FakeClient()
    input_data = {
        "_meta": {"game": "league_of_legends", "poster_type": "gameday",
                  "mode": "fresh", "output_format": "portrait_1080x1920", "quality": "medium"},
        "background": {"source": "custom", "image_path": "bg.png"},
        "design": {"vibe": "cinematic", "energy": "balanced"},
    }
    generate_image_prompt(background_image=b"img", input_data=input_data, client=client)
    assert GENERATED_BG_FRAMING not in client.instructions
