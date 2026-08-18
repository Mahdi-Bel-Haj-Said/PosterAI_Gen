"""
Key-art (background) prompt assembler — for the fine-tuned Qwen-Image LoRAs.

This is the prompt builder for the BACKGROUND layer, and it is deliberately
NOT a scaled-down version of the GPT-4o poster assembler (`assembler.py`).
The #1 rule of LoRA inference is: prompt in the same distribution you trained
in. So this module reproduces the training-caption grammar:

    <trigger>, <scene>, <c1> and <c2> palette, <m1> and <m2> mood,
    cinematic esports key art, highly detailed, <vibe>, <energy>

ENVIRONMENT-FIRST (refined post-V1 decision)
--------------------------------------------
V1 was trained on character-heavy splash art and learned to generate plausible
but *non-canonical* champions (fake Yasuo/Zed faces) as the dominant subject. For
a composited poster — where the real hero/player is added downstream and the
background must leave clean regions for overlays — a *dominant* wrong character
looks worse than none. So the product direction is **environment-first
backgrounds**: Runeterra-style settings, atmosphere, and lighting, where
incidental world life (a distant dragon/drake, a poro, minions, far-off soldiers,
circling birds) is welcome as SECONDARY flavor but never the focal subject.
Accurate *specific* champions remain a deferred v3 effort (a stacked per-champion
LoRA or composited official art).

Accordingly the `<scene>` slot describes an ENVIRONMENT (setting + feature +
atmosphere + effect); any creature/figure stays incidental, and the negative
prompt suppresses only a DOMINANT character portrait / a named champion (not
incidental background life). The caption grammar is otherwise unchanged.

Ground-truth facts (from the real V1 captions, still hold):
- **`<vibe>` and `<energy>` are raw trailing tokens** — e.g.
  `…, highly detailed, dark_fantasy, chill`. Values match the design enums.
- **No dedicated lighting slot** — lighting/effects are woven into the scene.
- **Palette is `"<c1> and <c2> palette"` with color WORDS**, never hex — a UI hex
  `primary_color` is mapped to the nearest named color.
- **Mood is `"<adj1> and <adj2> mood"`** — two adjectives.
- **No composition/overlay phrasing** — overlay-friendliness comes from dataset
  curation, not caption tokens.

Variety by design
-----------------
A static `vibe -> caption` mapping would make every background look the same.
Each slot is sampled from curated per-vibe banks via a seeded RNG:
- Pass `seed` for a reproducible caption (frozen eval set; the content-hash
  cache in `stages/background.py`).
- Omit `seed` and one is generated, used, and returned — so every production
  background differs, yet any specific one can be regenerated.

Public entry point: `build_keyart_prompt(input_data, seed=None)`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Game -> trigger token + LoRA name. The trigger MUST match the token the LoRA
# was trained on. (No hero noun: backgrounds are environment-only.)
# ---------------------------------------------------------------------------
_GAME_KEYART = {
    "league_of_legends": {"trigger": "lol_keyart", "lora": "lol_keyart"},
    "valorant": {"trigger": "valo_keyart", "lora": "valo_keyart"},
}

# ---------------------------------------------------------------------------
# SCENE banks, keyed by vibe. Each scene is composed as:
#   "<setting> <feature>[, <atmosphere>][, <effect>]"
# ENVIRONMENT-ONLY — settings/atmosphere/lighting, never characters. Keep these
# aligned with the V2 training captions (same vocabulary in captions and here).
# ---------------------------------------------------------------------------
_SCENE: Dict[str, Dict[str, List[str]]] = {
    "dark_fantasy": {
        "settings": [
            "a fog-choked graveyard of crumbling tombs",
            "a haunted forest of twisted black trees",
            "a ruined gothic cathedral overgrown with shadow",
            "a desolate moonlit moor",
            "a shadowed swamp of dead black water",
            "a crumbling stone fortress on a storm-dark cliff",
            "an abandoned battlefield strewn with broken statues",
        ],
        "features": [
            "shrouded in creeping mist",
            "lit by scattered ember light",
            "wrapped in cold pale moonlight",
            "littered with shattered armor and bone",
            "wreathed in slow-drifting shadow",
        ],
        "atmosphere": [
            "drifting fog and faint hovering spirits",
            "swirling ash and dead leaves",
            "flickering ghost-flames across the ground",
            "ravens circling a blood-red sky",
        ],
        "effects": [
            "eerie teal light seeping through the mist",
            "shafts of pale moonlight cutting the dark",
            "glowing arcane runes pulsing on ancient stone",
            "a deep crimson glow on the horizon",
        ],
    },
    "cinematic": {
        "settings": [
            "a vast mountain valley at dawn",
            "a windswept cliff overlooking a burning valley",
            "an ancient stone arena open to the sky",
            "a storm-lashed rocky coastline",
            "a grand ruined temple half-buried in sand",
            "a sprawling war-torn landscape at dusk",
        ],
        "features": [
            "framed with dramatic depth of field",
            "under sweeping volumetric light",
            "steeped in epic cinematic atmosphere",
            "scarred by distant battle",
        ],
        "atmosphere": [
            "drifting embers and dust in the air",
            "rolling storm clouds overhead",
            "distant smoke rising on the horizon",
        ],
        "effects": [
            "golden god rays breaking through the clouds",
            "dramatic rim light carving the terrain",
            "warm sunlight raking across the scene",
        ],
    },
    "cosmic": {
        "settings": [
            "a floating island adrift in deep space",
            "a shattered celestial temple among the stars",
            "a vast starfield above an alien landscape",
            "a crystalline void of drifting shards",
            "an ancient observatory open to the galaxy",
        ],
        "features": [
            "surrounded by swirling violet nebulae",
            "beneath a glowing eclipse",
            "amid slowly orbiting planet fragments",
            "wrapped in shimmering astral light",
        ],
        "atmosphere": [
            "drifting cosmic dust and stardust",
            "streaks of aurora light across the void",
            "distant galaxies turning slowly",
        ],
        "effects": [
            "iridescent nebula glow bleeding into the dark",
            "luminous stellar light washing the scene",
        ],
    },
    "cyberpunk": {
        "settings": [
            "a neon-lit megacity skyline at night",
            "a rain-slick downtown street of glowing signs",
            "a futuristic high-tech facility interior",
            "an industrial district drenched in neon",
            "a towering data-spire above the city",
        ],
        "features": [
            "wrapped in holographic haze",
            "reflecting neon across wet pavement",
            "crisscrossed by glowing power cables",
            "lit by towering digital billboards",
        ],
        "atmosphere": [
            "digital rain and drifting steam",
            "flickering holographic advertisements",
            "sparks raining from overhead wires",
        ],
        "effects": [
            "electric magenta and cyan glow",
            "chromatic light trails streaking the frame",
        ],
    },
    "minimal": {
        # Minimal = a CLEAN composition with ONE clear focal subject + generous
        # negative space — never an empty void. Every setting names a subject so
        # the render always has something to anchor on.
        "settings": [
            "a lone ancient monolith on a vast still salt flat",
            "a single silhouetted tree on an endless snowfield",
            "one weathered stone shrine above soft drifting mist",
            "a solitary curved-roof pavilion by a quiet mountain lake",
            "a single tall obelisk against a serene fog-veiled valley",
            "a lone ruined archway on a pale gradient desert",
            "a single great standing stone on a still shoreline",
        ],
        "features": [
            "composed with generous negative space and clean restraint",
            "bathed in soft even light with delicate tonal gradients",
            "reduced to a few simple, elegant forms",
            "framed by vast calm emptiness",
            "rendered in hushed, muted tones",
        ],
        "atmosphere": [
            "a faint drifting haze softening the horizon",
            "a single subtle wisp of light across the stillness",
            "thin low mist curling slowly over the ground",
            "a lone bird tracing a slow arc across the open sky",
        ],
        "effects": [
            "a gentle gradient of soft light fading into pale sky",
            "a quiet ambient glow along the far horizon",
            "a delicate rim of dawn light on distant forms",
            "soft diffused backlight haloing the scene",
        ],
    },
    "fire_energy": {
        "settings": [
            "a molten volcanic wasteland",
            "a battlefield engulfed in roaring flame",
            "a scorched desert under a burning sky",
            "a lava-filled cavern deep underground",
        ],
        "features": [
            "cracked with rivers of glowing magma",
            "wreathed in rising heat and black smoke",
            "littered with burning debris",
        ],
        "atmosphere": [
            "showering embers and drifting cinders",
            "waves of heat distortion rippling the air",
        ],
        "effects": [
            "explosive firelight flaring across the sky",
            "a fierce molten-orange glow",
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
        "imposing", "ominous", "haunting", "desolate", "brooding", "sinister",
        "eerie", "grim", "foreboding", "mournful", "mystic", "unsettling",
    ],
    "cyberpunk": ["electric", "high-tech", "moody", "futuristic", "sleek", "neon-noir", "restless"],
    "cosmic": ["elegant", "ethereal", "surreal", "transcendent", "vast", "mysterious", "serene"],
    "cinematic": ["epic", "dramatic", "grand", "somber", "sweeping", "majestic", "tense"],
    "minimal": ["calm", "refined", "serene", "restrained", "tranquil", "understated", "clean"],
    "fire_energy": ["fierce", "blazing", "volatile", "searing", "relentless", "molten"],
}

# Output format -> (width, height). Matches the poster canvas aspect.
_FORMAT_DIMS = {
    "portrait_1080x1920": (1080, 1920),
    "square_1080x1080": (1080, 1080),
    "landscape_1920x1080": (1920, 1080),
}

# Text-free + environment-FIRST enforcement. Baked-in pseudo-text is the #1
# failure mode, so text/logos are hard-suppressed. Incidental background
# creatures/figures (a distant dragon, a poro, minions, far-off soldiers) are
# now ALLOWED as atmosphere — only a DOMINANT character portrait / a specific
# named champion is suppressed, since the hero/player is composited downstream.
NEGATIVE_PROMPT = (
    "text, words, letters, numbers, typography, caption, title, subtitle, "
    "watermark, signature, logo, brand mark, ui, hud, interface, "
    "central figure, foreground character, large hero in the middle, "
    "person filling the frame, main character, armored warrior centered, "
    "single dominant figure, character close-up, character portrait, "
    "named champion, recognizable champion likeness, "
    "frame, border, blurry, low quality, jpeg artifacts, "
    "distorted, deformed, oversaturated, cluttered, "
    # Guard against near-empty renders (the minimal-vibe failure mode): the image
    # must always contain a clear subject, never be a flat void.
    "blank, empty featureless background, plain flat gradient, "
    "bare empty scene, no subject, foggy void with nothing in it"
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


# Energy is a DETAIL-DENSITY dial: how many atmosphere/effect clauses the scene
# carries, from sparse (chill) to packed (explosive). Not literal energy.
_ENERGY_DENSITY_P = {"chill": 0.25, "balanced": 0.6, "intense": 0.9, "explosive": 1.0}


def _scene(rng: random.Random, vibe: str, energy: str = "balanced") -> str:
    """Compose an ENVIRONMENT scene, with density scaled by energy."""
    bank = _SCENE[vibe]
    setting = rng.choice(bank["settings"])
    feature = rng.choice(bank["features"])
    parts = [f"{setting} {feature}"]
    p = _ENERGY_DENSITY_P.get(energy, 0.7)
    if bank["atmosphere"] and rng.random() < p:
        parts.append(rng.choice(bank["atmosphere"]))
    if bank["effects"] and rng.random() < p:
        parts.append(rng.choice(bank["effects"]))
    # explosive → pack in extra distinct atmosphere + effect clauses for density.
    if energy == "explosive":
        for extra in (rng.choice(bank["atmosphere"]), rng.choice(bank["effects"])):
            if extra not in parts:
                parts.append(extra)
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
    Build an ENVIRONMENT background-generation prompt for the fine-tuned
    Qwen-Image LoRA, in the training-caption grammar:

        <trigger>, <scene>, <c1> and <c2> palette, <m1> and <m2> mood,
        cinematic esports key art, highly detailed, <vibe>, <energy>

    Reads `_meta.game` (trigger/LoRA + fail-loud), `_meta.output_format`
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
        _scene(rng, vibe, energy),
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
