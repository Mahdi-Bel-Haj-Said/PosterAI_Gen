# EsportsPostAI — UI Design Brief

> A functional brief for the web UI. The backend (FastAPI + MongoDB + Redis +
> Cloudflare R2) already exists and is documented in `README.md`. This brief
> defines **what the UI must do** — every screen, input, output, and behavior.
> Visual treatment (look, colors, typography, layout style, theme) is
> intentionally left to the designer.

---

## 1. What the product is

EsportsPostAI is a SaaS tool that lets esports tournament organizers generate
**publish-ready esports posters** (gameday matchups, match results, roster
reveals, tournament announcements / banners) in **20–60 seconds** from a
guided form. The user fills in match data, picks a visual style, and the AI
produces a poster they can post to socials.

The backend is built end-to-end. This brief is **for the web UI only**.

---

## 2. Who uses it

- **Primary user — tournament organizer / esports marketing person.** Creates
  posters for upcoming games, results, roster announcements. Comes from
  Defendr (the parent platform) or signs up directly. Cranks out multiple
  posters per week per tournament. Not technical.
- **Secondary user — admin.** Issues API keys, monitors usage. Different
  scope; lives under a separate section in the same UI.

---

## 3. Functional requirements

- **Responsive** — works on laptops (primary) and on mobile (event-day quick
  posts).
- **Accessible** — full keyboard navigation, visible focus states, descriptive
  labels on every form field, screen-reader-friendly status announcements.
- **Async-friendly** — long-running operations (poster generation: 20–60 s)
  must give continuous feedback and never block the rest of the app.

---

## 4. Information architecture

The app has the following sections (the navigation pattern is up to the
designer):

1. **Dashboard** — landing after login.
2. **Create poster** — the primary action, a 5-step wizard.
3. **Poster history** — every poster the org has made.
4. **Brand library** — uploaded logos and player photos, organized by type.
5. **Tournaments & Style DNA** — manage the per-tournament visual style.
6. **Admin** (separate area, role-gated):
   - API keys
   - Usage & billing

There is also an **organization context** (which org the user is acting on
behalf of) — surface a way to see/switch it.

---

## 5. Screens — full spec

### 5.1 Dashboard

**Purpose:** landing screen; at-a-glance status + the primary call to action.

**Shows:**
- Primary call to action: **"Create new poster"** → opens the wizard at Step 1.
- This-month stats: posters created, estimated cost, success rate.
- Recent posters (latest few) — clicking one opens the poster detail.
- "In progress" — any jobs currently being generated.

### 5.2 Create poster — 5-step wizard (the centerpiece)

A persistent progress indicator shows the current step (1 → 2 → 3 → 4 → 5).
**Back** and **Next** controls; **Back never destroys data**; **Next is
disabled** until the step's required fields are valid.

#### Step 1 — Game + poster type

**Inputs:**
- **Game** (single-select): *League of Legends*, *Valorant*.
- **Poster type** (single-select): *Gameday*, *Game Results*, *Roster Reveal*,
  *Tournament Announcement*, *Tournament Banner*. Each option should be
  recognizable with a small label or preview.

**Validation:** both must be selected to continue.

#### Step 2 — Poster data

The form is **dynamic per poster type**.

**Always shown:**
- Tournament name (text, required)
- Tournament phase (text, optional — e.g. "Playoffs")
- Tournament logo (asset picker that opens the brand library OR upload new;
  optional)

**For `gameday` and `game_results`:**
- **Team 1:** name (required), short name (optional), logo (asset picker /
  upload, optional).
- **Team 2:** same.
- **Format** (select): *Bo1 / Bo3 / Bo5*.
- **Date** (date picker, optional).

**Gameday only:**
- Match time (time picker).
- Timezone (select — CET, EST, PST, UTC, KST, …).
- Stream platform (select — Twitch, YouTube, …).
- Stream URL (text, optional).

**Game results only:**
- Team 1 score (number 0–9).
- Team 2 score (number 0–9). Show a live "Winner: TEAM X" derived from the
  scores.
- **Valorant only:** dynamic list of map rows — map name (select: Haven,
  Ascent, Bind, Split, …) + rounds team 1 (number) + rounds team 2 (number).
  "+ Add map" control.
- **MVP** (collapsible / optional): toggle on → player name + stat label +
  stat value (e.g. "KDA: 8.5").

**Roster reveal:**
- Team — name + logo (asset picker / upload).
- Season (text, e.g. "2025 Summer").
- Head coach (text, optional).
- **Players (1–5 entries):** dynamic list. Each row: IGN + role (select; LoL:
  Top/Jungle/Mid/Bot/Support; Valorant:
  Duelist/Initiator/Controller/Sentinel/Flex) + optional photo upload +
  "New signing" checkbox.

**Tournament announcement:**
- Start date, location, prize pool, teams count, format, tagline, sub-tagline.

**Tournament banner:**
- Date range, location, prize pool, tagline.

**Validation:** required fields marked; inline errors below each field.

#### Step 3 — Visual style

Two paths via a toggle at the top of the step:

**Path A — "Fresh look" (default):**
- **Vibe** (single-select): *Cyberpunk*, *Cinematic*, *Dark Fantasy*,
  *Cosmic*, *Minimal*, *Fire & Energy*.
- **Dominant color** — color picker (hex input + visual picker), with sensible
  preset shortcuts.
- **Energy** (single-select): *Chill / Balanced / Intense / Explosive*. Show
  a one-line description of the current choice.

**Path B — "Match my previous posters" (consistency mode):**
- Available **only if the selected tournament already has an approved Style
  DNA**. When chosen, Path A is locked / hidden and a read-only summary
  shows the existing palette + "Using approved style for {tournament}".

#### Step 4 — Format + extras

- **Output format** (single-select, showing the aspect ratio):
  - *Portrait* 1080×1920 (story / reels)
  - *Square* 1080×1080 (feed)
  - *Landscape* 1920×1080 (banner / Twitter header)
- **Toggles** — each toggle, when ON, reveals its asset slot:
  - **Featured player** (gameday, game results, roster reveal only) — toggle
    + image upload / picker. Show a note: "Optional — the AI will scale &
    crop it to fit."
  - **Sponsor bar** — toggle + multiple sponsor logo upload / picker
    (drag-to-reorder). Note: "Sponsors appear as a strip at the bottom of
    the poster."

**No toggles for text fields** (match time, stream, etc.) — those follow the
rule "filled in Step 2 = shown on the poster; blank = hidden."

#### Step 5 — Review + Generate

- **Summary** — read-only mirror of all the inputs from Steps 1–4, grouped by
  step. Each group has an **Edit** link that jumps back to that step
  (preserving the data).
- **Estimated cost** indicator — `~$0.05`.
- **Generate** — primary action. Disabled while submitting.

On click → POST to backend → transition to the **Job progress** screen.

### 5.3 Job progress (post-Generate)

A focused screen showing:
- The pipeline status as a sequence of states lighting up in order:
  `Queued → Generating prompt → Generating poster → Applying sponsor bar →
  Done`.
- An honest timing hint: "Usually 20–60 seconds…".
- The data summary on the side (so the user remembers what they made).
- On `completed` → auto-redirect to **Poster result**.
- On `failed` → show the backend error message + "Try again" (jumps back to
  Step 5 with all inputs preserved).
- **No cancel** in v1 (jobs are short).

Implementation note: poll `GET /v1/posters/{job_id}` every 2 seconds.

### 5.4 Poster result

- The generated poster as the focal element of the screen.
- Actions: **Download**, **Copy share link** (the signed R2 URL), **Generate
  another like this** (pre-fills Step 5), **Back to history**.
- Metadata sidebar: created at, tournament, mode (fresh / consistency),
  estimated cost.
- If the user is happy with the result → **"Save this style as my
  tournament's DNA"** action — extracts a Style DNA from this poster and
  saves it as a draft for that tournament.

### 5.5 Poster history

A browsable view of every poster the org has made.
- **Filters:** status (All / Completed / Failed / Generating), tournament,
  date range.
- **Sort:** most recent first.
- **Each entry shows:** thumbnail, status, tournament, poster type, created
  date.
- Click → opens the **Poster result** screen.
- Pagination (or progressive loading).

### 5.6 Brand library

Organized by **asset type**: *Team logos*, *Player images*, *Sponsor logos*,
*Tournament logos*.

Per type:
- Listing of assets — each showing the image, label, file size.
- **Upload** action: file picker + optional label.
- Each asset has a delete action with a confirmation step.
- **Drag-and-drop upload** anywhere within the section.

### 5.7 Tournaments & Style DNA

Listing of tournaments (derived from the posters created so far — each unique
tournament_id).

Per tournament:
- DNA status: *None* / *Draft* / *Approved*.
- If a DNA exists → show the palette (visual color chips), vibe, energy,
  lighting, atmosphere, particle-effects description.
- Actions:
  - **Edit DNA** — form to tweak each field; saves as draft.
  - **Approve draft** — promotes draft → approved.
  - **Delete DNA** — removes both draft and approved (with confirmation).
  - **Extract from a poster** — opens a poster picker showing the
    tournament's completed posters → extracting creates a draft from the
    chosen poster.

### 5.8 Admin — API keys

- Listing of keys for the current org: prefix (e.g. `epai_aB3C…`), name,
  created at, last used, status.
- **+ New key** → form asking for a name → on submit, **show the full
  plaintext key ONCE** in a copyable input with a clear warning: *"Save this
  now. You won't see it again."*
- Revoke action on each key — confirmation step — soft delete (the row stays;
  status becomes *Revoked*).

### 5.9 Admin — Usage & billing

- **Date range picker** (default: this month).
- KPIs: total jobs, completed, failed, estimated cost ($).
- A simple chart: jobs per day across the range.
- A footnote: *"Costs are estimates — final billing reconciles against actual
  OpenAI usage."*

---

## 6. Async generation — the key UX pattern

Generation is **not instant**. The UI must make 20–60 seconds feel quick:
- The pipeline status indicator advances as backend statuses arrive.
- An honest approximate timer — not a fake progress bar.
- The user can navigate away and start *another* poster — the app is never
  locked.
- If the user navigates away while a job is in flight, surface a notification
  when it completes: *"Your FNATIC vs T1 poster is ready."*
- Failed jobs surface inline (with the backend's error message) — never as a
  blocking alert.

---

## 7. Empty states & errors

- Every list view needs an explicit **empty state** with a relevant call to
  action (empty Brand library → "Upload your first team logo").
- Validation errors are **inline below the field**, never popups.
- Generation failures (`failed` status) show the backend's error message and a
  **Try again** action that preserves the inputs.

---

## 8. Reference data (exact values for selects)

- **Games:** `league_of_legends`, `valorant`
- **Poster types:** `gameday`, `game_results`, `roster_reveal`,
  `tournament_announcement`, `tournament_banner`
- **Output formats:** `portrait_1080x1920`, `square_1080x1080`,
  `landscape_1920x1080`
- **Vibe presets:** `cyberpunk`, `cinematic`, `dark_fantasy`, `cosmic`,
  `minimal`, `fire_energy`
- **Energy levels:** `chill`, `balanced`, `intense`, `explosive`
- **LoL roles:** Top, Jungle, Mid, Bot, Support
- **Valorant roles:** Duelist, Initiator, Controller, Sentinel, Flex
- **Match format:** Bo1, Bo3, Bo5
- **Asset types:** `team-logos`, `player-images`, `sponsor-logos`,
  `tournament-logos`
- **Job statuses:** `queued`, `generating_prompt`, `generating_poster`,
  `applying_sponsor_bar`, `completed`, `failed`

---

## 9. API contract (so screens map to endpoints)

- `POST /v1/posters` — create a poster job. Body =
  `{ org_id, tournament_id, input: { …the full form… } }`.
- `GET /v1/posters/{job_id}` — poll for status + result (signed URL when
  complete).
- `GET /v1/posters?org_id=…` — list (poster history).
- `POST /v1/assets` — multipart upload (org_id, asset_type, file, optional
  name).
- `GET /v1/assets?org_id=…&asset_type=…` — list (brand library).
- `DELETE /v1/assets/{asset_id}` — remove.
- `POST /v1/style-dnas/{tournament_id}` (`source_job_id`) — extract DNA from
  a completed poster.
- `GET / PUT / DELETE /v1/style-dnas/{tournament_id}`,
  `POST /v1/style-dnas/{tournament_id}/approve` — DNA lifecycle.
- `POST / GET / DELETE /v1/api-keys` (admin) — key management.
- `GET /v1/usage` (admin) — usage & cost report.

---

## 10. What's out of scope (don't design these)

- Marketing pages / landing page.
- The authentication flow itself (assume the user is already signed in —
  surface a placeholder user menu).
- Real-time websockets (polling is fine for v1).
- Multi-org switching workflow (just show that the user *can* switch — no
  full design).
- Native mobile apps — responsive web is enough.

---

## 11. Deliverables

- **Mockups for every screen** listed in Section 5.
- **Responsive variants** for: dashboard, poster wizard (steps 1–5), poster
  result, poster history.
- **Component inventory** (the reusable UI components the system uses —
  buttons, form fields, list items, modals, status indicators, etc.).
- **State coverage** — for each non-trivial screen, also cover: empty state,
  loading state, error state.
