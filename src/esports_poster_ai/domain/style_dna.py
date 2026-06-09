"""
Pydantic models for the Style DNA used by consistency mode.

A Style DNA captures the *visual style* of an approved poster — palette,
lighting, atmosphere, particle effects, energy — without capturing any
content (team names, scores, logos, dates). It is reused as a hard
constraint when generating subsequent posters in a tournament series.

Two related shapes live here:

* `StyleDNASemantic`  — the small subset GPT-4o emits as structured JSON.
                        Decoupled from storage metadata so the structured
                        output schema stays focused.
* `StyleDNA`          — the full persisted document: programmatic palette
                        plus semantic fields plus storage metadata
                        (schema_version, status, timestamps, etc.).

Backwards compatibility: old Style DNA files from before the schema_version
field existed are loaded as schema_version=1 and treated as approved (no
draft concept existed previously).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


CURRENT_SCHEMA_VERSION = 1

Energy = Literal["chill", "balanced", "intense", "explosive"]
ColorTemperature = Literal["warm", "cool", "neutral"]
DNAStatus = Literal["draft", "approved"]


class StyleDNASemantic(BaseModel):
    """
    Semantic fields extracted by the vision model.

    Kept as a separate model so the JSON schema we hand to the model is
    minimal and focused — no storage metadata in the structured output.
    """

    lighting: str
    atmosphere: str
    particle_effects: str
    energy: Energy
    sd_style_keywords: str

    model_config = ConfigDict(extra="ignore")


class StyleDNA(BaseModel):
    """
    Full persisted Style DNA document.

    Field order is chosen so the JSON file reads top-to-bottom as:
    metadata, programmatic block, semantic block.
    """

    # --- metadata
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION)
    tournament_id: str
    status: DNAStatus = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    source_poster_path: Optional[str] = None

    # --- programmatic (palette extraction)
    palette: List[str] = Field(default_factory=list, description="Dominant hex colors, sorted by frequency.")
    color_temperature: ColorTemperature = "neutral"

    # --- semantic (vision model)
    lighting: str = ""
    atmosphere: str = ""
    particle_effects: str = ""
    energy: Energy = "balanced"
    sd_style_keywords: str = ""

    model_config = ConfigDict(extra="allow")

    # ---------------------------------------------------------------- helpers
    def to_prompt_dict(self) -> dict:
        """
        Render the subset of fields consumed by
        `prompt.blocks.consistency.build_consistency_block`.
        """
        return {
            "palette": self.palette,
            "lighting": self.lighting,
            "atmosphere": self.atmosphere,
            "particle_effects": self.particle_effects,
            "energy": self.energy,
            "sd_style_keywords": self.sd_style_keywords,
        }

    def approve(self) -> "StyleDNA":
        """Return a copy marked approved with an approval timestamp."""
        return self.model_copy(update={"status": "approved", "approved_at": datetime.now(timezone.utc)})


__all__ = [
    "StyleDNA",
    "StyleDNASemantic",
    "Energy",
    "ColorTemperature",
    "DNAStatus",
    "CURRENT_SCHEMA_VERSION",
]
