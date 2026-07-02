"""
Key-art (background) prompt assembler — for the fine-tuned Qwen-Image LoRAs.

This is the prompt builder for the BACKGROUND layer, and it is deliberately
NOT a scaled-down version of the GPT-4o poster assembler (`assembler.py`).
The #1 rule of LoRA inference is: prompt in the same distribution you trained
in. So this module reproduces the EXACT grammar of the real training captions
(see the samples under `train.md` / the caption dataset):

    <trigger>, <scene>, <c1> and <c2> palette, <m1> and <m2> mood,
    cinematic esports key art, highly detailed, <vibe>, <energy>

Ground-truth facts extracted from the real captions (these override the
simplified pattern sketched in train.md §5):

- **`<vibe>` and `<energy>` are raw tokens at the very end** — e.g.
  `…, highly detailed, dark_fantasy, intense`. The LoRA learned these tokens,
  so they MUST be appended verbatim (values match the design enums).
- **No dedicated lighting slot.** Lighting and effects are woven INTO the scene
  clause ("glowing red energy in his fist", "ghostly blue light illuminates…").
- **Scenes are character/champion-driven and action-heavy**, not environmental
  (Swain ascending, dual-champion combat, a towering monster). We compose
  scenes from champion/agent archetypes + action + setting + secondary +
  effect, so "match training" means character key art.
- **Palette is `"<c1> and <c2> palette"` with color WORDS**, never hex. The UI
  `primary_color` is a hex, so it is converted to the nearest color word.
- **Mood is `"<adj1> and <adj2> mood"`** — two adjectives.
- **No composition/overlay phrasing** — overlay-friendliness was baked in via
  dataset rating/curation (train.md §5), not caption tokens.

Variety by design
-----------------
A static `vibe -> caption` mapping would make every background look the same.
Each slot is sampled from curated per-vibe banks via a seeded RNG:
- Pass `seed` for a reproducible caption (frozen eval set, train.md §8; the
  content-hash cache in `stages/background.py`).
- Omit `seed` and one is generated, used, and returned — so every production
  background differs, yet any specific one can be regenerated.

Coverage note: the banks for `dark_fantasy` / `cyberpunk` / `cosmic` (LoL) are
grounded in the real captions provided. `cinematic` / `minimal` / `fire_energy`
and all of Valorant are EXTRAPOLATED and marked below — they should be
validated / replaced once real captions for those are available.

Public entry point: `build_keyart_prompt(input_data, seed=None)`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Game -> trigger token + LoRA name + the hero noun the scene banks fill in.
# The trigger MUST match the token the LoRA was trained on.
# ---------------------------------------------------------------------------
_GAME_KEYART = {
    "league_of_legends": {"trigger": "lol_keyart", "lora": "lol_keyart", "hero": "champion"},
    "valorant": {"trigger": "valo_keyart", "lora": "valo_keyart", "hero": "agent"},
}

# ---------------------------------------------------------------------------
# SCENE banks, keyed by vibe. Each scene is composed as:
#   "<subject> <action> <setting>[, <secondary>][, <effect>]"
# with "{hero}" filled from the game ("champion" / "agent"). Character-driven
# and action-heavy, matching the real training captions. dark_fantasy /
# cyberpunk / cosmic are data-grounded; the rest are extrapolated (see note).
# ---------------------------------------------------------------------------
_SCENE: Dict[str, Dict[str, List[str]]] = {
    "dark_fantasy": {
        "subjects": [
            "a dark warlord {hero} in ornate black and crimson armor",
            "a gaunt spectral mage {hero} wreathed in shadow",
            "a towering ancient monster with glowing eyes and mossy hide",
            "a hooded ghostly gunslinger {hero} in a long dark coat",
            "a winged demonic sovereign {hero} in horned black plate",
            "two dark warrior {hero}s in ornate black and red armor",
            "a shirtless white-haired warlord {hero} marked with glowing runes",
        ],
        "actions": [
            "raising a glowing red orb in his open palm",
            "ascending with massive black demon wings outstretched",
            "holding a glowing teal energy blade aloft",
            "floating upward with arms stretched wide",
            "looming over the battlefield below",
            "unleashing a burst of dark energy from his hands",
            "standing tall amid swirling smoke",
        ],
        "settings": [
            "against a blazing crimson sky",
            "in a deep red cathedral shrouded in smoke",
            "in a dark misty swamp",
            "in a spectral forest of twisted black trees",
            "in a barren moonlit wasteland",
            "against a wall of dark crimson smoke",
            "in a shattered void of falling debris",
        ],
        "secondary": [
            "crimson ravens swirling all around him",
            "smaller glowing spirits hovering in the fog",
            "terrified warriors cowering below",
            "a massive shattered golem falling apart beneath him",
            "dead bare trees framing both sides",
            "ghostly figures rising from the ground",
        ],
        "effects": [
            "glowing red energy pulsing from his fist",
            "deep teal ghost-flame energy surrounding the ground",
            "blood-red rune markings glowing across his chest and arms",
            "streaks of magenta fire consuming his hands",
            "eerie blue light illuminating the mist",
        ],
    },
    "cyberpunk": {
        "subjects": [
            "two {hero}s locked in mid-air combat",
            "a sleek augmented {hero} in a red armored mech",
            "a neon-lit {hero} in sharp high-tech armor",
            "a cybernetic {hero} crackling with electric energy",
        ],
        "actions": [
            "unleashing a blue lightning strike",
            "dodging with a glowing pink energy burst",
            "charging a crackling energy weapon",
            "leaping through a shower of sparks",
        ],
        "settings": [
            "in a dark cinematic close-up",
            "against a neon-lit night skyline",
            "in a rain-slick neon alley",
            "inside a glowing high-tech arena",
        ],
        "secondary": [
            "electric blue and hot pink energy clashing at center frame",
            "holographic glyphs flickering around them",
            "sparks and debris scattering through the air",
        ],
        "effects": [
            "electric arcs snaking across the frame",
            "neon glow reflecting off wet surfaces",
            "chromatic light trails streaking behind the motion",
        ],
    },
    "cosmic": {
        "subjects": [
            "a cosmic-skinned {hero} with flowing galaxy hair",
            "an ethereal star-forged {hero} wreathed in nebula light",
            "a celestial {hero} crowned with an eclipse halo",
        ],
        "actions": [
            "aiming an iridescent rifle",
            "summoning a swirling vortex of starlight",
            "drifting weightless with arms spread",
        ],
        "settings": [
            "surrounded by dark planet fragments and nebula swirls in deep space",
            "against a vast starfield and a glowing eclipse",
            "amid drifting cosmic dust and distant galaxies",
        ],
        "secondary": [
            "a glowing eclipse halo behind the head",
            "shattered planet shards orbiting slowly",
            "streaks of stardust spiraling inward",
        ],
        "effects": [
            "iridescent cosmic light shimmering across the scene",
            "violet nebula glow bleeding into the dark",
        ],
    },
    # --- EXTRAPOLATED below (no real captions yet — validate/replace) --------
    "cinematic": {
        "subjects": [
            "a battle-worn {hero} in intricately detailed armor",
            "a lone {hero} silhouetted against dramatic light",
            "a determined {hero} in a heroic stance",
        ],
        "actions": [
            "gripping a weapon at the ready",
            "turning toward the camera",
            "standing firm amid the aftermath",
        ],
        "settings": [
            "in a dramatic film-lit environment",
            "against a moody atmospheric backdrop",
            "amid drifting smoke and volumetric light",
        ],
        "secondary": [
            "embers drifting slowly through the air",
            "distant figures blurred in the background",
        ],
        "effects": [
            "strong rim light carving the silhouette",
            "volumetric god rays cutting through the haze",
        ],
    },
    "minimal": {
        "subjects": [
            "a single {hero} in a clean composed stance",
            "a lone {hero} rendered with restraint",
        ],
        "actions": [
            "standing calmly",
            "posed with quiet intensity",
        ],
        "settings": [
            "against a clean muted backdrop",
            "in a spare uncluttered space",
        ],
        "secondary": [],
        "effects": [
            "soft even light wrapping the figure",
            "a subtle glow outlining the silhouette",
        ],
    },
    "fire_energy": {
        "subjects": [
            "a fierce {hero} engulfed in flame",
            "a blazing {hero} in scorched armor",
        ],
        "actions": [
            "erupting with fire from both hands",
            "swinging a flaming weapon overhead",
        ],
        "settings": [
            "amid a storm of embers and rising heat",
            "against a wall of roaring flame",
        ],
        "secondary": [
            "sparks and cinders scattering everywhere",
            "molten cracks glowing underfoot",
        ],
        "effects": [
            "explosive firelight flaring across the frame",
            "waves of heat distortion rippling the air",
        ],
    },
}

# Full palettes used when the user gives NO primary_color, keyed by vibe.
_VIBE_PALETTES = {
    "dark_fantasy": [
        "blood red and charcoal", "deep teal and dark charcoal",
        "hot pink and dark charcoal", "white and blood red",
        "deep violet and charcoal", "crimson and black",
    ],
    "cyberpunk": ["electric blue and hot pink", "deep charcoal and neon cyan", "magenta and dark navy"],
    "cosmic": ["deep violet and cosmic pink", "dark navy and stellar teal", "purple and magenta"],
    "cinematic": ["amber and charcoal", "steel blue and black", "crimson and deep shadow"],
    "minimal": ["soft white and slate grey", "muted teal and off-white", "pale gold and grey"],
    "fire_energy": ["fiery orange and charcoal", "blazing red and black", "amber and deep crimson"],
}

# Dark base color paired with a user-supplied primary_color, keyed by vibe.
_VIBE_BASES = {
    "dark_fantasy": ["charcoal", "dark charcoal", "black", "dark navy"],
    "cyberpunk": ["deep charcoal", "black", "dark navy"],
    "cosmic": ["deep violet", "dark navy", "black"],
    "cinematic": ["charcoal", "black", "deep shadow"],
    "minimal": ["slate grey", "off-white", "soft grey"],
    "fire_energy": ["charcoal", "black", "deep crimson"],
}

# MOOD adjectives (two are sampled and joined with "and"), keyed by vibe.
_VIBE_MOODS = {
    "dark_fantasy": [
        "imposing", "regal", "commanding", "apocalyptic", "monstrous", "haunting",
        "menacing", "dominating", "ominous", "grim", "resolute", "unsettling",
        "powerful", "desolate", "brooding", "sinister",
    ],
    "cyberpunk": ["fast", "kinetic", "electric", "high-tech", "aggressive", "futuristic", "sleek"],
    "cosmic": ["elegant", "ominous", "ethereal", "surreal", "transcendent", "vast", "mysterious"],
    "cinematic": ["epic", "dramatic", "heroic", "grand", "somber", "triumphant", "tense"],
    "minimal": ["calm", "refined", "elegant", "restrained", "serene", "understated", "clean"],
    "fire_energy": ["fierce", "blazing", "aggressive", "relentless", "ferocious", "searing"],
}

# Output format -> (width, height). Matches the poster canvas aspect.
_FORMAT_DIMS = {
    "portrait_1080x1920": (1080, 1920),
    "square_1080x1080": (1080, 1080),
    "landscape_1920x1080": (1920, 1080),
}

# Text-free enforcement. Baked-in pseudo-text is the #1 failure mode for a
# composited-text pipeline (train.md §4), so text terms lead the list.
NEGATIVE_PROMPT = (
    "text, words, letters, numbers, typography, caption, title, subtitle, "
    "watermark, signature, logo, brand mark, ui, hud, interface, "
    "frame, border, blurry, low quality, jpeg artifacts, "
    "distorted, deformed, disfigured, oversaturated, cluttered"
)

# Defaults when the optional design fields are absent.
_DEFAULT_VIBE = "cinematic"
_DEFAULT_ENERGY = "balanced"

# Named colors (name -> RGB) for converting a hex primary_color to the nearest
# color WORD, since the training captions use words, not hex.
_NAMED_COLORS = {
    "white": (245, 245, 245), "black": (15, 15, 15), "charcoal": (45, 45, 50),
    "blood red": (140, 20, 25), "red": (200, 30, 30), "deep red": (110, 15, 15),
    "hot pink": (255, 60, 150), "magenta": (200, 20, 140), "pink": (240, 130, 180),
    "purple": (120, 40, 160), "deep violet": (80, 30, 120),
    "teal": (30, 140, 140), "deep teal": (20, 90, 95), "cyan": (40, 200, 220),
    "electric blue": (40, 120, 240), "blue": (40, 70, 200), "dark navy": (25, 35, 80),
    "gold": (210, 170, 60), "orange": (240, 140, 40), "emerald": (30, 160, 90),
    "silver": (185, 190, 195), "slate grey": (110, 115, 125), "brown": (110, 70, 45),
}

# The fixed caption body every training caption shared (before vibe/energy).
_CAPTION_TAIL = ("cinematic esports key art", "highly detailed")


@dataclass(frozen=True)
class KeyartPrompt:
    """A fully-resolved background-generation request for a Qwen-Image LoRA."""

    prompt: str
    negative_prompt: str
    lora: str
    trigger: str
    vibe: str
    energy: str
    width: int
    height: int
    seed: int


def _design(input_data: Dict[str, Any]) -> Dict[str, Any]:
    d = input_data.get("design") if isinstance(input_data, dict) else None
    return d if isinstance(d, dict) else {}


def _str_or_none(v: Any) -> Optional[str]:
    return v.strip() if isinstance(v, str) and v.strip() else None


def _vibe(design: Dict[str, Any]) -> str:
    v = _str_or_none(design.get("vibe"))
    return v if v in _SCENE else _DEFAULT_VIBE


def _energy(design: Dict[str, Any]) -> str:
    return _str_or_none(design.get("energy")) or _DEFAULT_ENERGY


def _color_word(value: str) -> str:
    """Return a training-distribution color WORD. A hex is mapped to the nearest
    named color; a plain word is passed through unchanged."""
    v = value.strip()
    if not v.startswith("#"):
        return v
    h = v.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return v
    return min(
        _NAMED_COLORS,
        key=lambda name: sum((c - t) ** 2 for c, t in zip(_NAMED_COLORS[name], (r, g, b))),
    )


def _scene(rng: random.Random, vibe: str, hero: str) -> str:
    bank = _SCENE[vibe]
    subject = rng.choice(bank["subjects"]).format(hero=hero)
    action = rng.choice(bank["actions"])
    setting = rng.choice(bank["settings"])
    parts = [f"{subject} {action} {setting}"]
    if bank["secondary"] and rng.random() < 0.75:
        parts.append(rng.choice(bank["secondary"]).format(hero=hero))
    if bank["effects"] and rng.random() < 0.75:
        parts.append(rng.choice(bank["effects"]))
    return ", ".join(parts)


def _palette_slot(rng: random.Random, vibe: str, design: Dict[str, Any]) -> str:
    color = _str_or_none(design.get("primary_color"))
    if color:
        base = rng.choice(_VIBE_BASES[vibe])
        return f"{_color_word(color)} and {base} palette"
    return f"{rng.choice(_VIBE_PALETTES[vibe])} palette"


def _mood_slot(rng: random.Random, vibe: str) -> str:
    a, b = rng.sample(_VIBE_MOODS[vibe], 2)
    return f"{a} and {b} mood"


def _dimensions(input_data: Dict[str, Any]) -> tuple[int, int]:
    meta = input_data.get("_meta") if isinstance(input_data, dict) else None
    fmt = meta.get("output_format") if isinstance(meta, dict) else None
    return _FORMAT_DIMS.get(fmt, _FORMAT_DIMS["portrait_1080x1920"])


def build_keyart_prompt(
    input_data: Dict[str, Any],
    *,
    seed: Optional[int] = None,
) -> KeyartPrompt:
    """
    Build a background-generation prompt for the fine-tuned Qwen-Image LoRA,
    in the real training-caption grammar:

        <trigger>, <scene>, <c1> and <c2> palette, <m1> and <m2> mood,
        cinematic esports key art, highly detailed, <vibe>, <energy>

    Reads `_meta.game` (trigger/LoRA/hero + fail-loud), `_meta.output_format`
    (dimensions), and the optional `design` object (`vibe` / `primary_color` /
    `energy`). `seed` makes the caption reproducible; when omitted a seed is
    generated, used, and returned so the same background can be regenerated.

    Raises `ValueError` for an unknown / missing game.
    """
    meta = input_data.get("_meta") if isinstance(input_data, dict) else None
    game = _str_or_none((meta or {}).get("game"))
    keyart = _GAME_KEYART.get(game)
    if not keyart:
        raise ValueError(
            f"Unknown game for keyart prompt: {game!r} "
            f"(expected one of {sorted(_GAME_KEYART)})"
        )

    if seed is None:
        seed = random.randrange(2**31)
    rng = random.Random(seed)

    design = _design(input_data)
    vibe = _vibe(design)
    energy = _energy(design)

    slots: List[str] = [
        keyart["trigger"],
        _scene(rng, vibe, keyart["hero"]),
        _palette_slot(rng, vibe, design),
        _mood_slot(rng, vibe),
        *_CAPTION_TAIL,
        vibe,
        energy,
    ]
    prompt = ", ".join(slots)
    width, height = _dimensions(input_data)

    return KeyartPrompt(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        lora=keyart["lora"],
        trigger=keyart["trigger"],
        vibe=vibe,
        energy=energy,
        width=width,
        height=height,
        seed=seed,
    )


__all__ = ["KeyartPrompt", "build_keyart_prompt", "NEGATIVE_PROMPT"]
