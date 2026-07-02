# EsportsPostAI

An automated AI pipeline that generates professional esports posters for League of Legends and Valorant from a single JSON input — cinematic background, styled hero title, team logos, match details, atmospheric effects, and optional sponsor bar — all unified into a single image.

The project ships as both a Python CLI **and** an HTTP API backed by an async job queue. A React web UI (`Poster-ai-frontend/`) drives the API end-to-end: wizard → upload → submit → live status → download — but the UI is only a reference console; the **product is the API**. The API is **multi-tenant**: it's integrated by *platforms* (the paying customers / clients), each owning many *orgs*. A single API key authenticates a platform; data is namespaced and isolated per platform, and completion can be delivered via signed **webhooks** or polling. Each org spends a token currency (**Red Coins**) per poster, and each client **self-serves its own configuration** (branding, pricing/economics, feature flags, plans, quotas) via `GET`/`PATCH /v1/me/config`. See *Authentication & multi-tenancy*, *Red Coins & per-client configuration* below, and `GUIDE.md` for the client integration walkthrough.

---

## Red Coins & per-client configuration (latest iteration)

The biggest recent change turns the service into a configurable, multi-tenant SaaS
where each client resells to their own orgs. Highlights:

### Red Coins — the token economy (org billing)
- Orgs spend **Red Coins** per poster; end users never see dollars. A poster costs
  `tokens = base_cost_usd × quality_mult × poster_markup × tokens_per_usd`
  (defaults: ×2 markup, 10,000 tokens/$ → a $0.05 poster = 1,000 coins).
- **Charged on success only** — a failed poster costs nothing. Submit is blocked
  with **HTTP 402** if the org's balance can't cover the estimate.
- Subscription tiers **Free / Pro / Kratos** grant monthly coins (1,500 / 30,000 /
  100,000 by default); orgs can also **top up** (fixed packs + a custom amount).
- UI: a **Billing** page (plans + coin packs + a stub payment modal) and a topbar
  balance pill. Endpoints: `GET /v1/coins`, `POST /v1/coins/purchase`,
  `POST /v1/coins/subscribe`.

### Per-client configuration (self-serve)
Each **client (platform)** configures their own product — no code, no redeploy —
and changes are isolated to that client:
- **Branding** (coin name/symbol, product name, logo, accent colors),
  **Features** (consistency / refine / sponsor bar / caption / social /
  background-upload + allowed quality tiers), **Plans** (per-tier label + price to
  orgs), **per-org Quotas**, and **Red Coins economics** (rate, markup, base cost,
  top-up rate, grants). BYOK credential fields are stored (live pipeline wiring
  deferred).
- **Self-serve API**: `GET`/`PATCH /v1/me/config` (key-gated; commercial fields are
  read-only). A **Settings** page edits the same blocks. Every billing/feature
  decision resolves the caller's config via `platforms/economics.py`, so a client's
  custom values take effect everywhere automatically.
- The **provider** owns the commercial envelope — *service type* (`hosted` / `byok`)
  and *monthly fee* — set on the **Clients** page (`GET /v1/admin/platforms`,
  `POST /v1/admin/platforms/{id}`). The Usage & Billing page also shows per-org
  Red Coins balance/used.

### Generation quality + cost preview
- User-selectable **quality** (`low` / `medium` / `high`) maps to the gpt-image-2
  `quality` param and a cost multiplier (≈ ×0.25 / ×1 / ×4).
- **`POST /v1/posters/estimate`** prices a poster (in the client's coins, with
  affordability) **without generating** it — clients don't reimplement pricing.

### Reliability & UX
- **Rejected-background error** is now user-facing ("looks copyrighted — pick a
  different background") instead of "empty text", with a **Change background &
  retry** flow that keeps all wizard inputs.
- **Prompt fidelity**: a verbatim *style footer* + a GPT-4o *system instruction*
  push the chosen dominant color / vibe / energy onto the image (works in
  consistency mode via the DNA palette).
- **Sponsor bar**: the prompt reserves a clean, empty strip and the Pillow bar
  height is **synced to the same orientation-based fraction** (landscape 5 % /
  square 8 % / portrait 10 %) via `sponsors_layout.py`.
- **Notifications**: a 2-second toast + a topbar bell center + a background job
  watcher, so completion is announced (and clickable) from any page.
- **Performance**: Style DNA list is one bulk call (`GET /v1/style-dnas`) +
  parallel server-side loads + a short server cache; dashboard/history/brand-library
  cache across navigation, and R2 responses now carry `Cache-Control` so images
  don't re-download.
- **Sponsor logos**: brand-library quick-pick + dedup; cleaner team-logo labels;
  responsive result-page poster frame with a full-screen lightbox.

### Tooling
- `GUIDE.md` is a refreshed **client integration guide** (auth, generate→poll→
  download, config, webhooks, errors, full endpoint reference).
- `start.bat` / `start-all.ps1` — one double-click launches Docker (Redis + Mongo),
  the API, the worker, and the frontend in their own windows.

---

## What it does

The user fills a JSON file with match or event data (team names, tournament, time, stream link, design preferences). The pipeline produces a publish-ready poster end-to-end. Five poster types per game (Gameday, Game Results, Roster Reveal, Tournament Announcement, Tournament Banner) and three output formats (portrait 1080×1920, square 1080×1080, landscape 1920×1080) are supported. A consistency mode keeps every poster in a tournament series visually coherent by extracting a Style DNA from an approved first poster and reusing it.

---

## Current status

| Component | Status |
| --- | --- |
| Background generation — local pool | working (fine-tuned SD on Runpod deferred) |
| 🟢 Background source resolver — user upload / system pool / Runpod stub | working — Runpod call is a documented stub |
| Prompt-generation stage (GPT-4o Vision) | working |
| Poster-generation stage (gpt-image-2 editing) | working |
| Sponsor bar overlay (Pillow) | working |
| 🟢 Sponsor logos flow as bytes (R2-aware, no local-path requirement) | working |
| Prompt assembler / router / blocks | working |
| Poster-type-adaptive METADATA (per-type factual injection) | working |
| 🟢 Roster photo ↔ IGN mapping (explicit reference-image-index → name + placement rule) | working |
| Visual-style block from `design` (vibe / color / energy) | working |
| Factual-text accuracy (verbatim block + image-model footer) | working (prompt-side mitigation; deterministic PIL layer recommended) |
| Style DNA injection into prompts | working |
| Style DNA extraction from approved posters | working (hybrid: programmatic palette + GPT-4o semantic) |
| 🟢 Style DNA `source_poster_url` signed for the UI | working |
| CLI entry point | working |
| Package layout, settings, retries, tests | working (247 unit tests passing) |
| Object storage abstraction (`Storage` protocol, `LocalStorage`, `R2Storage`) | working |
| Cloudflare R2 integration | working (verified live against the bucket) |
| Pipeline wired to storage — posters + Style DNA persisted to R2 | working |
| Storage-backed asset reads (logos resolved from R2 keys at run time) | working |
| HTTP API (FastAPI) — posters, assets, style-DNAs, api-keys, usage, health | working |
| Async job queue (RQ + Redis) + worker — durable jobs persisted in MongoDB | working |
| Multi-tenant model — **platform → org → tournament** (one API key per platform; many orgs per platform) | working |
| 🟢 Per-platform API-key enforcement (`get_auth_context` — Bearer key → `platform_id`; per-platform storage namespacing + row filtering + `assert_platform`, gated by `API_KEY_REQUIRED`) | working |
| 🟢 Org registry (`/v1/orgs` register / list / get / update / delete; per-org `tier`; `OrgStore`) | working |
| 🟢 Self-serve endpoints — `GET /v1/me` (platform identity), `GET /v1/orgs/{id}` (tier + quota), `GET /v1/backgrounds` (system pool), `GET /v1/style-dnas` (org-wide list) | working |
| 🟢 Client-editable per-org rate limits (`limits` on the org record; set via `POST`/`PATCH /v1/orgs`) | working |
| 🟢 Outbound webhooks (`poster.completed` / `poster.failed`; HMAC-signed, retried, SSRF-guarded; gated by `WEBHOOKS_ENABLED`) | working |
| React web UI (`Poster-ai-frontend/`) — Dashboard, Wizard, Job, Result | working |
| 🟢 React web UI — History page, Brand Library page | working |
| 🟢 Brand library: team-scoped assets, one-logo-per-team, quick-pick by team | working |
| 🟢 Background removal on upload (rembg + u2netp, CPU-friendly) | working |
| 🟢 Reference-image resize per kind (logos 512 / players 1024, aspect preserved) | working |
| 🟢 Refine mode (3rd pipeline mode — image-edit pass on a parent poster) | working |
| 🟢 Wizard draft persistence (localStorage) | working |
| 🟢 Itemized cost estimator on review step | working |
| 🟢 Score clamping per series format (Bo1 / Bo3 / Bo5 win-target rules) | working |
| 🟢 Roster reveal: enforce 0, 1, or 5 player photos (never 2/3/4) | working |
| CORS middleware on the API | working |
| 🟢 Background-upload quality gate — reject sub-HD, downscale > 2K to 2K (aspect-preserving) | working |
| 🟢 Public share landing page (`GET /p/{job_id}`) with OG + Twitter Card tags | working |
| 🟢 Gemini-generated social caption per poster (auto on completion + `POST /v1/posters/{id}/caption`) | working |
| 🟢 Quick Share modal (Twitter / Facebook / Instagram) with editable caption + auto-download | working |
| 🟢 Same-origin download proxy (`GET /v1/posters/{id}/download`) — real attachment, CORS-safe | working |
| 🟢 Postiz backend integration (`/v1/social/integrations`, `/v1/social/post`) | working (UI shown as "Coming soon" preview) |
| 🟢 Admin Usage & Billing dashboard (`GET /v1/admin/usage/orgs`) — sortable per-org stats, tier breakdown, top-N | working |
| 🟢 Static subscription tiers (Free / Pro / Enterprise) + `tier_for_org()` seam for the real billing integration | working |
| 🟢 Toast notification system (`toast.jsx`) — global `window.toast.{error,success,info}`, replaces `alert()` calls | working |
| 🟢 1–10 star poster rating UI (localStorage-backed, backend hook stubbed) | working |
| 🟢 Red Coins token economy — per-org wallet, charge-on-success, 402 submit-gate, tiers (Free/Pro/Kratos) + monthly grants, fixed packs + custom top-up | working |
| 🟢 Billing UI (plans + coin packs + custom amount + stub payment modal) + `GET /v1/coins`, `POST /v1/coins/purchase`, `POST /v1/coins/subscribe` | working (payment provider is a stub) |
| 🟢 Per-client self-serve config — `GET`/`PATCH /v1/me/config` (branding, features, plans, quotas, economics) + Settings page | working |
| 🟢 Per-client economics resolver (`platforms/economics.py`) wired into every billing path — each client's rate/markup/grants take effect everywhere | working |
| 🟢 Provider Clients console — per-platform rollup (service type hosted/BYOK, fee, cost-to-serve, net, orgs) + `GET`/`POST /v1/admin/platforms` | working |
| 🟢 Admin Usage & Billing — per-org Red Coins balance/used columns + totals | working |
| 🟢 BYOK credential fields (OpenAI/R2/Gemini) stored per client | stored only — live pipeline wiring deferred |
| 🟢 Quality selector (low/medium/high) → gpt-image-2 `quality` + cost multiplier; tiers gated by `allowed_qualities` | working |
| 🟢 Cost preview — `POST /v1/posters/estimate` prices a poster (in the client's coins) without generating | working |
| 🟢 User-facing rejected-background error (copyright) + "change background & retry" keeping all wizard inputs | working |
| 🟢 Prompt fidelity — verbatim style footer + GPT-4o system instruction carry color/vibe/energy to the image (fresh + consistency) | working |
| 🟢 Sponsor-bar reservation synced — prompt-reserved strip ↔ Pillow bar height share one orientation-based fraction (`sponsors_layout.py`) | working |
| 🟢 Notifications — 2 s toast + topbar bell center + background job watcher (clickable to result) | working |
| 🟢 Cross-navigation caching + stable signed URLs + R2 `Cache-Control` — dashboard/history/brand-library load once, images don't re-download | working |
| 🟢 Faster Style DNA — one bulk `GET /v1/style-dnas` + parallel loads + short server cache | working |
| 🟢 Sponsor-logo quick-pick + dedup; cleaner team-logo labels; responsive result frame + full-screen lightbox | working |
| 🟢 Client integration guide (`GUIDE.md`) + one-click launcher (`start.bat` / `start-all.ps1`) | working |
| Defendr integration | not started |

---

## SaaS architecture & client integration

The HTTP API is built to be **sold to platforms** (the paying customers) and consumed from their apps with an API key. The tenancy model is **platform → org → tournament**:

```
Platform   the integrating customer — one API key authenticates it
  └── Org          one of the platform's own customers/teams (registered via /v1/orgs)
        └── Tournament   a series of posters that can share one Style DNA
```

A platform integrates **once** with a single key and generates posters on behalf of **all of its orgs**, passing `org_id` per request. The key carries a `platform_id` (not an org), and every object is namespaced under `…/platforms/{platform_id}/orgs/{org_id}/…` so two platforms can reuse the same `org_id` with zero collision — **isolation by construction**.

### Integration lifecycle

```
1. (provider)  POST /v1/api-keys            → issue a key for a platform   (admin-only)
2. (platform)  POST /v1/orgs                → register each org it serves
3. (platform)  POST /v1/assets   (optional) → upload that org's logos
4. (platform)  POST /v1/posters             → 202 {job_id}
5. (platform)  GET  /v1/posters/{job_id}    → poll to "completed" + signed_url
       …or receive a signed webhook (poster.completed) instead of polling
6. (platform)  GET  /v1/posters/{job_id}/download → image bytes (storage-agnostic)
```

The key authenticates the platform; `org_id` must name an org registered under it; each org has **client-editable** rolling rate limits; completion can be **polled or pushed via signed webhooks**. Auth is gated by `API_KEY_REQUIRED` — `false` keeps the single-tenant localhost/dev flow unchanged, `true` enforces keys + isolation everywhere. Full detail in *Authentication & multi-tenancy* and the *Multi-tenancy* / *Outbound webhooks* / *Per-org rate limiting* sections.

### For integrators

- **`GUIDE.md`** — a self-contained, client-facing walkthrough (concepts, quick start, full poster-input schema, asset→logo mapping, editable limits, webhooks, error table). This is the doc to hand a client with their key.
- **`client-integration-test.html`** — a standalone one-page test client (paste a key → register org → generate → poll → render) for validating the whole integration in a browser without a build step.

### SaaS productization progress

| Capability | Status |
| --- | --- |
| Per-platform API-key authentication (`Authorization: Bearer`, key → `platform_id`) | 🟢 done |
| Tenant isolation (per-platform storage namespacing + row filtering + `assert_platform`) | 🟢 done |
| Org registry + management (`/v1/orgs`: register / list / get / update / delete) | 🟢 done |
| Client-editable per-org rate limits (rolling day/week/month on the org record) | 🟢 done |
| Self-serve introspection (`/v1/me`, `/v1/orgs/{id}`, `/v1/usage`, `/v1/backgrounds`) | 🟢 done |
| Async generation (queue + worker + durable job status) | 🟢 done |
| Outbound webhooks (signed, retried, SSRF-guarded; gated by `WEBHOOKS_ENABLED`) | 🟢 done |
| Client integration guide + browser test harness | 🟢 done |
| Hosting + HTTPS + CORS allowlist (lock down `allow_origins=["*"]`) | ⚪ deployment step |
| Client self-service console (register orgs / keys / webhooks from a UI) | ⚪ planned |
| BYOK — clients supply their own model keys (seam: `clients/*_client.py`) | ⚪ planned |
| Metered billing integration (today: out-of-band; seam: `tier_for_org()` / `org.tier`) | ⚪ planned |

> Billing is intentionally **out-of-band** (negotiated per client; no in-app prices). The enforced control a platform actually tunes is each org's **rate limits**, edited via `/v1/orgs`. The Free/Pro/Enterprise `tier` field remains only as an optional internal label.

---

## Architecture

### Pipeline (three online stages + optional overlay)

```
input JSON  (+ org_id, tournament_id)
    |
    v
[ background ]            -- select_background() returns bytes of a local image
    |                        (shared system pool; fine-tuned SD deferred)
    v
[ prompt generator ]      -- GPT-4o Vision reads the background + assembled
    |                        prompt and writes the image-generation prompt
    v
[ poster generator ]      -- gpt-image-2 editing mode receives the background,
    |                        the prompt, and team/tournament logos as inputs
    v
[ optional sponsor bar ]  -- Pillow composites a sponsor bar inside the canvas
    |                        when sponsors.enabled is true in the input JSON
    v
[ save_poster ]           -- writes the finished poster to BOTH a local
    |                        outputs/ copy and Cloudflare R2
    v
local: outputs/<poster_id>.png
R2:    defendr-poster-ai/orgs/{org_id}/tournaments/{tournament_id}/posters/<poster_id>.png
```

The previously planned "Stage 4 PIL logo overlay" that re-stamped team logos in pixel-perfect positions has been intentionally dropped. The image-generation stage owns logo placement; the only post-processing pass is the optional sponsor bar.

All images move through the pipeline as **bytes**, not filesystem paths. Only the `storage` layer knows about files vs. buckets — every other component (the OpenAI client, the stages) deals in `bytes`. This is what lets the exact same pipeline run on `LocalStorage` in dev and `R2Storage` in production.

### 🟢 HTTP API + async worker

```
                              ┌──────────────────────┐
   browser (React SPA)        │  FastAPI  (uvicorn)  │
   http://localhost:5173 ─▶   │  http://:8000/v1/*   │
   (Poster-ai-frontend/)      └─────────┬────────────┘
                                        │
            ┌───────────────────────────┴─────────────────────────────┐
            ▼                                                         ▼
     ┌──────────────┐                                          ┌──────────────┐
     │   MongoDB    │ ◀── job rows / asset metadata / api      │    Redis     │
     │ epai-mongo   │     keys / usage events                  │ epai-redis   │
     │   :27017     │                                          │    :6379     │
     └──────────────┘                                          └──────┬───────┘
                                                                      │
                                                              poster-ai queue
                                                                      │
                                                              ┌───────▼─────────┐
                                                              │ rq SimpleWorker │
                                                              │ run_fresh /     │
                                                              │ run_consistency │
                                                              │ run_refine      │
                                                              └─────────────────┘
```

- **`POST /v1/posters`** returns `{job_id, status: queued}` in 202 immediately; the worker picks it up and writes status transitions back to Mongo.
- **`GET /v1/posters/{id}`** is what the SPA polls. On `completed`, the API signs an R2 URL and returns it as `signed_url`.
- **🟢 `POST /v1/posters/{id}/refine`** enqueues a *new* job whose `_meta.mode = "refine"` and whose `input_data.refine` carries `parent_storage_key + user_prompt`. The refine handler treats the parent poster as the canvas for `gpt-image-2` edit mode.
- **🟢 `/v1/assets`** is the brand library: org-scoped uploads to R2, MongoDB metadata, team-scoped logos, background-removal on upload, soft-delete via `DELETE /v1/assets/{id}`.
- **🟢 `/v1/style-dnas/{tid}`** drives the consistency flow: extract / get / update draft / approve / delete. The `GET` response now includes a `source_poster_url` (signed) so the UI can show the poster the DNA was extracted from.
- **🟢 `/v1/api-keys`** and **🟢 `/v1/usage`** scaffold multi-tenancy: API key issuance and basic per-org usage queries, gated by an `ADMIN_TOKEN`.

The frontend is a static React SPA (Babel-in-browser, no build step) at `Poster-ai-frontend/EsportsPostAI.html`. CORS middleware on the API allows it to call `localhost:8000` from `localhost:5173`.

**Windows note:** RQ's default worker uses `os.fork()` which doesn't exist on Windows. Run the worker as `rq worker poster-ai --worker-class rq.SimpleWorker` so jobs execute in-process.

### Prompt system

The vision model never receives a static template. The assembler chains eight blocks in a fixed order and injects only those that apply, based on the routing decisions made from `_meta`:

```
input.json
    |
    v
router.route(input_data, style_dna?)
    |
    v
assembler.build_prompt(...)
    |
    1. BACKGROUND_ANALYSIS_BLOCK        static, always
    2. METADATA block                   dynamic, poster-type-adaptive, null fields skipped
    3. FACTUAL_TEXT_BLOCK                static, always — verbatim-text hard rule
    4. POSTER_TYPE_BLOCKS[poster_type]  dynamic, one of five
    5. GAME_RULES[game]                 only for game_results / roster_reveal
    6. asset_block                      dynamic, only assets present in JSON
    7. visual-style block               consistency DNA if present, else the design block
    8. OUTPUT_RULES_BLOCK               static, always
    |
    v
assembled prompt -> GPT-4o Vision -> writes the image-generation prompt
    |
    v
+ build_image_factual_footer(...) appended -> final prompt -> gpt-image-2
```

The **METADATA block is poster-type-adaptive** — each poster type gets its own builder injecting only the facts that apply (a `game_results` poster gets the series score and the derived winner; a `roster_reveal` poster gets the player list; a tournament poster gets the event details). Null/empty fields are skipped silently, which is what prevents `{stream_url}` placeholders from leaking into rendered posters.

The assembled prompt goes to **GPT-4o**, which writes the actual image-generation prompt. Because GPT-4o can paraphrase or drop factual values, `build_image_factual_footer()` re-appends the verbatim factual data plus a render-exactly rule **directly onto the prompt gpt-image-2 receives** — so the facts bypass GPT-4o's rewrite. See *Prompt accuracy & poster-type adaptation* below.

### Modes

`fresh` mode generates a standalone poster. `consistency` mode loads a saved Style DNA from object storage, keyed on `org_id` + `tournament_id`, and injects it into the prompt as a hard constraint on palette, lighting, atmosphere, and particle effects.

Every run carries an `org_id` (the tenant) and a `tournament_id`. Today both are static — `org_id` defaults to `"1"`, `tournament_id` comes from `--tournament-id` (defaulting to `_standalone` in fresh mode). When the HTTP API and Defendr integration land, these become real identifiers supplied per request; nothing else in the pipeline changes.

### Style DNA — how it works

A Style DNA captures the *visual style* of an approved poster without capturing any content (no team names, scores, logos, or dates). It exists so that the second, third, and subsequent posters in a tournament series stay visually coherent with the first one — same palette, same lighting language, same atmosphere — even though the data on each poster is different.

Extraction is hybrid by design. The vision model is strong at semantic description and weak at exact color extraction, so the work is split between two systems:

- **Palette** is extracted programmatically using PIL median-cut quantization. Free, deterministic, gives exact hex values sorted by frequency.
- **Lighting, atmosphere, particle effects, energy, and SD style keywords** are extracted by GPT-4o Vision. The model receives the approved poster *and* the already-extracted palette, and is told to use those palette colors as the only reference. This grounds the semantic description in concrete values and keeps the model focused on the work it's good at.

The extraction prompt explicitly forbids the model from including any content-derived information (team names, score lines, tournament names, dates, character identities). Bounding-box-level masking via OCR is an obvious next improvement but is deferred — see Roadmap.

DNA documents have a lifecycle, and they live in **object storage** (R2), not on the local filesystem. A freshly extracted DNA is saved as a draft at the storage key `.../tournaments/{tournament_id}/style-dna.draft.json`. The user reviews it, optionally edits it, and then promotes it to `.../tournaments/{tournament_id}/style-dna.json` via `--approve-dna` (which writes the approved object and deletes the draft). Consistency-mode runs prefer the approved object; if only a draft exists, they use it but log a warning. If neither exists, consistency mode falls back to fresh-mode behavior and logs a warning explaining how to extract a DNA after approving the resulting poster.

The complete workflow:

```
1. Generate the first poster of a tournament series.
   python run.py --input inputs/lol/gameday.json \
       --mode consistency --tournament-id ewc_2025
   # No DNA exists yet — runs as fresh, logs a "no DNA" warning.

2. Review the generated poster. If you like it, extract a Style DNA from it.
   python run.py --extract-dna \
       --source-poster outputs/poster_20260518_120000.png \
       --tournament-id ewc_2025
   # Saves the draft DNA object to R2 and prints a preview.

3. (Optional) Edit the draft DNA before promoting it.

4. Promote the draft to the approved DNA used by consistency mode.
   python run.py --approve-dna --tournament-id ewc_2025
   # Writes the approved DNA object, deletes the draft, stamps approved_at.

5. Generate every subsequent poster in the series. The approved DNA is
   automatically injected into the prompt.
   python run.py --input inputs/lol/gameday.json \
       --mode consistency --tournament-id ewc_2025
```

All of the above are scoped to an organization via `--org-id` (default `"1"`).

---

## Project structure

```
esports-poster-ai/
|
|-- pyproject.toml                       # dependencies, build, pytest config
|-- .env.example                         # template for required env vars
|-- .gitignore
|-- README.md                            # this file
|-- run.py                               # thin shim: python run.py --input ...
|
|-- src/
|   `-- esports_poster_ai/
|       |-- __init__.py
|       |-- __main__.py                  # python -m esports_poster_ai (CLI)
|       |-- cli.py                       # argparse entry
|       |-- config.py                    # Pydantic Settings (one source of truth)
|       |-- worker.py                    # `python -m esports_poster_ai.worker` (RQ entry)
|       |
|       |-- api/                         # FastAPI HTTP layer
|       |   |-- __main__.py              # `python -m esports_poster_ai.api` (uvicorn entry)
|       |   |-- app.py                   # FastAPI() + CORS + /health
|       |   |-- schemas.py               # request/response Pydantic models
|       |   |-- deps.py                  # 🟢 auth context (Bearer key -> platform), admin, store deps
|       |   `-- routes/
|       |       |-- posters.py           # POST/GET /v1/posters (+ refine, caption, download)
|       |       |-- assets.py            # POST/GET/DELETE /v1/assets
|       |       |-- style_dnas.py        # full DNA lifecycle endpoints (+ org-wide list)
|       |       |-- orgs.py              # 🟢 /v1/orgs — platform's org registry (+ editable limits)
|       |       |-- me.py                # 🟢 GET /v1/me — platform identity
|       |       |-- backgrounds.py       # 🟢 GET /v1/backgrounds — system background pool
|       |       |-- webhooks.py          # 🟢 /v1/webhook — callback registry + test/replay
|       |       |-- api_keys.py          # admin: issue / list / revoke keys (per platform)
|       |       |-- usage.py             # GET /v1/usage + /v1/usage/quota + admin rollup
|       |       |-- share.py             # 🟢 GET /p/{job_id} — public share landing page
|       |       `-- social.py            # 🟢 GET/POST /v1/social/* — Postiz-backed native posting
|       |
|       |-- jobs/                        # async job pipeline
|       |   |-- queue.py                 # RQ queue + enqueue_poster_job()
|       |   |-- store.py                 # JobStore — MongoDB `jobs` collection
|       |   `-- handlers.py              # process_job() — runs the pipeline + emits webhooks
|       |
|       |-- assets/
|       |   `-- store.py                 # AssetStore — MongoDB `assets` collection
|       |
|       |-- auth/
|       |   `-- store.py                 # ApiKeyStore — hashed key -> platform lookup
|       |
|       |-- orgs/                        # 🟢 org registry (orgs scoped under a platform)
|       |   `-- store.py                 # OrgStore — MongoDB `orgs` collection (tier + limits)
|       |
|       |-- quotas/                      # 🟢 per-org rolling-window rate limiting
|       |   `-- limiter.py               # compute_quotas / check_quota_or_raise + headers
|       |
|       |-- webhooks/                    # 🟢 outbound webhooks (push on job completion)
|       |   |-- signing.py               # HMAC-SHA256 signature + SSRF-safe URL check
|       |   |-- store.py                 # WebhookConfigStore + WebhookDeliveryStore
|       |   `-- delivery.py              # emit_job_event / deliver_webhook (retries, dead-letter)
|       |
|       |-- domain/                      # Pydantic input + record models
|       |   |-- inputs.py                # PosterInput with strict _meta literals
|       |   |-- job.py                   # Job + JobStatus literals (+ platform_id)
|       |   |-- asset.py                 # Asset record (+ platform_id)
|       |   |-- api_key.py               # ApiKey record (platform_id)
|       |   |-- org.py                   # 🟢 Org record + OrgRateLimits
|       |   |-- webhook.py               # 🟢 WebhookConfig + WebhookDelivery
|       |   `-- style_dna.py
|       |
|       |-- clients/
|       |   |-- openai_client.py         # retries, run_id logging, error mapping
|       |   `-- gemini_client.py         # 🟢 gemini-2.5-flash call for social captions
|       |
|       |-- social/                      # 🟢 social-posting integrations
|       |   |-- __init__.py              # exports PostizClient, get_postiz_client()
|       |   `-- postiz.py                # Postiz Public API client (integrations / upload / posts)
|       |
|       |-- billing/                     # 🟢 subscription tiers (placeholder for real billing)
|       |   |-- __init__.py              # public exports
|       |   `-- tiers.py                 # Free / Pro / Enterprise definitions + tier_for_org() seam
|       |
|       |-- prompt/                      # dynamic prompt assembler
|       |   |-- assembler.py
|       |   |-- router.py
|       |   `-- blocks/
|       |       |-- static.py             # background analysis, factual-text rule, output rules
|       |       |-- poster_type.py
|       |       |-- game_rules.py
|       |       |-- assets.py
|       |       |-- design.py             # VISUAL STYLE block (vibe / color / energy)
|       |       `-- consistency.py
|       |
|       |-- stages/                      # one file per stage (no numbers)
|       |   |-- background.py            # returns background image bytes
|       |   |-- prompt_generator.py
|       |   |-- poster_generator.py      # generate_poster() + save_poster()
|       |   |-- sponsor_bar.py
|       |   `-- caption_generator.py     # 🟢 Gemini-driven social caption per completed poster
|       |
|       |-- storage/                     # object-storage abstraction (R2 / local)
|       |   |-- base.py                  # Storage protocol + content-type helper
|       |   |-- keys.py                  # StorageKeys — the only place keys are formed
|       |   |-- local.py                 # LocalStorage (dev / tests)
|       |   |-- r2.py                    # R2Storage (boto3, Cloudflare R2)
|       |   `-- __init__.py              # get_storage() / get_keys() factories
|       |
|       |-- style_dna/                   # extraction + storage for consistency mode
|       |   |-- palette.py               # programmatic palette + temperature
|       |   |-- semantic.py              # GPT-4o vision call for semantic fields
|       |   |-- extractor.py             # orchestrates palette + semantic -> StyleDNA
|       |   `-- repository.py            # storage-backed draft / approved lifecycle
|       |
|       `-- modes/
|           |-- fresh.py                 # reads logos from local FS OR R2 storage keys
|           |-- consistency.py
|           `-- refine.py                # 🟢 image-edit pass over a parent poster
|
|-- Poster-ai-frontend/                  # React SPA (Babel-in-browser; no build step)
|   |-- EsportsPostAI.html               # entry — sets window.API_BASE, loads bundles
|   |-- styles.css
|   |-- api.jsx                          # fetch wrapper around the FastAPI endpoints
|   |-- app.jsx                          # hash router + theme tweaks
|   |-- shell.jsx                        # sidebar + topbar + icon set
|   |-- dashboard.jsx                    # live job list (polled), in-progress + recent
|   |-- wizard.jsx                       # 5-step Create Poster — controlled form + upload
|   |-- job-progress.jsx                 # polls GET /v1/posters/{job_id}
|   |-- poster-result.jsx                # signed-URL image + Download + Extract DNA + 🟢 RatingCard + QuickShareModal
|   |-- admin-usage.jsx                  # 🟢 admin Usage & Billing dashboard (sortable table, tier chips, top-N)
|   |-- toast.jsx                        # 🟢 global Toaster + window.toast.{error,success,info}
|   `-- tweaks-panel.jsx                 # design tokens panel
|
|-- tests/
|   |-- conftest.py
|   `-- unit/                            # deterministic modules; no network
|       |-- test_router.py
|       |-- test_assembler.py
|       |-- test_sponsor_bar.py
|       |-- test_domain_inputs.py
|       |-- test_storage_keys.py
|       |-- test_storage_local.py
|       |-- test_dna_repository.py
|       `-- ...                          # palette, schema, semantic prompt, etc.
|
|-- backgrounds/                         # local background image pool
|-- inputs/                              # CLI input JSONs (test fixtures in disguise)
|-- assets/                              # team / sponsor / player logos for CLI runs
|-- outputs/                             # local copy of generated posters
|-- scratch/                             # gitignored ad-hoc local output
`-- styles/                              # legacy local Style DNA files (no longer read)
```

The legacy `pipeline/`, `prompt/`, and `modes/` directories at the repo root have been removed — the `src/esports_poster_ai/` package is the single source of truth. The repo-root `styles/` directory is also legacy: Style DNA now lives in object storage, and the repository no longer reads local files.

---

## Installation

Requires Python 3.10 or newer.

Install the package and its dependencies in editable mode:

```
pip install -e .[dev]
```

The full set of runtime dependencies covers the CLI, the API, the worker, and storage: `pydantic`, `pydantic-settings`, `tenacity`, `openai`, `pillow`, `python-dotenv`, `boto3`, `fastapi`, `uvicorn`, `python-multipart`, `redis`, `rq`, `pymongo`, `pytest`.

Copy the env template and fill in the OpenAI key (and the R2 variables if you
want posters to be persisted to Cloudflare R2 — see Configuration):

```
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

**Background images:** drop one or more PNGs into a `backgrounds/` directory at the repo root (the path is configurable via `Settings.backgrounds_dir`). The first image alphabetically is the one `select_background()` picks. **Use original / non-IP artwork** — GPT-4o refuses to analyze recognizable copyrighted art (e.g. game splash art with characters or baked-in logos) and the prompt stage will return empty text. See *Known gaps*.

**API + worker also need:**

- **Redis** on `redis://localhost:6379/0` (the queue transport). On Windows the easiest path is `memurai` or Docker (`docker run -p 6379:6379 redis:7`). The worker must be launched with `--worker-class rq.SimpleWorker` on Windows because RQ's default `Worker` calls `os.fork()`.
- **MongoDB** on `mongodb://localhost:27017` (the job store, the asset catalog, and the API-key/usage tables). Local install or `docker run -p 27017:27017 mongo:7`.

Both URLs are overridable via `REDIS_URL` and `MONGODB_URL` in `.env`.

---

## Usage

There are three ways to drive the pipeline: the original CLI, the HTTP API, and the React web UI on top of the API.

### CLI

After installation, all of the following are equivalent:

```
python run.py --input inputs/lol/gameday.json
python -m esports_poster_ai --input inputs/lol/gameday.json
esports-poster --input inputs/lol/gameday.json
```

Consistency mode requires a tournament id (used to locate the Style DNA in storage):

```
python run.py --input inputs/lol/gameday.json --mode consistency --tournament-id ewc_2025
```

An organization id can be passed with `--org-id` (default `"1"`); it scopes where posters and Style DNA are stored. On completion the CLI prints the local path, the storage key, and a signed URL for the generated poster, and writes structured log lines to stderr with a per-run `run_id` for correlation.

### HTTP API + worker

The API runs the request/response side; the worker runs the pipeline. Both need Redis (queue) and MongoDB (job store) reachable. Start them in two terminals:

```
# Terminal 1 — HTTP API on :8000
python -m esports_poster_ai.api

# Terminal 2 — worker draining the `poster-ai` queue
python -m esports_poster_ai.worker
# Windows: use SimpleWorker instead — RQ's default Worker calls os.fork():
# rq worker poster-ai --worker-class rq.SimpleWorker --url redis://localhost:6379/0
```

Sanity-check the deployment:

```
curl http://localhost:8000/health
# {"status":"ok","mongodb":"ok","redis":"ok"}
```

Submit a poster (any CLI input JSON works):

```
curl -X POST http://localhost:8000/v1/posters \
  -H "Content-Type: application/json" \
  -d '{"org_id":"1","tournament_id":"ewc_2025","input": '"$(cat inputs/lol/gameday.json)"'}'
# -> {"job_id":"...","status":"queued",...}

curl http://localhost:8000/v1/posters/<job_id>
# -> {"status":"completed","signed_url":"https://...","storage_key":"..."}
```

### Web UI

Static files in `Poster-ai-frontend/`. No build step — open it through any HTTP server:

```
cd Poster-ai-frontend
python -m http.server 5173
# open http://localhost:5173/EsportsPostAI.html
```

The page expects the API at `http://localhost:8000` by default; override at the top of `EsportsPostAI.html` by setting `window.API_BASE`.

### Run tests

```
pytest
```

Tests cover the deterministic modules — the prompt router, assembler, sponsor-bar config detection, Pydantic input validation, the storage key builder, `LocalStorage`, and the storage-backed Style DNA repository. No OpenAI calls and no network are made.

---

## Configuration

All runtime configuration is centralized in `src/esports_poster_ai/config.py` and loaded from `.env`. Recognized variables:

```
OPENAI_API_KEY               required
OPENAI_PROMPT_MODEL          default: gpt-4o
OPENAI_IMAGE_MODEL           default: gpt-image-2
STAGE2_BUDGET_USD            default: 0.10  (per-call upper-bound cost guard)
STAGE2_MAX_OUTPUT_TOKENS     default: 2000
OPENAI_MAX_RETRIES           default: 3
OPENAI_INITIAL_BACKOFF_SECONDS  default: 1.0
OPENAI_MAX_BACKOFF_SECONDS   default: 16.0
LOG_LEVEL                    default: INFO
RUNPOD_API_KEY               reserved for the deferred SD background stage
RUNPOD_ENDPOINT_ID           reserved

R2_ACCESS_KEY_ID             Cloudflare R2 API token — Access Key ID
R2_SECRET_ACCESS_KEY         Cloudflare R2 API token — Secret Access Key
R2_ENDPOINT                  R2 S3 endpoint: https://<account_id>.r2.cloudflarestorage.com
R2_BUCKET                    R2 bucket name (shared with Defendr)
R2_KEY_PREFIX                default: defendr-poster-ai  (top-level namespace)
R2_PUBLIC_URL                optional; blank = use presigned URLs

REDIS_URL                    default: redis://localhost:6379/0
MONGODB_URL                  default: mongodb://localhost:27017
MONGODB_DB                   default: defendr_poster_ai

API_HOST                     default: 0.0.0.0
API_PORT                     default: 8000
MAX_ASSET_SIZE_MB            default: 10
ADMIN_TOKEN                  required for admin endpoints; blank = admin endpoints refuse all requests
API_KEY_REQUIRED             default: false. When true, every org-scoped endpoint requires a valid
                             `Authorization: Bearer <api-key>`; the PLATFORM is taken from the key,
                             org_id is per-request and must be registered under it, and all data is
                             namespaced + isolated per platform. When false (dev), org_id may be
                             passed directly and a key is optional (but still validated when present).
                             Set true before exposing beyond localhost.
COST_PER_POSTER_USD          default: 0.054  (used by GET /v1/usage)

QUOTA_DAY_DEFAULT            default: 3   ) per-org rolling-window quota defaults. Each org can
QUOTA_WEEK_DEFAULT           default: 15  ) override these via POST/PATCH /v1/orgs (`limits`),
QUOTA_MONTH_DEFAULT          default: 30  ) e.g. {"day":10,"week":50,"month":100}.

WEBHOOKS_ENABLED             default: false. Master switch for outbound webhooks. False = the emit
                             hook is a no-op and nothing about the pipeline changes.
WEBHOOK_TIMEOUT_SECONDS      default: 5.0
WEBHOOK_MAX_ATTEMPTS         default: 5    (delivery attempts before dead-letter)
WEBHOOK_BACKOFF_BASE_SECONDS default: 10.0 (exponential: base * 2**(attempt-1))
WEBHOOK_ALLOW_INSECURE_URLS  default: false. Dev-only: allow http:// + localhost/private callback
                             URLs (e.g. to test against a local listener). Keep false in production.

PUBLIC_BASE_URL              default: http://localhost:8000
                             public hostname embedded in /p/{job_id} OG/Twitter Card tags.
                             Set to your ngrok / public URL when sharing links publicly,
                             so Twitter/Facebook scrapers can fetch the landing page.

GEMINI_API_KEY               optional. Enables auto-generated social captions on completed
                             posters via gemini-2.5-flash. Blank = caption endpoints return
                             503 and the UI hides the caption-related affordances.

POSTIZ_BASE_URL              default: http://localhost:4007
                             base URL of your Postiz instance (self-hosted) or
                             https://api.postiz.com for cloud. The client appends
                             /api/public/v1 internally (self-host nginx layout).
POSTIZ_API_KEY               optional. Public-API key generated in the Postiz UI
                             (Settings → Developers → Access). Blank = /v1/social/*
                             endpoints return 503 and the UI shows a "Coming soon"
                             preview instead of the live native-post panel.
```

When the four required R2 variables are set, `get_storage()` returns `R2Storage`; otherwise it falls back to `LocalStorage` rooted at `scratch/storage/`. This means the pipeline runs with zero R2 configuration in dev and tests.

Reading `os.environ` directly anywhere in the codebase is discouraged — import `get_settings()` from `config.py` instead.

---

## Recent refactor — what changed and why

The codebase was a single-purpose CLI that grew up around a working prompt pipeline. The latest refactor prepares it for SaaS distribution without changing pipeline behavior. Each change below targets a specific limitation that would have surfaced as soon as an HTTP API, multi-tenancy, or paying customers were added.

**Adopted a `src/` package layout with `pyproject.toml`.** The previous tree had no `__init__.py` files and relied on running from the repo root for imports to resolve. That works for a CLI; it breaks the moment the package is imported from a FastAPI worker, dockerized, or shipped as a wheel. The new layout makes the project a real installable Python package (`pip install -e .`) while preserving the old `python run.py` invocation via a thin shim that prepends `src/` to `sys.path`.

**Centralized configuration in `config.py`.** Environment variables were being loaded independently inside `stage2_analysis.py` and `stage3_generation.py` via `load_dotenv()` and `os.getenv()`. Adding a new setting required edits in multiple files and risked drift. A single `Settings` Pydantic model now owns every knob — API keys, model names, retry policy, budget caps, log level — and modules pull what they need via `get_settings()`.

**Introduced an OpenAI client wrapper in `clients/openai_client.py`.** Stages used to instantiate `OpenAI()` directly and call the SDK in-line. There were no retries, no structured logging, and transient network errors crashed the pipeline. The wrapper owns the API key, applies a tenacity-based retry policy (exponential backoff on `APIConnectionError`, `RateLimitError`, `InternalServerError`, `APIError`), logs each call with a 12-character `run_id` for trace correlation, and translates SDK responses into the simple types the stages consume (`str` for prompts, `PIL.Image` for posters). Stages now contain orchestration logic only and never import `openai` themselves.

**Renamed `pipeline/` to `stages/` and dropped the stage numbers.** `stage1_background.py` became `background.py`, `stage2_analysis.py` became `prompt_generator.py`, `stage3_generation.py` became `poster_generator.py`. The numbers were accurate when the pipeline was strictly linear and had exactly four stages, but they would have lied the moment a quality-validation step, a draft/preview pass, or a retry-with-mutated-prompt loop was added. Roles are durable; positions are not. The empty `stage4_overlay.py` file was deleted — the image-generation model owns logo placement and there is no separate PIL re-stamp pass.

**Added Pydantic input models in `domain/`.** The pipeline used `Dict[str, Any]` end-to-end, with defensive null chains like `(input_data.get("_meta") or {}).get("output_format")` scattered through several modules. A typo in `_meta.poster_type` would silently produce nonsense rather than fail fast. The new `PosterInput` model strictly types the `_meta` block as `Literal` enums (`game`, `poster_type`, `mode`, `output_format`) so invalid values raise `ValidationError` at the boundary. The rest of the document is intentionally loose — fully spelling out a discriminated union for ten poster_type × game combinations is more rigor than the codebase needs today and can be added incrementally. The block builders still consume dicts and were not touched.

**Added a `tests/` directory with unit coverage for deterministic modules.** There were no tests previously, which is why a doc/code drift in the sponsor-bar logic went unnoticed for some time. The new suite uses inline dict fixtures and synthetic PIL images — no OpenAI calls, no network, fast enough to run on every save. Coverage targets the modules where regressions are most likely to bite: `prompt/router.py`, `prompt/assembler.py`, `stages/sponsor_bar.py`, and `domain/inputs.py`. Integration tests against the OpenAI API are intentionally out of scope until a recorded-cassette pattern is in place.

**Documented the sponsor-bar doc/code drift.** The previous `project_overview.md` claimed the sponsor bar used a WCAG binary search on opacity in `[0.20, 0.60]`. The actual implementation uses a simpler dark-logos-go-on-light-bar heuristic and computes opacity in `[0.55, 0.85]` based on region brightness. The new sponsor_bar module includes a docstring note about this, and the doc itself should be updated in a follow-up pass. The behavior was left unchanged because the current heuristic produces good results in practice.

**Added `.env.example` and `.gitignore`.** Standard hygiene; the original `.env.example` existed but was extended with the new configuration knobs.

Things that intentionally did **not** change in this refactor: the prompt blocks themselves (`static.py`, `poster_type.py`, `game_rules.py`, `assets.py`, `consistency.py` are byte-for-byte equivalent, only their import paths moved), the sponsor-bar rendering pipeline, the input JSON schemas, the CLI invocation, and the output filename format.

---

## Storage layer & R2 integration

The pipeline used to read and write the local filesystem everywhere. It now goes through an object-storage abstraction, and posters + Style DNA are persisted to Cloudflare R2. This is the foundation for the HTTP API and multi-tenancy.

**`Storage` protocol + two backends.** `storage/base.py` defines a tiny protocol — `get_bytes`, `put_bytes`, `exists`, `delete`, `signed_url`, `list_keys`. `LocalStorage` stores objects as files under a root directory (dev and tests, zero credentials needed). `R2Storage` is the same interface backed by boto3 against the R2 S3-compatible endpoint, with presigned URLs and a lazy boto3 import. `get_storage()` picks the backend automatically from configuration.

**Key scheme — the bucket is shared with Defendr.** Defendr already owns an R2 bucket, so this service namespaces *every* object under a single top-level prefix (`defendr-poster-ai/`, configurable via `R2_KEY_PREFIX`) to avoid collisions. `storage/keys.py` (`StorageKeys`) is the only place keys are formed; it validates every path segment against traversal. The layout:

```
# org-level — brand asset library, reused across all the org's tournaments
defendr-poster-ai/orgs/{org_id}/assets/team-logos/{asset_id}.png
defendr-poster-ai/orgs/{org_id}/assets/player-images/{asset_id}.png
defendr-poster-ai/orgs/{org_id}/assets/sponsor-logos/{asset_id}.png
defendr-poster-ai/orgs/{org_id}/assets/tournament-logos/{asset_id}.png

# tournament-level — each tournament has its own visual identity + poster history
defendr-poster-ai/orgs/{org_id}/tournaments/{tournament_id}/style-dna.json
defendr-poster-ai/orgs/{org_id}/tournaments/{tournament_id}/style-dna.draft.json
defendr-poster-ai/orgs/{org_id}/tournaments/{tournament_id}/posters/{poster_id}.png

# shared system data — not org-scoped
defendr-poster-ai/system/backgrounds/{name}
```

Assets are org-level on purpose: a team logo is the same across every tournament an org runs, so it is uploaded once and reused (the brand-asset-library goal). Style DNA and posters are tournament-level, because each tournament has its own theme and its own poster history.

**Note on bucket-level isolation.** R2 API tokens scope to a *bucket*, not a key prefix. A token used here can technically read/write all of Defendr's objects in the shared bucket — the `defendr-poster-ai/` prefix is an organizational boundary, not a security one. The mitigation is strict discipline: `StorageKeys` is the single chokepoint for key formation. A dedicated bucket would be cleaner and is worth revisiting.

**Pipeline wired to storage.** Images now flow through the pipeline as `bytes`, never filesystem paths — `OpenAIClient` accepts image bytes, `select_background()` returns bytes, and only the `storage` layer touches files or buckets. `save_poster()` writes each finished poster to **both** a local `outputs/` copy and R2. The Style DNA repository is fully storage-backed (draft/approved objects, promotion deletes the draft). Every run carries an `org_id` and `tournament_id` that determine the storage keys.

**Storage-backed asset reads (logos resolved at run time).** `_read_image()` in `modes/fresh.py` is dual-mode: CLI runs reference local files like `assets/logos/T1.png`, while API runs reference R2 storage keys like `defendr-poster-ai/orgs/1/assets/team-logos/{asset_id}.png`. The resolver tries the local filesystem first (cheap), then falls back to `get_storage().get_bytes(key)`. This is what lets an asset uploaded through `POST /v1/assets` actually reach the image-edit call — same path covers team logos, tournament logos, and the featured-player image. Sponsor bar still expects local files; migrating that one is a small follow-up.

---

## HTTP API

A thin FastAPI layer wraps the pipeline so any tenant can drive it over HTTP. The API never blocks — every poster goes through the async job queue, so requests return a `job_id` immediately and the worker does the work.

Run it with:

```
python -m esports_poster_ai.api          # uvicorn on $API_HOST:$API_PORT (default 0.0.0.0:8000)
```

CORS is enabled (currently `allow_origins=["*"]`) so a static frontend served from any port can call the API in development.

### Endpoints

```
GET  /health                                       # liveness — checks Mongo + Redis (503 if either is down)

POST /v1/posters                                   # enqueue a poster job; body = {org_id, tournament_id, input}
GET  /v1/posters/{job_id}                          # job status + signed_url on completion
GET  /v1/posters?org_id=&tournament_id=&limit=     # list (most-recent-first)
POST /v1/posters/{job_id}/refine                   # freeform image-edit pass over a completed poster
POST /v1/posters/{job_id}/caption?regenerate=      # 🟢 get-or-generate Gemini caption (503 if GEMINI_API_KEY unset)
GET  /v1/posters/{job_id}/download                 # 🟢 same-origin proxy stream with Content-Disposition: attachment

POST /v1/assets                                    # multipart: org_id, asset_type, file, name? -> {asset_id, storage_key, signed_url}
GET  /v1/assets?org_id=&asset_type=&limit=         # list an org's brand library
GET  /v1/assets/{asset_id}                         # one asset + signed_url
DEL  /v1/assets/{asset_id}                         # remove from R2 + metadata

POST /v1/style-dnas/{tournament_id}                # extract a draft DNA from a completed poster job
GET  /v1/style-dnas/{tournament_id}?status=        # active / draft / approved
PUT  /v1/style-dnas/{tournament_id}                # replace draft with edited DNA
POST /v1/style-dnas/{tournament_id}/approve        # promote draft -> approved
DEL  /v1/style-dnas/{tournament_id}                # remove both objects

POST /v1/api-keys           (admin)                # issue a hashed API key FOR A PLATFORM (body: platform_id) — plaintext returned ONCE
GET  /v1/api-keys?platform_id= (admin)             # list a platform's keys
DEL  /v1/api-keys/{key_id}  (admin)                # revoke

GET  /v1/usage?org_id=&period_start=&period_end=   # job counts + estimated_cost_usd over a window
GET  /v1/usage/quota?org_id=                       # current rolling 24h / 7d / 30d windows

GET  /v1/me                                        # 🟢 the caller's PLATFORM identity (platform_id, authenticated, org_count)

POST /v1/orgs                                      # 🟢 register an org under the platform (body: org_id?, name?, tier?)
GET  /v1/orgs                                      # 🟢 list the platform's registered orgs
GET  /v1/orgs/{org_id}                             # 🟢 one org: tier + tier metadata + live rolling quota
PATCH /v1/orgs/{org_id}                            # 🟢 update an org's name / tier / metadata
DEL  /v1/orgs/{org_id}                             # 🟢 de-register an org (does not delete its stored posters/assets)

GET  /v1/backgrounds                               # 🟢 list the shared system background pool (local pool + any R2 system backgrounds)
GET  /v1/style-dnas?org_id=                        # 🟢 list ALL of an org's Style DNAs (one per tournament, active view)

PUT  /v1/webhook                                   # 🟢 register/replace the platform's callback URL (+events); secret returned ONCE
GET  /v1/webhook                                   # 🟢 current webhook config (no secret)
POST /v1/webhook/rotate-secret                     # 🟢 new signing secret
POST /v1/webhook/test                              # 🟢 synchronous synthetic `ping` to the configured URL
GET  /v1/webhook/deliveries                        # 🟢 recent delivery attempts (audit/debug)
POST /v1/webhook/deliveries/{id}/replay            # 🟢 re-enqueue a past delivery
DEL  /v1/webhook                                   # 🟢 disable webhooks
GET  /v1/admin/usage/orgs                          # 🟢 admin: per-org rollup — tier, posters, modes, rolling windows, tier-cap utilization, spend, MRR. Currently ungated; flip require_admin_token to lock it down.

GET  /v1/social/integrations                       # 🟢 list connected social accounts (proxied from Postiz; 503 if not configured)
POST /v1/social/post                               # 🟢 publish/schedule a poster to selected integrations via Postiz

GET  /p/{job_id}                                   # 🟢 PUBLIC share landing page — HTML with OG + Twitter Card meta tags;
                                                   # social platforms scrape this to render image-card previews
```

The request/response schemas live in `src/esports_poster_ai/api/schemas.py`. The `input` field of `POST /v1/posters` is validated as the existing `PosterInput` — same schema the CLI uses — so the API and CLI consume identical JSON.

### Authentication & multi-tenancy

The service is integrated by **platforms** (the paying customers — e.g. a tournament-management SaaS), and each platform has **many orgs** registered inside it. So the hierarchy is **platform → org → tournament**: a platform integrates once with a single API key and generates posters on behalf of all of its orgs.

Two layers:

- **Admin endpoints** (API-key issuance/revocation, admin usage) require an `X-Admin-Token` header matched against `Settings.admin_token`. A key is issued **for a platform**: `POST /v1/api-keys {"platform_id": "...", "name": "..."}`.
- **🟢 Per-platform API-key auth** on every org-scoped endpoint, via the `get_auth_context` dependency in `api/deps.py`. A caller authenticates with `Authorization: Bearer <api-key>`; the key is verified against the hashed `api_keys` table (`auth/store.py`) and resolves to a **`platform_id`** (not an org). The request still carries `org_id` per call — the platform says which of *its* orgs the operation is for — and that org must be **registered under the platform** (`POST /v1/orgs`). Resources loaded by id (jobs, assets) are guarded by `assert_platform`, which returns 404 on cross-platform access, so one platform can never read another's data.

  **Isolation is by construction:** every object is namespaced under `…/platforms/{platform_id}/orgs/{org_id}/…` in object storage, and job/asset rows carry `platform_id` and are filtered by it. Org ids are unique only *within* a platform, so two platforms can both have an org called `team-alpha` with no collision.

  The gate has two modes, controlled by `API_KEY_REQUIRED`:

  - **`false` (dev default)** — single-tenant localhost surface: `org_id` is passed directly, a key is optional, `platform_id` is null (flat storage layout), and there is no registration/isolation enforcement. The existing frontend keeps working untouched. Any key that *is* sent is still validated.
  - **`true`** — a valid Bearer key is mandatory on every org-scoped endpoint (missing/invalid key → 401); the platform comes from the key, `org_id` must name an org registered under it (else 404), and all data is confined to that platform. **Flip this to `true` before exposing the API beyond localhost.**

  This is what makes a real key-authenticated integration work: a platform is issued a key (admin endpoint), registers its orgs (`POST /v1/orgs`), and from then on every call is scoped and isolated to that platform.

---

## Async job pipeline

A poster takes 20–60 s end-to-end and cannot be returned synchronously over HTTP. The job pipeline decouples the request from the work.

```
client --POST /v1/posters--> FastAPI
                                |
                                v
                       enqueue_poster_job()
                          |              \
                          v               v
              JobStore (MongoDB)   RQ Queue (Redis: "poster-ai")
              status="queued"           |
                                        v
                                   RQ worker
                                  process_job(job_id)
                                        |
                                        v
                              run_fresh / run_consistency
                                        |
                                        v
                       on_status(...) callback -> JobStore.update_status()
                                        |
                                        v
                       JobStore.mark_completed / mark_failed
```

- **Redis** is the *transport* — it moves `job_id`s from the enqueuer to a worker. Queue name: `poster-ai`.
- **MongoDB** is the *system of record* — every job is persisted with full status history. The same row doubles as the billing trail.
- **JobStatus** transitions: `queued → generating_prompt → generating_poster → applying_sponsor_bar → completed` (or `→ failed`).
- The worker entry point is `python -m esports_poster_ai.worker`, which calls `process_job` from `jobs/handlers.py`.

### Running the worker

```
python -m esports_poster_ai.worker
```

On **Windows**, RQ's default `Worker` forks via `os.fork()` and dies on the first job. Use the in-process `SimpleWorker` instead:

```
rq worker poster-ai --worker-class rq.SimpleWorker --url redis://localhost:6379/0
```

A failure is recorded as `status=failed` with the error text on the job row — the worker never raises, so the queue stays drained and the billing trail intact.

---

## Web UI (`Poster-ai-frontend/`)

A React single-page app drives the API end-to-end. It deliberately has **no build step** — React + ReactDOM + Babel-standalone are loaded from a CDN inside `EsportsPostAI.html`, and the `.jsx` files are transpiled in the browser. This keeps the frontend trivially deployable as static files.

Serve it however you like (any static server works). In dev:

```
cd Poster-ai-frontend
python -m http.server 5173
# open http://localhost:5173/EsportsPostAI.html
```

The API base URL is set at the top of `EsportsPostAI.html` via `window.API_BASE` (default `http://localhost:8000`).

### Screens & flows

| Screen | Route | Behavior |
| --- | --- | --- |
| Dashboard | `#/` | Polls `GET /v1/posters` every 5 s. Splits jobs into *in-progress* (live progress ring) and *recent completed* (clickable thumbnails to result). Stats are computed live from the same payload. 🟢 Style DNA library section discovers saved DNAs from the org's tournament jobs. |
| Wizard | `#/create` | Five steps: game/type → poster data → visual style → format & extras → review. Every input is controlled. `AssetUpload` slots fire `POST /v1/assets` and store the returned `storage_key` in form state. Step 3 fetches `GET /v1/style-dnas/{tournament_id}` when "Match my previous posters" is chosen and renders a thumbnail of the source poster. Submit POSTs `/v1/posters` and navigates to `#/job/{job_id}`. 🟢 Draft persists across refresh via `localStorage`. 🟢 Live itemized cost estimator on Step 5. 🟢 Score clamping (Bo1/3/5) and 🟢 roster-photo validation (0, 1, or 5). 🟢 Step 4 carries a background-source picker (system pool / custom upload / AI-generated *coming soon*). |
| Job progress | `#/job/{job_id}` | Polls `GET /v1/posters/{job_id}` every 2 s. Maps backend `status` → pipeline stage UI. Auto-routes to `#/result/{job_id}` on `completed`; shows error block on `failed`. |
| Poster result | `#/result/{job_id}` | Renders the R2-signed-URL image. Real Download PNG (proxied through `/v1/posters/{id}/download` for a true Save dialog) + Copy share link (the permanent `/p/{job_id}` URL). "Extract & save as draft" calls `POST /v1/style-dnas/{tournament_id}`. 🟢 "Approve this style" promotes the draft. 🟢 "Refine" card sends a freeform prompt + this poster to `POST /v1/posters/{id}/refine` and routes to the new job. 🟢 **Quick Share** trio (Twitter / Facebook / Instagram) opens a modal with the editable Gemini caption + Copy button; Confirm copies the caption to clipboard, downloads the PNG, and opens the platform compose page. 🟢 **Post directly to your accounts** preview panel mirrors the upcoming Postiz-driven one-click posting + scheduling UI, fully visible but disabled behind a COMING SOON pill — backend is wired, the UI is parked until OAuth UX is polished. |
| 🟢 History | `#/history` | Polls `GET /v1/posters` every 8 s. Status tab filters (All / Completed / In progress / Failed) + tournament dropdown + search. Cards link to result (completed) or job (in-progress/failed). |
| 🟢 Brand library | `#/brand` | Tabbed catalog of `/v1/assets` per type. Team logos and player images are team-scoped (one logo per team enforced server-side); team selector at the top filters and drives uploads. Multi-file upload, per-tile delete. Background-removal checkbox (default on for logos/players, hidden on the Backgrounds tab). |
| 🟢 Admin Usage & Billing | `#/admin/usage` | One `GET /v1/admin/usage/orgs` payload drives everything: 4 stat cards (orgs / posters / lifetime spend / MRR), subscription-tier breakdown chips, a sortable per-org table (tier badge, total posters, 24h/7d/30d rolling counts, avg-per-day, success rate, days active, mode-mix F/C/R pills, tier-cap utilization bar that goes red ≥ 90 %, lifetime spend, relative "last seen"), and a top-5 bar chart of biggest orgs by posters in the last 30 days. Auto-refresh every 30 s. Currently surfaces to everyone; one-line gate flip in the route makes it admin-only. |

### Asset uploads

`AssetUpload` (in `wizard.jsx`) is wired to the real `/v1/assets` endpoint. Picking a file:

1. POSTs `multipart/form-data` with `org_id`, `asset_type`, `file`, `name`.
2. The API writes the bytes to R2 under `defendr-poster-ai/orgs/{org_id}/assets/{type}/{asset_id}.{ext}` and persists the metadata to the `assets` MongoDB collection.
3. Returns `{asset_id, storage_key, signed_url, …}`.
4. The slot displays the signed URL as a thumbnail (proof the upload succeeded) and stores the asset object in wizard state.
5. On submit, `buildInputJSON()` maps `team.logo_asset.storage_key → match.team1.logo_path`, etc.
6. The worker resolves those keys against R2 via the storage-backed `_read_image()` (see *Storage layer* above) and hands the actual bytes to the image-edit call.

Supported asset types are the `AssetType` enum values from `storage/keys.py`: `team-logos`, `player-images`, `sponsor-logos`, `tournament-logos`.

---

## Prompt accuracy & poster-type adaptation

After storage, the focus moved to the prompt: making each poster type request the *right* facts, and making the rendered text *match the input*.

**Cleaned up the input JSON system.** The `game_results` inputs encoded the series outcome three times (per-team `score` + `result`, `match.winner`, and a separate `game_results` block). That is now a single source of truth — `team.score` per team; winner and per-team W/L are *derived*, never stored. Valorant `game_results` keeps per-map detail as `match.maps[]` (`map_name`, `rounds_team1`, `rounds_team2`) — distinct data, not a duplicate of the series score. Every input now also carries a `design` block and a `sponsors` block; `roster_reveal` carries five player slots; the dead `_meta.reference_poster_path` field was removed.

**Made the METADATA block poster-type-adaptive.** The assembler used to emit one generic metadata block for every poster type — and it never injected the score, so `game_results` posters had the model *inventing* one. `prompt/assembler.py` now dispatches on `poster_type`: each type has its own builder that injects only the facts that apply — series score + derived winner + Valorant maps + MVP for `game_results`, the player list for `roster_reveal`, event details for the tournament types, and so on.

**Wired the `design` block into the prompt.** `design` (`vibe`, `primary_color`, `energy`) was previously dead — no prompt block consumed it. `prompt/blocks/design.py` now renders a VISUAL STYLE block from it. `vibe` is a strict preset enum (cyberpunk, cinematic, dark_fantasy, cosmic, minimal, fire_energy) and `energy` uses the same vocabulary as the Style DNA. In consistency mode the Style DNA governs visual style, so the assembler injects the design block only when no DNA applies.

**Player-image feature reaches the model.** `player_feature` (an optional featured player image) is supported on `gameday` and `game_results`; `roster_reveal` uses its per-player `image_path` fields. Previously player photos were never passed to the image stage — only logos were. `modes/fresh.py` now collects player images too and hands them to `gpt-image-2` as reference inputs.

**Fixed a consistency-mode bug.** `build_prompt` gated the Style DNA block on `_meta.mode == "consistency"` — a field in the input JSON. But the CLI decides consistency via `--mode`, and the templates all say `_meta.mode: "fresh"`. So a loaded DNA was silently dropped at the prompt stage — consistency mode never actually applied a style. The block is now keyed on the *actual presence* of a `style_dna`, not the JSON field.

**Factual-text accuracy — a two-layer mitigation.** Image-generation models are unreliable text renderers: they garble digits, swap scores, invent tournament names. Two prompt-side measures push back:

1. `FACTUAL_TEXT_BLOCK` — a static "render factual text verbatim, invent nothing" hard rule, injected right after METADATA (instructs GPT-4o).
2. `build_image_factual_footer()` — the verbatim factual data plus a render-exactly rule, appended **directly onto the prompt gpt-image-2 receives**, bypassing GPT-4o's paraphrase.

In testing these took a `game_results` poster from a wrong score and an invented tournament name to the correct score *and* the correct tournament name. They are a real improvement but **not a guarantee** — see *Known gaps*.

---

## Roadmap

The work below is ordered so each phase rests on the previous one. Skipping ahead is possible but discouraged — for example, exposing an HTTP API before adding a job queue produces requests that block for 30+ seconds and time out under load.

### Phase 1 — Reliability hardening (next)

**Deterministic PIL text-composite layer** — the highest-value item. Image-model text rendering is unreliable (see *Known gaps*); the prompt-side mitigations help but do not guarantee correctness. The fix is to render factual text (score, team names, date, tournament) with Pillow after the image stage, on clean zones, instead of trusting the model. This is the change that makes the score *always* correct.

Wire the new `OpenAIClient` retry hook into integration tests against recorded cassettes. Add a poster-quality fallback: if the image stage returns obviously broken output (wrong size, empty bytes, OCR-detected garbled text), retry once with a slightly mutated prompt before failing the run. Add bounding-box-level content masking to Style DNA extraction — OCR the approved poster and either mask text regions before the semantic call or pass the bounding boxes to the extraction prompt as "ignore these regions." Update `project_overview.md` so it matches the code.

### Phase 2 — Storage abstraction — **done**

The `Storage` protocol, `LocalStorage`, `R2Storage`, the key scheme, the pipeline wiring, **and storage-backed asset reads** are complete and verified live against R2 — see the *Storage layer & R2 integration* section above.

Remaining loose ends:

- **Sponsor bar still reads local files.** `stages/sponsor_bar.py` opens logos via `PIL.Image.open(path)`; sponsor logos uploaded via `POST /v1/assets` are skipped silently. Fix: download from storage to a temp file or refactor `add_sponsor_bar` to accept bytes.
- **Backgrounds are still local.** `select_background()` reads the local `backgrounds/` pool. Migrating to `system/backgrounds/` in R2 is a small follow-up (upload the pool, read by key).
- **Repo hygiene.** Move `inputs/`, `assets/` into `tests/fixtures/`; the legacy `styles/` directory can be deleted (Style DNA is in storage now).
- **A dedicated bucket** instead of sharing Defendr's, if/when billing allows — for real tenant isolation.

### Phase 3 — Async job pipeline — **done**

RQ + Redis as the transport, MongoDB as the system of record, status transitions captured per-stage, the worker entry at `python -m esports_poster_ai.worker`. See the *Async job pipeline* section above. Windows users need `--worker-class rq.SimpleWorker` (RQ's default `Worker` calls `os.fork()`).

### Phase 4 — HTTP API — **done**

FastAPI app at `python -m esports_poster_ai.api` exposes `/v1/posters`, `/v1/assets`, `/v1/style-dnas/{id}`, `/v1/api-keys`, `/v1/usage`, and `/health`. CORS is enabled. The `input` field on `POST /v1/posters` is validated as `PosterInput` — same schema the CLI uses — so a tenant can swap between CLI and API with the same JSON. See the *HTTP API* section above for the full endpoint table.

Remaining loose ends:

- 🟢 **Webhook callbacks on job completion** — **done**. Per-platform signed webhooks (`poster.completed` / `poster.failed`) with HMAC-SHA256 signatures, an SSRF-guarded HTTPS callback registry (`PUT /v1/webhook`), a separate delivery queue with exponential-backoff retries + dead-letter, a delivery audit log + replay, and a synchronous `POST /v1/webhook/test`. Gated behind `WEBHOOKS_ENABLED` (default off; the emit hook is a wrapped no-op until turned on). See `webhooks/` + `api/routes/webhooks.py`.
- **`Retry-After` honoring** on 429s (mentioned in *Known gaps*).

### Phase 5 — Multi-tenancy — **partial**

`api_keys` (hashed) and `usage_events` collections exist, `org_id` scopes every business row, `JobStore.usage_summary()` powers `GET /v1/usage`. Admin endpoints gate on `Settings.admin_token`.

🟢 **Per-platform API-key enforcement is now wired in.** The service is sold to *platforms* (the integrating customers), each owning many orgs — so the key resolves to a `platform_id` and the request carries `org_id` per call (validated against the platform's org registry). The `get_auth_context` dependency (`api/deps.py`) verifies the Bearer key against the hashed `api_keys` table; every object is namespaced under `platforms/{platform_id}/…` and job/asset rows are filtered by `platform_id`, with `assert_platform` returning 404 on cross-platform access. Orgs are registered/managed via `/v1/orgs`. Gated behind `API_KEY_REQUIRED` (default `false` so the localhost dev flow is untouched; set `true` for production). See *Authentication & multi-tenancy* above. The remaining item:

- **Rate limiting + per-org quotas** — ✅ the rolling-window quota enforcement is already shipped (see *Per-org rate limiting*). Sub-second token-bucket precision and max-parallel-jobs limits are still deferred until the second real tenant lands.

### Phase 6 — Defendr integration — not started

Defendr becomes the first API consumer. Its backend calls `POST /v1/posters` when a match is scheduled, passes tournament/team data inline, and receives a webhook (once webhooks land) on completion. No shared database between the two services — they remain bounded contexts that communicate over HTTP. This preserves the standalone-SaaS path: any other esports org can sign up with a separate API key and use the same API without any Defendr-specific assumptions.

### Phase 1 — Reliability hardening (still the next priority)

The original Phase 1 items remain the highest-value work, now that the API and UI exist and we are closer to real customers:

**Deterministic PIL text-composite layer** — the highest-value item. Image-model text rendering is unreliable; the prompt-side mitigations help but do not guarantee correctness. Render factual text (score, team names, date, tournament) with Pillow after the image stage, on clean zones, instead of trusting the model. This is the change that makes the score *always* correct.

Wire the `OpenAIClient` retry hook into integration tests against recorded cassettes. Add a poster-quality fallback: if the image stage returns obviously broken output (wrong size, empty bytes, OCR-detected garbled text), retry once with a slightly mutated prompt before failing the run. Add bounding-box-level content masking to Style DNA extraction — OCR the approved poster and either mask text regions before the semantic call or pass the bounding boxes to the extraction prompt as "ignore these regions." Update internal docs so they match the code.

### Smaller items worth scheduling somewhere along the way

A draft/preview mode that runs the image stage at `quality="low"` first and only commits to `quality="medium"` once the customer approves the draft — cuts cost on rejected attempts. A multi-output mode that generates several candidates and lets the customer pick one — drives perceived quality up significantly. A "save draft" affordance in the wizard so a partially-filled form survives a refresh. Cost tracking written into the `jobs` row so billing reports are a SQL/aggregation query later. Background pool in R2 (`system/backgrounds/`) with a curated set of original artwork. **Sponsor-bar storage support** to close the last asset-reading gap.

### Recommended immediate next steps

The critical path now runs through quality and tenancy, not plumbing:

1. **Phase 1 PIL text-composite layer.** This is the gap that will bite first when a real tenant generates a wrong-score result poster.
2. **Auth middleware that pins `org_id` from a bearer key.** Quick win; turns `org_id` from a per-request claim into a verified one. Required before the API is exposed beyond localhost.
3. **Sponsor-bar storage support.** Closes the last asset-reading gap, mirrors what `_read_image` already does.
4. ~~**Webhook callbacks on job completion.**~~ 🟢 **done** — signed, retried, per-platform webhooks behind `WEBHOOKS_ENABLED` (see *Phase 4* loose ends and `webhooks/`).
5. **Background pool in R2.** Curated artwork uploaded to `system/backgrounds/`; `select_background()` reads from storage instead of the local folder.
6. **Defer rate-limiting and quotas** until the second tenant lands.

---

## Cost per poster (approximate)

| Stage | Model | Cost |
| --- | --- | --- |
| Background | local picker (placeholder for fine-tuned SD) | ~$0.00 |
| Prompt generation | GPT-4o Vision | ~$0.008 |
| Poster generation | gpt-image-2 medium | ~$0.046 |
| Sponsor bar | Pillow, local | free |
| **End-to-end** | | **~$0.054** |

Once retries and customer-requested regenerations are accounted for, expect real delivered cost to be closer to $0.15–0.25 per poster. Plan pricing accordingly.

---

## Known gaps

Content masking in Style DNA extraction is prompt-level only — the extraction prompt instructs the vision model not to reference team names, scores, or other content visible on the poster, but there is no bounding-box-level masking via OCR yet. The model honors the instructions in practice but a determined adversarial poster (lots of large text covering the whole frame) could leak content into the DNA. Phase 1 will add OCR-based masking.

The doc/code drift in the sponsor-bar opacity logic is acknowledged in the module docstring but not yet reconciled in `project_overview.md`.

Image-model text rendering is not guaranteed. `gpt-image-2` is an unreliable text renderer — it garbles digits, swaps scores, and invents names. The `FACTUAL_TEXT_BLOCK` and `build_image_factual_footer()` measures (see *Prompt accuracy & poster-type adaptation*) measurably reduce this, but no prompt instruction makes an image model render exact text 100% of the time. The robust fix — recommended but not yet built — is a **deterministic PIL text-composite layer**: the image model renders the scene and the stylized hero title, the factual fields (score, names, date, tournament) are left as clean zones, and Pillow stamps the exact text afterward, the same way the sponsor bar already works. There is also no OCR quality gate to *detect* a bad render and retry.

Backgrounds must be original, non-IP artwork. GPT-4o **refuses** to analyze recognizable copyrighted art (e.g. official game splash art depicting a known character) for the purpose of generating a derivative poster — the prompt stage returns a refusal and the run fails. Official splash art is also an IP liability. The local `backgrounds/` pool must contain only original or properly licensed images with no recognizable characters or baked-in branding; this is part of why a fine-tuned background generator is on the roadmap.

There is no rate-limit retry distinct from transient-error retry — a 429 from OpenAI is retried with exponential backoff up to 3 attempts, but a sustained rate-limit burst will exhaust retries quickly. The client wrapper should honor `Retry-After` headers explicitly now that the API is live.

🟢 ~~Sponsor logos uploaded via `POST /v1/assets` land in R2 correctly but `stages/sponsor_bar.py` still opens its inputs as local files via `PIL.Image.open(path)`~~ — **fixed**. `_load_logos` now accepts `{"bytes": …}` entries and `modes/fresh.py:_resolve_sponsor_logos` reads sponsor logos through the storage-aware `_read_image`, so uploaded sponsors composite correctly.

🟢 ~~The web UI's wizard form is in-memory only — navigating away discards the state.~~ — **fixed**. Wizard draft (form + step) is persisted to `localStorage` under `epai_wizard_draft_v1` and cleared on generate or discard. Ephemeral fields (fetched DNAs, libraries) are stripped so re-load triggers a refresh.

🟢 ~~End-user API endpoints currently accept any `org_id` for development. The hashed-key table and admin issuance flow exist, but the bearer-token-to-tenant middleware is not yet wired in.~~ — **fixed**. `get_auth_context` (`api/deps.py`) verifies a Bearer API key, resolves it to a **platform**, namespaces and filters all data by `platform_id`, and requires the request's `org_id` to be registered under that platform (`/v1/orgs`). Gated behind `API_KEY_REQUIRED` (default `false` for the localhost dev flow); set it `true` before exposing the API publicly. See *Authentication & multi-tenancy*.

---

## 🟢 Recent additions

Everything in this section was added in the most recent iteration on top of the HTTP API + jobs scaffolding. Each item also appears in the *Current status* table with a 🟢 marker.

### 🟢 Pipeline & data model

- **Storage-backed asset reads.** `_read_image` in `modes/fresh.py` now tries a local path first, then falls back to `get_storage().get_bytes(key)`. R2 storage keys uploaded via `/v1/assets` are resolved transparently — team logos, tournament logos, and player photos all reach `gpt-image-2` as bytes. Same change made `_resolve_sponsor_logos` flow as bytes so the sponsor bar composites uploaded sponsors correctly.
- **Tournament logo for match posters.** `_extract_input_images` now passes `tournament.logo_path` as a reference image for `gameday` and `game_results` too (previously only for tournament_* posters), so the real logo lands on the poster instead of being invented from the name.
- **Roster photo ↔ IGN mapping.** `_roster_reveal_meta` emits an explicit `Reference image #N: PLAYER PHOTO → IGN (Role)` block plus a hard "never swap, never substitute" placement rule. The mapping lands in both the GPT-4o prompt and the `gpt-image-2` factual footer so it bypasses the paraphrase pass.
- **Background source resolver.** `stages/background.py` is the single home for canvas selection: priority is **user upload** (local path or R2 key) → **AI-generated** (Runpod fine-tuned SD, currently a documented stub) → **system pool** (the existing local picker). The wizard exposes the three sources as a picker on Step 4.
- **Reference-image resize.** `processing/resize.py` introduces `LOGO_MAX_DIM=512` and `PLAYER_MAX_DIM=1024` and runs aspect-preserving resize on each reference image right before the `gpt-image-2` call. A 1024×680 logo becomes 512×340 — never a square. Below-cap inputs pass through unchanged.
- **Background removal on upload.** `processing/background_removal.py` calls `rembg` with the lightweight `u2netp` model (4.7 MB, ~1–2 s on CPU). Default ON for team / tournament / player / sponsor logos via the upload route; skipped automatically when the input already carries alpha; falls back to original bytes on any error.
- 🟢 **Background-upload quality gate.** `processing/background_quality.py` runs at `POST /v1/assets` whenever `asset_type=backgrounds`. Two guarantees: (1) anything below HD on the SHORTER edge (`min(w, h) < 720`) is rejected with **HTTP 422** and an actionable message — no point spending generation tokens on a 800×600 input that'll look weak on a 1080-tall poster; (2) anything above ~2K on the LONGER edge (`max(w, h) > 2048`) is downscaled aspect-preserving via Lanczos before storage — `gpt-image-2` tokenizes inputs by area, so an 8K wallpaper costs ~16× the input tokens of a 1920×1080 background for no visible benefit (the model rasterizes onto a 1024/1536-wide canvas anyway). Source with alpha → PNG out; opaque source → JPEG q=92. Examples: 3840×2160 → 2048×1152, 7680×4320 → 2048×1152, 1920×1080 → unchanged. Constants `BACKGROUND_MIN_SHORT_EDGE=720` and `BACKGROUND_MAX_LONG_EDGE=2048` live in the module so the thresholds are tweakable in one place. Other asset types (team / sponsor / player / tournament logos) are unaffected — they have their own runtime resize step in `processing/resize.py`. Covered by `tests/unit/test_background_quality.py` (23 cases: HD floor, 2K boundary, 4K/8K downscale, portrait orientation, alpha preservation, custom thresholds, unreadable bytes).
- **Refine mode (3rd pipeline mode).** `JobMode` literal now `Literal["fresh", "consistency", "refine"]`. `modes/refine.py` handles `POST /v1/posters/{job_id}/refine`: fetches the parent poster from R2, sends it as the canvas to `gpt-image-2` in edit mode with a focused prompt that preserves layout, factual text, and asset placement.

### 🟢 Brand library (assets)

- **`team` field on assets** (`domain/asset.py`): logos and player images can be tagged with their owning team.
- **One-logo-per-team** enforced server-side: uploading a team logo for a team that already has one deletes the prior asset (R2 + Mongo) before storing the new one.
- **Team-scoped list filter:** `GET /v1/assets?asset_type=player-images&team=GNG`.
- **`AssetType.BACKGROUND`** added so users can upload custom canvas images alongside logos/players/sponsors.
- **Delete endpoint** `DELETE /v1/assets/{asset_id}` removes from R2 + Mongo.
- One-time cleanup ran during development collapsed ~24 duplicate logos down to one-per-team and back-filled the `team` field from `LOGO`-style filenames.

### 🟢 Style DNA polish

- **Source poster URL.** `StyleDNAResponse` now carries `source_poster_url` (signed R2 link), so the UI shows a thumbnail of the poster the DNA was extracted from. Legacy CLI-era DNAs (local source path) gracefully return `null`.
- **Approve flow in the UI.** Result page exposes "Approve this style" right after "Extract & save as draft", hitting `POST /v1/style-dnas/{tid}/approve`.
- **Dashboard library.** A "Style DNA" grid on the dashboard lists every saved DNA discovered from the org's tournament jobs (palette swatches, status badge, source poster, energy/lighting summary).

### 🟢 Web UI iteration

- **History page** (`#/history`) — full poster catalog with status filter tabs, tournament dropdown, search, 8 s auto-refresh.
- **Brand Library page** (`#/brand`) — tabbed asset library (team / tournament / player / sponsor / **background**), team selector for the team-scoped tabs, multi-file upload, per-tile delete, "Remove background on upload" checkbox.
- **Quick-pick logos in the wizard** — the team picker chips in `TeamBlock` are derived from previously uploaded team-logo assets (deduped by team token). Clicking a chip fills name + short + the existing logo asset, no re-upload needed.
- **Consistency mode polish** — only the typed tournament's DNA is offered (strict slug match), no more dropdown of every DNA. Source poster thumb shown next to the palette/energy/lighting fields.
- **Refine card** on the result page — freeform prompt textarea, 2 000-char counter, submit enqueues a refine job and navigates to its progress page.
- **Itemized cost estimator** on Step 5 — base + format + per-logo / per-player / MVP / valorant map / DNA / vibe / energy modifiers. Live total on the Generate CTA. Logged in EUR per project convention.
- **Score clamping** — Bo1 / Bo3 / Bo5 with both a *win-target* per side (1 / 2 / 3) and a *series sum* (1 / 3 / 5). Re-clamps when the format changes.
- **Roster reveal validation** — count of player photos must be 0, 1, or 5; 2/3/4 blocks Continue (Step 2) and Generate (Step 5) with a clear red message.
- **Draft persistence** — wizard form + current step persisted to `localStorage`; cleared on submit or discard.
- **Tweaks panel** — runtime accent/density/bg-mood overrides via `app.jsx` CSS variables (carry-over from the design pass).

### 🟢 Per-org rate limiting (client-editable)

- **Three rolling windows** enforced per `(platform, org)`: **24 h / 7 d / 30 d**. Service defaults (`QUOTA_DAY/WEEK/MONTH_DEFAULT`, default **3 / 15 / 30**) apply until the owning platform sets its own.
- **The platform edits each org's limits** via `POST`/`PATCH /v1/orgs` — the `limits` object (`{day, week, month}`) lives on the org record (`domain/org.py:OrgRateLimits`). Any window left unset falls back to the service default, so a platform can raise just the daily cap (e.g. `{"day": 10}`) or set all three (`{"day":10,"week":50,"month":100}`). This replaced the old fixed-default + separate-collection scheme.
- **Counting:** rolling-window counts come straight from the `jobs` collection, scoped by `platform_id` — every `mode` (fresh / consistency / refine) consumes one slot. The billing trail *is* the rate-limit trail.
- **Enforcement:** `POST /v1/posters` and `POST /v1/posters/{id}/refine` check the windows (using the org's edited limits) before enqueueing. On block they return **429 Too Many Requests** with a JSON body (`{detail, window, used, limit, reset_at}`), a `Retry-After: <seconds>` header, and full `X-RateLimit-{Limit,Remaining,Reset}` headers per window.
- **Inspection:** `GET /v1/usage/quota?org_id={id}` and `GET /v1/orgs/{id}` return the three windows with `{window, used, limit, remaining, reset_at}` reflecting that org's edited limits. Every successful poster create / refine response also carries the same `X-RateLimit-*` headers.
- **In the UI:** the wizard's Generate button surfaces the 429 inline; the top nav bar and dashboard show live **D / W / M** chips with color states and reset countdowns.

### 🟢 Multi-tenancy — platform → org → tournament

The service is integrated by **platforms** (the paying customers), each owning **many orgs**. A single API key authenticates a platform; the request carries `org_id` per call.

- **Identity:** an API key carries a `platform_id` (`auth/store.py`, issued via `POST /v1/api-keys`). `api/deps.py:get_auth_context` resolves the key → platform and exposes `require_org` / `require_org_registered` / `resolve_org_limits` / `assert_platform`.
- **Org registry:** `orgs/store.py` + `domain/org.py` — orgs are keyed by `(platform, org)`, registered/managed through `/v1/orgs`, and carry their own `tier` (label) and `limits` (enforced quota).
- **Isolation by construction:** `get_keys(platform_id=…)` namespaces every object under `…/platforms/{platform_id}/orgs/{org_id}/…`; Job/Asset rows carry `platform_id` and queries filter by it. Org ids are unique only within a platform, so two platforms can reuse the same id with no collision. `assert_platform` returns 404 on cross-platform access.
- **Modes:** dev (`API_KEY_REQUIRED=false`) keeps the single-tenant localhost flow unchanged (`platform_id` is null, flat layout, no enforcement). Production (`true`) requires a key, registered orgs, and full isolation. See *Authentication & multi-tenancy*.
- **Self-serve:** `GET /v1/me` (platform identity), `GET /v1/orgs/{id}` (tier + live quota), `GET /v1/backgrounds` (system pool), `GET /v1/style-dnas` (org-wide DNA list).
- **Client integration guide:** `GUIDE.md` is a self-contained, client-facing walkthrough (concepts, quick start, full poster-input schema, asset→logo mapping, editable limits, webhooks, error table).

### 🟢 Outbound webhooks

Push instead of poll: a platform registers a callback URL and we POST a signed event when one of its posters finishes. **Gated by `WEBHOOKS_ENABLED` (default off)** — the emit hook in `jobs/handlers.py` is a wrapped no-op until turned on, so the existing pipeline is unchanged.

- **Events:** `poster.completed`, `poster.failed` (+ a synthetic `ping`). Payload carries `job_id`, `org_id`, `tournament_id`, `status`, `storage_key`, a freshly-signed `signed_url`, and `caption`.
- **Security:** HMAC-SHA256 signature in `X-EPAI-Signature: t=<ts>,v1=<hex>` (Stripe-style, replay-guarded via the timestamp); HTTPS-only callback URLs with an **SSRF guard** that rejects loopback/private/reserved hosts (`webhooks/signing.py`). `WEBHOOK_ALLOW_INSECURE_URLS` relaxes this for local testing.
- **Reliability:** deliveries run on a **separate `epai-webhooks` RQ queue** (the poster worker is never blocked), with exponential-backoff retries up to `WEBHOOK_MAX_ATTEMPTS`, then **dead-letter**. A `webhook_deliveries` collection is the audit trail.
- **Management (`/v1/webhook`, platform-authenticated):** `PUT` (set URL + events, secret shown once), `GET`, `POST /rotate-secret`, `POST /test` (synchronous ping, immediate feedback — no worker/Redis needed), `GET /deliveries`, `POST /deliveries/{id}/replay`, `DELETE`.
- **Running it:** the existing `python -m esports_poster_ai.worker` already drains the webhook queue alongside posters — no extra process. Modules: `webhooks/{signing,store,delivery}.py`, `api/routes/webhooks.py`, `domain/webhook.py`.

### 🟢 Ops & tooling

- **CORS middleware** on the FastAPI app (`allow_origins=["*"]` for dev) so the static-served SPA can call `localhost:8000`.
- **`SimpleWorker` documented** as required on Windows (default RQ worker calls `os.fork()`).
- **Health endpoint** (`GET /health`) returns `{status, mongodb, redis}` so the dashboard can show a "backend unreachable" pill when something's down.

### 🟢 Social sharing & captions

The result page is now a full social-publishing surface — auto-generated caption, image-card share links, guided quick-share to Twitter/Facebook/Instagram, and a fully-wired (but UI-deferred) backend for one-click native posting through Postiz.

**Public share landing page (`GET /p/{job_id}`).** A new public route in `api/routes/share.py` returns a minimal HTML document with full OpenGraph + Twitter Card meta tags — `og:image`, `og:title`, `og:description`, `twitter:card="summary_large_image"`. Twitter, Facebook, LinkedIn, Discord, WhatsApp, Slack, and Telegram all scrape this page to build their preview cards. Two design choices worth noting: the page re-signs the R2 URL on every visit (so embedded image links never expire), and humans hitting the page get bounced to the actual image via `<meta http-equiv="refresh">` while crawlers ignore the refresh and just read the tags. Cache-Control is `public, max-age=300` — long enough that a viral burst doesn't hammer R2, short enough that a fresh caption shows up quickly. `PUBLIC_BASE_URL` configures the absolute URL embedded in `og:url`.

**Gemini-generated social caption.** `clients/gemini_client.py` + `stages/caption_generator.py` add a tiny `gemini-2.5-flash` call that produces a 1–2-line social caption from the poster's input JSON. Persisted on the `Job` document as `caption`, so the same string drives: the social-card `og:description` on `/p/{job_id}`, the Quick Share modal's prefilled textarea, and the (parked) native-post panel. `POST /v1/posters/{job_id}/caption?regenerate=` is idempotent — first call generates, later calls return the cache unless `regenerate=true`. Returns 503 when `GEMINI_API_KEY` is unset so the frontend can degrade silently.

🟢 **Caption-quality iteration.** The first cut produced vague filler ("A series concludes. Another chapter…"). Five concrete fixes pushed it to fan-grade output ("JSK 3-1 GNG. 🔥 Playoff run looking clean after that series. GG WP. #EWC2026 #LoLEsports #Gaming"):

- **Per-poster-type field extraction** now pulls every relevant input fact: teams + shortnames + scores + derived winner + format + schedule + stream (gameday / game_results), MVP block (`player_name`, `agent_name`, `stat_label`/`stat_value` for Valorant), per-map results (`maps[].map_name + rounds`), full player roster (`ign`, `role`, `is_new_signing`) for `roster_reveal`, plus prize pool / location / tagline / teams_count for `tournament_*`. The `design` block (`vibe`, `primary_color`, `energy`) is deliberately *excluded* — those drive the IMAGE, not the social copy.
- **Refine-mode walk-back.** A refined poster's `input_data` only carries `_meta` + `refine.parent_job_id` — the actual facts live on the parent. `_resolve_input_data` follows the link so a refined poster's caption uses the same facts the original would. Fixed half-finished captions like "EWC 2026 match results are…".
- **Game lexicon.** `_GAME_LEXICON` contains ~20 LoL terms (`mid-lane diff`, `jungle pathing`, `baron buff`, `dragon soul`, `objective control`, `tower dive`, …) and ~20 Valorant terms (`spike plant`, `retake`, `eco round`, `clutch`, `1v3`, `ace`, `entry frag`, …) plus a `_ESPORTS_VOCABULARY` of universals (`comeback`, `playoff run`, `dynasty`, `rivalry`, `upset`, …). The prompt injects a `VOCABULARY` section so the LLM has authentic slang to draw on instead of inventing marketing copy.
- **Auto-built `SUGGESTED HASHTAGS`** per job: game-canonical first (`#LoLEsports`, `#VALORANT`), then a tournament slug + matching league tag (`#EWC2026 #EWC`), then per-team tags (`#JSK #JSKWIN #GNG`) — `#TEAMWIN` only on the actual winner for results, both sides for gameday — finally esports generics (`#Esports #Gaming`). The prompt tells the model to pick 3-6 from this list and forbids inventing new ones.
- **Stricter prompt + 5 poster-type-distinct few-shots.** "Score MUST appear if teams + score are in facts. Tournament MUST appear if in facts. Do NOT mention design choices (no cyberpunk, intense vibe, etc.)." Few-shots cover gameday, LoL results, Valorant results (with map list + MVP agent), roster reveal with new signings, and tournament announcement with prize pool — each demonstrating the vocabulary in action.
- **Gemini 2.5 Flash `thinkingBudget: 0` fix.** Captions were getting truncated mid-sentence ("...JSK 3-1 GNG. Statement win on the…"). Root cause: Gemini 2.5 Flash defaults to "thinking mode" — it burns invisible reasoning tokens against the same `maxOutputTokens` budget as visible output. With a 300-token budget, ~200 went to thinking and the caption ran out of room. `gemini_client.py` now sets `generationConfig.thinkingConfig.thinkingBudget = 0` — no reasoning step, full budget for visible output. Faster, cheaper, complete sentences.

**Quick Share modal.** Three buttons on the result page (Twitter / Facebook / Instagram) open a single guided-share popup that mirrors what'll happen when we ship real native posting. Confirm runs three steps atomically: write the (possibly-edited) caption to clipboard, fetch the poster bytes via the same-origin proxy and trigger a browser save, then open the platform's compose URL in a new tab. The user drops the downloaded PNG into the composer and pastes the caption. Works around three real limitations: (1) Twitter's web-intent only accepts text not images, (2) Facebook's sharer needs a URL not an image, and (3) Instagram has no web-compose intent at all. The same modal mounts identically for all three platforms, just with different copy and a different target URL.

**Postiz backend integration (UI parked).** `social/postiz.py` is a thin sync httpx client wrapping the Postiz Public API — `GET /api/public/v1/integrations`, `POST /api/public/v1/upload`, `POST /api/public/v1/posts`. `get_postiz_client()` returns `None` when `POSTIZ_API_KEY` is unset so route handlers (`GET /v1/social/integrations`, `POST /v1/social/post`) degrade to 503 cleanly. The POST handler fetches the poster bytes from R2 ourselves (rather than letting Postiz hit a signed URL that may expire mid-upload), uploads to Postiz, then creates either an immediate or scheduled post on each selected integration. Note the URL: the docs say `/public/v1/...` but the self-hosted docker image routes the public API under `/api/public/v1/...` (nginx strips `/api` before forwarding) — the client appends the right prefix automatically. The frontend `NativePostPanel` exists and works end-to-end against the backend, but is currently swapped out for a `NativePostPreviewPanel` showing the same UI fully disabled behind a `COMING SOON` pill while OAuth + per-platform dev-app onboarding is in development. One line in `poster-result.jsx` flips the live UI back on.

**Same-origin download proxy.** `GET /v1/posters/{job_id}/download` streams the R2 bytes back with `Content-Disposition: attachment; filename="{tournament}_{job_id}.png"`. Solves two distinct problems: the Quick Share modal can't `fetch()` the raw R2 signed URL because of CORS (no `Access-Control-Allow-Origin` from the R2 bucket), and the Download PNG button used to open the image in a new tab instead of saving (browsers ignore the `download` attribute on cross-origin links). Both the modal and the button now point at this endpoint, so PNGs go straight to the Downloads folder regardless of browser.

**ngrok-skip-browser-warning header wrapping.** Free-tier ngrok serves a one-time HTML interstitial to any request with a browser User-Agent, which made `fetch()` from the SPA fail with "Failed to fetch" (JSON.parse on HTML). `api.jsx` now wraps every API call through an `_fetch` helper that injects `ngrok-skip-browser-warning: 1` on every request — ngrok accepts any value and routes straight through. Safe no-op against non-ngrok hosts (FastAPI ignores unknown headers). Lets the same frontend bundle drive both `localhost` and an ngrok tunnel without per-environment code changes.

🟢 **Default back to localhost — ngrok no longer required for Quick Share.** The Quick Share flow (download PNG → copy caption to clipboard → open the platform compose URL in a new tab) is **entirely client-side and same-origin**: it never needs Twitter/Facebook/Instagram to scrape anything from your machine. The PNG is uploaded by the user inside the native composer, not pulled from a public URL. Result: `window.API_BASE` in `EsportsPostAI.html` and `PUBLIC_BASE_URL` in `.env` both default back to `http://localhost:8000`, and the dev loop is just FastAPI + Mongo + Redis again — no tunnel. The `/p/{job_id}` landing page, the `og:` / `twitter:` meta tags, and the `_fetch` ngrok-header wrapper all stay in the codebase, idle. Re-exposing the API via ngrok (or a real domain) is a single env-var flip the day you want shared `Copy share link` URLs to render image-card previews on Discord / Slack / Twitter / LinkedIn — no code changes.

### 🟢 Admin Usage & Billing

A real dashboard replaced the "Coming up next" placeholder at `#/admin/usage`. Surfaces every stat an operator needs to understand who's using the platform, who's about to hit their quota, and where the money is going — all from one API call.

**Static subscription tiers (placeholder for real billing).** `billing/tiers.py` defines three hardcoded tiers as `TierInfo` Pydantic models: **Free** (30 posters/mo, $0), **Pro** (200 posters/mo, $49), **Enterprise** (2,000 posters/mo, $499). Each carries a `color_token` CSS variable name so badge styling stays centralised. `tier_for_org(org_id)` is a static map (`{"1": "pro", "demo-enterprise": "enterprise", …}`) with `free` as the default — **the single chokepoint** where a real billing-provider integration (Stripe, Defendr's billing service, etc.) plugs in. Every caller in the codebase looks up tiers through that function, never by reaching into the constants dict directly, so the swap doesn't ripple.

**Single-query per-org rollup.** `JobStore.list_orgs_aggregate()` runs one MongoDB aggregation pipeline that returns, per `org_id`: total jobs / completed / failed, counts in rolling 24 h / 7 d / 30 d windows (completed-only — failures don't count toward billing), mode breakdown (fresh / consistency / refine), `first_activity_at` / `last_activity_at`, and `days_active_30d` (distinct calendar days with ≥ 1 completed poster — distinguishes power users from one-off spikes). The pipeline uses `$dateToString` + `$addToSet` for the days-active computation; a pure-Python fallback (`_fallback_orgs_aggregate`) kicks in automatically when the driver / backend (mongomock in tests, very old Mongo) can't run it, so the route never depends on a specific Mongo version.

**`GET /v1/admin/usage/orgs`.** New route in `api/routes/usage.py` (its own `admin_router` so the `/v1/admin/*` prefix is clean to gate later). Returns an `AdminUsageResponse` with: a `List[AdminOrgStats]` (full per-org row), `AdminTotals` (cross-org headline numbers — orgs, lifetime posters, lifetime spend, MRR sum, 30-day completed), `AdminTierBreakdown` (chip-row counts), and the full `Dict[SubscriptionTier, TierInfo]` so the UI can render tier metadata without a second call. Tier utilization is computed as `100 × completed_30d / tier.monthly_poster_cap` and clamped to 0 in the UI's progress bar (over-quota orgs still report > 100 in JSON so the operator sees the breach). Currently UNGATED so the existing demo UI keeps working without auth wiring; one-line gate flip (`token = Depends(require_admin_token)`) makes it admin-only when the ADMIN_TOKEN-flavoured surface ships everywhere.

**The dashboard UI.** `Poster-ai-frontend/admin-usage.jsx` is one self-contained component with no third-party charting deps — everything renders with plain divs + CSS variables, matching the existing tweaks-panel theme. Layout: header with refresh button and last-updated timestamp; four big stat cards (ORGS / POSTERS COMPLETED / EST. SPEND / MRR with sub-line context); a row of tier-breakdown chips colored by tier accent; a sortable table where each header is clickable (current sort key + direction shown in the table caption); each org row carries a colored tier badge, a 3-segment F/C/R mode-mix chip strip whose opacity scales with that mode's share, a tier-utilization progress bar that flips red ≥ 90 % / amber ≥ 70 % / cyan otherwise, and a relative-time "last seen". Bottom block: a top-5 bar chart of biggest orgs by posters in the last 30 days. Polls every 30 s plus a manual refresh button. Hooks are all declared above the early-return guards (Rules of Hooks — `useMemo` for `sortedOrgs` and `top5` runs even while `data` is null and just resolves to empty arrays).

**Other UX polish landed alongside.**

- **Toast notification system.** `toast.jsx` introduces a `<Toaster />` mounted inside `<Shell>` plus a `window.toast.{error, success, info}` global. Every previously-inline `alert("Upload failed: …")` now pushes a top-right card with a colored left border (crimson / green / cyan), an icon, the message, an `aria-live="polite"` announcement for screen readers, click-anywhere-to-dismiss, Escape support, and auto-dismiss after a type-dependent TTL (errors stay 6 s, success 3.2 s, info 4 s). Stack capped to 5 so a runaway loop can't paper the screen. The `AssetUpload` slots in the wizard now BOTH show their existing inline-red border (spatial context — which tile failed) AND emit a toast (room for a multi-line message like the new HD-floor 422), so the user sees both.
- **Inline 1–10 star rating on the result page.** `RatingCard` in `poster-result.jsx` renders 10 filled-star icons that color-shift between bright crimson (selected / hovered) and dim grey. Per-star Tab focus, ARIA `role="radiogroup"` / `role="radio"` / `aria-checked`, semantic labels ("Needs work" / "Decent" / "Strong" / "Excellent"), click-the-same-star-again clears, and a `Clear` link appears once a score is set. Persisted to `localStorage` keyed by `poster-rating:<job_id>` so testing across page refreshes works. The future-backend hook is a marked TODO inside `commit()` — one line to swap in `window.api.ratePoster(jobId, next)` when `POST /v1/posters/{id}/rating` ships.
- **Sponsor upload `accept` fix.** The Step-3 sponsor input in `wizard.jsx` was the lone outlier with `accept="image/*"` while the rest of the app enforces `image/png,image/jpeg,image/webp`. Tightened so the OS file dialog only offers supported formats.

---

## 🟢 Future enhancements

A grab bag of features that have come up during testing and design conversations but aren't built yet. They're listed roughly in the order they'd most likely be picked up.

| Idea | Sketch |
| --- | --- |
| ~~🟢 **Quick share to social media**~~ ✅ **Done** | Three buttons on the result page (Twitter / Facebook / Instagram) open a Quick Share modal: editable AI-generated caption + Copy button, Confirm triggers PNG download via the same-origin `/v1/posters/{id}/download` proxy, writes the caption to clipboard, and opens the platform compose page in a new tab. The public `/p/{job_id}` landing page (OG + Twitter Card meta tags) makes shared links render proper image previews on every major platform. Backend `social/postiz.py` + `/v1/social/*` is also wired for true one-click native posting through a self-hosted Postiz instance — currently shown as a `COMING SOON` preview while OAuth UX is polished. Future work along the same axis: LinkedIn / WhatsApp / Telegram / Discord buttons, Web Share API on mobile for native share-sheet integration. |
| 🟢 **Local database for tests** | Spin Mongo + Redis as ephemeral containers (`testcontainers-python`) in `conftest.py`, or mock them with `mongomock` + `fakeredis`. Replaces "tests need MongoDB/Redis on localhost" with a self-contained suite that still exercises store/queue code paths. |
| ~~🟢 **Usage & billing stats per org**~~ ✅ **Done** | Shipped: `GET /v1/admin/usage/orgs` returns one payload covering every org's tier, lifetime posters, 24h/7d/30d rolling counts, mode mix, success rate, distinct days active, lifetime + 30-day spend, tier-cap utilization %, plus cross-org totals and an MRR sum. The `#/admin/usage` screen renders all of it as 4 stat cards + tier chips + sortable table + top-5 bar chart, refreshing every 30 s. Three static subscription tiers (Free / Pro / Enterprise) defined in `billing/tiers.py` with `tier_for_org()` as the single seam for the real billing-provider integration. Future work along this axis: token-level cost attribution per stage (the OpenAI client already logs per-call token counts — those become a deeper "cost breakdown" view), historical time-series charts, and webhook hooks into the billing provider once it's wired. |
| ~~🟢 **Tokens, rate limiting per org**~~ ✅ **Done** | Rolling 24h / 7d / 30d quotas, defaulting to 3/15/30 posters per org, enforced on `POST /v1/posters` and refine. 429 with `Retry-After`, full `X-RateLimit-*` headers, `GET /v1/usage/quota` endpoint, live nav-bar + dashboard chips. Per-org overrides via the `orgs` Mongo collection. Future work: max-parallel-jobs, token-level limits, optional Redis token-bucket for sub-second precision. |
| 🟢 **Discord bot** | Slash command `/poster gameday team1 team2 ...` posts a follow-up "generating…" message and edits in the signed URL on completion. Backend wise it's a thin shim around `POST /v1/posters` + `GET /v1/posters/{id}`; the bot just reuses the public API with a per-server API key. |
| 🟢 **Runpod fine-tuned SD background generation** | Fill in `stages/background.py:_generate_with_runpod`. Pipeline already routes to it when `background.source == "generated"`; the wizard already exposes the option behind a `SOON` chip. Steps documented in the function's docstring: read settings, build SD prompt from `design` + `_meta`, POST to Runpod, poll, cache by content hash. |
| 🟢 **Deterministic PIL text-composite layer** | The README's standing Phase 1 item — render the scene + stylized hero title with `gpt-image-2`, leave clean zones for factual text, stamp the exact strings (score, names, date, tournament) with Pillow. Eliminates the model's text-rendering unreliability for the things customers care about most. |
| 🟢 **OCR-based content masking in Style DNA extraction** | Bounding-box-level masking of text regions on the approved poster before the GPT-4o semantic call, so team names / scores / dates can't leak into the extracted DNA. |
| 🟢 **Edit-data-and-regenerate** | A second-class refine that re-runs the full pipeline from an edited copy of the parent's input JSON, in consistency mode under the parent's Style DNA. The reliable path for factual edits (time, score, names) since refine mode uses `gpt-image-2` text rendering which is unreliable for those. |
| 🟢 **Multi-output drafts** | A "draft" mode that generates several candidates at `quality="low"` so the user can pick one before committing to a `quality="medium"` final pass. Cuts cost on rejected attempts. |

---

## License

Proprietary; all rights reserved. To be revisited before any open-source release.
