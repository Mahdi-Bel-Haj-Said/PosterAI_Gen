// wizard.jsx — 5-step Create Poster wizard (wired to FastAPI backend)

const STEPS = [
  { n: 1, code: "01", title: "Game & type",   sub: "Pick the canvas" },
  { n: 2, code: "02", title: "Poster data",   sub: "Fill in the match" },
  { n: 3, code: "03", title: "Visual style",  sub: "Set the vibe" },
  { n: 4, code: "04", title: "Format & extras", sub: "Size & assets" },
  { n: 5, code: "05", title: "Review",        sub: "Confirm & generate" },
];

const GAMES = [
  { id: "league_of_legends", name: "League of Legends", short: "LoL", accent: "oklch(60% 0.18 220)", logo: "assets/games/lol.jpg" },
  { id: "valorant",          name: "Valorant",          short: "VAL", accent: "oklch(60% 0.22 15)", logo: "assets/games/valorant.jpg" },
];

// Game badge: shows the logo image if present (drop official files into
// Poster-ai-frontend/assets/games/), else falls back to the styled short-label tile.
function GameMark({ game }) {
  const [failed, setFailed] = React.useState(false);
  const showImg = game.logo && !failed;
  return (
    <div style={{
      width: 56, height: 56, borderRadius: 12, overflow: "hidden",
      background: showImg ? "var(--surface-2)" : `linear-gradient(135deg, ${game.accent}, oklch(20% 0.05 350))`,
      border: "1px solid var(--line-strong)",
      fontFamily: "var(--f-display)", fontSize: 18, color: "white",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {showImg
        ? <img src={game.logo} alt={game.name} onError={() => setFailed(true)}
               style={{ width: "100%", height: "100%", objectFit: "contain", padding: 6 }} />
        : game.short}
    </div>
  );
}

const POSTER_TYPES = [
  { id: "gameday",                title: "Gameday",         desc: "Upcoming matchup w/ time + stream",   ico: "clock" },
  { id: "game_results",           title: "Game Results",    desc: "Final score, maps, MVP",              ico: "target" },
  { id: "roster_reveal",          title: "Roster Reveal",   desc: "Lineup announcement",                 ico: "user" },
  { id: "tournament_announcement",title: "Tournament Announce", desc: "Hype drop with prize pool",       ico: "bolt" },
  { id: "tournament_banner",      title: "Tournament Banner",   desc: "Header / hero banner",            ico: "image" },
];

const VIBES = [
  { id: "cyberpunk",    label: "Cyberpunk",    desc: "Neon, chrome, glitch",        grad: ["oklch(45% 0.25 320)", "oklch(45% 0.20 200)"] },
  { id: "cinematic",    label: "Cinematic",    desc: "Volumetric light, drama",     grad: ["oklch(35% 0.18 30)",  "oklch(15% 0.05 280)"] },
  { id: "dark_fantasy", label: "Dark Fantasy", desc: "Smoke, ember, gothic",        grad: ["oklch(30% 0.18 25)",  "oklch(15% 0.10 320)"] },
  { id: "cosmic",       label: "Cosmic",       desc: "Stars, nebula, deep space",   grad: ["oklch(35% 0.22 280)", "oklch(20% 0.18 220)"] },
  { id: "minimal",      label: "Minimal",      desc: "Clean type, flat palette",    grad: ["oklch(85% 0.02 200)", "oklch(35% 0.02 200)"] },
  { id: "fire_energy",  label: "Fire & Energy",desc: "Heat, sparks, intensity",     grad: ["oklch(60% 0.22 40)",  "oklch(30% 0.20 15)"] },
];

const ENERGY = [
  { id: "chill",     label: "Chill",     desc: "Calm composition, soft contrast" },
  { id: "balanced",  label: "Balanced",  desc: "Even rhythm, readable hierarchy" },
  { id: "intense",   label: "Intense",   desc: "Hard contrast, kinetic angles" },
  { id: "explosive", label: "Explosive", desc: "Max drama, particle work, motion blur" },
];

const FORMATS = [
  { id: "portrait_1080x1920",  name: "Portrait",  ratio: "9:16", dims: "1080×1920", use: "Story · Reels",       w: 70,  h: 124 },
  { id: "square_1080x1080",    name: "Square",    ratio: "1:1",  dims: "1080×1080", use: "Feed post",           w: 100, h: 100 },
  { id: "landscape_1920x1080", name: "Landscape", ratio: "16:9", dims: "1920×1080", use: "Banner · Twitter hdr", w: 140, h: 78 },
];

// Render-quality tiers for gpt-image-2. `mult` is the cost relative to medium,
// applied to the image-generation portion of the estimate. The ratios follow
// OpenAI's image-model quality tiers (token-based): low ≈ 0.25×, high ≈ 4×
// medium. Change these in one place if your gpt-image-2 billing differs.
const QUALITY = [
  { id: "low",    name: "Low",    mult: 0.25, blurb: "Fastest & cheapest — quick drafts and tests." },
  { id: "medium", name: "Medium", mult: 1.0,  blurb: "Balanced detail and cost.", recommended: true },
  { id: "high",   name: "High",   mult: 4.0,  blurb: "Sharpest detail — best for finals / print." },
];
const QUALITY_MULT = QUALITY.reduce((m, q) => ((m[q.id] = q.mult), m), {});

const COLOR_PRESETS = ["#E83A57", "#3AC0E8", "#FFD24B", "#7B5CFF", "#22C58A", "#FF6A1F"];

const PRESET_TEAMS = [
  { name: "FNATIC", short: "FNC" },
  { name: "T1",     short: "T1"  },
  { name: "G2 ESPORTS", short: "G2" },
  { name: "KOI",    short: "KOI" },
];

const VALORANT_MAPS = ["Haven","Ascent","Bind","Split","Lotus","Pearl","Sunset","Icebox","Breeze","Fracture"];
const LOL_ROLES = ["Top","Jungle","Mid","Bot","Support"];
const VALORANT_ROLES = ["Duelist","Initiator","Controller","Sentinel","Flex","IGL"];
// Role dropdown options for the roster, per game.
function rolesForGame(game) { return game === "valorant" ? VALORANT_ROLES : LOL_ROLES; }
// Default 5-slot roster roles, by position, per game — used to seed the roster
// and to remap when the user switches games (so a Valorant roster never shows
// League roles like Top/Jungle/ADC).
const DEFAULT_ROSTER_ROLES = {
  league_of_legends: ["Top","Jungle","Mid","Bot","Support"],
  valorant: ["Duelist","Initiator","Controller","Sentinel","Flex"],
};
// Guarantee a game-appropriate role: keep it if valid for this game, otherwise
// fall back to the positional default. Stops a stale default (e.g. a slot-2
// "Jungle" that was never re-selected) from reaching a Valorant poster.
function coerceRole(role, game, i) {
  if (rolesForGame(game).includes(role)) return role;
  const defaults = DEFAULT_ROSTER_ROLES[game] || DEFAULT_ROSTER_ROLES.league_of_legends;
  return defaults[i % defaults.length];
}

function slugify(s) {
  return (s || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "_standalone";
}

// Max total games in a best-of-N series — the score sum can never exceed this.
function seriesMaxGames(format) {
  return { bo1: 1, bo3: 3, bo5: 5 }[(format || "").toLowerCase()] || 5;
}

// Games needed to WIN a best-of-N series — no single team can exceed this.
// Bo1 -> 1, Bo3 -> 2, Bo5 -> 3. (A Bo3 ends at 2, so 3-0 is impossible.)
function seriesWinTarget(format) {
  return { bo1: 1, bo3: 2, bo5: 3 }[(format || "").toLowerCase()] || 3;
}

// Roster reveal rule: 0, 1, or 5 player photos — never 2/3/4.
// 0 = text-only roster (just IGNs), 1 = single hero, 5 = full lineup;
// partial counts (2/3/4) look broken so the wizard blocks them.
const ROSTER_PHOTO_ALLOWED = [0, 1, 5];
function rosterPhotoCount(form) {
  if (form.poster_type !== "roster_reveal") return null;
  return (form.roster_players || []).filter((p) => p && p.image_asset).length;
}
function rosterPhotoValid(form) {
  const c = rosterPhotoCount(form);
  if (c === null) return true;
  return ROSTER_PHOTO_ALLOWED.indexOf(c) !== -1;
}

// Clamp a single score: >= 0, <= the win target, and (this + other) <= the series max.
function clampScore(raw, other, format) {
  const target = seriesWinTarget(format);
  const max = seriesMaxGames(format);
  let v = parseInt(raw, 10);
  if (!Number.isFinite(v) || v < 0) v = 0;
  const o = Number.isFinite(+other) ? +other : 0;
  v = Math.min(v, target);              // a team can't win more than the target
  if (v + o > max) v = Math.max(0, max - o);  // and the series can't run past N games
  return v;
}

// --- Valorant map-result validation -----------------------------------------
// A Valorant map is first-to-13, win by 2. Valid finals: regulation (winner 13,
// loser 0..11) OR overtime (winner >= 14, exactly +2, loser >= 12). So 13-0 …
// 13-11, then 14-12, 15-13, 16-14, …  Ties and 13-12 are impossible.
function isValidValorantMapScore(a, b) {
  const t1 = parseInt(a, 10), t2 = parseInt(b, 10);
  if (!Number.isFinite(t1) || !Number.isFinite(t2) || t1 < 0 || t2 < 0) return false;
  if (t1 === t2) return false;                              // a map always has a winner
  const hi = Math.max(t1, t2), lo = Math.min(t1, t2);
  if (hi === 13 && lo <= 11) return true;                  // regulation
  if (hi >= 14 && hi - lo === 2 && lo >= 12) return true;  // overtime, win by 2
  return false;
}

// Required fields per poster type, as user-facing strings. Empty = valid.
//
// The form already marks these with a red asterisk (`<FormField req>`), but
// nothing enforced them: you could leave the tournament and both team names
// blank and still generate, producing a poster captioned "Team A vs Team B".
// This makes the asterisk mean what it says.
const REQUIRED_FIELDS = {
  gameday: [
    ["tournament_name", "Tournament name"],
    ["match_format", "Format"],
  ],
  game_results: [
    ["tournament_name", "Tournament name"],
    ["match_format", "Format"],
  ],
  tournament_announcement: [
    ["ann_start_date", "Start date"],
    ["ann_location", "Location"],
    ["ann_prize_pool", "Prize pool"],
    ["ann_tagline", "Tagline"],
  ],
  tournament_banner: [
    ["banner_date_range", "Date range"],
    ["ann_location", "Location"],
    ["ann_prize_pool", "Prize pool"],
    ["ann_tagline", "Tagline"],
  ],
};

function isBlank(v) { return v == null || String(v).trim() === ""; }

function requiredFieldIssues(form) {
  const type = form.poster_type;
  const issues = [];

  for (const [key, label] of (REQUIRED_FIELDS[type] || [])) {
    if (isBlank(form[key])) issues.push(`${label} is required.`);
  }

  // Both sides of a matchup need a name — the poster is built around them.
  if (type === "gameday" || type === "game_results") {
    if (isBlank(form.team_a && form.team_a.name)) issues.push("Team 1 name is required.");
    if (isBlank(form.team_b && form.team_b.name)) issues.push("Team 2 name is required.");
  }

  if (type === "roster_reveal" && isBlank(form.roster_team && form.roster_team.name)) {
    issues.push("Team name is required.");
  }

  return issues;
}

function requiredFieldsValid(form) { return requiredFieldIssues(form).length === 0; }

// Every problem with the SERIES score, as user-facing strings. Empty = valid.
//
// `clampScore` only stops a score being *impossible* (no team above the win
// target, no series longer than N games). That still lets through scores that
// are merely undecided — 2-0 or 2-2 in a BO5 — which are fine mid-series but
// cannot be the FINAL score on a results poster. A results poster states an
// outcome, so exactly one team must have reached the win target.
function seriesScoreIssues(form) {
  if (form.poster_type !== "game_results") return [];

  const fmt = (form.match_format || "bo5").toLowerCase();
  const target = seriesWinTarget(fmt);
  const max = seriesMaxGames(fmt);
  const label = fmt.toUpperCase();

  const a = parseInt(form.score_a, 10);
  const b = parseInt(form.score_b, 10);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b < 0) {
    return ["Enter both team scores."];
  }

  const issues = [];
  const hi = Math.max(a, b);
  const lo = Math.min(a, b);

  if (a === b) {
    issues.push(`A ${label} can't end ${a}-${b} — a series always has a winner.`);
  } else if (hi < target) {
    issues.push(
      `${a}-${b} isn't a finished ${label} — the winner needs ${target} ` +
      `map${target === 1 ? "" : "s"}, not ${hi}.`
    );
  } else if (hi > target) {
    // clampScore normally prevents this; kept so a pasted or restored draft
    // can't slip an impossible score past the wizard.
    issues.push(`A ${label} is first to ${target}, so ${hi} map wins is impossible.`);
  } else if (lo >= target) {
    issues.push(`Both teams can't reach ${target} in a ${label}.`);
  }

  if (a + b > max) {
    issues.push(`A ${label} runs at most ${max} map${max === 1 ? "" : "s"}, but ${a}-${b} is ${a + b}.`);
  }
  return issues;
}

function seriesScoreValid(form) { return seriesScoreIssues(form).length === 0; }

// Games actually played = sum of the series score. A 3-2 BO5 played 5 maps; a
// 3-0 played 3. The number of Valorant maps must equal this.
function gamesPlayed(form) {
  return (parseInt(form.score_a, 10) || 0) + (parseInt(form.score_b, 10) || 0);
}

// First Valorant map not already used (for adding / defaulting without repeats).
function firstUnusedMap(maps) {
  const used = new Set((maps || []).map((m) => m.map_name));
  return VALORANT_MAPS.find((x) => !used.has(x)) || VALORANT_MAPS[0];
}

// Every problem with the current Valorant map list, as user-facing strings.
// Empty array = valid. Only meaningful for Valorant game_results.
function valorantMapIssues(form) {
  if (form.game !== "valorant" || form.poster_type !== "game_results") return [];
  const maps = form.valorant_maps || [];
  const n = gamesPlayed(form);
  const fmt = (form.match_format || "BO5").toUpperCase();
  const issues = [];

  if (maps.length > n) {
    issues.push(`Too many maps — a ${fmt} ending ${form.score_a}-${form.score_b} has ${n} map${n === 1 ? "" : "s"}.`);
  }
  const seen = {};
  maps.forEach((m) => { const k = (m.map_name || "").toLowerCase(); if (k) seen[k] = (seen[k] || 0) + 1; });
  const dups = Object.keys(seen).filter((k) => seen[k] > 1);
  if (dups.length) issues.push(`Each map can appear only once (repeated: ${dups.join(", ")}).`);

  maps.forEach((m, i) => {
    if (!isValidValorantMapScore(m.rounds_team1, m.rounds_team2)) {
      issues.push(`Map ${i + 1}${m.map_name ? ` (${m.map_name})` : ""}: ${m.rounds_team1 || 0}-${m.rounds_team2 || 0} isn't a valid Valorant score.`);
    }
  });

  // Once every map is filled in, the map wins must match the series score.
  if (n > 0 && maps.length === n && maps.every((m) => isValidValorantMapScore(m.rounds_team1, m.rounds_team2))) {
    let w1 = 0, w2 = 0;
    maps.forEach((m) => { (+m.rounds_team1 > +m.rounds_team2) ? w1++ : w2++; });
    if (w1 !== (+form.score_a || 0) || w2 !== (+form.score_b || 0)) {
      issues.push(`Map wins (${w1}-${w2}) don't match the series score (${form.score_a}-${form.score_b}).`);
    }
  }
  return issues;
}

function valorantMapsValid(form) { return valorantMapIssues(form).length === 0; }

// When the series score or format drops the games-played count, trim extra
// Valorant maps so the list can never exceed the number of games played.
function withTrimmedMaps(form, patch) {
  const next = { ...form, ...patch };
  const n = gamesPlayed(next);
  if (next.game === "valorant" && (next.valorant_maps || []).length > n) {
    return { ...patch, valorant_maps: next.valorant_maps.slice(0, n) };
  }
  return patch;
}

/* ============================================================
   Cost estimator (EUR). Grounded in the pipeline's real cost drivers:
     - GPT-4o prompt stage  (base)
     - gpt-image-2 generation (base; larger canvas costs more output tokens)
     - each reference image handed to the models adds input tokens
     - sponsor logos are composited locally by Pillow -> free
     - vibe/energy/DNA are heuristic complexity modifiers (prompt length /
       regeneration likelihood), not hard API line items.
   Every contribution is itemized so the number is explainable, never magic.
   ============================================================ */
const COST = {
  promptBase: 0.008,       // GPT-4o Vision prompt stage
  imageBase: 0.030,        // gpt-image-2 medium, base generation
  formatLarge: 0.010,      // portrait/landscape: larger canvas = more output tokens
  teamLogo: 0.003,         // per team/tournament logo reference image
  tournamentLogo: 0.003,
  playerImage: 0.005,      // featured player photo (high-detail reference)
  rosterPlayerImage: 0.005,// per roster player photo
  mvp: 0.002,              // extra MVP block (text/data)
  valorantMap: 0.001,      // per map result row
  consistency: 0.002,      // Style DNA hard-constraint block (longer prompt)
  vibe: { minimal: -0.005, cyberpunk: 0.002, cosmic: 0.002, dark_fantasy: 0.003, fire_energy: 0.005 },
  energy: { chill: -0.003, balanced: 0, intense: 0.003, explosive: 0.005 },
  floor: 0.010,            // a run never costs less than this
};

function estimateCost(form) {
  const items = [];
  const add = (label, amount) => items.push({ label, amount });
  const pt = form.poster_type;

  // Render quality scales the image-generation output-token cost only. The
  // prompt stage and reference-image input tokens are unaffected.
  const q = form.quality || "medium";
  const qmult = QUALITY_MULT[q] != null ? QUALITY_MULT[q] : 1.0;
  const qlabel = q.charAt(0).toUpperCase() + q.slice(1);

  add("Prompt analysis (GPT-4o)", COST.promptBase);
  add(`Poster generation (gpt-image-2 · ${qlabel} ×${qmult})`, COST.imageBase * qmult);

  if (form.format_id !== "square_1080x1080") {
    const fmt = FORMATS.find((f) => f.id === form.format_id);
    add(`Large canvas (${fmt ? fmt.dims : form.format_id})`, COST.formatLarge * qmult);
  }

  // --- reference images (each adds model input tokens)
  let teamLogos = 0;
  if (pt === "gameday" || pt === "game_results") {
    if (form.team_a.logo_asset) teamLogos++;
    if (form.team_b.logo_asset) teamLogos++;
    if (form.tournament_logo_asset) add("Tournament logo", COST.tournamentLogo);
  } else if (pt === "roster_reveal") {
    if (form.roster_team.logo_asset) teamLogos++;
  } else if (form.tournament_logo_asset) {
    add("Tournament logo", COST.tournamentLogo);
  }
  if (teamLogos) add(`Team logos ×${teamLogos}`, COST.teamLogo * teamLogos);

  if ((pt === "gameday" || pt === "game_results") && form.featured_player && form.featured_player_asset) {
    add("Featured player image", COST.playerImage);
  }
  if (pt === "roster_reveal") {
    const n = form.roster_players.filter((p) => p.image_asset).length;
    if (n) add(`Roster player images ×${n}`, COST.rosterPlayerImage * n);
  }

  // --- data complexity
  if (pt === "game_results" && form.mvp_on) add("MVP highlight", COST.mvp);
  if (pt === "game_results" && form.game === "valorant") {
    const n = (form.valorant_maps || []).length;
    if (n) add(`Valorant map results ×${n}`, COST.valorantMap * n);
  }

  // --- sponsor bar is composited locally (Pillow) -> free
  if (form.sponsor_bar && form.sponsor_assets.length) {
    add(`Sponsor bar ×${form.sponsor_assets.length} (composited locally)`, 0);
  }

  // --- style: consistency DNA, or fresh-mode vibe/energy modifiers
  if (form.style_mode === "consistency" && form.style_dna) {
    add("Style DNA constraints", COST.consistency);
  } else if (form.style_mode === "fresh") {
    const v = COST.vibe[form.vibe];
    if (v) add(`Vibe: ${form.vibe}`, v);
    const e = COST.energy[form.energy];
    if (e) add(`Energy: ${form.energy}`, e);
  }

  const raw = items.reduce((s, i) => s + i.amount, 0);
  const total = Math.max(raw, COST.floor);
  return { items, total, floored: total > raw };
}

function eur(n) {
  return "€" + n.toFixed(3);
}

// Users are billed in Red Coins, never dollars. `rc()` converts an internal
// USD cost into the displayed coin amount (tokensForUsd + fmtCoins are global,
// defined in api.jsx). A signed delta is used for the itemised lines.
//
// `scale` (coins per USD) is optional. It exists for hosts that bill a flat
// per-quality price instead of metered tokens: passing a scale derived from the
// real charge keeps the itemised lines summing to the amount actually billed,
// rather than showing a breakdown that disagrees with the invoice.
function rc(usd, scale) {
  const coins = scale != null ? Math.round(usd * scale) : tokensForUsd(usd);
  return fmtCoins(coins) + " " + coinSym();
}
function rcDelta(usd, scale) {
  if (usd === 0) return "free";
  const coins = scale != null
    ? Math.round(Math.abs(usd) * scale)
    : tokensForUsd(Math.abs(usd));
  return (usd < 0 ? "−" : "+") + fmtCoins(coins) + " " + coinSym();
}

// What one poster costs in coins.
//
// Defaults to the metered token model. A host may override it — Defendr bills a
// flat price per render quality — in which case both the headline figure and the
// insufficient-balance gate use the host's number, so the wizard can never quote
// one price and charge another.
function coinTotalFor(form, usdTotal) {
  if (typeof window.posterCoinTotal === "function") {
    const coins = window.posterCoinTotal(form, usdTotal);
    if (Number.isFinite(coins) && coins >= 0) return coins;
  }
  return tokensForUsd(usdTotal);
}

// Derive a clean team token from an asset. Prefer the explicit `team` tag when
// the asset carries one; otherwise clean the name/filename by dropping common
// noise words (file types, "logo", "svg", "organization", …):
//   "GNG_LOGO.png" -> "GNG", "T1 SVG" -> "T1",
//   "organization fnatic svg" -> "FNATIC", "Team Vitality.png" -> "VITALITY"
const _LOGO_NOISE = /^(logo|logos|team|esports?|official|organization|org|gaming|club|svg|png|jpg|jpeg|webp|vector|icon|transparent|hd|final|copy)$/i;
function teamKeyFromAsset(a) {
  if (a && typeof a.team === "string" && a.team.trim()) return a.team.trim().toUpperCase();
  const base = (a.name || a.filename || "").replace(/\.[a-z0-9]+$/i, "");
  const tokens = base.split(/[^a-z0-9]+/i).filter(Boolean).filter((t) => !_LOGO_NOISE.test(t));
  return tokens.join(" ").toUpperCase().trim();
}

// Collapse a team-logo asset list into one chip per team (most-recent wins).
// The API returns assets newest-first, so the first occurrence per key is kept.
function buildTeamLogoLibrary(assets) {
  const seen = new Map();
  for (const a of assets || []) {
    const key = teamKeyFromAsset(a);
    if (!key) continue;
    if (!seen.has(key)) seen.set(key, { key, short: key.split(" ")[0].slice(0, 4), asset: a });
  }
  return Array.from(seen.values());
}

// Identity for a sponsor logo, used for dedup + quick-pick selection state.
// Where the pipeline should read an asset from.
//
// An asset is either uploaded to the brand library (`storage_key`) or referenced
// in place by public URL (`url`) — the latter is how host-platform assets (team
// logos, tournament covers already sitting in the platform's own storage) get
// used without a re-upload. The generator resolves both, so the only rule here
// is: prefer the explicit URL, fall back to the stored key.
function assetPath(a) {
  if (!a) return null;
  // Storage key first. `url` is a presigned link that expires in an hour, so a
  // job retried or refined later would resolve a dead asset — and when a host
  // wraps this SPA its asset objects can carry BOTH keys, in which case
  // preferring `url` sent a signed URL where the pipeline expected a key.
  return a.storage_key || a.url || null;
}

// Same sponsor name (case-insensitive, extension stripped) = same sponsor, even
// if re-uploaded under a new storage key. Falls back to the storage key / id.
function sponsorKeyOf(a) {
  if (!a) return "";
  const n = (a.name || "").trim().toLowerCase().replace(/\.(png|jpe?g|webp)$/i, "");
  return n || a.storage_key || a.asset_id || "";
}

// Short display label for a sponsor chip.
function sponsorLabel(a) {
  const n = (a && a.name ? a.name : "").trim().replace(/\.(png|jpe?g|webp)$/i, "");
  if (!n) return "logo";
  return n.length > 14 ? n.slice(0, 13) + "…" : n;
}

// Collapse a sponsor-logo asset list into one chip per sponsor (most-recent
// wins). The API returns assets newest-first, so the first per key is kept.
function buildSponsorLibrary(assets) {
  const seen = new Map();
  for (const a of assets || []) {
    const key = sponsorKeyOf(a);
    if (!key) continue;
    if (!seen.has(key)) seen.set(key, a);
  }
  return Array.from(seen.values());
}

// Short display label for a player-image chip (the IGN / filename).
function playerLabel(a) {
  const n = (a && a.name ? a.name : "").trim().replace(/\.(png|jpe?g|webp)$/i, "");
  if (!n) return "player";
  return n.length > 14 ? n.slice(0, 13) + "…" : n;
}

// Collapse player-image assets into one chip per player (most-recent wins).
function buildPlayerImageLibrary(assets) {
  const seen = new Map();
  for (const a of assets || []) {
    const key = (a.name || "").trim().toLowerCase().replace(/\.(png|jpe?g|webp)$/i, "")
      || a.storage_key || a.asset_id;
    if (!key) continue;
    if (!seen.has(key)) seen.set(key, a);
  }
  return Array.from(seen.values());
}

// Reusable "QUICK PICK" chip row for image assets already in the brand library.
// Clicking a chip calls onPick(asset). Mirrors the team-logo quick-pick style.
function ImageQuickPick({ library, selectedId, onPick, labelOf = playerLabel }) {
  if (!library || library.length === 0) return null;
  return (
    <div className="row" style={{ gap: 6, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
      <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.08em" }}>QUICK PICK:</span>
      {library.map((a) => {
        const on = selectedId && a.asset_id === selectedId;
        return (
          <button key={a.asset_id} title={labelOf(a)}
            onClick={() => onPick(a)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              fontFamily: "var(--f-mono)", fontSize: 10, letterSpacing: "0.06em",
              padding: "2px 8px 2px 3px", background: on ? "var(--crim-soft)" : "transparent",
              border: "1px solid " + (on ? "var(--crim-line)" : "var(--line)"), borderRadius: 999,
              color: "var(--fg-2)", cursor: "pointer",
            }}>
            {a.signed_url
              ? <img src={a.signed_url} alt="" style={{ width: 18, height: 18, borderRadius: "50%", objectFit: "cover", background: "var(--surface-3)" }} />
              : <span style={{ width: 18, height: 18, borderRadius: "50%", background: "var(--surface-3)" }} />}
            {labelOf(a)}
          </button>
        );
      })}
    </div>
  );
}

function emptyTeam() { return { name: "", short: "", logo_asset: null }; }
function emptyPlayer(role) {
  return { ign: "", role, image_asset: null, nationality_flag_asset: null, is_new_signing: false };
}

function defaultForm() {
  return {
    org_id: (window.api && window.api.orgId) || "1",
    game: "league_of_legends",
    poster_type: "gameday",

    // tournament
    tournament_id: "",
    tournament_name: "",
    tournament_phase: "",
    tournament_logo_asset: null,

    // matchup (gameday + game_results)
    team_a: emptyTeam(),
    team_b: emptyTeam(),
    match_format: "Bo5",
    match_date: "",
    match_time: "",
    timezone: "CET",

    // gameday stream
    stream_platform: "Twitch",
    stream_url: "",

    // game_results
    score_a: 0,
    score_b: 0,
    // Valorant per-map results — added by the user, capped at games-played
    // (score_a + score_b), no repeated maps. See valorantMapIssues().
    valorant_maps: [],
    mvp_on: false,
    mvp_ign: "",
    mvp_stat_label: "",
    mvp_stat_value: "",

    // roster_reveal
    roster_team: emptyTeam(),
    roster_season: "",
    roster_coach: "",
    roster_players: [
      emptyPlayer("Top"),
      emptyPlayer("Jungle"),
      emptyPlayer("Mid"),
      emptyPlayer("Bot"),
      emptyPlayer("Support"),
    ],

    // announcement / banner
    ann_start_date: "",
    ann_location: "",
    ann_prize_pool: "",
    ann_teams_count: "",
    ann_format: "",
    ann_tagline: "",
    ann_sub_tagline: "",
    banner_date_range: "",

    // style
    style_mode: "fresh",
    vibe: "cinematic",
    color: "#E83A57",
    color_mode: "dominant", // "dominant" (force color) | "auto" (derive from background)
    energy: "intense",
    style_dna: null,
    style_dna_status: null, // "approved" | "draft" | null
    style_dna_loading: false,

    // format + extras
    format_id: "portrait_1080x1920",
    quality: "medium",
    featured_player: false,
    featured_player_asset: null,
    sponsor_bar: false,
    sponsor_assets: [],
    // Background canvas source: "system_pool" (current default) | "custom"
    // (user upload) | "generated" (Runpod fine-tuned SD — not yet wired).
    background_source: "custom",
    custom_background_asset: null,

    // brand library — team logos already uploaded for this org (quick-pick)
    team_logo_library: [],
    // brand library — sponsor logos already uploaded for this org (quick-pick)
    sponsor_library: [],
    // brand library — player images already uploaded for this org (quick-pick)
    player_image_library: [],
    // previously-used tournament names (datalist suggestions on the name field)
    tournament_name_suggestions: [],
    // all the org's saved Style DNAs — pickable in consistency mode on any poster
    style_library: [],
  };
}

/* ============================================================
   Draft persistence — keep wizard inputs across page refreshes.
   Stored in localStorage; cleared on a successful generate or Discard.
   ============================================================ */
const WIZARD_DRAFT_KEY = "epai_wizard_draft_v1";

// Fetched/transient fields — not persisted (re-derived on load).
const _EPHEMERAL_FIELDS = ["style_dna", "style_dna_status", "style_dna_loading", "team_logo_library", "sponsor_library", "player_image_library", "tournament_name_suggestions", "style_library"];

function loadWizardDraft() {
  try {
    const raw = localStorage.getItem(WIZARD_DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function saveWizardDraft(form, step) {
  try {
    const slim = { ...form };
    for (const k of _EPHEMERAL_FIELDS) delete slim[k];
    localStorage.setItem(WIZARD_DRAFT_KEY, JSON.stringify({ form: slim, step }));
  } catch (_) { /* quota / private mode — non-fatal */ }
}

function clearWizardDraft() {
  try { localStorage.removeItem(WIZARD_DRAFT_KEY); } catch (_) {}
}

// Re-point the saved draft at a given step (used by "Change background & retry"
// on a failed job, so reopening the wizard lands on the background step with
// all the previously-entered inputs intact). No-op if there's no draft.
function setWizardDraftStep(step) {
  try {
    const raw = localStorage.getItem(WIZARD_DRAFT_KEY);
    if (!raw) return;
    const d = JSON.parse(raw);
    d.step = step;
    localStorage.setItem(WIZARD_DRAFT_KEY, JSON.stringify(d));
  } catch (_) { /* non-fatal */ }
}

// Step that holds the background source picker (Step 4: Format & extras).
const WIZARD_BACKGROUND_STEP = 4;

/* ============================================================
   Input JSON builder — maps form state → backend PosterInput.
   ============================================================ */
function buildInputJSON(form) {
  const game = form.game;
  const poster_type = form.poster_type;
  const mode = form.style_mode;
  const output_format = form.format_id;

  const design = {
    vibe: form.vibe,
    // In auto mode the poster takes its palette from the background, so don't
    // send a forced color.
    primary_color: form.color_mode === "auto" ? null : form.color,
    color_mode: form.color_mode,
    energy: form.energy,
  };

  const sponsors = {
    enabled: !!form.sponsor_bar && form.sponsor_assets.length > 0,
    logos: form.sponsor_assets.map((a) => ({ path: assetPath(a) })),
  };

  // Background source — the pipeline resolves it in stages/background.py.
  //   system_pool: omit the block; pipeline picks from the local pool.
  //   custom:      emit source + the uploaded image storage key.
  //   generated:   emit source only; pipeline will call Runpod (deferred).
  let background = null;
  if (form.background_source === "custom" && form.custom_background_asset) {
    background = { source: "custom", image_path: assetPath(form.custom_background_asset) };
  } else if (form.background_source === "generated") {
    background = { source: "generated" };
  }

  const _meta = { game, poster_type, mode, output_format, quality: form.quality || "medium" };

  const teamPayload = (t, withScore, score) => {
    const o = {
      name: t.name || "",
      short_name: t.short || "",
      logo_path: assetPath(t.logo_asset),
    };
    if (withScore) o.score = Number.isFinite(+score) ? +score : null;
    return o;
  };

  if (poster_type === "gameday") {
    return {
      _meta,
      tournament: {
        name: form.tournament_name,
        logo_path: assetPath(form.tournament_logo_asset),
        phase: form.tournament_phase || null,
      },
      match: {
        team1: teamPayload(form.team_a, false),
        team2: teamPayload(form.team_b, false),
        format: form.match_format ? form.match_format.toLowerCase() : null,
        date: form.match_date || "",
        time: form.match_time || "",
        timezone: form.timezone || null,
      },
      stream: {
        platform: form.stream_platform || null,
        url: form.stream_url || null,
      },
      player_feature: {
        enabled: !!form.featured_player,
        image_path: assetPath(form.featured_player_asset),
      },
      sponsors,
      design,
      ...(background && { background }),
    };
  }

  if (poster_type === "game_results") {
    const base = {
      _meta,
      tournament: {
        name: form.tournament_name,
        logo_path: assetPath(form.tournament_logo_asset),
        phase: form.tournament_phase || null,
      },
      match: {
        team1: teamPayload(form.team_a, true, form.score_a),
        team2: teamPayload(form.team_b, true, form.score_b),
        format: form.match_format ? form.match_format.toLowerCase() : null,
        date: form.match_date || "",
      },
      player_feature: {
        enabled: !!form.featured_player,
        image_path: assetPath(form.featured_player_asset),
      },
      mvp: {
        enabled: !!form.mvp_on,
        player_name: form.mvp_on ? (form.mvp_ign || null) : null,
        stat_label: form.mvp_on ? (form.mvp_stat_label || null) : null,
        stat_value: form.mvp_on ? (form.mvp_stat_value || null) : null,
        image_path: null,
      },
      sponsors,
      design,
      ...(background && { background }),
    };
    if (game === "valorant") {
      base.match.maps = form.valorant_maps.map((m) => ({
        map_name: m.map_name || "",
        rounds_team1: Number.isFinite(+m.rounds_team1) ? +m.rounds_team1 : null,
        rounds_team2: Number.isFinite(+m.rounds_team2) ? +m.rounds_team2 : null,
      }));
      base.mvp.agent_name = null;
      base.mvp.agent_render_path = null;
    }
    return base;
  }

  if (poster_type === "roster_reveal") {
    return {
      _meta,
      team: {
        name: form.roster_team.name || "",
        logo_path: assetPath(form.roster_team.logo_asset) || "",
      },
      roster: {
        season: form.roster_season || null,
        head_coach: form.roster_coach || null,
        players: form.roster_players.map((p, i) => ({
          ign: p.ign || "",
          role: coerceRole(p.role, game, i),
          image_path: assetPath(p.image_asset),
          nationality_flag_path: assetPath(p.nationality_flag_asset),
          is_new_signing: !!p.is_new_signing,
        })),
      },
      sponsors,
      design,
      ...(background && { background }),
    };
  }

  if (poster_type === "tournament_announcement") {
    return {
      _meta,
      tournament: {
        name: form.tournament_name,
        logo_path: assetPath(form.tournament_logo_asset),
        start_date: form.ann_start_date || "",
        location: form.ann_location || null,
        prize_pool: form.ann_prize_pool || null,
        teams_count: form.ann_teams_count ? +form.ann_teams_count : null,
        format: form.ann_format || null,
        tagline: form.ann_tagline || null,
        sub_tagline: form.ann_sub_tagline || null,
      },
      sponsors,
      design,
      ...(background && { background }),
    };
  }

  if (poster_type === "tournament_banner") {
    return {
      _meta,
      tournament: {
        name: form.tournament_name,
        logo_path: assetPath(form.tournament_logo_asset),
        date_range: form.banner_date_range || null,
        location: form.ann_location || null,
        prize_pool: form.ann_prize_pool || null,
        tagline: form.ann_tagline || null,
      },
      sponsors,
      design,
      ...(background && { background }),
    };
  }

  return { _meta, design, sponsors, ...(background && { background }) };
}

/* ============================================================
   Asset upload component
   ============================================================ */
function AssetUpload({ assetType, orgId, asset, onChange, label = "Upload", small, square, wide }) {
  const inputRef = React.useRef(null);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const h = small ? 40 : square ? 56 : wide ? 120 : 80;

  const pick = () => inputRef.current && inputRef.current.click();

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const a = await window.api.uploadAsset({ orgId, assetType, file, name: file.name });
      onChange(a);
    } catch (e) {
      const msg = e.message || "Upload failed";
      // Inline crimson border on the tile gives the user spatial context
      // (which slot failed); a parallel toast gives them room to actually
      // read multi-line error messages like the HD/2K background gate.
      setError(msg);
      window.toast.error(`Couldn't upload "${file.name}": ${msg}`);
    } finally {
      setUploading(false);
    }
  };

  const clear = (e) => {
    e.stopPropagation();
    onChange(null);
  };

  const hasAsset = !!(asset && asset.signed_url);

  return (
    <div style={{ width: square ? 56 : "100%" }}>
      <button
        type="button"
        onClick={pick}
        title={error || (hasAsset ? asset.filename : label)}
        style={{
          width: square ? 56 : "100%",
          height: h,
          // Longhand, not the `background` shorthand: the shorthand resets
          // backgroundImage/Size/Position, so on a rerender it wiped the very
          // thumbnail this button exists to show — and React warns about the
          // mixed shorthand/longhand pair.
          backgroundColor: hasAsset ? "transparent" : "var(--bg-elev)",
          backgroundImage: hasAsset ? `url(${asset.signed_url})` : "none",
          backgroundSize: "cover",
          backgroundPosition: "center",
          border: "1px " + (hasAsset ? "solid" : "dashed") + " " + (error ? "var(--crim)" : "var(--line-strong)"),
          borderRadius: 8,
          color: "var(--fg-3)",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          cursor: "pointer",
          fontSize: 12,
          position: "relative",
          overflow: "hidden",
        }}>
        {uploading ? (
          <span className="mono" style={{ fontSize: 10, color: "var(--cy)" }}>UPLOADING…</span>
        ) : hasAsset ? (
          <span
            onClick={clear}
            style={{
              position: "absolute", top: 4, right: 4,
              width: 18, height: 18, borderRadius: "50%",
              background: "rgba(0,0,0,0.6)", color: "white",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, lineHeight: 1, cursor: "pointer",
            }}>×</span>
        ) : (
          <>
            <Icon name={square ? "image" : "upload"} size={square ? 18 : 14} />
            {!square && <span>{label}</span>}
          </>
        )}
      </button>
      {error && <div style={{ fontSize: 10, color: "var(--crim)", marginTop: 4 }}>{error}</div>}
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        style={{ display: "none" }}
        onChange={(e) => handleFile(e.target.files && e.target.files[0])}
      />
    </div>
  );
}

/* ───── Progress rail ───── */
function ProgressRail({ current, onJump }) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(5, 1fr)",
      gap: 6,
      marginBottom: 36,
      position: "relative",
    }}>
      {STEPS.map((s) => {
        const done = s.n < current;
        const active = s.n === current;
        return (
          <button key={s.n}
            onClick={() => onJump(s.n)}
            style={{
              background: "transparent",
              border: 0,
              padding: 0,
              cursor: s.n <= current ? "pointer" : "default",
              opacity: s.n > current ? 0.5 : 1,
              textAlign: "left",
            }}>
            <div style={{
              height: 4,
              borderRadius: 999,
              background: active
                ? "linear-gradient(90deg, var(--crim), var(--cy))"
                : done ? "var(--crim)" : "var(--surface-3)",
              marginBottom: 12,
              transition: "all .3s",
            }} />
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span className="mono" style={{
                fontSize: 11,
                color: active ? "var(--crim)" : done ? "var(--fg-2)" : "var(--fg-4)",
                fontWeight: 600,
              }}>{s.code}</span>
              <span style={{
                fontFamily: "var(--f-display)",
                fontSize: 14,
                color: active ? "var(--fg)" : done ? "var(--fg-2)" : "var(--fg-4)",
              }}>{s.title}</span>
            </div>
            <div style={{ fontSize: 11, color: "var(--fg-4)", marginTop: 2 }}>{s.sub}</div>
          </button>
        );
      })}
    </div>
  );
}

/* ───── Step 1: Game + Type ───── */
function Step1({ form, set }) {
  return (
    <>
      <SectionLabel n="01.A" label="Select your game" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 36 }}>
        {GAMES.map((g) => {
          const on = form.game === g.id;
          return (
            <button key={g.id}
              onClick={() => {
                const patch = { game: g.id };
                // AI-generated backgrounds are LoL-only; drop a stale "generated"
                // selection when switching to a game that doesn't support it.
                if (g.id !== "league_of_legends" && form.background_source === "generated") {
                  patch.background_source = "custom";
                }
                // Roster roles are game-specific — remap by position so a Valorant
                // roster shows Duelist/Initiator/… not League's Top/Jungle/ADC
                // (and vice-versa). Player names/photos are preserved.
                if (g.id !== form.game) {
                  const roles = DEFAULT_ROSTER_ROLES[g.id] || DEFAULT_ROSTER_ROLES.league_of_legends;
                  patch.roster_players = (form.roster_players || []).map(
                    (p, i) => ({ ...p, role: roles[i % roles.length] })
                  );
                }
                set(patch);
              }}
              className="card"
              style={{
                padding: 0, cursor: "pointer", background: "var(--surface-2)",
                borderColor: on ? "var(--crim)" : "var(--line)",
                outline: on ? "3px solid var(--crim-soft)" : "none",
                outlineOffset: -1,
                textAlign: "left",
                position: "relative",
                overflow: "hidden",
                minHeight: 168,
              }}>
              {/* Game key-art as the card hero, with a bottom scrim for the label. */}
              <img src={g.logo} alt="" aria-hidden="true"
                   onError={(e) => { e.currentTarget.style.display = "none"; }}
                   style={{ position: "absolute", inset: 0, width: "100%", height: "100%",
                            objectFit: "cover", objectPosition: "center 26%",
                            opacity: on ? 1 : 0.85, transition: "opacity .3s" }} />
              <div style={{ position: "absolute", inset: 0,
                    background: "linear-gradient(to top, rgba(8,8,11,0.95) 6%, rgba(8,8,11,0.45) 42%, rgba(8,8,11,0.08) 100%)" }} />
              <div style={{ position: "relative", padding: "24px", minHeight: 168, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 21, letterSpacing: "-0.01em", color: "#fff", textShadow: "0 2px 14px rgba(0,0,0,0.7)" }}>{g.name}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--fg-2)", letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 4 }}>
                  {g.id === "valorant" ? "5v5 tactical · maps" : "5v5 moba · roles"}
                </div>
              </div>
              {on && (
                <div style={{ position: "absolute", top: 14, right: 14 }}>
                  <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--crim)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 2px 10px rgba(0,0,0,0.5)" }}>
                    <Icon name="check" size={14}/>
                  </div>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <SectionLabel n="01.B" label="Poster type" hint="Each type drives a different layout & required fields." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
        {POSTER_TYPES.map((t) => {
          const on = form.poster_type === t.id;
          return (
            <button key={t.id}
              onClick={() => set({ poster_type: t.id })}
              className="card"
              style={{
                padding: 14, cursor: "pointer", background: "transparent",
                borderColor: on ? "var(--crim)" : "var(--line)",
                outline: on ? "3px solid var(--crim-soft)" : "none",
                outlineOffset: -1,
                textAlign: "left",
                aspectRatio: "0.85 / 1",
                display: "flex", flexDirection: "column",
              }}>
              <MiniPosterPreview type={t.id} on={on} />
              <div style={{ marginTop: 12 }}>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 13.5, letterSpacing: "-0.01em" }}>{t.title}</div>
                <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 4, lineHeight: 1.3 }}>{t.desc}</div>
              </div>
            </button>
          );
        })}
      </div>
    </>
  );
}

// Duotone line-art thumbnails per poster type. Colors are applied via `style` so
// CSS variables resolve; c1 = primary (crimson), c2 = secondary (cyan).
const POSTER_TYPE_ART = {
  gameday: (c1, c2) => (
    <>
      <path d="M14 24 h24 v20 q0 11 -12 17 q-12 -6 -12 -17 z" strokeWidth="3" strokeLinejoin="round" style={{ stroke: c1, fill: "none" }} />
      <path d="M62 24 h24 v20 q0 11 -12 17 q-12 -6 -12 -17 z" strokeWidth="3" strokeLinejoin="round" style={{ stroke: c2, fill: "none" }} />
      <text x="50" y="50" textAnchor="middle" style={{ fill: c1, font: "800 17px var(--f-display, sans-serif)" }}>VS</text>
      <circle cx="50" cy="80" r="9" strokeWidth="2.5" style={{ stroke: c2, fill: "none" }} />
      <path d="M50 80 v-5 M50 80 h4" strokeWidth="2.5" strokeLinecap="round" style={{ stroke: c2, fill: "none" }} />
    </>
  ),
  game_results: (c1, c2) => (
    <>
      <text x="33" y="42" textAnchor="middle" style={{ fill: c1, font: "800 26px var(--f-display, sans-serif)" }}>2</text>
      <rect x="45" y="29" width="10" height="3.5" style={{ fill: c2 }} />
      <text x="67" y="42" textAnchor="middle" style={{ fill: c2, font: "800 26px var(--f-display, sans-serif)" }}>1</text>
      <path d="M40 60 h20 v6 q0 10 -10 12 q-10 -2 -10 -12 z" strokeWidth="3" strokeLinejoin="round" style={{ stroke: c1, fill: "none" }} />
      <path d="M40 62 q-7 0 -7 -7 M60 62 q7 0 7 -7" strokeWidth="2.5" style={{ stroke: c1, fill: "none" }} />
      <rect x="46" y="82" width="8" height="6" style={{ fill: c1 }} />
      <rect x="39" y="88" width="22" height="3" style={{ fill: c1 }} />
    </>
  ),
  roster_reveal: (c1, c2) => (
    <>
      {[16, 33, 50, 67, 84].map((x, i) => {
        const col = i % 2 ? c2 : c1;
        return (
          <g key={x}>
            <circle cx={x} cy="42" r="7" strokeWidth="2.5" style={{ stroke: col, fill: "none" }} />
            <path d={`M${x - 10} 74 q0 -13 10 -13 q10 0 10 13`} strokeWidth="2.5" style={{ stroke: col, fill: "none" }} />
          </g>
        );
      })}
    </>
  ),
  tournament_announcement: (c1, c2) => (
    <>
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
        const rad = (a * Math.PI) / 180, cx = 50, cy = 44;
        return <line key={a} x1={cx + 21 * Math.cos(rad)} y1={cy + 21 * Math.sin(rad)} x2={cx + 30 * Math.cos(rad)} y2={cy + 30 * Math.sin(rad)} strokeWidth="2" strokeLinecap="round" style={{ stroke: c2 }} />;
      })}
      <path d="M40 32 h20 v6 q0 10 -10 12 q-10 -2 -10 -12 z" strokeWidth="3" strokeLinejoin="round" style={{ stroke: c1, fill: "none" }} />
      <rect x="46" y="50" width="8" height="6" style={{ fill: c1 }} />
      <rect x="39" y="56" width="22" height="3" style={{ fill: c1 }} />
      <text x="50" y="88" textAnchor="middle" style={{ fill: c2, font: "800 16px var(--f-display, sans-serif)" }}>$</text>
    </>
  ),
  tournament_banner: (c1, c2) => (
    <>
      <circle cx="66" cy="32" r="8" strokeWidth="2.5" style={{ stroke: c2, fill: "none" }} />
      <path d="M14 64 L34 38 L48 58 L62 42 L86 64 Z" strokeWidth="3" strokeLinejoin="round" style={{ stroke: c1, fill: "none" }} />
      <line x1="12" y1="64" x2="88" y2="64" strokeWidth="2.5" style={{ stroke: c1 }} />
      <rect x="24" y="76" width="52" height="13" rx="2" strokeWidth="2.5" style={{ stroke: c2, fill: "none" }} />
      <line x1="31" y1="82.5" x2="69" y2="82.5" strokeWidth="2" style={{ stroke: c2 }} />
    </>
  ),
};

function MiniPosterPreview({ type, on }) {
  const c1 = on ? "var(--crim)" : "var(--fg-3)";
  const c2 = on ? "var(--cy)" : "var(--fg-4)";
  const bg = "linear-gradient(140deg, oklch(20% 0.04 350), oklch(12% 0.02 350))";
  const art = POSTER_TYPE_ART[type];
  return (
    <div style={{
      flex: 1, borderRadius: 6, background: bg,
      border: "1px solid var(--line)",
      position: "relative", overflow: "hidden", minHeight: 100,
    }}>
      <div style={{ position: "absolute", inset: 0, opacity: 0.4,
        backgroundImage: "repeating-linear-gradient(0deg, rgba(255,255,255,0.03) 0 1px, transparent 1px 4px)" }} />
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
        <svg viewBox="0 0 100 100" width="100%" height="100%" style={{ maxHeight: 92 }}>
          {art ? art(c1, c2) : null}
        </svg>
      </div>
      <div className="mono" style={{ position: "absolute", top: 8, left: 10, fontSize: 7, letterSpacing: "0.18em", color: c1, textTransform: "uppercase" }}>
        {type.replace(/_/g, " ").toUpperCase()}
      </div>
    </div>
  );
}

/* ───── Step 2: Poster data ───── */
function Step2({ form, set }) {
  const ptype = form.poster_type;
  // "Phase" (Playoffs / Quarterfinals) only makes sense for a specific match —
  // not for whole-tournament announce/banner posters, so hide it there.
  const showPhase = ptype === "gameday" || ptype === "game_results";
  return (
    <>
      {ptype !== "roster_reveal" && (
        <>
          <SectionLabel n="02.A" label="Tournament"
            hint="Pick one of your tournaments from the list, or type any name." />
          <div style={{ display: "grid", gridTemplateColumns: showPhase ? "1fr 1fr 240px" : "1fr 240px", gap: 14, marginBottom: 32 }}>
            <FormField label="Tournament name" req>
              {/* Free text, with a dropdown of the org's previously-used tournaments. */}
              <input className="input" list="epai-tournament-names" value={form.tournament_name}
                     onChange={(e) => set({ tournament_name: e.target.value })}
                     placeholder="Pick or type a tournament name" />
              <datalist id="epai-tournament-names">
                {(form.tournament_name_suggestions || []).map((n) => <option key={n} value={n} />)}
              </datalist>
            </FormField>
            {showPhase && (
              <FormField label="Tournament phase">
                <input className="input" value={form.tournament_phase} onChange={(e) => set({ tournament_phase: e.target.value })} placeholder="Playoffs · Quarterfinals" />
              </FormField>
            )}
            <FormField label="Tournament logo">
              <AssetUpload assetType="tournament-logos" orgId={form.org_id}
                           asset={form.tournament_logo_asset}
                           onChange={(a) => set({ tournament_logo_asset: a })}
                           label="Pick or upload" small />
            </FormField>
          </div>
        </>
      )}

      {(ptype === "gameday" || ptype === "game_results") && (
        <>
          <SectionLabel n="02.B" label="Matchup" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 24 }}>
            <TeamBlock side="A" form={form} team={form.team_a} onChange={(t) => set({ team_a: t })} />
            <TeamBlock side="B" form={form} team={form.team_b} onChange={(t) => set({ team_b: t })} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 24 }}>
            <FormField label="Format" req>
              <Segmented value={form.match_format} options={["Bo1","Bo3","Bo5"]} onChange={(v) => {
                // Shrinking the format may make the current scores invalid — re-clamp
                // each to the new win target, then to the new total.
                const target = seriesWinTarget(v);
                const max = seriesMaxGames(v);
                let a = Math.min(Number.isFinite(+form.score_a) ? +form.score_a : 0, target);
                let b = Math.min(Number.isFinite(+form.score_b) ? +form.score_b : 0, target);
                if (a + b > max) { b = Math.min(b, max); a = Math.min(a, max - b); }
                set(withTrimmedMaps(form, { match_format: v, score_a: a, score_b: b }));
              }} />
            </FormField>
            <FormField label="Date">
              <input className="input" type="date" value={form.match_date} onChange={(e) => set({ match_date: e.target.value })} />
            </FormField>
            {ptype === "gameday" && (
              <FormField label="Match time">
                <input className="input" type="time" value={form.match_time} onChange={(e) => set({ match_time: e.target.value })} />
              </FormField>
            )}
          </div>

          {ptype === "gameday" && (
            <>
              <SectionLabel n="02.C" label="Stream" />
              <div style={{ display: "grid", gridTemplateColumns: "180px 200px 1fr", gap: 14, marginBottom: 24 }}>
                <FormField label="Timezone">
                  <select className="select" value={form.timezone} onChange={(e) => set({ timezone: e.target.value })}>
                    {["CET","EST","PST","UTC","KST","BRT","GMT","IST"].map((t) => <option key={t}>{t}</option>)}
                  </select>
                </FormField>
                <FormField label="Platform">
                  <select className="select" value={form.stream_platform} onChange={(e) => set({ stream_platform: e.target.value })}>
                    {["Twitch","YouTube","Kick","AfreecaTV"].map((t) => <option key={t}>{t}</option>)}
                  </select>
                </FormField>
                <FormField label="Stream URL">
                  <input className="input" value={form.stream_url} onChange={(e) => set({ stream_url: e.target.value })} placeholder="https://twitch.tv/menaproleague" />
                </FormField>
              </div>
            </>
          )}

          {ptype === "game_results" && (() => {
            const seriesBad = !seriesScoreValid(form);
            const scoreStyle = seriesBad
              ? { borderColor: "var(--crim)", outline: "2px solid var(--crim-soft)", outlineOffset: -1 }
              : undefined;
            return (
            <>
              <SectionLabel n="02.C" label="Score"
                hint={`${form.match_format} — first to ${seriesWinTarget(form.match_format)} wins; the two scores can total at most ${seriesMaxGames(form.match_format)}.`} />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 14, marginBottom: 24, alignItems: "end" }}>
                <FormField label="Team 1 score" req>
                  <input className="input" type="number" value={form.score_a} style={scoreStyle}
                         onChange={(e) => set(withTrimmedMaps(form, { score_a: clampScore(e.target.value, form.score_b, form.match_format) }))}
                         min="0" max={seriesWinTarget(form.match_format)} />
                </FormField>
                <FormField label="Team 2 score" req>
                  <input className="input" type="number" value={form.score_b} style={scoreStyle}
                         onChange={(e) => set(withTrimmedMaps(form, { score_b: clampScore(e.target.value, form.score_a, form.match_format) }))}
                         min="0" max={seriesWinTarget(form.match_format)} />
                </FormField>
                <div className="card" style={{ padding: "10px 14px", display: "flex", alignItems: "center", gap: 10, borderColor: "var(--crim-line)", background: "var(--crim-soft)" }}>
                  <span className="mono" style={{ fontSize: 10.5, letterSpacing: "0.1em", color: "var(--fg-3)", textTransform: "uppercase" }}>Winner</span>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>
                    {(+form.score_a) > (+form.score_b)
                      ? (form.team_a.name || "Team A")
                      : (+form.score_b) > (+form.score_a)
                        ? (form.team_b.name || "Team B")
                        : "—"}
                  </span>
                </div>
              </div>

              {form.game === "valorant" && (() => {
                const n = gamesPlayed(form);
                const maps = form.valorant_maps;
                const issues = valorantMapIssues(form);
                const canAdd = maps.length < n;
                return (
                <>
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: 10, alignItems: "center" }}>
                    <span className="label" style={{ marginBottom: 0 }}>
                      Map results · <span className="mono" style={{ color: (maps.length === n && n > 0) ? "var(--cy)" : "var(--fg-3)" }}>{maps.length}/{n}</span>
                    </span>
                    <button className="btn btn-ghost" style={{ height: 30, fontSize: 12, opacity: canAdd ? 1 : 0.4, cursor: canAdd ? "pointer" : "not-allowed" }}
                            disabled={!canAdd}
                            title={canAdd ? "Add the next map" : `A ${(form.match_format || "BO5").toUpperCase()} ending ${form.score_a}-${form.score_b} played ${n} map${n === 1 ? "" : "s"}`}
                            onClick={() => set({ valorant_maps: [...maps, { map_name: firstUnusedMap(maps), rounds_team1: "", rounds_team2: "" }] })}>
                      <Icon name="plus" size={12}/> Add map
                    </button>
                  </div>
                  <div className="col" style={{ gap: 8, marginBottom: 12 }}>
                    {maps.map((m, i) => {
                      const scoreOk = isValidValorantMapScore(m.rounds_team1, m.rounds_team2);
                      const usedElsewhere = new Set(maps.filter((_, j) => j !== i).map((x) => x.map_name));
                      const badStyle = { border: "1px solid var(--crim)" };
                      return (
                      <div key={i} className="card" style={{ padding: "10px 14px", display: "grid", gridTemplateColumns: "1fr 80px 80px 24px", gap: 14, alignItems: "center" }}>
                        <select className="select" value={m.map_name}
                                onChange={(e) => { const next = [...maps]; next[i] = { ...next[i], map_name: e.target.value }; set({ valorant_maps: next }); }}>
                          {VALORANT_MAPS.filter((x) => x === m.map_name || !usedElsewhere.has(x)).map((x) => <option key={x}>{x}</option>)}
                        </select>
                        <input className="input" type="number" min="0" value={m.rounds_team1} style={scoreOk ? undefined : badStyle}
                               onChange={(e) => { const next = [...maps]; next[i] = { ...next[i], rounds_team1: e.target.value }; set({ valorant_maps: next }); }} />
                        <input className="input" type="number" min="0" value={m.rounds_team2} style={scoreOk ? undefined : badStyle}
                               onChange={(e) => { const next = [...maps]; next[i] = { ...next[i], rounds_team2: e.target.value }; set({ valorant_maps: next }); }} />
                        <button className="btn-icon" style={{ background: "transparent", border: 0, color: "var(--fg-3)", cursor: "pointer" }}
                                onClick={() => set({ valorant_maps: maps.filter((_, j) => j !== i) })}>
                          <Icon name="cross" size={14} />
                        </button>
                      </div>
                      );
                    })}
                  </div>
                  {issues.length > 0 ? (
                    <div className="card" style={{ padding: "10px 14px", marginBottom: 24, borderColor: "var(--crim-line)", background: "var(--crim-soft)" }}>
                      {issues.map((msg, k) => (
                        <div key={k} className="mono" style={{ fontSize: 11, color: "var(--crim)" }}>• {msg}</div>
                      ))}
                    </div>
                  ) : (
                    <div className="mono" style={{ fontSize: 11, color: "var(--fg-4)", marginBottom: 24 }}>
                      Maps = games played ({n}). Valid scores: 13-0 … 13-11, or OT 14-12, 15-13, 16-14 …
                    </div>
                  )}
                </>
                );
              })()}

              <div className="card" style={{ padding: 14, marginBottom: 24, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>Highlight MVP <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>· optional</span></div>
                  <div className="hint" style={{ marginTop: 2 }}>Adds a featured player block with their key stat.</div>
                </div>
                <SwitchToggle on={form.mvp_on} onChange={(v) => set({ mvp_on: v })} />
              </div>
              {form.mvp_on && (
                <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr", gap: 14, marginBottom: 24, marginTop: -8 }}>
                  <FormField label="Player IGN"><input className="input" value={form.mvp_ign} onChange={(e) => set({ mvp_ign: e.target.value })} placeholder="Caps" /></FormField>
                  <FormField label="Stat label"><input className="input" value={form.mvp_stat_label} onChange={(e) => set({ mvp_stat_label: e.target.value })} placeholder="KDA" /></FormField>
                  <FormField label="Stat value"><input className="input" value={form.mvp_stat_value} onChange={(e) => set({ mvp_stat_value: e.target.value })} placeholder="8.5" /></FormField>
                </div>
              )}
            </>
          );
          })()}
        </>
      )}

      {ptype === "roster_reveal" && <RosterFields form={form} set={set} />}
      {ptype === "tournament_announcement" && <AnnouncementFields form={form} set={set} />}
      {ptype === "tournament_banner" && <BannerFields form={form} set={set} />}
    </>
  );
}

function RosterFields({ form, set }) {
  const setPlayer = (i, patch) => {
    const next = [...form.roster_players];
    next[i] = { ...next[i], ...patch };
    set({ roster_players: next });
  };
  return (
    <>
      <SectionLabel n="02.A" label="Team" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 240px", gap: 14, marginBottom: 10 }}>
        <FormField label="Team name" req>
          <input className="input" value={form.roster_team.name}
                 onChange={(e) => set({ roster_team: { ...form.roster_team, name: e.target.value } })} placeholder="MED-IA" />
        </FormField>
        <FormField label="Team logo">
          <AssetUpload assetType="team-logos" orgId={form.org_id}
                       asset={form.roster_team.logo_asset}
                       onChange={(a) => set({ roster_team: { ...form.roster_team, logo_asset: a } })}
                       label="Pick or upload" small />
        </FormField>
      </div>
      {/* Team logos already in the brand library — one click fills name + logo. */}
      {(form.team_logo_library || []).length > 0 && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 24 }}>
          <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.08em" }}>QUICK PICK:</span>
          {form.team_logo_library.map((t) => {
            const on = form.roster_team.logo_asset && form.roster_team.logo_asset.asset_id === t.asset.asset_id;
            return (
              <button key={t.asset.asset_id} title={`Use ${t.key} + its logo`}
                onClick={() => set({ roster_team: { ...form.roster_team, name: t.key, logo_asset: t.asset } })}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  fontFamily: "var(--f-mono)", fontSize: 10, letterSpacing: "0.06em",
                  padding: "2px 8px 2px 3px", background: on ? "var(--crim-soft)" : "transparent",
                  border: "1px solid " + (on ? "var(--crim-line)" : "var(--line)"), borderRadius: 999,
                  color: "var(--fg-2)", cursor: "pointer",
                }}>
                {t.asset.signed_url
                  ? <img src={t.asset.signed_url} alt="" style={{ width: 18, height: 18, borderRadius: "50%", objectFit: "cover", background: "var(--surface-3)" }} />
                  : <span style={{ width: 18, height: 18, borderRadius: "50%", background: "var(--surface-3)" }} />}
                {t.key}
              </button>
            );
          })}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 28 }}>
        <FormField label="Season">
          <input className="input" value={form.roster_season} onChange={(e) => set({ roster_season: e.target.value })} placeholder="2026 Summer" />
        </FormField>
        <FormField label="Head coach">
          <input className="input" value={form.roster_coach} onChange={(e) => set({ roster_coach: e.target.value })} placeholder="kaSing" />
        </FormField>
      </div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
        <span className="label" style={{ marginBottom: 0 }}>Players · {form.roster_players.length}</span>
        <RosterPhotoStatus form={form} />
      </div>
      <div className="col" style={{ gap: 8 }}>
        {form.roster_players.map((p, i) => (
          <div key={i} className="card" style={{ padding: 12 }}>
            <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 140px 130px", gap: 12, alignItems: "center" }}>
              <AssetUpload assetType="player-images" orgId={form.org_id}
                           asset={p.image_asset}
                           onChange={(a) => setPlayer(i, { image_asset: a })}
                           square />
              <input className="input" value={p.ign} placeholder="IGN" onChange={(e) => setPlayer(i, { ign: e.target.value })} />
              <select className="select" value={coerceRole(p.role, form.game, i)} onChange={(e) => setPlayer(i, { role: e.target.value })}>
                {rolesForGame(form.game).map((r) => <option key={r}>{r}</option>)}
              </select>
              <label style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 6, color: p.is_new_signing ? "var(--cy)" : "var(--fg-3)", cursor: "pointer" }}>
                <input type="checkbox" checked={p.is_new_signing} onChange={(e) => setPlayer(i, { is_new_signing: e.target.checked })}
                       style={{ accentColor: "var(--cy)" }} />
                New signing
              </label>
            </div>
            <ImageQuickPick library={form.player_image_library}
                            selectedId={p.image_asset && p.image_asset.asset_id}
                            onPick={(a) => setPlayer(i, { image_asset: a })} />
          </div>
        ))}
      </div>
    </>
  );
}

function RosterPhotoStatus({ form }) {
  const c = rosterPhotoCount(form);
  if (c === null) return null;
  const ok = rosterPhotoValid(form);
  const tone = ok ? "var(--ok)" : "var(--crim)";
  const label = c === 0
    ? "Text-only roster · OK (optional: add 1 hero photo or all 5)"
    : c === 1
      ? "Single hero · OK"
      : c === 5
        ? "Full lineup · OK"
        : `Invalid — pick 0, 1, or all 5 photos (currently ${c})`;
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: tone }} />
      <span className="mono" style={{ fontSize: 11, color: tone, letterSpacing: "0.05em", textTransform: "uppercase" }}>
        {c} / 5 photos · {label}
      </span>
    </span>
  );
}

const TOURNAMENT_FORMATS = [
  "Single Elimination", "Double Elimination", "Round Robin", "Swiss",
  "Groups + Playoffs", "GSL Groups", "League / Round Robin",
];

function AnnouncementFields({ form, set }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
      <FormField label="Start date" req>
        <input className="input" type="date" value={form.ann_start_date} onChange={(e) => set({ ann_start_date: e.target.value })} />
      </FormField>
      <FormField label="Location" req>
        <input className="input" value={form.ann_location} onChange={(e) => set({ ann_location: e.target.value })} placeholder="Riyadh, KSA" />
      </FormField>
      <FormField label="Prize pool" req>
        <input className="input" value={form.ann_prize_pool} onChange={(e) => set({ ann_prize_pool: e.target.value })} placeholder="$50,000" />
      </FormField>
      <FormField label="Teams count">
        <input className="input" type="number" value={form.ann_teams_count} onChange={(e) => set({ ann_teams_count: e.target.value })} placeholder="16" />
      </FormField>
      <FormField label="Format">
        <select className="select" value={form.ann_format} onChange={(e) => set({ ann_format: e.target.value })}>
          <option value="">— select format —</option>
          {TOURNAMENT_FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </FormField>
      <FormField label="">‎</FormField>
      <FormField label="Tagline" req>
        <div className="row" style={{ gap: 6 }}>
          <input className="input" style={{ flex: 1 }} value={form.ann_tagline} onChange={(e) => set({ ann_tagline: e.target.value })} placeholder="The road to glory begins." />
          <TaglineRollButton posterType="tournament_announcement" set={set} withSub />
        </div>
      </FormField>
      <FormField label="Sub-tagline">
        <input className="input" value={form.ann_sub_tagline} onChange={(e) => set({ ann_sub_tagline: e.target.value })} placeholder="16 teams. One throne." />
      </FormField>
    </div>
  );
}

// "🎲 Random" — fills the tagline field (and sub-tagline, when `withSub`) from the
// curated backend bank, for users who'd rather not write their own. Re-click to
// re-roll; the value stays editable afterward.
function TaglineRollButton({ posterType, set, withSub }) {
  const [busy, setBusy] = React.useState(false);
  const roll = async () => {
    setBusy(true);
    try {
      const r = await window.api.randomTagline(posterType);
      const patch = { ann_tagline: r.tagline || "" };
      if (withSub) patch.ann_sub_tagline = r.sub_tagline || "";
      set(patch);
    } catch (e) {
      if (window.toast && window.toast.error) window.toast.error("Couldn't fetch a tagline: " + e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <button type="button" className="btn btn-ghost" onClick={roll} disabled={busy}
            title="Fill with a random tagline from the bank"
            style={{ padding: "0 12px", whiteSpace: "nowrap", flexShrink: 0 }}>
      🎲 {busy ? "…" : "Random"}
    </button>
  );
}

function BannerFields({ form, set }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
      <FormField label="Date range" req>
        <input className="input" value={form.banner_date_range} onChange={(e) => set({ banner_date_range: e.target.value })} placeholder="Jul 4 — Aug 12" />
      </FormField>
      <FormField label="Location" req>
        <input className="input" value={form.ann_location} onChange={(e) => set({ ann_location: e.target.value })} placeholder="Riyadh, KSA" />
      </FormField>
      <FormField label="Prize pool" req>
        <input className="input" value={form.ann_prize_pool} onChange={(e) => set({ ann_prize_pool: e.target.value })} placeholder="$50,000" />
      </FormField>
      <FormField label="Tagline" req style={{ gridColumn: "span 3" }}>
        <div className="row" style={{ gap: 6 }}>
          <input className="input" style={{ flex: 1 }} value={form.ann_tagline} onChange={(e) => set({ ann_tagline: e.target.value })} placeholder="The road to glory begins." />
          <TaglineRollButton posterType="tournament_banner" set={set} />
        </div>
      </FormField>
    </div>
  );
}

function TeamBlock({ side, form, team, onChange }) {
  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <span className="mono" style={{ fontSize: 10.5, letterSpacing: "0.14em", color: "var(--crim)", textTransform: "uppercase" }}>Team {side}</span>
        <span className="badge" style={{ background: "transparent", borderStyle: "dashed" }}>vs</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 100px", gap: 12, marginBottom: 10 }}>
        <AssetUpload assetType="team-logos" orgId={form.org_id}
                     asset={team.logo_asset}
                     onChange={(a) => onChange({ ...team, logo_asset: a })}
                     square />
        <FormField label="Team name" req inline>
          <input className="input" value={team.name} onChange={(e) => onChange({ ...team, name: e.target.value })} />
        </FormField>
        <FormField label="Short" inline>
          <input className="input" value={team.short} onChange={(e) => onChange({ ...team, short: e.target.value })} maxLength="4" />
        </FormField>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.08em" }}>QUICK PICK:</span>

        {/* Teams whose logos are already in the brand library — one click fills name + logo. */}
        {(form.team_logo_library || []).map((t) => {
          const on = team.logo_asset && team.logo_asset.asset_id === t.asset.asset_id;
          return (
            <button key={t.asset.asset_id}
              title={`Use ${t.key} + its uploaded logo`}
              onClick={() => onChange({ ...team, name: t.key, short: t.short, logo_asset: t.asset })}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                fontFamily: "var(--f-mono)", fontSize: 10, letterSpacing: "0.06em",
                padding: "2px 8px 2px 3px", background: on ? "var(--crim-soft)" : "transparent",
                border: "1px solid " + (on ? "var(--crim-line)" : "var(--line)"), borderRadius: 999,
                color: "var(--fg-2)", cursor: "pointer",
              }}>
              {t.asset.signed_url
                ? <img src={t.asset.signed_url} alt="" style={{ width: 18, height: 18, borderRadius: "50%", objectFit: "cover", background: "var(--surface-3)" }} />
                : <span style={{ width: 18, height: 18, borderRadius: "50%", background: "var(--surface-3)" }} />}
              {t.key}
            </button>
          );
        })}

        {/* Static presets without an uploaded logo — fill name only (user uploads). */}
        {PRESET_TEAMS.filter((p) => !(form.team_logo_library || []).some((t) => t.short === p.short)).map((t) => (
          <button key={t.name}
            onClick={() => onChange({ ...team, name: t.name, short: t.short })}
            style={{
              fontFamily: "var(--f-mono)", fontSize: 10, letterSpacing: "0.06em",
              padding: "3px 8px", background: "transparent",
              border: "1px solid var(--line)", borderRadius: 999,
              color: "var(--fg-2)", cursor: "pointer",
            }}>
            {t.short}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ───── Step 3: Visual style ───── */
function Step3({ form, set }) {
  const fresh = form.style_mode === "fresh";
  // If the client disabled consistency, never leave the form stuck on it.
  React.useEffect(() => {
    if (!features().consistency && form.style_mode === "consistency") {
      set({ style_mode: "fresh", tournament_id: "", style_dna: null, style_dna_status: null });
    }
  }, [form.style_mode]);

  // In consistency mode, load the org's whole saved-style library so the user can
  // PICK any style — decoupled from the poster's tournament name. (Roster Reveal
  // has no tournament name, and a style may come from a different tournament.)
  React.useEffect(() => {
    if (form.style_mode !== "consistency") return;
    let cancelled = false;
    set({ style_dna_loading: true });
    window.api.listStyleDnas({ orgId: form.org_id })
      .then((res) => {
        if (cancelled) return;
        set({ style_library: res.style_dnas || [], style_dna_loading: false });
      })
      .catch(() => { if (!cancelled) set({ style_library: [], style_dna_loading: false }); });
    return () => { cancelled = true; };
  }, [form.style_mode, form.org_id]);

  return (
    <>
      <div style={{ display: "flex", gap: 0, marginBottom: 28, background: "var(--surface)", padding: 4, borderRadius: 10, border: "1px solid var(--line)" }}>
        {[
          { id: "fresh", label: "Fresh look", desc: "Define a new look for this poster" },
          { id: "consistency", label: "Match a saved style", desc: "Reuse any saved Style DNA from your library" },
        ].filter((m) => m.id !== "consistency" || features().consistency).map((m) => {
          const on = form.style_mode === m.id;
          return (
            <button key={m.id} onClick={() => set(m.id === "fresh"
              ? { style_mode: "fresh", tournament_id: "", style_dna: null, style_dna_status: null }
              : { style_mode: "consistency" })}
              style={{
                flex: 1, background: on ? "var(--surface-3)" : "transparent",
                border: 0, padding: "12px 16px", borderRadius: 7, cursor: "pointer", textAlign: "left",
                color: on ? "var(--fg)" : "var(--fg-3)",
              }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
                {on && <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--crim)" }} />}
                {m.label}
              </div>
              <div style={{ fontSize: 11.5, marginTop: 4, color: on ? "var(--fg-3)" : "var(--fg-4)" }}>{m.desc}</div>
            </button>
          );
        })}
      </div>

      {fresh ? (
        <>
          <SectionLabel n="03.A" label="Vibe" hint="The overall look & feel — color treatment, lighting, composition." />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 32 }}>
            {VIBES.map((v) => {
              const on = form.vibe === v.id;
              return (
                <button key={v.id} onClick={() => set({ vibe: v.id })}
                  className="card"
                  style={{
                    padding: 0, cursor: "pointer", background: "transparent",
                    borderColor: on ? "var(--crim)" : "var(--line)",
                    outline: on ? "3px solid var(--crim-soft)" : "none", outlineOffset: -1,
                    textAlign: "left", overflow: "hidden",
                  }}>
                  <div style={{ height: 96, background: `linear-gradient(140deg, ${v.grad[0]}, ${v.grad[1]})`, position: "relative", overflow: "hidden" }}>
                    {/* Real generated example for this vibe; falls back to the gradient if missing. */}
                    <img src={`assets/vibes/${v.id}.png`} alt="" aria-hidden="true"
                         onError={(e) => { e.currentTarget.style.display = "none"; }}
                         style={{ position: "absolute", inset: 0, width: "100%", height: "100%",
                                  objectFit: "cover", objectPosition: "center 35%",
                                  opacity: on ? 1 : 0.9, transition: "opacity .3s" }} />
                    <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, rgba(0,0,0,0.08) 0 1px, transparent 1px 3px)" }} />
                    {on && <div style={{ position: "absolute", top: 8, right: 8, width: 22, height: 22, borderRadius: "50%", background: "var(--crim)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 2px 8px rgba(0,0,0,0.5)" }}>
                      <Icon name="check" size={12}/>
                    </div>}
                  </div>
                  <div style={{ padding: "12px 14px" }}>
                    <div style={{ fontFamily: "var(--f-display)", fontSize: 14 }}>{v.label}</div>
                    <div style={{ fontSize: 11.5, color: "var(--fg-3)", marginTop: 3 }}>{v.desc}</div>
                  </div>
                </button>
              );
            })}
          </div>

          <SectionLabel n="03.B" label="Color" />
          <div className="card" style={{ padding: 18, marginBottom: 32 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: form.color_mode === "dominant" ? 16 : 0 }}>
              {[
                { id: "dominant", title: "Dominant color", desc: "Force one color across the whole poster." },
                { id: "auto", title: "Match background", desc: "Let the AI take colors from the background." },
              ].map((m) => {
                const on = form.color_mode === m.id;
                return (
                  <button key={m.id} onClick={() => set({ color_mode: m.id })} className="card"
                    style={{ padding: 14, cursor: "pointer", background: "transparent",
                      borderColor: on ? "var(--crim)" : "var(--line)",
                      outline: on ? "3px solid var(--crim-soft)" : "none", outlineOffset: -1, textAlign: "left" }}>
                    <div style={{ fontFamily: "var(--f-display)", fontSize: 13.5 }}>{m.title}</div>
                    <div style={{ fontSize: 11.5, color: "var(--fg-3)", marginTop: 4 }}>{m.desc}</div>
                  </button>
                );
              })}
            </div>
            {form.color_mode === "dominant" ? (
              <div className="row" style={{ gap: 14 }}>
                <div style={{ width: 56, height: 56, borderRadius: 10, background: form.color, border: "2px solid var(--line-strong)", boxShadow: `0 0 30px ${form.color}55` }} />
                <div className="col" style={{ flex: 1, gap: 8 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <input className="input mono" style={{ width: 130, fontFamily: "var(--f-mono)", textTransform: "uppercase" }} value={form.color} onChange={(e) => set({ color: e.target.value })} />
                    <input type="color" value={form.color} onChange={(e) => set({ color: e.target.value })}
                      style={{ width: 40, height: 40, padding: 0, border: "1px solid var(--line)", borderRadius: 8, background: "transparent" }} />
                    <div style={{ width: 1, height: 28, background: "var(--line)" }} />
                    <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                      {COLOR_PRESETS.map((c) => (
                        <button key={c} onClick={() => set({ color: c })}
                          style={{ width: 28, height: 28, borderRadius: 6, background: c, border: "1px solid var(--line-strong)",
                            outline: form.color.toLowerCase() === c.toLowerCase() ? "2px solid white" : "none", outlineOffset: 1, cursor: "pointer" }} />
                      ))}
                    </div>
                  </div>
                  <div className="hint" style={{ marginTop: 2 }}>Used as the dominant hue across the entire poster.</div>
                </div>
              </div>
            ) : (
              <div className="hint">The poster's palette is pulled from the AI-generated background — no single forced color. Works best with an AI-generated or uploaded background.</div>
            )}
          </div>

          <SectionLabel n="03.C" label="Energy" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            {ENERGY.map((e, i) => {
              const on = form.energy === e.id;
              return (
                <button key={e.id} onClick={() => set({ energy: e.id })}
                  className="card"
                  style={{
                    padding: 14, cursor: "pointer", background: "transparent",
                    borderColor: on ? "var(--crim)" : "var(--line)",
                    outline: on ? "3px solid var(--crim-soft)" : "none", outlineOffset: -1,
                    textAlign: "left",
                  }}>
                  <div style={{ display: "flex", gap: 3, marginBottom: 10 }}>
                    {[1,2,3,4].map((n) => (
                      <div key={n} style={{
                        flex: 1, height: 4, borderRadius: 1,
                        background: n <= i + 1 ? (on ? "var(--crim)" : "var(--fg-2)") : "var(--surface-3)",
                      }} />
                    ))}
                  </div>
                  <div style={{ fontFamily: "var(--f-display)", fontSize: 14 }}>{e.label}</div>
                  <div style={{ fontSize: 11.5, color: "var(--fg-3)", marginTop: 4 }}>{e.desc}</div>
                </button>
              );
            })}
          </div>
        </>
      ) : (
        <ConsistencyPanel form={form} set={set} />
      )}
    </>
  );
}

function ConsistencyPanel({ form, set }) {
  const lib = form.style_library || [];

  const pick = (tid) => {
    const dna = tid ? (lib.find((d) => d.tournament_id === tid) || null) : null;
    set({ style_dna: dna, style_dna_status: dna ? dna.status : null, tournament_id: dna ? tid : "" });
  };

  return (
    <div className="col" style={{ gap: 18 }}>
      <div className="card" style={{ padding: 18 }}>
        <div className="label" style={{ marginBottom: 8 }}>Choose a saved style</div>
        {form.style_dna_loading ? (
          <div className="mono" style={{ fontSize: 11, color: "var(--cy)", letterSpacing: "0.1em" }}>● LOADING YOUR STYLES…</div>
        ) : lib.length === 0 ? (
          <div className="hint">
            No saved styles yet. Generate a poster, then click <b>“Extract &amp; save as draft”</b> on the result to
            save its style — it'll then be reusable here on <b>any</b> poster type.
          </div>
        ) : (
          <>
            <select className="select" value={form.style_dna ? form.style_dna.tournament_id : ""}
                    onChange={(e) => pick(e.target.value)}>
              <option value="">— none (use fresh styling) —</option>
              {lib.map((d) => (
                <option key={d.tournament_id} value={d.tournament_id}>
                  {d.tournament_id} · {d.status}
                </option>
              ))}
            </select>
            <div className="hint" style={{ marginTop: 8 }}>
              Any saved style applies to any poster — including Roster Reveal, which has no tournament name.
            </div>
          </>
        )}
      </div>
      {form.style_dna && <DnaCard form={form} />}
    </div>
  );
}

function DnaCard({ form }) {
  if (!form.style_dna) return null;
  const dna = form.style_dna;
  return (
    <div className="card" style={{ padding: 24, borderColor: "var(--cy-line)" }}>
      <div className="row" style={{ gap: 14, marginBottom: 18 }}>
        <div style={{ width: 44, height: 44, borderRadius: 10, background: "var(--cy-soft)", color: "var(--cy)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon name="sparkles" />
        </div>
        <div>
          <div style={{ fontFamily: "var(--f-display)", fontSize: 18, letterSpacing: "-0.01em" }}>Using {dna.status} Style DNA</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--cy)", marginTop: 4, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            {dna.tournament_id} · {dna.status}{dna.approved_at ? ` · approved ${new Date(dna.approved_at).toLocaleDateString()}` : ""}
          </div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: dna.source_poster_url ? "180px 1fr" : "1fr", gap: 20 }}>
        {/* Source poster — the image this DNA was extracted from */}
        {dna.source_poster_url && (
          <div>
            <div className="label" style={{ marginBottom: 6 }}>Extracted from</div>
            <a href={dna.source_poster_url} target="_blank" rel="noopener"
               style={{ display: "block", borderRadius: 8, overflow: "hidden", border: "1px solid var(--line)", background: "var(--surface-2)" }}>
              <img src={dna.source_poster_url} alt="Source poster"
                   style={{ display: "block", width: "100%", height: "auto" }} />
            </a>
            <div className="hint" style={{ marginTop: 6 }}>This poster's look drives the style.</div>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr", gap: 18, alignContent: "start" }}>
          <DNAField label="Palette">
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              {(dna.palette || []).slice(0, 6).map((c) => (
                <div key={c} style={{ width: 28, height: 28, borderRadius: 4, background: c, border: "1px solid var(--line)" }} />
              ))}
            </div>
          </DNAField>
          <DNAField label="Energy" value={dna.energy || "—"} />
          <DNAField label="Lighting" value={dna.lighting || "—"} />
          <DNAField label="Atmosphere" value={dna.atmosphere || "—"} />
          <DNAField label="Particles" value={dna.particle_effects || "—"} />
          <DNAField label="Temperature" value={dna.color_temperature || "—"} />
        </div>
      </div>
    </div>
  );
}

function DNAField({ label, value, children }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 6 }}>{label}</div>
      {children || <div style={{ fontFamily: "var(--f-display)", fontSize: 14 }}>{value}</div>}
    </div>
  );
}

/* ───── Step 4: Format + extras ───── */
function Step4({ form, set }) {
  const canFeaturePlayer = ["gameday","game_results"].includes(form.poster_type);
  const [newSponsorName, setNewSponsorName] = React.useState("");
  // Feature flags configured by the client (which qualities/features orgs get).
  const feats = features();
  const allowedQ = feats.allowed_qualities || ["low", "medium", "high"];
  // If the chosen quality isn't offered on this plan, snap to the first allowed.
  React.useEffect(() => {
    if (!allowedQ.includes(form.quality)) set({ quality: allowedQ[0] || "medium" });
  }, [form.quality]);

  // Is this sponsor name already on the poster or in the brand library?
  const sponsorNameTaken = (name) => {
    const k = sponsorKeyOf({ name });
    return form.sponsor_assets.some((s) => sponsorKeyOf(s) === k)
        || (form.sponsor_library || []).some((s) => sponsorKeyOf(s) === k);
  };

  // Add/remove a library sponsor from the poster (dedup by sponsor identity).
  const toggleSponsor = (a) => {
    const k = sponsorKeyOf(a);
    if (form.sponsor_assets.some((s) => sponsorKeyOf(s) === k)) {
      set({ sponsor_assets: form.sponsor_assets.filter((s) => sponsorKeyOf(s) !== k) });
    } else {
      set({ sponsor_assets: [...form.sponsor_assets, a] });
    }
  };

  // Upload a brand-new sponsor: requires a UNIQUE name + a logo file. The name
  // is stored as the asset's name, so the chip shows the sponsor name (not the
  // filename) and duplicate names are rejected.
  const addSponsor = async (file, rawName) => {
    if (!file) return;
    const name = (rawName || "").trim();
    if (!name) { window.toast.error("Enter a sponsor name first."); return; }
    if (sponsorNameTaken(name)) { window.toast.info(`"${name}" is already in your sponsors.`); return; }
    try {
      const a = await window.api.uploadAsset({ orgId: form.org_id, assetType: "sponsor-logos", file, name });
      const patch = { sponsor_assets: [...form.sponsor_assets, a] };
      if (!(form.sponsor_library || []).some((s) => sponsorKeyOf(s) === sponsorKeyOf(a))) {
        patch.sponsor_library = [a, ...(form.sponsor_library || [])];
      }
      set(patch);
      setNewSponsorName("");
      window.toast.success(`"${name}" added.`);
    } catch (e) {
      window.toast.error(`Sponsor upload failed: ${e.message}`);
    }
  };
  const sponsorInputRef = React.useRef(null);
  // Validate the typed name, then open the file picker for its logo.
  const tryPickSponsorLogo = () => {
    const name = newSponsorName.trim();
    if (!name) { window.toast.error("Enter a sponsor name first."); return; }
    if (sponsorNameTaken(name)) { window.toast.info(`"${name}" is already in your sponsors.`); return; }
    if (sponsorInputRef.current) sponsorInputRef.current.click();
  };

  return (
    <>
      <SectionLabel n="04.A" label="Output format" hint="Where will you post this?" />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 36 }}>
        {FORMATS.map((f) => {
          const on = form.format_id === f.id;
          return (
            <button key={f.id} onClick={() => set({ format_id: f.id })}
              className="card"
              style={{
                padding: 20, cursor: "pointer", background: "transparent",
                borderColor: on ? "var(--crim)" : "var(--line)",
                outline: on ? "3px solid var(--crim-soft)" : "none", outlineOffset: -1,
                textAlign: "left",
                display: "flex", gap: 16, alignItems: "center",
              }}>
              <div style={{
                width: f.w, height: f.h, flexShrink: 0,
                background: on ? "linear-gradient(140deg, var(--crim), oklch(45% 0.18 320))" : "var(--surface-3)",
                borderRadius: 4,
                border: "1px solid var(--line-strong)",
              }} />
              <div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>{f.name}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 4, letterSpacing: "0.06em" }}>
                  {f.dims} · {f.ratio}
                </div>
                <div style={{ fontSize: 12, color: "var(--fg-2)", marginTop: 6 }}>{f.use}</div>
              </div>
            </button>
          );
        })}
      </div>

      <SectionLabel n="04.B" label="Render quality" hint="Higher quality = sharper detail, higher cost." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 12 }}>
        {QUALITY.filter((qq) => allowedQ.includes(qq.id)).map((qq) => {
          const on = (form.quality || "medium") === qq.id;
          const tierForm = { ...form, quality: qq.id };
          const tierTotal = estimateCost(tierForm).total;
          const tierScale = tierTotal > 0 ? coinTotalFor(tierForm, tierTotal) / tierTotal : null;
          return (
            <button key={qq.id} onClick={() => set({ quality: qq.id })}
              className="card"
              style={{
                padding: 18, cursor: "pointer", background: "transparent",
                borderColor: on ? "var(--crim)" : "var(--line)",
                outline: on ? "3px solid var(--crim-soft)" : "none", outlineOffset: -1,
                textAlign: "left",
              }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>{qq.name}</span>
                <span className="mono" style={{
                  fontSize: 11, padding: "2px 7px", borderRadius: 999,
                  background: on ? "var(--crim-soft)" : "var(--surface-3)",
                  color: on ? "var(--crim)" : "var(--fg-3)",
                }}>×{qq.mult}</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--fg-2)", minHeight: 32 }}>{qq.blurb}</div>
              <div className="mono" style={{ fontSize: 12.5, color: "var(--fg)", marginTop: 8 }}>≈ {rc(tierTotal, tierScale)}</div>
              {qq.recommended && (
                <div className="mono" style={{ fontSize: 9.5, color: "var(--fg-4)", marginTop: 4, letterSpacing: "0.1em" }}>RECOMMENDED</div>
              )}
            </button>
          );
        })}
      </div>
      <div className="hint" style={{ marginBottom: 36 }}>
        Relative to <b>Medium</b>: <b>Low</b> ≈ ×0.25, <b>High</b> ≈ ×4. Quality changes only the
        image-generation cost — the prompt stage and your uploaded logos cost the same regardless.
      </div>

      <SectionLabel n="04.C" label="Extras" />
      <div className="col" style={{ gap: 12 }}>
        {canFeaturePlayer && (
          <ToggleCard
            title="Featured player"
            desc="Drops a hero portrait into the composition. The AI scales & crops to fit the poster."
            on={form.featured_player}
            onChange={(v) => set({ featured_player: v })}
            expand={form.featured_player && (
              <div className="col" style={{ gap: 4 }}>
                <div className="row" style={{ gap: 14 }}>
                  <AssetUpload assetType="player-images" orgId={form.org_id}
                               asset={form.featured_player_asset}
                               onChange={(a) => set({ featured_player_asset: a })}
                               label="Pick or upload player photo" wide />
                </div>
                <ImageQuickPick library={form.player_image_library}
                                selectedId={form.featured_player_asset && form.featured_player_asset.asset_id}
                                onPick={(a) => set({ featured_player_asset: a })} />
              </div>
            )}
          />
        )}
        <BackgroundSourceCard form={form} set={set} />
        {feats.sponsor_bar && <ToggleCard
          title="Sponsor bar"
          desc="A strip of sponsor logos along the bottom of the poster."
          on={form.sponsor_bar}
          onChange={(v) => set({ sponsor_bar: v })}
          expand={form.sponsor_bar && (
            <>
              <div className="hint" style={{ marginBottom: 10 }}>
                Pick from your library or upload new. Recommended: 3–6. Duplicate sponsors are skipped automatically.
              </div>

              {/* Quick pick — sponsor logos already uploaded for this org. Click to
                  add/remove; selecting an already-added sponsor toggles it off. */}
              {(form.sponsor_library || []).length > 0 && (
                <div className="row" style={{ gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.08em", marginRight: 2 }}>QUICK PICK:</span>
                  {form.sponsor_library.map((a) => {
                    const on = form.sponsor_assets.some((s) => sponsorKeyOf(s) === sponsorKeyOf(a));
                    return (
                      <button key={a.asset_id || sponsorKeyOf(a)}
                        title={on ? "Remove from this poster" : "Add to this poster"}
                        onClick={() => toggleSponsor(a)}
                        style={{
                          display: "flex", alignItems: "center", gap: 6,
                          fontFamily: "var(--f-mono)", fontSize: 10, letterSpacing: "0.04em",
                          padding: "2px 8px 2px 3px",
                          background: on ? "var(--crim-soft)" : "transparent",
                          border: "1px solid " + (on ? "var(--crim-line)" : "var(--line)"), borderRadius: 999,
                          color: "var(--fg-2)", cursor: "pointer",
                        }}>
                        {a.signed_url
                          ? <img src={a.signed_url} alt="" style={{ width: 18, height: 18, borderRadius: 4, objectFit: "contain", background: "var(--surface-3)" }} />
                          : <span style={{ width: 18, height: 18, borderRadius: 4, background: "var(--surface-3)" }} />}
                        {sponsorLabel(a)}
                        {on && <Icon name="check" size={10} />}
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                {form.sponsor_assets.map((s, i) => (
                  <div key={s.asset_id} title={s.name || sponsorLabel(s)} className="img-ph" style={{
                    height: 44, width: 100, fontSize: 9, letterSpacing: "0.16em",
                    backgroundImage: s.signed_url ? `url(${s.signed_url})` : "none",
                    backgroundSize: "contain", backgroundRepeat: "no-repeat", backgroundPosition: "center",
                    position: "relative",
                  }}>
                    <span onClick={() => set({ sponsor_assets: form.sponsor_assets.filter((_, j) => j !== i) })}
                          style={{
                            position: "absolute", top: -6, right: -6,
                            width: 16, height: 16, borderRadius: "50%",
                            background: "rgba(0,0,0,0.7)", color: "white",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: 10, lineHeight: 1, cursor: "pointer",
                          }}>×</span>
                  </div>
                ))}
              </div>

              {/* Add a new sponsor — a unique name plus its logo file. */}
              <div className="row" style={{ gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
                <input
                  className="input"
                  placeholder="Sponsor name (e.g. Red Bull)"
                  value={newSponsorName}
                  onChange={(e) => setNewSponsorName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); tryPickSponsorLogo(); } }}
                  style={{ maxWidth: 220 }}
                />
                <button className="btn btn-ghost" onClick={tryPickSponsorLogo}>
                  <Icon name="upload" size={13} /> Add logo
                </button>
                <input ref={sponsorInputRef} type="file" accept="image/png,image/jpeg,image/webp" style={{ display: "none" }}
                       onChange={(e) => { addSponsor(e.target.files && e.target.files[0], newSponsorName); e.target.value = ""; }} />
              </div>
            </>
          )}
        />}
      </div>
    </>
  );
}

function BackgroundSourceCard({ form, set }) {
  // The fine-tuned background model is trained on League of Legends key art only,
  // so AI-generated backgrounds are LoL-only for now; Valorant keeps the SOON tag.
  const aiAvailable = form.game === "league_of_legends";
  // "System pool" was removed as a choice — coerce any stale draft to a valid one.
  React.useEffect(() => {
    if (form.background_source === "system_pool") set({ background_source: "custom" });
  }, [form.background_source]);
  const sources = [
    { id: "custom",      title: "Upload your own", desc: "Provide the base canvas yourself.", icon: "upload" },
    { id: "generated",   title: "AI-generated",
      desc: aiAvailable
        ? "Custom per poster · fine-tuned model."
        : "League of Legends only for now.",
      icon: "sparkles", soon: !aiAvailable },
  ];
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
        <div style={{ fontWeight: 600 }}>Background source</div>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", letterSpacing: "0.06em" }}>BASE CANVAS</span>
      </div>
      <div className="hint" style={{ marginBottom: 12 }}>The image the model uses as the starting canvas.</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
        {sources.map((s) => {
          const on = form.background_source === s.id;
          const disabled = !!s.soon;
          return (
            <button key={s.id}
              onClick={() => { if (!disabled) set({ background_source: s.id }); }}
              disabled={disabled}
              className="card"
              style={{
                padding: 14, cursor: disabled ? "not-allowed" : "pointer", background: "transparent",
                borderColor: on ? "var(--crim)" : "var(--line)",
                outline: on ? "3px solid var(--crim-soft)" : "none", outlineOffset: -1,
                textAlign: "left", opacity: disabled ? 0.55 : 1,
                position: "relative",
              }}>
              <div className="row" style={{ gap: 8, marginBottom: 6 }}>
                <Icon name={s.icon} size={14} />
                <span style={{ fontFamily: "var(--f-display)", fontSize: 13.5 }}>{s.title}</span>
                {s.soon && (
                  <span className="mono" style={{
                    marginLeft: "auto", fontSize: 9, padding: "2px 6px",
                    color: "var(--cy)", border: "1px solid var(--cy-line)", borderRadius: 999, letterSpacing: "0.08em",
                  }}>SOON</span>
                )}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--fg-3)" }}>{s.desc}</div>
            </button>
          );
        })}
      </div>

      {form.background_source === "custom" && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px dashed var(--line)" }}>
          <AssetUpload assetType="backgrounds" orgId={form.org_id}
                       asset={form.custom_background_asset}
                       onChange={(a) => set({ custom_background_asset: a })}
                       label="Pick or upload background" wide />
        </div>
      )}

      {form.background_source === "generated" && aiAvailable && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px dashed var(--line)", color: "var(--fg-3)", fontSize: 12 }}>
          A unique background is generated for this poster with our fine-tuned League of Legends
          key-art model, guided by your chosen vibe and energy. Most posters are served instantly;
          the occasional first-of-its-kind combo may take a moment to create.
        </div>
      )}
    </div>
  );
}

function ToggleCard({ title, desc, on, onChange, expand }) {
  return (
    <div className="card" style={{ padding: 18, borderColor: on ? "var(--crim-line)" : "var(--line)" }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600 }}>{title}</div>
          <div className="hint" style={{ marginTop: 2 }}>{desc}</div>
        </div>
        <SwitchToggle on={on} onChange={onChange} />
      </div>
      {expand && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px dashed var(--line)" }}>
          {expand}
        </div>
      )}
    </div>
  );
}

/* ───── Step 5: Review ───── */
function Step5({ form, jump, onGenerate, generating, error }) {
  const fmt = FORMATS.find((f) => f.id === form.format_id);
  const ptype = POSTER_TYPES.find((p) => p.id === form.poster_type);
  const cost = estimateCost(form);
  const costTokens = coinTotalFor(form, cost.total);
  // Coins per USD, so every itemised line below adds up to `costTokens`.
  const costScale = cost.total > 0 ? costTokens / cost.total : null;

  // Red Coins balance, so we can price in tokens and block if short.
  const [balance, setBalance] = React.useState(null);
  React.useEffect(() => {
    let cancelled = false;
    window.api.getCoins({ orgId: form.org_id })
      .then((c) => { if (!cancelled) setBalance(c && typeof c.balance === "number" ? c.balance : null); })
      .catch(() => { /* non-fatal — backend still enforces the gate */ });
    return () => { cancelled = true; };
  }, [form.org_id]);
  const insufficient = balance != null && balance < costTokens;

  const groups = [
    { step: 1, title: "Game & type", fields: [
      ["Game", GAMES.find((g) => g.id === form.game)?.name],
      ["Poster type", ptype?.title],
    ]},
    { step: 2, title: "Poster data", fields:
      form.poster_type === "roster_reveal" ? [
        ["Team", form.roster_team.name || "—"],
        ["Season", form.roster_season || "—"],
        ["Head coach", form.roster_coach || "—"],
        ["Players", form.roster_players.filter((p) => p.ign).length + " filled"],
      ] : form.poster_type === "tournament_announcement" || form.poster_type === "tournament_banner" ? [
        ["Tournament", form.tournament_name || "—"],
        ["Location", form.ann_location || "—"],
        ["Prize pool", form.ann_prize_pool || "—"],
        ["Tagline", form.ann_tagline || "—"],
      ] : [
        ["Tournament", form.tournament_name || "—"],
        ["Phase", form.tournament_phase || "—"],
        ["Matchup", `${form.team_a.name || "Team A"}  vs  ${form.team_b.name || "Team B"}`],
        ["Format", form.match_format],
        form.poster_type === "game_results"
          ? ["Score", `${form.score_a} — ${form.score_b}`]
          : ["Time", `${form.match_date || "—"} · ${form.match_time || "—"} ${form.timezone}`],
        form.poster_type === "gameday"
          ? ["Stream", `${form.stream_platform} · ${form.stream_url || "—"}`]
          : ["MVP", form.mvp_on ? form.mvp_ign : "Off"],
      ]
    },
    { step: 3, title: "Visual style", fields: form.style_mode === "fresh" ? [
      ["Mode", "Fresh look"],
      ["Vibe", VIBES.find((v) => v.id === form.vibe)?.label],
      ["Color", form.color_mode === "auto" ? "Match background (AI-picked)" : `Dominant · ${form.color}`],
      ["Energy", ENERGY.find((e) => e.id === form.energy)?.label],
    ] : [
      ["Mode", "Match previous posters"],
      ["Source DNA", form.style_dna ? `${form.style_dna.tournament_id} · ${form.style_dna.status}` : "None — will fall back to fresh"],
    ]},
    { step: 4, title: "Format & extras", fields: [
      ["Output", fmt ? `${fmt.name} · ${fmt.dims}` : "—"],
      ["Quality", (() => { const q = form.quality || "medium"; const m = QUALITY_MULT[q] != null ? QUALITY_MULT[q] : 1.0; return `${q.charAt(0).toUpperCase() + q.slice(1)} · ×${m}`; })()],
      ["Featured player", form.featured_player ? (form.featured_player_asset ? "On · 1 image" : "On · no image") : "Off"],
      ["Sponsor bar", form.sponsor_bar ? `On · ${form.sponsor_assets.length} sponsors` : "Off"],
      ["Background",
        form.background_source === "custom"
          ? (form.custom_background_asset ? "Custom · 1 image" : "Custom · no image yet")
          : form.background_source === "generated"
            ? (form.game === "league_of_legends" ? "AI-generated · fine-tuned model" : "AI-generated — coming soon")
            : "Upload your own"],
    ]},
  ];

  return (
    <>
      <div className="col" style={{ gap: 12, marginBottom: 28 }}>
        {groups.map((g) => (
          <div key={g.step} className="card" style={{ padding: 20 }}>
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
              <div className="row" style={{ gap: 12 }}>
                <span className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", color: "var(--crim)" }}>0{g.step}</span>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>{g.title}</span>
              </div>
              <button className="btn btn-ghost" style={{ height: 30, fontSize: 12 }} onClick={() => jump(g.step)}>
                <Icon name="edit" size={12} /> Edit
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "14px 28px" }}>
              {g.fields.map(([k, v], i) => (
                <div key={i}>
                  <div className="label" style={{ marginBottom: 4 }}>{k}</div>
                  <div style={{ fontSize: 13.5, fontWeight: 500 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Itemized cost estimate */}
      <div className="card" style={{ padding: 20, marginBottom: 12 }}>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <div className="row" style={{ gap: 12, alignItems: "center" }}>
            <span style={{ width: 18, height: 18, borderRadius: "50%", background: "var(--crim)", display: "inline-block", flexShrink: 0 }} title="Red Coins" />
            <span style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>Estimated cost</span>
          </div>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 18, color: "var(--fg)" }}>{rc(cost.total, costScale)}</span>
        </div>
        <div className="col" style={{ gap: 6 }}>
          {cost.items.map((it, i) => (
            <div key={i} className="row" style={{ justifyContent: "space-between", fontSize: 12.5 }}>
              <span style={{ color: "var(--fg-3)" }}>{it.label}</span>
              <span className="mono" style={{
                color: it.amount < 0 ? "var(--ok)" : it.amount === 0 ? "var(--fg-4)" : "var(--fg-2)",
              }}>
                {rcDelta(it.amount, costScale)}
              </span>
            </div>
          ))}
          <div style={{ height: 1, background: "var(--line)", margin: "6px 0" }} />
          <div className="row" style={{ justifyContent: "space-between", fontSize: 13, fontWeight: 600 }}>
            <span>Total{cost.floored ? " (minimum)" : ""}</span>
            <span className="mono">{rc(cost.total, costScale)}</span>
          </div>
        </div>
        <div className="hint" style={{ marginTop: 10 }}>
          Estimate only — actual cost depends on model tokens and any regeneration. Sponsor logos are
          composited locally and don't add model cost.
        </div>
      </div>

      {error && (
        <div className="card" style={{ padding: 16, marginBottom: 16, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Couldn't submit</div>
          <div className="mono" style={{ fontSize: 11.5, color: "var(--fg-2)", whiteSpace: "pre-wrap" }}>{error}</div>
        </div>
      )}

      <div className="card" style={{
        padding: 24,
        background: "linear-gradient(120deg, oklch(15% 0.04 8), oklch(13% 0.012 350), oklch(15% 0.04 195))",
        borderColor: "oklch(28% 0.04 8)",
        position: "relative", overflow: "hidden",
      }}>
        <div className="ai-grid" style={{ position: "absolute", inset: 0, opacity: 0.3, pointerEvents: "none" }} />
        {(() => {
          const rosterBad = !rosterPhotoValid(form);
          const mapsBad = !valorantMapsValid(form);
          // A draft restored from an earlier session can carry a score that the
          // current format no longer allows, so re-check it here rather than
          // trusting that step 2 already gated it.
          const seriesBad = !seriesScoreValid(form);
          const requiredBad = !requiredFieldsValid(form);
          const c = rosterPhotoCount(form);
          const note = requiredBad
            ? requiredFieldIssues(form)[0]
            : rosterBad && form.poster_type === "roster_reveal"
              ? `Invalid roster — pick 0, 1, or all 5 player photos (currently ${c}).`
              : seriesBad
                ? seriesScoreIssues(form)[0]
                : mapsBad
                  ? valorantMapIssues(form)[0]
                  : null;
          const blocked = requiredBad || rosterBad || seriesBad || mapsBad || insufficient;
          const headline = requiredBad
            ? "Fill in the required fields to continue."
            : rosterBad
              ? "Fix the roster photos to continue."
              : seriesBad
                ? "Fix the series score to continue."
                : mapsBad
                  ? "Fix the Valorant map results to continue."
                  : insufficient
                    ? "Not enough Red Coins for this poster."
                    : "All looks good. Let's make this poster.";
          return (
            <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24 }}>
              <div>
                <div className="badge ai" style={{ marginBottom: 12 }}><Icon name="sparkles" size={12} /> {blocked ? "Almost ready" : "Ready to generate"}</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 24, letterSpacing: "-0.01em", marginBottom: 6 }}>
                  {headline}
                </div>
                {note && (
                  <div className="mono" style={{ fontSize: 12, color: "var(--crim)", marginBottom: 8 }}>{note}</div>
                )}
                {insufficient && !rosterBad && (
                  <div className="mono" style={{ fontSize: 12, color: "var(--crim)", marginBottom: 8 }}>
                    Need {fmtCoins(costTokens)} {coinSym()} · you have {fmtCoins(balance)} {coinSym()}. Top up to continue.
                  </div>
                )}
                <div className="row" style={{ gap: 18, color: "var(--fg-3)", fontSize: 12.5 }}>
                  <span><span className="muted">Est. time</span> <span style={{ color: "var(--fg)", fontFamily: "var(--f-mono)" }}>20–60s</span></span>
                  <span style={{ width: 1, height: 14, background: "var(--line)" }} />
                  <span><span className="muted">Est. cost</span> <span style={{ color: "var(--fg)", fontFamily: "var(--f-mono)" }}>{rc(cost.total, costScale)}</span></span>
                  {balance != null && (
                    <>
                      <span style={{ width: 1, height: 14, background: "var(--line)" }} />
                      <span><span className="muted">Balance</span> <span style={{ color: insufficient ? "var(--crim)" : "var(--fg)", fontFamily: "var(--f-mono)" }}>{fmtCoins(balance)} {coinSym()}</span></span>
                    </>
                  )}
                </div>
              </div>
              <button className="btn btn-ai btn-lg" style={{ height: 54, padding: "0 32px", fontSize: 15, opacity: blocked ? 0.5 : 1, cursor: blocked ? "not-allowed" : "pointer" }}
                      onClick={onGenerate} disabled={generating || blocked}>
                <Icon name="sparkles" size={16} /> {generating ? "Submitting…" : "Generate poster"}
                <Icon name="arrow_right" size={14} />
              </button>
            </div>
          );
        })()}
      </div>
    </>
  );
}

/* ───── Tiny helpers ───── */
function SectionLabel({ n, label, hint }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div className="row" style={{ gap: 12, alignItems: "baseline" }}>
        <span className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", color: "var(--crim)" }}>{n}</span>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 18, letterSpacing: "-0.01em" }}>{label}</span>
      </div>
      {hint && <div className="hint" style={{ marginTop: 4, marginLeft: 32 }}>{hint}</div>}
    </div>
  );
}

function FormField({ label, req, children, inline, style }) {
  return (
    <div style={style}>
      {label && <label className="label">{label}{req && <span className="req">*</span>}</label>}
      {children}
    </div>
  );
}

function Segmented({ value, options, onChange }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${options.length}, 1fr)`, gap: 4, background: "var(--bg-elev)", padding: 4, borderRadius: 8, border: "1px solid var(--line)" }}>
      {options.map((o) => (
        <button key={o} onClick={() => onChange(o)}
          style={{
            padding: "8px 10px", border: 0, borderRadius: 5,
            background: value === o ? "var(--crim)" : "transparent",
            color: value === o ? "white" : "var(--fg-2)",
            fontFamily: "var(--f-mono)", fontSize: 12, letterSpacing: "0.06em", cursor: "pointer", fontWeight: 600,
          }}>
          {o}
        </button>
      ))}
    </div>
  );
}

function SwitchToggle({ on, onChange }) {
  return (
    <button onClick={() => onChange(!on)}
      style={{
        position: "relative",
        width: 44, height: 24, borderRadius: 999, border: 0,
        background: on ? "var(--crim)" : "var(--surface-3)",
        cursor: "pointer", transition: "background .15s", padding: 0, flexShrink: 0,
      }}>
      <div style={{
        position: "absolute", top: 3, left: on ? 23 : 3, width: 18, height: 18, borderRadius: "50%",
        background: "white", transition: "left .15s", boxShadow: "0 2px 6px rgba(0,0,0,.3)",
      }} />
    </button>
  );
}

/* ───── Container ───── */
function Wizard({ navigate }) {
  // Restore any saved draft so a refresh doesn't lose the user's inputs.
  const _draft = loadWizardDraft();
  const [step, setStep] = React.useState(() => (_draft && _draft.step) || 1);
  const [form, setForm] = React.useState(() => ({ ...defaultForm(), ...(_draft && _draft.form) }));
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState(null);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  // Persist the draft (form + current step) on every change.
  React.useEffect(() => { saveWizardDraft(form, step); }, [form, step]);

  // ---- Autofill from a host-platform tournament -----------------------------
  //
  // A "Generate poster" button on a tournament or match page deep links here as
  // `?tournamentId=…&matchId=…&type=…`. The host already knows who is playing,
  // when, and where to watch; asking the user to retype it is the whole problem
  // this integration exists to remove.
  //
  // Optional on both sides: `api.autofillFromTournament` is a host capability the
  // standalone build does not have, and without the query params this is inert.
  const [prefillNote, setPrefillNote] = React.useState(null);
  const autofilledRef = React.useRef(false);

  React.useEffect(() => {
    if (autofilledRef.current) return;
    if (typeof window.api.autofillFromTournament !== "function") return;

    const params = new URLSearchParams(
      (window.location.search || "") +
      // Hash-routed builds carry the query after the route.
      ((window.location.hash || "").split("?")[1] ? "&" + window.location.hash.split("?")[1] : "")
    );
    const tournamentId = params.get("tournamentId");
    if (!tournamentId) return;

    // Guard before the await: a slow response must not let a second run through.
    autofilledRef.current = true;
    let cancelled = false;

    (async () => {
      try {
        const res = await window.api.autofillFromTournament(tournamentId, {
          matchId: params.get("matchId") || undefined,
          type: params.get("type") || undefined,
        });
        if (cancelled || !res || !res.prefill) return;

        // Merge, never replace: `defaultForm()` fields the host cannot know
        // (vibe, energy, quality, output format) must survive untouched.
        set(res.prefill);

        const missing = res.missing || [];
        setPrefillNote(
          missing.length
            ? `Filled in from your tournament. Still needed: ${missing.join(", ")}.`
            : "Filled in from your tournament — check it over and pick a style."
        );
      } catch (e) {
        // Never block manual creation because the prefill failed.
        if (!cancelled) setPrefillNote(`Couldn't autofill from the tournament: ${e.message}`);
      }
    })();

    return () => { cancelled = true; };
  }, []);

  // Load the org's previously-uploaded team logos so quick-pick can reuse them.
  React.useEffect(() => {
    let cancelled = false;
    window.api.listAssets({ orgId: form.org_id, assetType: "team-logos", limit: 200 })
      .then((res) => {
        if (cancelled) return;
        set({ team_logo_library: buildTeamLogoLibrary(res.assets || []) });
      })
      .catch(() => { /* non-fatal — quick-pick just falls back to static presets */ });

    // Sponsor logos already in the brand library, deduped to one chip per sponsor.
    window.api.listAssets({ orgId: form.org_id, assetType: "sponsor-logos", limit: 200 })
      .then((res) => {
        if (cancelled) return;
        set({ sponsor_library: buildSponsorLibrary(res.assets || []) });
      })
      .catch(() => { /* non-fatal — quick-pick just stays empty */ });

    // Player images already in the brand library, deduped to one chip per player.
    window.api.listAssets({ orgId: form.org_id, assetType: "player-images", limit: 200 })
      .then((res) => {
        if (cancelled) return;
        set({ player_image_library: buildPlayerImageLibrary(res.assets || []) });
      })
      .catch(() => { /* non-fatal — quick-pick just stays empty */ });

    // Suggestions for the tournament-name field, from two sources:
    //
    //   1. the org's real tournaments, when the host platform can list them
    //      (`api.listTournaments`) — so the user picks an event they already
    //      created instead of retyping its name and risking a typo, which would
    //      silently start a separate tournament for Style DNA and history;
    //   2. names used on this org's previous posters, as a fallback.
    //
    // The field stays free text either way: the list is a convenience, never a
    // constraint, so a one-off event that lives nowhere else still works.
    const collectSuggestions = async () => {
      const names = [];
      const push = (raw) => {
        const n = (raw || "").trim();
        if (n && n !== "_standalone" && !names.includes(n)) names.push(n);
      };

      // Optional capability: the standalone build has no tournaments to list.
      if (typeof window.api.listTournaments === "function") {
        try {
          const res = await window.api.listTournaments();
          for (const t of (res.list || res.tournaments || [])) push(t.name);
        } catch (_) { /* non-fatal — fall through to past posters */ }
      }

      try {
        const res = await window.api.listPosters({ orgId: form.org_id, limit: 100 });
        for (const p of (res.posters || res.jobs || [])) {
          push(p.input_data?.tournament?.name || p.tournament_id);
        }
      } catch (_) { /* non-fatal — the name field just has fewer suggestions */ }

      if (!cancelled) set({ tournament_name_suggestions: names.slice(0, 30) });
    };
    collectSuggestions();
    return () => { cancelled = true; };
  }, [form.org_id]);

  const next = () => setStep((s) => Math.min(5, s + 1));
  const back = () => setStep((s) => Math.max(1, s - 1));

  const generate = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const tournamentId = form.tournament_id || slugify(form.tournament_name || form.roster_team.name);
      const input = buildInputJSON(form);
      const job = await window.api.createPoster({
        orgId: form.org_id,
        tournamentId,
        input,
      });
      // Keep the draft until the job actually SUCCEEDS (cleared on the progress
      // page when status === completed). That way a failed generation — e.g. a
      // rejected background — can be retried without re-filling the whole form.
      navigate(`#/job/${job.job_id}`);
    } catch (e) {
      // Friendly message for insufficient Red Coins (402).
      if (e.status === 402 && e.body && e.body.detail) {
        const d = e.body.detail;
        setSubmitError(
          `Not enough Red Coins — this poster needs ${fmtCoins(d.needed)} RC and you have ${fmtCoins(d.balance)} RC. Top up to continue.`
        );
      // Friendly message for rate-limit (429): show which window was hit
      // and when one slot frees up.
      } else if (e.status === 429 && e.body && e.body.detail) {
        const d = e.body.detail;
        const w = (d.windows || []).find((x) => x.remaining <= 0) || (d.windows || [])[0];
        const reset = w && w.reset_at ? new Date(w.reset_at).toLocaleString() : "later";
        setSubmitError(
          `Rate limit reached — ${w ? `${w.used}/${w.limit} posters in the last ${w.window}` : d.message}. ` +
          `One slot frees up at ${reset}.`
        );
      } else {
        setSubmitError(e.message || "Submission failed");
      }
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>NEW POSTER · DRAFT</div>
          <h1>Create poster</h1>
          <p>Five quick steps. The AI handles the rest.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost" style={{ fontSize: 12.5 }} onClick={() => { clearWizardDraft(); setForm(defaultForm()); setStep(1); navigate("#/"); }}><Icon name="cross" size={12}/> Discard</button>
        </div>
      </div>

      <ProgressRail current={step} onJump={(n) => n <= step && setStep(n)} />

      <div style={{ minHeight: 480 }}>
        {step === 1 && <Step1 form={form} set={set} />}
        {step === 2 && <Step2 form={form} set={set} />}
        {step === 3 && <Step3 form={form} set={set} />}
        {step === 4 && <Step4 form={form} set={set} />}
        {step === 5 && <Step5 form={form} jump={(n) => setStep(n)} onGenerate={generate} generating={submitting} error={submitError} />}
      </div>

      {prefillNote && (
        <div className="card" style={{
          padding: "11px 14px", marginBottom: 18,
          borderColor: "var(--cy-line)", background: "var(--cy-soft, var(--surface-2))",
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <Icon name="sparkles" size={14} />
          <div style={{ flex: 1, fontSize: 12.5, lineHeight: 1.5 }}>{prefillNote}</div>
          <button className="btn btn-ghost" style={{ padding: "2px 6px" }}
                  onClick={() => setPrefillNote(null)} aria-label="Dismiss">
            <Icon name="cross" size={12} />
          </button>
        </div>
      )}

      {step < 5 && (() => {
        // Missing fields first — a blank form shouldn't lead with a complaint
        // about map scores the user hasn't reached yet.
        const requiredBlocking = step === 2 && !requiredFieldsValid(form);
        const rosterBlocking = step === 2 && !rosterPhotoValid(form);
        // Checked before the map list: if the series score itself is wrong, the
        // "map wins don't match the score" complaint is just noise on top of it.
        const seriesBlocking = step === 2 && !seriesScoreValid(form);
        const mapsBlocking = step === 2 && !valorantMapsValid(form);
        const blocking = requiredBlocking || rosterBlocking || seriesBlocking || mapsBlocking;
        const blockingHint = requiredBlocking
          ? requiredFieldIssues(form)[0]
          : rosterBlocking
            ? `Roster reveal needs 0 (text-only), 1 (hero), or all 5 player photos — not ${rosterPhotoCount(form)}.`
            : seriesBlocking
              ? seriesScoreIssues(form)[0]
              : mapsBlocking
                ? valorantMapIssues(form)[0]
                : null;
        return (
          <div className="row" style={{
            marginTop: 36, paddingTop: 24, borderTop: "1px solid var(--line)",
            justifyContent: "space-between",
          }}>
            <button className="btn btn-ghost" onClick={back} disabled={step === 1} style={{ opacity: step === 1 ? 0.4 : 1 }}>
              <Icon name="arrow_left" size={14} /> Back
            </button>
            <div className="mono" style={{ fontSize: 11, color: blockingHint ? "var(--crim)" : "var(--fg-3)", letterSpacing: "0.06em", textAlign: "center" }}>
              {blockingHint || <>STEP {String(step).padStart(2, "0")} <span style={{ color: "var(--fg-4)" }}>/ 05</span></>}
            </div>
            <button className="btn btn-primary" onClick={next} disabled={blocking}
                    style={blocking ? { opacity: 0.45, cursor: "not-allowed" } : undefined}>
              Continue <Icon name="arrow_right" size={14} />
            </button>
          </div>
        );
      })()}
    </div>
  );
}

Object.assign(window, { Wizard, clearWizardDraft, setWizardDraftStep, WIZARD_BACKGROUND_STEP });
