"""
Tiered key-art prompt builder.

Layers OPTIONAL, additive modules on top of the deterministic bank sampler
(`keyart.build_keyart_prompt`) so prompt quality can scale with the product's
quality tier without a rewrite:

    economy  : bank sampler only.                    (free, instant)
    balanced : bank base -> LLM enrich.              (creative, grounded)
    premium  : RAG-grounded LLM candidate.           (max creative, in-distribution)

(Map to the product's low / medium / high quality selector.)

Design guarantees
-----------------
- **One interface:** `build_prompt(input_data, tier=..., seed=..., llm=..., store=...)`.
- **Additive tiers:** upgrading is enabling a module + injecting an LLM/store —
  not a refactor. The seams (`PromptLLM`, `CaptionStore`) are dependency-injected
  and provider-agnostic.
- **Always safe:** if the LLM/store is missing or errors, or its output fails
  grammar validation, we return the in-distribution **bank** prompt. The pipeline
  never breaks and never ships an off-distribution prompt.
- **Validated:** every returned prompt matches the training-caption grammar
  (trigger, `... palette`, `... mood`, fixed tail, exact trailing `vibe, energy`).

The LLM calls are intentionally behind a tiny `PromptLLM` protocol so this module
is unit-testable with no network (see tests) and works with any provider — inject
a cheap small model (e.g. Haiku / 4o-mini) for prompt work; the prompt-side cost
is ~$0.001 regardless of tier (the cost dial is best-of-N image generation, done
downstream, not here).
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import List, Literal, Optional, Protocol, runtime_checkable

from esports_poster_ai.prompt.keyart import KeyartPrompt, build_keyart_prompt
from esports_poster_ai.prompt.keyart_lore import (
    RUNETERRA_REGIONS,
    choose_region,
    choose_variety,
    runeterra_reference,
)

QualityTier = Literal["economy", "balanced", "premium"]

# Map the product's quality selector -> prompt tier.
_QUALITY_TO_TIER = {"low": "economy", "medium": "balanced", "high": "premium"}


@runtime_checkable
class PromptLLM(Protocol):
    """Minimal text-completion seam. Inject any provider (OpenAI, Gemini, etc.)."""

    def complete(self, *, system: str, user: str) -> str: ...


@runtime_checkable
class CaptionStore(Protocol):
    """Retrieval seam for RAG grounding — returns in-distribution exemplars."""

    def retrieve(self, vibe: str, energy: str, k: int) -> List[str]: ...


# ---------------------------------------------------------------------------
# System prompts (guardrailed — keep the LLM in-distribution)
# ---------------------------------------------------------------------------
_ENRICH_SYSTEM = """\
You improve captions for a fine-tuned League of Legends key-art BACKGROUND model.
You are given ONE base caption. Rewrite it to be more vivid and creative while
obeying EVERY rule:

1. Keep the EXACT structure and order:
   <trigger>, <scene>, <c1> and <c2> palette, <m1> and <m2> mood, cinematic esports key art, highly detailed, <vibe>, <energy>
2. Enrich ONLY the <scene> with specific, evocative environmental detail (terrain,
   structures, sky, light, weather, atmosphere). Keep it a painterly LoL fantasy
   environment. The <energy> token is a DETAIL-DENSITY dial (NOT literal energy):
   follow the ENERGY directive in the user message — chill = keep it sparse and
   calm (~20-30 words, few elements), explosive = pack in many elements and
   intricate detail (~55-70 words, the opposite of minimal).
3. Copy these VERBATIM from the base, unchanged: the trigger, the
   "<c1> and <c2> palette" wording, the "<m1> and <m2> mood" wording, the text
   "cinematic esports key art, highly detailed", and the final <vibe>, <energy>
   tokens.
4. Compose the shot as the FRAMING in the user message specifies — VARY the
   camera; do NOT always produce a flat, centred wide landscape. Leave one
   uncluttered OPEN AREA (where the framing puts it) for a hero composited later.
   The user message also lists a LIGHT / time-of-day, an ATMOSPHERE, and a FOCAL
   POINT to build the scene around — incorporate them (ENERGY governs how many;
   keep sparse scenes clean), adapting the light so the vibe's mood still leads.
   Incidental background life is welcome ONLY as small, distant flavor — a far-off
   drake, a poro, tiny far-off soldiers, circling birds. NEVER make a person /
   warrior / character the central or foreground subject; no hero in the middle,
   no character portrait or close-up; any figure stays TINY and far away. Never
   name or depict a specific champion, and never add text or logos.
5. The user message MAY name a specific Runeterra region to ground the scene in
   (use that region's ENVIRONMENTAL motifs from the WORLD REFERENCE below). If it
   does NOT, leave the base's setting as a free, non-region environment — do not
   add a region. When a region is used, the base's vibe and energy STILL dominate
   the mood, sky, and lighting — the region only supplies architecture and terrain.
   Never name a champion.
6. Output ONLY the single rewritten caption line — no quotes, no commentary.

{reference}""".format(reference=runeterra_reference())

_PREMIUM_SYSTEM = """\
You are a creative prompt writer for a fine-tuned League of Legends key-art
BACKGROUND model. Given a vibe, an energy, and EXAMPLE captions in the target
style, write ONE brand-new caption for a fresh, original environment.

Rules:
1. Match the EXACT format of the examples:
   lol_keyart, <scene>, <c1> and <c2> palette, <m1> and <m2> mood, cinematic esports key art, highly detailed, <vibe>, <energy>
2. Write a NEW scene inspired by the examples' STYLE — do NOT copy any example.
   Painterly LoL fantasy environment. Scale the scene length to the ENERGY
   directive: ~20-30 words when sparse (chill), up to ~55-70 words when dense
   (explosive).
3. The <energy> token is a DETAIL-DENSITY dial, NOT literal energy: follow the
   ENERGY directive in the user message for how many elements / how much detail
   to pack in — chill = sparse and calm, explosive = maximally busy and detailed
   (the opposite of minimal).
4. The caption MUST end with exactly these two tokens, in order: the given
   <vibe>, then the given <energy>.
5. Compose the shot as the FRAMING in the user message specifies — VARY the
   camera and composition; do NOT always produce a flat, centred wide landscape.
   Whatever the framing, leave one uncluttered OPEN AREA (where the framing puts
   it) clear of any large subject — a hero is composited there later. Incidental
   Runeterra life is welcome ONLY as small, distant background flavor: a far-off
   drake, a poro, tiny far-off soldiers, circling birds. NEVER make a person /
   warrior / character the central or foreground subject; no hero standing in the
   middle, no character portrait or close-up. Any figure must be TINY and far
   away. Never name or depict a specific champion; no text or logos. The user
   message also lists a LIGHT / time-of-day, an ATMOSPHERE, and a FOCAL POINT to
   build the scene around — incorporate them (ENERGY governs how many you
   emphasise; keep sparse scenes clean), adapting the light so the vibe's mood
   still leads.
6. The user message tells you EITHER to set the scene in a specific Runeterra
   region (use that region's ENVIRONMENTAL motifs from the WORLD REFERENCE below,
   so it reads as that place) OR to write a FREE, original environment that is
   NOT tied to any named region. Follow it exactly. When a region is used, the
   requested vibe and energy STILL dominate the mood, sky, and lighting — the
   region only supplies architecture and terrain (a cosmic scene set in a bright
   region becomes that region under a starlit/nebula sky, never plain daylight).
   Either way it must look like painterly LoL key art, and never name a champion.
7. Output ONLY the single caption line — no quotes, no commentary.

{reference}""".format(reference=runeterra_reference())


# Energy is a DETAIL-DENSITY dial (not literal energy): how many elements / how
# much detail the scene packs, from sparse (chill) to maximally busy (explosive).
_ENERGY_DENSITY = {
    "chill": (
        "ENERGY = chill → a CALM, SPARSE scene: only a few elements, lots of open "
        "negative space, one clear focal area, minimal clutter."
    ),
    "balanced": (
        "ENERGY = balanced → a MODERATE scene: several well-placed elements with some "
        "breathing room; neither bare nor busy."
    ),
    "intense": (
        "ENERGY = intense → a BUSY, richly detailed scene: many layered elements, "
        "strong depth, lots happening across the frame."
    ),
    "explosive": (
        "ENERGY = explosive → a MAXIMALLY DENSE, detail-packed scene, the OPPOSITE of "
        "minimal: fill the frame with many elements (structures, terrain, atmosphere, "
        "effects, drifting debris, incidental background life), intricate layered detail "
        "everywhere, dramatic and overwhelming richness — while staying a coherent, "
        "readable cinematic composition (not random noise)."
    ),
}


def _energy_directive(energy: str) -> str:
    """How busy/detailed the scene should be for this energy (density dial)."""
    return _ENERGY_DENSITY.get(energy, _ENERGY_DENSITY["balanced"])


def _region_directive(region: Optional[str], *, mode: str) -> str:
    """One line telling the LLM to ground in `region` (with its motifs) or stay free.

    `mode` is "new" (premium writes a fresh scene) or "enrich" (balanced rewrites
    the base) — only the wording differs.
    """
    if region:
        motifs = RUNETERRA_REGIONS[region]
        verb = "Set this scene in" if mode == "new" else "Ground the scene in"
        return (
            f"{verb} {region} ({motifs}) — use its architecture, terrain, and landmarks so "
            f"it reads as that place, BUT the requested vibe and energy must dominate the "
            f"mood, sky, lighting, and colour (e.g. a cosmic scene = that region under a "
            f"starlit/nebula sky, not its default daylight). Never name a champion."
        )
    if mode == "new":
        return (
            "Write a FREE, original environment — it need NOT be a specific Runeterra "
            "region. Be creative and varied."
        )
    return "Keep the base's setting as-is (no specific region); just enrich it."


# Reconciles the ONLY contradictory pairing: the `minimal` vibe (wants sparse,
# clean) against a dense ENERGY like intense/explosive (wants packed detail).
# Without this, the model collapses to one pole — usually a blank gradient. The
# resolution: one bold, richly-detailed focal subject on a clean, open field.
_MINIMAL_DIRECTIVE = (
    "MINIMAL VIBE: here 'minimal' means a CLEAN, uncluttered composition built "
    "around ONE clear, striking focal subject (a structure, landmark, or natural "
    "feature) with generous negative space around it. It must NEVER be an empty, "
    "blank, or featureless image — there is ALWAYS a clear League-of-Legends "
    "subject. If the ENERGY is dense (intense/explosive), do NOT fill the whole "
    "frame: concentrate all the rich, intricate detail INTO that single focal "
    "subject and keep the surrounding space clean and open."
)


def _variety_directive(variety: Optional[dict]) -> str:
    """
    Turn the sampled creative axes into a directive block. This is what makes two
    captions of the same (vibe, energy) look different — a distinct camera, light,
    atmosphere, and centrepiece each time.
    """
    if not variety:
        return ""
    return (
        "CREATIVE VARIETY (make this scene DISTINCT from other captions of the same "
        "vibe — ENERGY governs how many of these to emphasise; keep sparse scenes clean):\n"
        f"- FRAMING: compose as {variety['framing']}. Do not default to a flat, centred wide landscape.\n"
        f"- LIGHT: {variety['light']} — adapt it so the vibe's mood still leads.\n"
        f"- ATMOSPHERE: {variety['weather']}.\n"
        f"- FOCAL POINT: build the scene around {variety['motif']} "
        "(rendered in the chosen region's materials, when a region is set)."
    )


def _premium_user(
    vibe: str,
    energy: str,
    exemplars: List[str],
    base: str,
    region: Optional[str],
    variety: Optional[dict] = None,
) -> str:
    lines = [
        f"vibe: {vibe}",
        f"energy: {energy}",
        _energy_directive(energy),
        _region_directive(region, mode="new"),
    ]
    if vibe == "minimal":
        lines.append(_MINIMAL_DIRECTIVE)
    variety_block = _variety_directive(variety)
    if variety_block:
        lines += ["", variety_block]
    lines += ["", "EXAMPLES (style reference — do not copy):"]
    lines.extend(f"- {e}" for e in (exemplars or [base]))
    lines.append("")
    lines.append(f"Write ONE new caption ending in: {vibe}, {energy}")
    return "\n".join(lines)


def _enrich_user(base: KeyartPrompt, region: Optional[str], variety: Optional[dict] = None) -> str:
    """User message for the balanced tier: the base caption + energy/region/variety directives."""
    variety_block = _variety_directive(variety)
    minimal_block = f"\n{_MINIMAL_DIRECTIVE}" if base.vibe == "minimal" else ""
    tail = f"\n\n{variety_block}" if variety_block else ""
    return (
        f"{_energy_directive(base.energy)}\n{_region_directive(region, mode='enrich')}{minimal_block}{tail}\n\n"
        f"Base caption to rewrite:\n{base.prompt}"
    )


# ---------------------------------------------------------------------------
# Validation — reject anything that drifts off the training-caption grammar
# ---------------------------------------------------------------------------
def _is_valid(prompt: str, trigger: str, vibe: str, energy: str) -> bool:
    p = (prompt or "").strip()
    return (
        p.startswith(f"{trigger}, ")
        and p.endswith(f", {vibe}, {energy}")
        and " palette," in p
        and " mood," in p
        and "cinematic esports key art, highly detailed" in p
        and len(p.split()) >= 12
    )


def _try(fn) -> Optional[str]:
    """Run an LLM step; any failure -> None (caller falls back to the bank)."""
    try:
        out = fn()
        return out.strip() if isinstance(out, str) and out.strip() else None
    except Exception:  # noqa: BLE001 — never let prompt work break generation
        return None


def build_prompt(
    input_data: dict,
    *,
    tier: str = "balanced",
    seed: Optional[int] = None,
    llm: Optional[PromptLLM] = None,
    store: Optional[CaptionStore] = None,
) -> KeyartPrompt:
    """
    Build a key-art prompt at the requested tier, always returning a valid,
    in-distribution `KeyartPrompt`.

    - `tier`: "economy" | "balanced" | "premium" (also accepts "low"/"medium"/
      "high"). Falls back one level whenever the required dependency is missing.
    - `llm`: required for balanced/premium; if None → behaves as economy.
    - `store`: optional RAG exemplar source for premium; if None → premium still
      runs using the bank base as its single style example.

    The bank base is ALWAYS computed first, so any failure downstream returns a
    guaranteed-valid prompt.
    """
    tier = _QUALITY_TO_TIER.get(tier, tier)
    if tier not in ("economy", "balanced", "premium"):
        raise ValueError(f"Unknown tier: {tier!r}")

    base = build_keyart_prompt(input_data, seed=seed)
    if tier == "economy" or llm is None:
        return base

    # Decide region grounding + creative variety per prompt (reproducible with the
    # caption seed, from ONE rng so a fresh seed → a fresh region + framing + light
    # + weather + focal motif). A specific region ~half the time, a free non-region
    # scene otherwise; the variety axes make same-combo scenes look different.
    rng = random.Random(base.seed)
    region = choose_region(base.vibe, rng)
    variety = choose_variety(rng)

    if tier == "balanced":
        candidate = _try(
            lambda: llm.complete(system=_ENRICH_SYSTEM, user=_enrich_user(base, region, variety))
        )
    else:  # premium
        exemplars = _try(lambda: "\n".join(store.retrieve(base.vibe, base.energy, 5))) if store else None
        exemplar_list = exemplars.split("\n") if exemplars else []
        user = _premium_user(base.vibe, base.energy, exemplar_list, base.prompt, region, variety)
        candidate = _try(lambda: llm.complete(system=_PREMIUM_SYSTEM, user=user))

    if candidate and _is_valid(candidate, base.trigger, base.vibe, base.energy):
        return replace(base, prompt=candidate)
    return base  # fallback — in-distribution, never fails


# ---------------------------------------------------------------------------
# A simple, no-embeddings CaptionStore: retrieve real training captions filtered
# by vibe (and preferring the same energy). Good enough to start; swap for an
# embedding-based store later without touching build_prompt.
# ---------------------------------------------------------------------------
class VibeFilterStore:
    """Retrieve in-distribution exemplars by matching the trailing vibe token."""

    def __init__(self, captions: List[str], *, rng: Optional[random.Random] = None):
        self._rng = rng or random.Random()
        self._by_vibe: dict[str, List[str]] = {}
        for c in captions:
            c = c.strip()
            toks = [t.strip() for t in c.split(",")]
            if len(toks) >= 2:
                self._by_vibe.setdefault(toks[-2], []).append(c)

    @classmethod
    def from_dir(cls, path, **kw) -> "VibeFilterStore":
        from pathlib import Path

        caps = [
            p.read_text(encoding="utf-8", errors="replace").strip()
            for p in Path(path).glob("*.txt")
            if p.stem != "metadata"
        ]
        return cls([c for c in caps if c], **kw)

    def retrieve(self, vibe: str, energy: str, k: int) -> List[str]:
        pool = self._by_vibe.get(vibe) or [c for cs in self._by_vibe.values() for c in cs]
        if not pool:
            return []
        same_energy = [c for c in pool if c.endswith(f", {energy}")]
        chosen = same_energy if len(same_energy) >= k else pool
        return self._rng.sample(chosen, min(k, len(chosen)))


def load_caption_store(settings=None) -> Optional["VibeFilterStore"]:
    """Load the RAG exemplar store from `settings.keyart_captions_dir`.

    Returns None if the directory is missing/empty, so the premium tier simply
    falls back to the bank base rather than erroring.
    """
    from esports_poster_ai.config import get_settings

    s = settings or get_settings()
    path = s.keyart_captions_dir
    if not path.exists():
        return None
    store = VibeFilterStore.from_dir(path)
    return store if store._by_vibe else None


__all__ = [
    "QualityTier",
    "PromptLLM",
    "CaptionStore",
    "VibeFilterStore",
    "load_caption_store",
    "build_prompt",
]
