"""
The (energy, vibe) combo space for the pre-generated background bank.

Users pick 1 of 4 energies x 1 of 6 vibes = 24 combos. The bank keeps a small
pool of ready backgrounds per combo. The energy/vibe vocabularies are derived
straight from the input enums (`DesignEnergy`, `VibePreset`) via `get_args`, so
this list can never silently drift out of sync with what the UI can send.

A combo maps to:
- a stable **slug** `"{energy}_{vibe}"` — the R2 sub-folder name, and
- a minimal **input_data** dict the key-art prompt builder understands.

LoL-only for now (trigger token `lol_keyart`); Valorant is a later, additive
game dimension and would multiply the combo count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, get_args

from esports_poster_ai.domain.inputs import DesignEnergy, VibePreset

# Declaration order is preserved by get_args → deterministic combo ordering.
ENERGIES: tuple[str, ...] = get_args(DesignEnergy)  # chill, balanced, intense, explosive
VIBES: tuple[str, ...] = get_args(VibePreset)       # cyberpunk … fire_energy

# The bank is League-of-Legends key art today (matches the trained LoRA trigger).
BANK_GAME = "league_of_legends"


@dataclass(frozen=True)
class Combo:
    """One (energy, vibe) pair — the unit the bank is organised around."""

    energy: str
    vibe: str

    @property
    def slug(self) -> str:
        """R2 sub-folder name, e.g. `chill_cyberpunk`."""
        return f"{self.energy}_{self.vibe}"

    def input_data(self, *, output_format: str = "square_1080x1080") -> Dict[str, object]:
        """Minimal poster-input dict the key-art prompt builder consumes."""
        return {
            "_meta": {"game": BANK_GAME, "output_format": output_format},
            "design": {"vibe": self.vibe, "energy": self.energy},
        }


def all_combos() -> List[Combo]:
    """Every (energy, vibe) combo — 24 of them, in a stable order."""
    return [Combo(energy=e, vibe=v) for e in ENERGIES for v in VIBES]


def combo_from_slug(slug: str) -> Optional[Combo]:
    """Parse a `energy_vibe` slug back into a Combo, or None if it isn't valid."""
    for combo in all_combos():
        if combo.slug == slug:
            return combo
    return None


def combo_or_none(energy: Optional[str], vibe: Optional[str]) -> Optional[Combo]:
    """Build a Combo from a raw (energy, vibe) pair, or None if either is unknown."""
    if energy in ENERGIES and vibe in VIBES:
        return Combo(energy=energy, vibe=vibe)  # type: ignore[arg-type]
    return None


__all__ = [
    "Combo",
    "ENERGIES",
    "VIBES",
    "BANK_GAME",
    "all_combos",
    "combo_from_slug",
    "combo_or_none",
]
