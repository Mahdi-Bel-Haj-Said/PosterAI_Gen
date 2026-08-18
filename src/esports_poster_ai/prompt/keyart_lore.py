"""
Runeterra world reference for the key-art prompt LLM.

Grounds generated backgrounds in the *real* League of Legends world so scenes
feel authentically LoL instead of generic fantasy. Every entry is expressed as
**renderable environmental motifs** — landscape, architecture, atmosphere,
iconic objects — because the LoRA paints scenes, not lore proper nouns (a word
like "Noxtoraa" means nothing to the model, but "brutal black-iron war-citadel,
blood-red banners" does).

HARD RULE baked into the phrasing: places, architecture, weather, flora, and
iconic objects only — **no champion names, no specific persons**. Incidental
crowds/creatures are allowed by the caption rules but stay secondary.

Region → vibe mapping (`VIBE_REGIONS`) lets each request steer toward the
regions that fit its requested vibe (cyberpunk → Zaun/Piltover, etc.).
"""

from __future__ import annotations

from typing import Dict, List, Optional

# region -> compact, renderable environmental motif string (NO champion names).
RUNETERRA_REGIONS: Dict[str, str] = {
    "Shurima": (
        "endless sun-scorched desert, colossal half-buried sandstone ruins, a great "
        "golden sun disc, towering obelisks and tomb-cities swallowed by dunes, mirage "
        "heat and drifting sand"
    ),
    "Noxus": (
        "brutal black-iron war-citadels and a towering imposing bastion, blood-red "
        "banners, crenelated battlements, narrow twisting stone alleys, circling crows, "
        "storm-dark skies over a martial empire"
    ),
    "Ionia": (
        "serene spirit forests, drifting pink spirit-blossom petals, lantern-lit shrines "
        "and tranquil curved-roof temples, misty green mountains, koi ponds, a calm "
        "magical harmony"
    ),
    "Demacia": (
        "gleaming white-stone citadels and grand ordered halls, pale petricite walls, "
        "marble and gold, soaring-bird heraldry, sunlit highland fields, lawful noble "
        "architecture"
    ),
    "Piltover": (
        "bright brass-and-gold art-deco spires, clockwork gears and ornate clocktowers, "
        "glowing blue hextech crystals, elegant sunlit bridges, a gleaming city of progress"
    ),
    "Zaun": (
        "smog-choked undercity twilight, toxic green chem-glow, corroded pipework and "
        "lattice ironwork, drifting shimmer vapor, stained-glass foundries, deep gloomy "
        "sump levels"
    ),
    "Freljord": (
        "brutal frozen tundra and vast glaciers, jagged true-ice spires, aurora-lit night "
        "skies, snow-blasted peaks, ancient ice-buried ruins, howling blizzards"
    ),
    "Bilgewater": (
        "lawless fog-bound port town, weathered docks and creaking ship timbers, giant "
        "sea-serpent bones, lantern-lit harbor mist, tangles of salt-crusted rope and nets"
    ),
    "Shadow Isles": (
        "cursed rolling black mist, spectral green wisps and ghost-flame, drowned "
        "overgrown ruins, dead twisted trees, haunted gothic cathedrals, eternal gloom"
    ),
    "Targon": (
        "a colossal cosmic mountain rising above the clouds, star-strewn celestial skies, "
        "shimmering auroras and constellations, floating carved monoliths, prismatic "
        "divine light"
    ),
    "Ixtal": (
        "deep primeval emerald jungle, vine-choked stone arcologies, glowing elemental "
        "glyphs, hidden waterfalls and overgrown temples, dense canopy light"
    ),
    "The Void": (
        "an alien violet abyss, corrosive purple growths and writhing tendrils, fractured "
        "shattered reality, glowing rifts, biomechanical horror terrain"
    ),
}

# vibe -> regions whose aesthetic fits that vibe. The LLM is told to prefer these.
VIBE_REGIONS: Dict[str, List[str]] = {
    "cyberpunk": ["Zaun", "Piltover"],
    "dark_fantasy": ["Noxus", "Shadow Isles", "Bilgewater"],
    "cosmic": ["Targon", "The Void"],
    "cinematic": ["Demacia", "Shurima", "Ionia", "Freljord"],
    "minimal": ["Ionia", "Freljord"],
    "fire_energy": ["Shurima", "Noxus", "Ixtal"],
}


# How often a prompt is grounded in a specific region at all. The rest are FREE,
# non-region scenes — so the same combo generated many times yields a healthy mix
# of "clearly Shurima/Zaun/…" and "generic LoL fantasy", instead of always the
# same region. Keeps regional flavor present without making the bank predictable.
GROUND_PROBABILITY = 0.5
# Of the grounded prompts, how often to pull a WILDCARD region from ALL of
# Runeterra instead of the vibe's fitting set — a dash of cross-pollination
# variety (e.g. a cosmic scene lit by a Freljord aurora). Raised from 0.2 so a
# combo's regions don't keep repeating (cosmic wasn't always Targon, etc.).
WILDCARD_PROBABILITY = 0.35


# --- Creative variety axes -------------------------------------------------
# Sampled per prompt (seeded) so scenes in the SAME combo differ in camera,
# light, weather, and centrepiece — the main lever against "samey" backgrounds.
# All are renderable and region-agnostic: a chosen region supplies the material
# and architecture; these supply the SHOT and ATMOSPHERE. They stay subordinate
# to the vibe — the LLM is told the vibe's mood still leads, so e.g. a cosmic
# scene stays night-like even if "golden hour" is suggested — and subordinate to
# ENERGY, which governs how many are emphasised (sparse for chill, all for
# explosive).

FRAMINGS: List[str] = [
    "a sweeping wide establishing landscape, open sky, clear lower-centre for a hero",
    "a dramatic low-angle looking up at a towering structure, open sky above",
    "a high aerial vantage looking down across the terrain, an open clearing in the mid-ground",
    "a view from a high ledge overlooking a vast valley, an open foreground shelf",
    "a huge iconic landmark dominating one side of the frame, a deep vista opening on the other",
    "a distant silhouette of the landmark against an enormous glowing sky, flat open foreground",
    "a natural frame of rock arches or foliage around a bright, open centre gap",
]

LIGHTING: List[str] = [
    "cold blue pre-dawn twilight",
    "warm golden-hour light",
    "clear high-noon light",
    "amber sunset dusk",
    "deep starlit night",
    "an eerie eclipse half-light",
    "dramatic storm light with distant lightning",
    "soft overcast diffuse light",
    "glowing bioluminescent night",
]

WEATHER: List[str] = [
    "crisp clear air",
    "rolling fog",
    "drifting rain",
    "swirling snow",
    "a hazy sandstorm",
    "drifting embers and ash",
    "petals and leaves carried on the wind",
    "a shimmering aurora overhead",
    "low ground-mist and volumetric god-rays",
]

FOCAL_MOTIFS: List[str] = [
    "a colossal ruined statue",
    "a shattered stone bridge",
    "an ancient gateway arch",
    "a beached shipwreck",
    "a great floating carved monolith",
    "a towering waterfall",
    "a vast impact crater",
    "a single immense ancient tree",
    "a crumbling watchtower",
    "a half-sunken temple",
    "a field of standing runestones",
    "a broken colossus half-buried in the ground",
]


def choose_variety(rng) -> Dict[str, str]:
    """
    Sample independent creative axes for one prompt (seeded → reproducible with
    the caption seed). Returns {framing, light, weather, motif}. Multiplying these
    axes gives thousands of distinct scene recipes, so even a few images per combo
    feel different while staying within the training-caption grammar.
    """
    return {
        "framing": rng.choice(FRAMINGS),
        "light": rng.choice(LIGHTING),
        "weather": rng.choice(WEATHER),
        "motif": rng.choice(FOCAL_MOTIFS),
    }


def runeterra_reference() -> str:
    """The full region motif list, formatted for a system prompt."""
    lines = [
        "RUNETERRA WORLD REFERENCE (League of Legends locales — environments only, "
        "for inspiration; NEVER name a champion or a specific person):"
    ]
    lines.extend(f"- {region}: {motifs}" for region, motifs in RUNETERRA_REGIONS.items())
    return "\n".join(lines)


def choose_region(vibe: Optional[str], rng) -> Optional[str]:
    """
    Decide this prompt's region grounding:
      - ~50% of the time → None (a free, non-region scene),
      - otherwise a region: mostly one that fits the vibe, sometimes a wildcard.

    `rng` is a seeded `random.Random` so the choice is reproducible with the
    prompt's seed. Returns a region name (key of RUNETERRA_REGIONS) or None.
    """
    if rng.random() >= GROUND_PROBABILITY:
        return None
    if rng.random() < WILDCARD_PROBABILITY:
        return rng.choice(list(RUNETERRA_REGIONS))
    regions = VIBE_REGIONS.get(vibe or "") or list(RUNETERRA_REGIONS)
    return rng.choice(regions)


__all__ = [
    "RUNETERRA_REGIONS",
    "VIBE_REGIONS",
    "GROUND_PROBABILITY",
    "WILDCARD_PROBABILITY",
    "FRAMINGS",
    "LIGHTING",
    "WEATHER",
    "FOCAL_MOTIFS",
    "runeterra_reference",
    "choose_region",
    "choose_variety",
]
