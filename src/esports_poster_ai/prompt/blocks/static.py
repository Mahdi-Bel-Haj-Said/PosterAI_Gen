"""
Static prompt blocks that never change regardless of game, poster type, or mode.

BACKGROUND_ANALYSIS_BLOCK: instructs GPT-4o to analyze the background image
  (STEP 1) before writing the image-generation prompt.
FACTUAL_TEXT_BLOCK: hard rule — render METADATA verbatim, invent nothing.
OUTPUT_RULES_BLOCK: STEP 3 template + universal poster generation rules.

`build_fact_hierarchy_block` is the one thing here that varies: the ranking rule
is static, but the prize pool is promoted to headline fact when the brief has one.
"""

from __future__ import annotations

from typing import Any, Dict


FACTUAL_TEXT_BLOCK = """
CRITICAL — FACTUAL TEXT IS VERBATIM, INVENT NOTHING:
The METADATA above is the ONLY source of factual content for this poster.
Every factual value — team names, scores, dates, times, tournament name,
phase, format, stream, player names — must appear on the poster EXACTLY as
written in METADATA, character for character.

- Do NOT invent, guess, complete, "correct", or embellish any factual value.
- Do NOT add a tournament name, date, time, score, phase, or format that is
  not present in METADATA. If a field is absent from METADATA it does NOT
  appear on the poster — leave that zone as atmospheric fill instead.
- Do NOT use real-world knowledge about the teams, players, or tournament.
  Treat the logos purely as graphics — never infer a real event, real score,
  real date, or real result from them.
- Do NOT use logos from the internet other than Twitch logo , kick logo , League of legends logo and valorant logo if needed
- Render every digit of every score EXACTLY as given. If METADATA says the
  series score is "2 — 3", the poster must read "2 — 3" — never any other
  numbers. The same applies to the match format (e.g. "bo5", not "bo3").
- The winner is whichever team METADATA marks as the winner — never decide
  the winner yourself, and never contradict it.
- When you write the image-generation prompt, copy these factual values into
  it verbatim, and include an explicit instruction that GPT-Image-2 must
  render them exactly and add no other text.
- Any text on the poster that is not in METADATA must be purely decorative
  (hero title, hype/result phrase) — it must never look like factual data.
- FIELD NAMES ARE NOT POSTER COPY: in METADATA the text before each colon is a
  field name written for YOU. Never render "Game", "Poster Type", "Tagline",
  "Sub-tagline", "Headline statement", or "Supporting statement" on the poster.
  A short caption above a DATA value (PRIZE POOL, START DATE, LOCATION, FORMAT)
  is normal poster design and is allowed. Creative copy is different: a tagline
  is a styled statement and NEVER gets a caption, a label, or quotation marks
  — rendering the word "TAGLINE" on the poster is a hard failure.
""".strip()


FACT_HIERARCHY_BLOCK = """
FACT HIERARCHY — THE FACTS ARE NOT ALL EQUALLY IMPORTANT:
The hero title rule above is unchanged — it stays the single largest text
element on the poster. This rule governs everything BELOW it: the factual values
must NOT all be rendered at one shared size.

Rank the factual values from METADATA into three weights and state the ranking
in your output prompt:
- HEADLINE FACT — choose exactly ONE: the single value that most makes a viewer
  act on this poster. Render it as the largest factual element, roughly half the
  hero title's cap height, in the accent color and with its own breathing room.
- SUPPORTING FACTS — two or three values: roughly half the headline fact's size.
  Clean and clearly legible, but visibly subordinate to it.
- MINOR FACTS — everything else: small and quiet. A single clean row, a caption
  line, or a corner. Reference detail, not a feature.

How to rank: the value that is UNIQUE or DIFFERENTIATING outranks the value that
is generic or expected. Prize pool, kickoff time, and a series score sell a
poster; entry format, team count, circuit name, season labels, and phase names
are reference detail a viewer reads only after they already care. Where the
poster type has an obvious headline — the series score on a results poster —
use it.

This OVERRIDES the natural symmetry of the chosen layout pattern: in a Bento
Grid the headline fact takes a visibly larger cell than the others; in a Radial
layout it sits at the hub; in a Progressive layout it opens or closes the run.

Creative copy (the CREATIVE COPY lines in METADATA — tagline, sub-tagline) is
NOT a fact and takes NO part in this ranking. It is stylized TIER 1 text with its
own treatment, and it never appears as a labelled row.

Do NOT render the facts as a row of equal icon + label cells at one uniform size
— that is the exact failure this rule exists to prevent.
""".strip()


# When a prize pool is present it is named as the headline fact outright, rather
# than left to the model's ranking. The generic rule below already says a prize
# pool "sells a poster", but in practice the model kept rendering it as one more
# equal chip in a row of venue / format / team-count — so the money, the single
# strongest reason to enter, read no louder than the bracket type.
_PRIZE_POOL_HEADLINE = """
HEADLINE FACT FOR THIS POSTER — DECIDED, NOT A SUGGESTION:
This poster has a PRIZE POOL. It IS the headline fact. Render the prize-pool
value as the largest and most prominent factual element on the poster — roughly
half the hero title's cap height, in the accent color, with its own breathing
room and clear separation from every other value.
- It must be unmistakably larger and louder than the venue, the dates, the
  format, the team count, the circuit, and the stream handle. A viewer skimming
  the poster reads the hero title, then the prize pool, then everything else.
- SPECIFICALLY: the prize-pool value is rendered LARGER than the date and LARGER
  than the location. If the date and the venue are set at one size, the prize
  pool is set visibly bigger than both — not equal to them, and never smaller.
- It does NOT belong in a small caption strip along the bottom edge, and it is
  not grouped with FORMAT, CIRCUIT, or TEAM COUNT. Those are minor facts; the
  prize pool sits in the main composition with the prominent content.
- It never sits as one equal chip in a row of identical labelled pills. If other
  facts are presented as a row, the prize pool is lifted OUT of that row and
  given its own weight and position.
- Its caption (PRIZE POOL) stays small; the VALUE is what carries the size. The
  amount itself is the element that must catch the eye — a large caption over a
  small number is the wrong way round.
""".strip()

# The one poster type where something outranks the money: on a results poster the
# score is the whole point, and the prize pool is history by then.
_SCORE_HEADLINE_TYPES = {"game_results"}


def headline_prize_pool(input_data: Dict[str, Any]) -> str:
    """The prize-pool value when it should be this poster's headline fact, else ""."""
    if not isinstance(input_data, dict):
        return ""

    meta = input_data.get("_meta")
    poster_type = meta.get("poster_type") if isinstance(meta, dict) else None
    if poster_type in _SCORE_HEADLINE_TYPES:
        return ""

    tournament = input_data.get("tournament")
    prize = tournament.get("prize_pool") if isinstance(tournament, dict) else None
    if isinstance(prize, (int, float)):
        return str(prize)
    if isinstance(prize, str) and prize.strip():
        return prize.strip()
    return ""


def build_fact_hierarchy_block(input_data: Dict[str, Any]) -> str:
    """Fact hierarchy, with the prize pool promoted to headline when present."""
    if not headline_prize_pool(input_data):
        return FACT_HIERARCHY_BLOCK
    return FACT_HIERARCHY_BLOCK + "\n\n" + _PRIZE_POOL_HEADLINE


def build_image_prize_pool_rule(input_data: Dict[str, Any]) -> str:
    """
    The prize-pool emphasis, restated for the prompt gpt-image-2 actually sees.

    The FACT HIERARCHY block lives in GPT-4o's prompt, so whether the emphasis
    survives depends on GPT-4o writing it into the prompt it produces — and in
    practice it kept arriving as one more small labelled chip. This is the same
    telephone-hop fix already used for the factual data and the style directives:
    say it again, verbatim, on the prompt the image model receives.

    Returns "" when no prize pool applies.
    """
    prize = headline_prize_pool(input_data)
    if not prize:
        return ""
    return (
        "=== SIZE OF THE PRIZE POOL — NON-NEGOTIABLE ===\n\n"
        f'The prize pool is "{prize}". It is the most prominent factual element on\n'
        "this poster — second in visual weight only to the hero title itself.\n"
        "- Render it BIGGER than the date. Render it BIGGER than the location.\n"
        "  Bigger than the format, the team count, and the circuit.\n"
        "- Roughly half the hero title's cap height, in the accent color, with\n"
        "  clear space around it.\n"
        "- Do NOT place it in a small caption strip along the bottom edge, and do\n"
        "  NOT set it as one equal chip in a row with FORMAT or TEAM COUNT.\n"
        "- Its caption (PRIZE POOL) stays small — the AMOUNT is what must be seen\n"
        "  first. A big label over a small number is wrong."
    )


BACKGROUND_ANALYSIS_BLOCK = """
You are an expert esports creative director and visual prompt engineer specializing
in generating detailed image generation prompts for my image generation models.

You will be given:
1. A background image to analyze
2. Match/event metadata

Your job is to:
1. Deeply analyze the background image
2. Generate a single, exhaustive image generation prompt that instructs my image generation model
   to create a professional esports poster using that background

---

STEP 1 — BACKGROUND ANALYSIS:
Analyze the background image and extract the following:

SCENE:
- Describe the main character(s) or subject(s): pose, position, facing direction
- Describe all background elements: environment, objects, textures
- Identify any existing light sources and their color/direction
- Identify any existing effects: particles, sparks, smoke, bokeh, motion blur
- Describe the overall mood and energy of the scene

COLOR PALETTE:
- Extract 5-6 dominant colors with approximate hex values
- Identify the primary accent color (most vibrant/energetic color in scene)
- Identify shadow and midtone colors
- Note any color temperature (warm/cool/neutral)

LIGHTING:
- Main light source: position, color, intensity
- Secondary light sources if any
- Shadow direction and softness
- Rim lighting or glow effects present

EMPTY ZONES:
- Identify all areas of the image that are relatively empty or dark
- Map them by position: top-left, top-center, top-right,
  center-left, center, center-right, bottom-left, bottom-center, bottom-right
- These zones are where poster content will be placed
""".strip()


OUTPUT_RULES_BLOCK = """
---

STEP 3 — GENERATE THE FULL PROMPT:
Now write the complete image generation prompt using everything above.
The prompt must follow this exact structure:

\"\"\"
BACKGROUND ANALYSIS:
[your full scene description — characters, environment, light sources, effects, mood]

COLOR PALETTE:
[extracted colors with hex values, accent color, shadow/midtone, temperature]

LIGHTING:
[full lighting description — main source, secondary, rim light, shadow direction]

MOOD & ATMOSPHERE:
[mood description derived from the scene]

FACTUAL CONTENT — render exactly, verbatim, invent nothing:
[Copy here EVERY factual value from the METADATA block — team names, series
score, winner, date, time, format, tournament name, phase, stream, player
names — exactly as given, character for character. This is the ONLY text
content allowed on the poster. Do not add any name, score, date, or
tournament not listed here. Then instruct GPT-Image-2 to render these values
exactly and add no other text.]

---

FACT HIERARCHY:
[state which single value is the HEADLINE fact, which two or three are
SUPPORTING, and which are MINOR, with their relative sizes — per the fact
hierarchy rule. Every factual value must land in one of the three.]

---

POSTER GENERATION INSTRUCTIONS:
Using this background as the scene foundation, create a cinematic professional
esports poster. Follow every instruction below with precision.

PRESERVE FROM BACKGROUND — NON-NEGOTIABLE:
- Keep every existing visual element intact: characters, environment, particles,
  lighting, smoke, bokeh, and all atmospheric effects
- Do not alter the main character's pose, position, or facing direction
- Do not move, recolor, or remove any existing light source
- Maintain all existing color temperature and grading
- The background is the foundation — build on top of it, never replace it

HERO TITLE:
- Text: [DETERMINED BY POSTER TYPE — see Step 2]
- Must be the single largest text element on the entire poster — larger than
  team names, player names, tournament name, and all other text
- Position: [best empty zone identified in Step 1]
- Font: a bold display typeface — its exact SHAPE and FINISH vary per poster and
  are specified in the TYPOGRAPHY DIRECTION block near the end. Do NOT default to
  the same chunky wide metallic block every time.
- TEXT EFFECT INTENSITY — the hero title's scene integration is SCALED by the
  ENERGY LEVEL given in the VISUAL STYLE block (or the Style DNA in consistency
  mode). Apply ONLY the effects listed for that level and no others. If no energy
  level is given, use BALANCED. Whatever the level, this integration is for the
  HERO TITLE ONLY; factual text (scores, team names, dates, tournament) stays
  clean and legible — see the TYPOGRAPHY SYSTEM section.
  * chill — clean letterforms. Directional light from the main light source,
    matching its color and angle, and NOTHING else. No texture on the letters,
    no particles, no chromatic aberration, no glow bleed.
  * balanced — directional light, PLUS a soft light wrap in the accent color
    along the letter edges facing the light, PLUS the scene texture on the letter
    surfaces at a LOW 15–25% opacity. NO particles or sparks crossing the
    letters, NO chromatic aberration, NO debris in front of the text, NO glow
    bleeding out from the letterforms.
  * intense — everything in balanced, with the letter texture raised to
    30–40%, the scene's particle/spark effect drawn AROUND the letters, and
    subtle chromatic aberration on the letter edges.
  * explosive — the full stack: texture at 40–50%, the dominant
    particle/energy effect bleeding INTO and THROUGH the letters, the background
    pattern peeking from BEHIND them where they cross dark areas, chromatic
    aberration, and scene debris floating IN FRONT of some letters to break the
    text plane.
  * LEGIBILITY FLOOR — applies to intense and explosive, and OVERRIDES the two
    lines above wherever they conflict. These levels add drama to the title, not
    damage:
      - Every letter keeps its full shape. The core stroke of each glyph stays
        unbroken, uncovered, and instantly readable — a viewer must be able to
        read the title in one glance, at a distance, without effort.
      - Debris and particles in front of the text may cross the OUTER EDGES of a
        few letters only. They never sit across a letter's centre, never bridge
        two letters into one shape, and never obscure a whole character.
      - Effects concentrate around and behind the word, not evenly over it. Keep
        the area immediately inside the letterforms clean enough that the shape
        reads against whatever is behind it.
      - If an effect would make any character ambiguous, drop that effect. A
        clean explosive title beats a dramatic unreadable one every time.
  * A calmer level is NOT a weaker poster. At chill or balanced, a cleanly lit
    title with crisp edges is the CORRECT result — do not add effects back in
    because the title looks "too plain".

ASSETS — handle each asset according to what was provided:
- Team logos: integrate naturally into the scene — they must feel lit by the
  existing light source, not pasted on top. Apply subtle rim glow matching
  the scene's accent color around logo edges. Never place logos on a flat
  colored background or card.
- Featured player image (if provided): a player photo is supplied as one of the
  reference images. Render the player LARGE and prominent — a primary hero
  subject of the poster, in the foreground. Never make the player a small accent
  and never hide them behind the logos or hero title. You MAY freely resize,
  crop, re-frame, or cut the player out of their original background to make
  them fit the poster — the photo does NOT need to match the poster's aspect
  ratio. Crop to a head-and-shoulders or waist-up framing if that integrates
  better into the available space. Integrate the result as a scene-lit cutout:
  apply the background's light direction, color temperature, and shadows so the
  player belongs in the scene. Preserve the player's likeness.
- Tournament logo (if provided): the ACTUAL tournament logo is supplied as one
  of the reference images. Reproduce it EXACTLY as given — do not redraw,
  restyle, recolor, re-letter, re-typeset, stretch, crop, or add effects,
  textures, glows, particles, or chromatic aberration to the mark itself. Keep
  its own colors, its own typeface, its proportions, and its aspect ratio. It is
  a brand asset to be placed, not artwork to reinterpret. Place it in a zone that
  does not compete with the hero title, smaller than the team logos. You MAY
  match its overall brightness to the surrounding scene so it does not look
  pasted on — that is a brightness match only, and nothing about the mark
  itself changes.
- Org logo (if provided): place discreetly in a corner. Small. Subtle glow only.
- If an asset is NOT provided: fill that zone with atmospheric effects
  extended naturally from the background — particles, energy streams, smoke
  tendrils, or depth layers. Never leave any zone flat or empty.

LAYOUT — follow ONE layout pattern:
LAYOUT PATTERN: [name the single pattern you chose in Step 2.5, plus one line on
why it fits this format, this amount of content, and this background]

Map all metadata and assets onto that pattern, using the empty zones identified
in Step 1. Place every content element (hero title, logos, score, factual text)
in the deliberate position the chosen pattern dictates — do not fall back to a
generic top / middle / bottom stack unless the chosen pattern IS that. How much
atmospheric fill the remaining space receives is governed by COMPOSITION DENSITY
below — follow the visual style.

[Then list every element and where the pattern puts it — hero title, each logo,
the score, the factual text, the corners — naming positions concretely, e.g.
"hero title: upper-left anchor of the diagonal", "team logos: the two large
bento cells", "score: centre of the radial ring".]

COMPOSITION DENSITY — governed by the visual style (the VISUAL STYLE block,
or the Style DNA in consistency mode). The visual style's directives OVERRIDE
the defaults in this section:
- Default, for energetic / dense styles (cyberpunk, fire & energy, cosmic,
  dark fantasy): extend particle effects, energy arcs, and smoke from the main
  character or light source; apply low-opacity texture overlays to flat zones;
  use depth layers with foreground atmospheric elements. Avoid a completely
  empty, flat, uninteresting frame.
- HOW FAR those effects spread is set by the EFFECT BUDGET in the VISUAL STYLE
  block, not by this rule and not by the vibe. This line says what the effects
  are made of; the budget says how much of the frame they may cover. Filling
  every corner because the vibe is "dense" is the failure, not the goal — a
  calm area is atmosphere, not a hole to plug.
- For a minimal / restrained style: do the OPPOSITE — embrace generous
  negative space, keep the composition calm and uncluttered, use few elements
  and sparse, subtle effects. Clean, intentionally empty areas are correct —
  do not fill them.

QUIET ZONES — applies at EVERY density and energy level, and OVERRIDES the
"avoid large dead, flat areas" default wherever they conflict:
- Density belongs to the SCENE, not to the text. Behind and immediately around
  the hero title, the factual values, the logos, and the sponsor strip, the
  background stays calm: no competing sparks, debris, hot highlights, or busy
  pattern directly behind text.
- A high-energy poster is a calm frame with ONE loud focal area, not a frame
  that is loud everywhere. If everything glows, nothing reads as the focus.
- Keep a clear contrast step between text and whatever sits behind it. Where the
  scene is bright and busy, darken or soften that patch; where it is dark, let
  the text carry the light.
- Some quiet area is a feature, not a gap to fill. A poster that is uniformly
  busy edge to edge is a FAILURE of this rule, however energetic the brief.

TYPOGRAPHY SYSTEM — TWO TIERS of text, treated very differently:

TIER 1 — STYLIZED TEXT (hero title, and creative copy: hype / result / reveal
phrase). This text is a visual centerpiece:
- Hero title: a bold display face — its typeface + finish are set by the
  TYPOGRAPHY DIRECTION block (vary it per poster, don't reuse the same look); the
  single largest text element; fully integrated into the scene per the HERO TITLE
  rules above (particles, texture, light wrap, chromatic aberration).
- Creative copy: styled per the TYPOGRAPHY DIRECTION block, clearly differentiated
  from BOTH the hero title and the factual text.

TIER 2 — FACTUAL TEXT (team names, series score, date, time, format,
tournament name, phase, stream info, player IGNs). This text carries the
poster's real information and MUST be clean and instantly legible —
legibility beats scene integration:
- Crisp, sharp glyphs with high contrast against their zone. Minimal texture
  on the letterforms. NO particles, debris, smoke, or chromatic aberration
  crossing or breaking the characters.
- It may sit in a clean zone or a subtle scene-lit panel if that improves
  readability — a clean, readable factual element is correct, not a flaw.
- Series score (results posters): large, bold, crisp, unmistakable — one of
  the most prominent elements after the hero title; every digit exact.
- Every OTHER factual value is sized by the FACT HIERARCHY block — NOT all at
  one shared size. Its headline fact is large and unmistakable, its supporting
  facts clearly smaller, and its minor facts (typically circuit, format, team
  count, season, phase, stream handle) small and lightweight, placed where they
  do not compete with the hero title or logos.

TIER 2A — THE HEADLINE VALUE (the one fact named as HEADLINE VALUE in METADATA,
or chosen as the headline fact). It is factual text, so it stays crisp and exact
— but it is NOT styled like the rest of Tier 2:
- It gets DISPLAY treatment: big, heavy numerals, the accent color, its own
  breathing room. Think of it as the second-loudest thing on the poster after the
  hero title, not as the first row of a data table.
- It does NOT share a component with the other facts. Where the date, location,
  format and team count sit together — a stack of pills, a row of icon chips, a
  footer strip, a bordered panel — the headline value is NOT one of those
  members. It lives outside that group, in its own space.
- If the other facts carry a small icon each, the headline value does not get a
  matching icon at a matching size. Matching furniture is what makes it read as a
  peer.
- Size it against the facts around it: its digits are at least TWICE the cap
  height of the date. If a viewer cannot tell at a glance which value the poster
  is selling, this rule has failed.
- Factual text uses the extracted palette / team accent colors — but never at
  the cost of contrast and readability.

All fonts share the visual language of the background — sharp and electric for
aggressive neon scenes, refined and dramatic for dark cinematic scenes.

COLOR GRADING — strict rules:
- All new elements must use ONLY the colors extracted in Step 1
- Each team's elements (logo zone, name) use only that team's logo colors
- Do not introduce any color that does not exist in the extracted palette
- Overall tone must match the background's color temperature exactly
- Winner elements (in results posters) receive brighter treatment;
  loser elements receive desaturated/cooler treatment — using only palette colors

DO NOT:
- Blend two layout patterns, or abandon the chosen pattern partway — one
  pattern governs the whole composition
- Override the visual style: do not fill or clutter the composition when the
  visual style is minimal — minimal means negative space; keep it
- Leave large dead, flat areas when the visual style is dense / energetic
- Apply particle/texture integration or chromatic aberration to FACTUAL text
  (scores, names, dates, tournament) — that text stays clean and legible;
  heavy scene integration is for the hero title only
- Invent, add, or alter any factual text — names, scores, dates, tournament
  names: render only what the metadata provides (see the verbatim-text rule)
- Place logos or text on bright white, black, or solid-colored backgrounds or cards
- Redraw, restyle, recolor, re-letter, or add effects, textures, or particles to
  ANY provided logo (team, tournament, or game wordmark) — every supplied mark
  is reproduced exactly as given. Scene lighting may fall around a logo; it never
  rewrites the mark
- Introduce colors outside the extracted palette from Step 1
- Make the hero title smaller than any other text element
- Hide the hero title behind other elements — it must always be fully readable
- Add a vignette or color grade that changes the background's existing mood
- Duplicate or echo the background image — use it once as the foundation only
- Generate placeholder text, brackets, or template labels in the output poster
- Render a METADATA field name as visible text — especially "TAGLINE" or
  "SUB-TAGLINE", which must never appear on the poster in any form
[add any background-specific don'ts based on your Step 1 analysis]
\"\"\"

---

IMPORTANT RULES:
- The final prompt must be self-contained and ready to paste directly into
  GPT Image with no modifications needed
- Be extremely specific about positions, sizes, colors, and effects
- Never use vague words like "good", "nice", or "beautiful" —
  replace with concrete visual instructions every time
- Always describe exactly how the hero title interacts with the scene's light
  and texture — but ONLY at the intensity the energy level allows. Never
  describe particles crossing the letters, chromatic aberration, or glow bleed
  at chill or balanced energy
- Output ONLY the final prompt inside triple quotes — no explanation,
  no preamble, no commentary before or after
""".strip()
