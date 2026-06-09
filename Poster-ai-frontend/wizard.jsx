// wizard.jsx — 5-step Create Poster wizard (wired to FastAPI backend)

const STEPS = [
  { n: 1, code: "01", title: "Game & type",   sub: "Pick the canvas" },
  { n: 2, code: "02", title: "Poster data",   sub: "Fill in the match" },
  { n: 3, code: "03", title: "Visual style",  sub: "Set the vibe" },
  { n: 4, code: "04", title: "Format & extras", sub: "Size & assets" },
  { n: 5, code: "05", title: "Review",        sub: "Confirm & generate" },
];

const GAMES = [
  { id: "league_of_legends", name: "League of Legends", short: "LoL", accent: "oklch(60% 0.18 220)" },
  { id: "valorant",          name: "Valorant",          short: "VAL", accent: "oklch(60% 0.22 15)" },
];

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

const COLOR_PRESETS = ["#E83A57", "#3AC0E8", "#FFD24B", "#7B5CFF", "#22C58A", "#FF6A1F"];

const PRESET_TEAMS = [
  { name: "FNATIC", short: "FNC" },
  { name: "T1",     short: "T1"  },
  { name: "G2 ESPORTS", short: "G2" },
  { name: "KOI",    short: "KOI" },
];

const VALORANT_MAPS = ["Haven","Ascent","Bind","Split","Lotus","Pearl","Sunset","Icebox","Breeze","Fracture"];
const LOL_ROLES = ["Top","Jungle","Mid","Bot","Support"];

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
  floor: 0.030,            // a run never costs less than this
};

function estimateCost(form) {
  const items = [];
  const add = (label, amount) => items.push({ label, amount });
  const pt = form.poster_type;

  add("Prompt analysis (GPT-4o)", COST.promptBase);
  add("Poster generation (gpt-image-2)", COST.imageBase);

  if (form.format_id !== "square_1080x1080") {
    const fmt = FORMATS.find((f) => f.id === form.format_id);
    add(`Large canvas (${fmt ? fmt.dims : form.format_id})`, COST.formatLarge);
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

// Derive a clean team token from an asset's name/filename:
// "GNG_LOGO.png" -> "GNG", "JSK LOGO" -> "JSK", "Team Vitality.png" -> "VITALITY"
const _LOGO_NOISE = /^(logo|logos|team|esports|official|png|jpg|jpeg|webp)$/i;
function teamKeyFromAsset(a) {
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
    valorant_maps: [
      { map_name: "Haven", rounds_team1: 0, rounds_team2: 0 },
    ],
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
    energy: "intense",
    style_dna: null,
    style_dna_status: null, // "approved" | "draft" | null
    style_dna_loading: false,

    // format + extras
    format_id: "portrait_1080x1920",
    featured_player: false,
    featured_player_asset: null,
    sponsor_bar: false,
    sponsor_assets: [],
    // Background canvas source: "system_pool" (current default) | "custom"
    // (user upload) | "generated" (Runpod fine-tuned SD — not yet wired).
    background_source: "system_pool",
    custom_background_asset: null,

    // brand library — team logos already uploaded for this org (quick-pick)
    team_logo_library: [],
  };
}

/* ============================================================
   Draft persistence — keep wizard inputs across page refreshes.
   Stored in localStorage; cleared on a successful generate or Discard.
   ============================================================ */
const WIZARD_DRAFT_KEY = "epai_wizard_draft_v1";

// Fetched/transient fields — not persisted (re-derived on load).
const _EPHEMERAL_FIELDS = ["style_dna", "style_dna_status", "style_dna_loading", "team_logo_library"];

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
    primary_color: form.color,
    energy: form.energy,
  };

  const sponsors = {
    enabled: !!form.sponsor_bar && form.sponsor_assets.length > 0,
    logos: form.sponsor_assets.map((a) => ({ path: a.storage_key })),
  };

  // Background source — the pipeline resolves it in stages/background.py.
  //   system_pool: omit the block; pipeline picks from the local pool.
  //   custom:      emit source + the uploaded image storage key.
  //   generated:   emit source only; pipeline will call Runpod (deferred).
  let background = null;
  if (form.background_source === "custom" && form.custom_background_asset) {
    background = { source: "custom", image_path: form.custom_background_asset.storage_key };
  } else if (form.background_source === "generated") {
    background = { source: "generated" };
  }

  const _meta = { game, poster_type, mode, output_format };

  const teamPayload = (t, withScore, score) => {
    const o = {
      name: t.name || "",
      short_name: t.short || "",
      logo_path: t.logo_asset ? t.logo_asset.storage_key : null,
    };
    if (withScore) o.score = Number.isFinite(+score) ? +score : null;
    return o;
  };

  if (poster_type === "gameday") {
    return {
      _meta,
      tournament: {
        name: form.tournament_name,
        logo_path: form.tournament_logo_asset?.storage_key || null,
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
        image_path: form.featured_player_asset?.storage_key || null,
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
        logo_path: form.tournament_logo_asset?.storage_key || null,
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
        image_path: form.featured_player_asset?.storage_key || null,
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
        logo_path: form.roster_team.logo_asset?.storage_key || "",
      },
      roster: {
        season: form.roster_season || null,
        head_coach: form.roster_coach || null,
        players: form.roster_players.map((p) => ({
          ign: p.ign || "",
          role: p.role,
          image_path: p.image_asset?.storage_key || null,
          nationality_flag_path: p.nationality_flag_asset?.storage_key || null,
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
        logo_path: form.tournament_logo_asset?.storage_key || null,
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
        logo_path: form.tournament_logo_asset?.storage_key || null,
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
          background: hasAsset ? "transparent" : "var(--bg-elev)",
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
              onClick={() => set({ game: g.id })}
              className="card"
              style={{
                padding: 24, cursor: "pointer", background: "transparent",
                borderColor: on ? "var(--crim)" : "var(--line)",
                outline: on ? "3px solid var(--crim-soft)" : "none",
                outlineOffset: -1,
                textAlign: "left",
                position: "relative",
                overflow: "hidden",
              }}>
              <div style={{ position: "absolute", right: -40, top: -40, width: 160, height: 160,
                    borderRadius: "50%", background: `radial-gradient(circle, ${g.accent}, transparent 60%)`,
                    opacity: 0.4, pointerEvents: "none" }} />
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ width: 56, height: 56, borderRadius: 12,
                      background: `linear-gradient(135deg, ${g.accent}, oklch(20% 0.05 350))`,
                      border: "1px solid var(--line-strong)",
                      fontFamily: "var(--f-display)", fontSize: 18, color: "white",
                      display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {g.short}
                </div>
                <div>
                  <div style={{ fontFamily: "var(--f-display)", fontSize: 20, letterSpacing: "-0.01em" }}>{g.name}</div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", letterSpacing: "0.08em", textTransform: "uppercase", marginTop: 4 }}>
                    {g.id === "valorant" ? "5v5 tactical · maps" : "5v5 moba · roles"}
                  </div>
                </div>
                {on && (
                  <div style={{ marginLeft: "auto", color: "var(--crim)" }}>
                    <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--crim)", color: "white", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Icon name="check" size={14}/>
                    </div>
                  </div>
                )}
              </div>
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

function MiniPosterPreview({ type, on }) {
  const accent = on ? "var(--crim)" : "var(--fg-3)";
  const bg = "linear-gradient(140deg, oklch(20% 0.04 350), oklch(12% 0.02 350))";
  return (
    <div style={{
      flex: 1, borderRadius: 6, background: bg,
      border: "1px solid var(--line)", padding: 10,
      position: "relative", overflow: "hidden", minHeight: 100,
    }}>
      <div style={{ position: "absolute", inset: 0, opacity: 0.5,
        backgroundImage: "repeating-linear-gradient(0deg, rgba(255,255,255,0.03) 0 1px, transparent 1px 4px)" }} />
      <div className="mono" style={{ fontSize: 7, letterSpacing: "0.18em", color: accent, textTransform: "uppercase" }}>
        {type.replace(/_/g, " ").toUpperCase()}
      </div>
    </div>
  );
}

/* ───── Step 2: Poster data ───── */
function Step2({ form, set }) {
  const ptype = form.poster_type;
  return (
    <>
      {ptype !== "roster_reveal" && (
        <>
          <SectionLabel n="02.A" label="Tournament" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 240px", gap: 14, marginBottom: 32 }}>
            <FormField label="Tournament name" req>
              <input className="input" value={form.tournament_name} onChange={(e) => set({ tournament_name: e.target.value })} placeholder="MENA Pro League" />
            </FormField>
            <FormField label="Tournament phase">
              <input className="input" value={form.tournament_phase} onChange={(e) => set({ tournament_phase: e.target.value })} placeholder="Playoffs · Quarterfinals" />
            </FormField>
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
                set({ match_format: v, score_a: a, score_b: b });
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

          {ptype === "game_results" && (
            <>
              <SectionLabel n="02.C" label="Score"
                hint={`${form.match_format} — first to ${seriesWinTarget(form.match_format)} wins; the two scores can total at most ${seriesMaxGames(form.match_format)}.`} />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 14, marginBottom: 24, alignItems: "end" }}>
                <FormField label="Team 1 score" req>
                  <input className="input" type="number" value={form.score_a}
                         onChange={(e) => set({ score_a: clampScore(e.target.value, form.score_b, form.match_format) })}
                         min="0" max={seriesWinTarget(form.match_format)} />
                </FormField>
                <FormField label="Team 2 score" req>
                  <input className="input" type="number" value={form.score_b}
                         onChange={(e) => set({ score_b: clampScore(e.target.value, form.score_a, form.match_format) })}
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

              {form.game === "valorant" && (
                <>
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
                    <span className="label" style={{ marginBottom: 0 }}>Map results</span>
                    <button className="btn btn-ghost" style={{ height: 30, fontSize: 12 }}
                            onClick={() => set({ valorant_maps: [...form.valorant_maps, { map_name: "Haven", rounds_team1: 0, rounds_team2: 0 }] })}>
                      <Icon name="plus" size={12}/> Add map
                    </button>
                  </div>
                  <div className="col" style={{ gap: 8, marginBottom: 24 }}>
                    {form.valorant_maps.map((m, i) => (
                      <div key={i} className="card" style={{ padding: "10px 14px", display: "grid", gridTemplateColumns: "1fr 80px 80px 24px", gap: 14, alignItems: "center" }}>
                        <select className="select" value={m.map_name}
                                onChange={(e) => {
                                  const next = [...form.valorant_maps]; next[i] = { ...next[i], map_name: e.target.value }; set({ valorant_maps: next });
                                }}>
                          {VALORANT_MAPS.map((x) => <option key={x}>{x}</option>)}
                        </select>
                        <input className="input" type="number" value={m.rounds_team1}
                               onChange={(e) => { const next = [...form.valorant_maps]; next[i] = { ...next[i], rounds_team1: e.target.value }; set({ valorant_maps: next }); }} />
                        <input className="input" type="number" value={m.rounds_team2}
                               onChange={(e) => { const next = [...form.valorant_maps]; next[i] = { ...next[i], rounds_team2: e.target.value }; set({ valorant_maps: next }); }} />
                        <button className="btn-icon" style={{ background: "transparent", border: 0, color: "var(--fg-3)", cursor: "pointer" }}
                                onClick={() => set({ valorant_maps: form.valorant_maps.filter((_, j) => j !== i) })}>
                          <Icon name="cross" size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}

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
          )}
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
      <div style={{ display: "grid", gridTemplateColumns: "1fr 240px", gap: 14, marginBottom: 24 }}>
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
          <div key={i} className="card" style={{ padding: 12, display: "grid", gridTemplateColumns: "60px 1fr 140px 130px", gap: 12, alignItems: "center" }}>
            <AssetUpload assetType="player-images" orgId={form.org_id}
                         asset={p.image_asset}
                         onChange={(a) => setPlayer(i, { image_asset: a })}
                         square />
            <input className="input" value={p.ign} placeholder="IGN" onChange={(e) => setPlayer(i, { ign: e.target.value })} />
            <select className="select" value={p.role} onChange={(e) => setPlayer(i, { role: e.target.value })}>
              {LOL_ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>
            <label style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 6, color: p.is_new_signing ? "var(--cy)" : "var(--fg-3)", cursor: "pointer" }}>
              <input type="checkbox" checked={p.is_new_signing} onChange={(e) => setPlayer(i, { is_new_signing: e.target.checked })}
                     style={{ accentColor: "var(--cy)" }} />
              New signing
            </label>
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
        <input className="input" value={form.ann_format} onChange={(e) => set({ ann_format: e.target.value })} placeholder="Double elim" />
      </FormField>
      <FormField label="">‎</FormField>
      <FormField label="Tagline" req>
        <input className="input" value={form.ann_tagline} onChange={(e) => set({ ann_tagline: e.target.value })} placeholder="The road to glory begins." />
      </FormField>
      <FormField label="Sub-tagline">
        <input className="input" value={form.ann_sub_tagline} onChange={(e) => set({ ann_sub_tagline: e.target.value })} placeholder="16 teams. One throne." />
      </FormField>
    </div>
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
        <input className="input" value={form.ann_tagline} onChange={(e) => set({ ann_tagline: e.target.value })} placeholder="The road to glory begins." />
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

  // In consistency mode, look up the Style DNA for the tournament the user
  // actually typed (matched by its slug). Only that tournament's style shows.
  React.useEffect(() => {
    if (form.style_mode !== "consistency") return;
    const tid = slugify(form.tournament_name);
    let cancelled = false;

    if (!tid || tid === "_standalone") {
      set({ style_dna: null, style_dna_status: null, style_dna_loading: false });
      return;
    }

    set({ style_dna_loading: true });
    window.api.getStyleDna({ orgId: form.org_id, tournamentId: tid })
      .then((dna) => {
        if (cancelled) return;
        set({
          style_dna: dna,
          style_dna_status: dna ? dna.status : null,
          tournament_id: dna ? tid : "",
          style_dna_loading: false,
        });
      })
      .catch(() => {
        if (cancelled) return;
        set({ style_dna: null, style_dna_status: null, style_dna_loading: false });
      });
    return () => { cancelled = true; };
  }, [form.style_mode, form.tournament_name, form.org_id]);

  return (
    <>
      <div style={{ display: "flex", gap: 0, marginBottom: 28, background: "var(--surface)", padding: 4, borderRadius: 10, border: "1px solid var(--line)" }}>
        {[
          { id: "fresh", label: "Fresh look", desc: "Define a new look for this poster" },
          { id: "consistency", label: "Match my previous posters", desc: "Use the tournament's approved Style DNA" },
        ].map((m) => {
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
                  <div style={{ height: 90, background: `linear-gradient(140deg, ${v.grad[0]}, ${v.grad[1]})`, position: "relative", overflow: "hidden" }}>
                    <div style={{ position: "absolute", inset: 0, backgroundImage: "repeating-linear-gradient(0deg, rgba(0,0,0,0.1) 0 1px, transparent 1px 3px)" }} />
                    {on && <div style={{ position: "absolute", top: 8, right: 8, width: 22, height: 22, borderRadius: "50%", background: "var(--crim)", color: "white", display: "flex", alignItems: "center", justifyContent: "center" }}>
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

          <SectionLabel n="03.B" label="Dominant color" />
          <div className="card" style={{ padding: 18, marginBottom: 32 }}>
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
        <ConsistencyPanel form={form} />
      )}
    </>
  );
}

function ConsistencyPanel({ form }) {
  const tid = slugify(form.tournament_name);

  // No tournament name typed yet — can't match a style.
  if (!tid || tid === "_standalone") {
    return (
      <div className="card" style={{ padding: 24, borderColor: "var(--line)" }}>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 16, marginBottom: 8 }}>Enter a tournament name first</div>
        <div className="hint">
          Go back to <b>Step 2</b> and type the tournament name. If a Style DNA was saved for that exact
          tournament, it appears here and is applied to this poster.
        </div>
      </div>
    );
  }

  if (form.style_dna_loading) {
    return (
      <div className="card" style={{ padding: 24, borderColor: "var(--cy-line)" }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--cy)", letterSpacing: "0.1em" }}>
          ● MATCHING STYLE FOR “{form.tournament_name}”…
        </div>
      </div>
    );
  }

  // Name typed, but no DNA stored for it.
  if (!form.style_dna) {
    return (
      <div className="card" style={{ padding: 24, borderColor: "var(--line)" }}>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 16, marginBottom: 8 }}>
          No saved style for “{form.tournament_name}”
        </div>
        <div className="hint">
          No Style DNA is stored for tournament <code>{tid}</code>. This poster will use fresh-mode styling.
          Generate it, then click <b>"Extract &amp; save as draft"</b> on the result to create one for this tournament.
        </div>
      </div>
    );
  }

  return <DnaCard form={form} />;
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
  const addSponsor = async (file) => {
    if (!file) return;
    try {
      const a = await window.api.uploadAsset({ orgId: form.org_id, assetType: "sponsor-logos", file, name: file.name });
      set({ sponsor_assets: [...form.sponsor_assets, a] });
      window.toast.success(`"${file.name}" added.`);
    } catch (e) {
      window.toast.error(`Sponsor upload failed: ${e.message}`);
    }
  };
  const sponsorInputRef = React.useRef(null);

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

      <SectionLabel n="04.B" label="Extras" />
      <div className="col" style={{ gap: 12 }}>
        {canFeaturePlayer && (
          <ToggleCard
            title="Featured player"
            desc="Drops a hero portrait into the composition. The AI scales & crops to fit the poster."
            on={form.featured_player}
            onChange={(v) => set({ featured_player: v })}
            expand={form.featured_player && (
              <div className="row" style={{ gap: 14 }}>
                <AssetUpload assetType="player-images" orgId={form.org_id}
                             asset={form.featured_player_asset}
                             onChange={(a) => set({ featured_player_asset: a })}
                             label="Pick or upload player photo" wide />
              </div>
            )}
          />
        )}
        <BackgroundSourceCard form={form} set={set} />
        <ToggleCard
          title="Sponsor bar"
          desc="A strip of sponsor logos along the bottom of the poster."
          on={form.sponsor_bar}
          onChange={(v) => set({ sponsor_bar: v })}
          expand={form.sponsor_bar && (
            <>
              <div className="hint" style={{ marginBottom: 10 }}>Upload sponsor logos. Recommended: 3–6.</div>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                {form.sponsor_assets.map((s, i) => (
                  <div key={s.asset_id} className="img-ph" style={{
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
                <button className="img-ph" style={{ height: 44, width: 60, fontSize: 9, background: "transparent", color: "var(--fg-3)", borderStyle: "dashed", cursor: "pointer" }}
                        onClick={() => sponsorInputRef.current && sponsorInputRef.current.click()}>
                  + ADD
                </button>
                <input ref={sponsorInputRef} type="file" accept="image/png,image/jpeg,image/webp" style={{ display: "none" }}
                       onChange={(e) => addSponsor(e.target.files && e.target.files[0])} />
              </div>
            </>
          )}
        />
      </div>
    </>
  );
}

function BackgroundSourceCard({ form, set }) {
  const sources = [
    { id: "system_pool", title: "System pool", desc: "Use one of the built-in backgrounds.", icon: "layers" },
    { id: "custom",      title: "Upload your own", desc: "Provide the base canvas yourself.", icon: "upload" },
    { id: "generated",   title: "AI-generated", desc: "Custom per poster · Runpod fine-tuned model.", icon: "sparkles", soon: true },
  ];
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
        <div style={{ fontWeight: 600 }}>Background source</div>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", letterSpacing: "0.06em" }}>BASE CANVAS</span>
      </div>
      <div className="hint" style={{ marginBottom: 12 }}>The image the model uses as the starting canvas.</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
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

      {form.background_source === "generated" && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px dashed var(--line)", color: "var(--fg-3)", fontSize: 12 }}>
          AI-generated backgrounds use a fine-tuned Stable Diffusion model on Runpod.
          The plumbing is ready in <code>stages/background.py</code>; the call itself will be wired once the Runpod endpoint is live.
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
      ["Dominant color", form.color],
      ["Energy", ENERGY.find((e) => e.id === form.energy)?.label],
    ] : [
      ["Mode", "Match previous posters"],
      ["Source DNA", form.style_dna ? `${form.style_dna.tournament_id} · ${form.style_dna.status}` : "None — will fall back to fresh"],
    ]},
    { step: 4, title: "Format & extras", fields: [
      ["Output", fmt ? `${fmt.name} · ${fmt.dims}` : "—"],
      ["Featured player", form.featured_player ? (form.featured_player_asset ? "On · 1 image" : "On · no image") : "Off"],
      ["Sponsor bar", form.sponsor_bar ? `On · ${form.sponsor_assets.length} sponsors` : "Off"],
      ["Background",
        form.background_source === "custom"
          ? (form.custom_background_asset ? "Custom · 1 image" : "Custom · no image yet")
          : form.background_source === "generated"
            ? "AI-generated (Runpod) — coming soon"
            : "System pool"],
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
          <div className="row" style={{ gap: 12 }}>
            <span className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", color: "var(--crim)" }}>€</span>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>Estimated cost</span>
          </div>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 18, color: "var(--fg)" }}>{eur(cost.total)}</span>
        </div>
        <div className="col" style={{ gap: 6 }}>
          {cost.items.map((it, i) => (
            <div key={i} className="row" style={{ justifyContent: "space-between", fontSize: 12.5 }}>
              <span style={{ color: "var(--fg-3)" }}>{it.label}</span>
              <span className="mono" style={{
                color: it.amount < 0 ? "var(--ok)" : it.amount === 0 ? "var(--fg-4)" : "var(--fg-2)",
              }}>
                {it.amount === 0 ? "free" : (it.amount < 0 ? "−" : "+") + "€" + Math.abs(it.amount).toFixed(3)}
              </span>
            </div>
          ))}
          <div style={{ height: 1, background: "var(--line)", margin: "6px 0" }} />
          <div className="row" style={{ justifyContent: "space-between", fontSize: 13, fontWeight: 600 }}>
            <span>Total{cost.floored ? " (minimum)" : ""}</span>
            <span className="mono">{eur(cost.total)}</span>
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
          const blocked = !rosterPhotoValid(form);
          const c = rosterPhotoCount(form);
          const note = blocked && form.poster_type === "roster_reveal"
            ? `Invalid roster — pick 0, 1, or all 5 player photos (currently ${c}).`
            : null;
          return (
            <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24 }}>
              <div>
                <div className="badge ai" style={{ marginBottom: 12 }}><Icon name="sparkles" size={12} /> {blocked ? "Almost ready" : "Ready to generate"}</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 24, letterSpacing: "-0.01em", marginBottom: 6 }}>
                  {blocked ? "Fix the roster photos to continue." : "All looks good. Let's make this poster."}
                </div>
                {blocked && note && (
                  <div className="mono" style={{ fontSize: 12, color: "var(--crim)", marginBottom: 8 }}>{note}</div>
                )}
                <div className="row" style={{ gap: 18, color: "var(--fg-3)", fontSize: 12.5 }}>
                  <span><span className="muted">Est. time</span> <span style={{ color: "var(--fg)", fontFamily: "var(--f-mono)" }}>20–60s</span></span>
                  <span style={{ width: 1, height: 14, background: "var(--line)" }} />
                  <span><span className="muted">Est. cost</span> <span style={{ color: "var(--fg)", fontFamily: "var(--f-mono)" }}>{eur(cost.total)}</span></span>
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

  // Load the org's previously-uploaded team logos so quick-pick can reuse them.
  React.useEffect(() => {
    let cancelled = false;
    window.api.listAssets({ orgId: form.org_id, assetType: "team-logos", limit: 200 })
      .then((res) => {
        if (cancelled) return;
        set({ team_logo_library: buildTeamLogoLibrary(res.assets || []) });
      })
      .catch(() => { /* non-fatal — quick-pick just falls back to static presets */ });
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
      clearWizardDraft();  // submitted — start fresh next time
      navigate(`#/job/${job.job_id}`);
    } catch (e) {
      // Friendly message for rate-limit (429): show which window was hit
      // and when one slot frees up.
      if (e.status === 429 && e.body && e.body.detail) {
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

      {step < 5 && (() => {
        const rosterBlocking = step === 2 && !rosterPhotoValid(form);
        const blockingHint = rosterBlocking
          ? `Roster reveal needs 0 (text-only), 1 (hero), or all 5 player photos — not ${rosterPhotoCount(form)}.`
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
            <button className="btn btn-primary" onClick={next} disabled={rosterBlocking}
                    style={rosterBlocking ? { opacity: 0.45, cursor: "not-allowed" } : undefined}>
              Continue <Icon name="arrow_right" size={14} />
            </button>
          </div>
        );
      })()}
    </div>
  );
}

Object.assign(window, { Wizard });
