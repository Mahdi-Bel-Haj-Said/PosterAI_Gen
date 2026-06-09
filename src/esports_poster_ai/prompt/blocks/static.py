"""
Static prompt blocks that never change regardless of game, poster type, or mode.

BACKGROUND_ANALYSIS_BLOCK: instructs GPT-4o to analyze the background image
  (STEP 1) before writing the image-generation prompt.
FACTUAL_TEXT_BLOCK: hard rule — render METADATA verbatim, invent nothing.
OUTPUT_RULES_BLOCK: STEP 3 template + universal poster generation rules.
"""


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
""".strip()


BACKGROUND_ANALYSIS_BLOCK = """
You are an expert esports creative director and visual prompt engineer specializing
in generating detailed image generation prompts for GPT Image models.

You will be given:
1. A background image to analyze
2. Match/event metadata

Your job is to:
1. Deeply analyze the background image
2. Generate a single, exhaustive image generation prompt that instructs GPT-Image-2
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
- Font: ultra-bold, wide/expanded, all-caps
- MANDATORY text integration into the scene — all of the following apply.
  This heavy integration is for the HERO TITLE ONLY; factual text (scores,
  team names, dates, tournament) is kept clean and legible — see the
  TYPOGRAPHY SYSTEM section:
  * The scene's dominant particle/spark/energy effect bleeds INTO and AROUND
    the letters — not behind them, physically through them
  * Apply the scene's dominant texture onto letter surfaces at 40–50% opacity
  * Letters receive directional light from the main light source —
    matching color, angle, and intensity exactly
  * Light wrap: the primary accent color glows softly along letter edges
    facing the main light source
  * The background texture or pattern peeks out from BEHIND the letters
    at zones where letters overlap dark areas
  * Subtle chromatic aberration on letter edges — color split matching scene energy
  * Scene particles and debris float IN FRONT of some letters, breaking the
    text plane — this makes the title feel embedded in the scene, not pasted

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
- Tournament logo (if provided): place in a zone that does not compete with
  the hero title. Smaller than team logos. Apply scene lighting.
- Org logo (if provided): place discreetly in a corner. Small. Subtle glow only.
- If an asset is NOT provided: fill that zone with atmospheric effects
  extended naturally from the background — particles, energy streams, smoke
  tendrils, or depth layers. Never leave any zone flat or empty.

LAYOUT — assign every piece of content to a specific zone:
Map all metadata and assets to the empty zones identified in Step 1.
Place every content element (hero title, logos, score, factual text) in a
clear, deliberate zone. How much atmospheric fill the remaining zones receive
is governed by COMPOSITION DENSITY below — follow the visual style.

TOP ZONE: [assign content or atmospheric fill]
MIDDLE ZONE: [assign content or atmospheric fill]
BOTTOM ZONE: [assign content or atmospheric fill]
CORNERS: [assign org logo, tournament phase badge, or atmospheric fill]

COMPOSITION DENSITY — governed by the visual style (the VISUAL STYLE block,
or the Style DNA in consistency mode). The visual style's directives OVERRIDE
the defaults in this section:
- Default, for energetic / dense styles (cyberpunk, fire & energy, cosmic,
  dark fantasy): extend particle effects, energy arcs, and smoke from the main
  character or light source into empty corners and edges; apply low-opacity
  texture overlays to flat zones; use depth layers with foreground atmospheric
  elements. Avoid large dead, flat areas.
- For a minimal / restrained style: do the OPPOSITE — embrace generous
  negative space, keep the composition calm and uncluttered, use few elements
  and sparse, subtle effects. Clean, intentionally empty areas are correct —
  do not fill them.

TYPOGRAPHY SYSTEM — TWO TIERS of text, treated very differently:

TIER 1 — STYLIZED TEXT (hero title, and creative copy: hype / result / reveal
phrase). This text is a visual centerpiece:
- Hero title: ultra-bold, wide, all-caps; the single largest text element;
  fully integrated into the scene per the HERO TITLE rules above (particles,
  texture, light wrap, chromatic aberration).
- Creative copy: italic or condensed, matching scene energy, clearly
  differentiated from the factual text.

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
- Match details (time, date, format), tournament info, stream info: smaller,
  clean, lightweight; placed where they do not compete with the hero title
  or logos.
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
- Override the visual style: do not fill or clutter the composition when the
  visual style is minimal — minimal means negative space; keep it
- Leave large dead, flat areas when the visual style is dense / energetic
- Apply particle/texture integration or chromatic aberration to FACTUAL text
  (scores, names, dates, tournament) — that text stays clean and legible;
  heavy scene integration is for the hero title only
- Invent, add, or alter any factual text — names, scores, dates, tournament
  names: render only what the metadata provides (see the verbatim-text rule)
- Place logos or text on bright white, black, or solid-colored backgrounds or cards
- Introduce colors outside the extracted palette from Step 1
- Make the hero title smaller than any other text element
- Hide the hero title behind other elements — it must always be fully readable
- Add a vignette or color grade that changes the background's existing mood
- Duplicate or echo the background image — use it once as the foundation only
- Generate placeholder text, brackets, or template labels in the output poster
[add any background-specific don'ts based on your Step 1 analysis]
\"\"\"

---

IMPORTANT RULES:
- The final prompt must be self-contained and ready to paste directly into
  GPT Image with no modifications needed
- Be extremely specific about positions, sizes, colors, and effects
- Never use vague words like "good", "nice", or "beautiful" —
  replace with concrete visual instructions every time
- The text integration section is non-negotiable — always describe exactly
  how the hero title interacts with the scene's physics, light, and texture
- Output ONLY the final prompt inside triple quotes — no explanation,
  no preamble, no commentary before or after
""".strip()
