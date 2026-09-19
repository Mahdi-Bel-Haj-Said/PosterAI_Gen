"""
Poster-type-specific prompt blocks (Step 2 adaptation).
"""

POSTER_TYPE_BLOCKS = {
    "gameday": """
IF GAMEDAY:
  - Hero title: "GAMEDAY" — largest text element on poster
  - Show both team logos facing each other with VS divider between them
  - Display: match time + timezone, stream platform + URL (if provided), tournament name + phase (if provided)
  - If a featured player image is provided: render that player LARGE and prominent
    as a central hero figure of the poster — foreground, scene-lit, integrated;
    never a small accent and never hidden behind the logos
  - Teaser/hype sentence at bottom matching the scene energy
    """.strip(),
    "game_results": """
IF GAME_RESULTS:
  - Hero title: "MATCH RESULTS" or "GG" — largest text element
  - Show both team logos with the series score between them
  - Winner logo: larger, brighter, elevated — loser logo: slightly smaller, cooler tone
  - Score format depends on game (injected dynamically — see game_rules block)
  - MVP section at bottom if provided: player name + stat
  - If a featured player image is provided: render that player LARGE and prominent
    as a central hero figure of the poster — foreground, scene-lit, integrated;
    never a small accent and never hidden behind the logos
  - Victory/defeat mood must influence visual treatment
    """.strip(),
    "roster_reveal": """
IF ROSTER_REVEAL:
  - Hero title: "THE ROSTER" or "MEET THE TEAM" — largest text element
  - Team logo: large and prominent
  - Present up to 5 players. HOW they are arranged is set by the ROSTER
    ARRANGEMENT block — do NOT default to five rectangular cards in a row
  - Each player: IGN (large) + role (small) + photo ONLY IF a photo is provided
    for that player + flag (if provided)
  - Players WITHOUT a provided photo: render their IGN + role as TEXT ONLY and NO
    portrait — a neutral faceless silhouette or a monogram at most. NEVER invent,
    generate, or hallucinate a face/headshot for a player whose photo was not
    supplied (a fabricated face is a hard failure).
  - NEW badge beside players where is_new_signing is true
  - Head coach name at bottom if provided
  - Season / split identifier at bottom if provided
    """.strip(),
    "tournament_announcement": """
IF TOURNAMENT_ANNOUNCEMENT:
  - Hero title: tournament name or tagline — largest text element
  - Tournament logo if available, else bold stylized text treatment
  - PRIZE POOL (if provided): the HEADLINE FACT. Render the amount larger and
    louder than every other value here. It is the single strongest reason a team
    enters, and it must be the first thing read after the hero title
  - Start date + location (if provided): clearly SMALLER than the prize pool
  - "X TEAMS COMPETING" if teams_count provided: smaller still
  - Format / circuit if provided: minor, quiet reference detail
  - Tagline and sub-tagline if provided
    """.strip(),
    "tournament_banner": """
IF TOURNAMENT_BANNER (landscape format):
  - Wide cinematic composition — content spread horizontally
  - Tournament name or logo as the dominant element
  - PRIZE POOL (if provided): the HEADLINE FACT. Give it its own position and
    visibly more weight than every other value — never pair it with the location
    as an equal, and never let the date outsize it
  - Date range and location: placed separately, clearly smaller than the prize pool
  - Tagline centered or integrated into the composition
    """.strip(),
}
