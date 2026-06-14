# EsportsPostAI — Integration Guide

Welcome. This guide shows you how to integrate **EsportsPostAI** into your platform and start generating esports posters for your organizations. If you have your **API key**, you can be live in about 10 minutes.

---

## 1. Concepts

The service has a three-level hierarchy:

```
Platform  (YOU — your app, authenticated by one API key)
   └── Org        (one of your customers / teams — you register these)
         └── Tournament   (a series of posters that can share one visual style)
```

- **Your API key authenticates your platform.** Keep it secret (server-side only — never ship it in a browser or mobile app).
- You address each of **your orgs** by passing an `org_id` on every request. Org ids are yours to choose and only need to be unique *within your platform*.
- Everything you create is **isolated to your platform** — no other customer can see your data, and you can't see theirs.

---

## 2. What you need

| Item | Example |
| --- | --- |
| **Base URL** | `https://api.YOURDOMAIN.com` |
| **API key** | `epai_xxxxxxxxxxxxxxxxxxxxxxxx` |

Every request sends your key in the `Authorization` header:

```
Authorization: Bearer epai_xxxxxxxxxxxxxxxxxxxxxxxx
```

All request/response bodies are JSON unless noted (asset upload is multipart).

---

## 3. Quick start (5 calls)

### Step 1 — Register an org (once per org)

```bash
curl -X POST https://api.YOURDOMAIN.com/v1/orgs \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"org_id": "team-alpha", "name": "Team Alpha"}'
```

### Step 2 — Upload that org's logos (returns a `storage_key`)

```bash
curl -X POST https://api.YOURDOMAIN.com/v1/assets \
  -H "Authorization: Bearer $KEY" \
  -F org_id=team-alpha \
  -F asset_type=team-logos \
  -F team=FNC \
  -F file=@fnatic_logo.png
# → { "asset_id": "...", "storage_key": "...orgs/team-alpha/assets/team-logos/....png", ... }
```

Save the returned `storage_key` — you'll reference it in the poster input as a logo path.

### Step 3 — Generate a poster

```bash
curl -X POST https://api.YOURDOMAIN.com/v1/posters \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "org_id": "team-alpha",
        "tournament_id": "spring-2026",
        "input": { ...poster input JSON, see section 5... }
      }'
# → 202 { "job_id": "abc123", "status": "queued" }
```

### Step 4 — Poll until it's done

```bash
curl https://api.YOURDOMAIN.com/v1/posters/abc123 \
  -H "Authorization: Bearer $KEY"
# → { "status": "completed", "signed_url": "https://...", "storage_key": "..." }
```

Poll every ~2–3 seconds. `status` moves through
`queued → generating_prompt → generating_poster → completed` (or `failed`).

### Step 5 — Use the image

- `signed_url` in the response is a ready-to-display image link (valid ~1 hour; re-fetch the job to get a fresh one).
- To force a file download instead, use the proxy:
  `GET /v1/posters/{job_id}/download` → returns the PNG as an attachment.

That's the whole loop. Everything below is detail and optional features.

---

## 4. Managing your orgs

| Method & path | What it does |
| --- | --- |
| `POST /v1/orgs` | Register an org. Body: `org_id?` (generated if omitted), `name?`, `limits?` (see §6). |
| `GET /v1/orgs` | List your registered orgs. |
| `GET /v1/orgs/{org_id}` | One org + its live rolling quota. |
| `PATCH /v1/orgs/{org_id}` | Update `name`, `limits`, `metadata`. |
| `DELETE /v1/orgs/{org_id}` | De-register an org (does **not** delete its already-generated posters). |
| `GET /v1/me` | Your platform identity + how many orgs you've registered. |

You must register an org **before** generating posters or uploading assets for it.

---

## 5. The poster input

`POST /v1/posters` takes `{ org_id, tournament_id, input }`. The `input` object describes the poster. It always starts with a `_meta` block and then carries blocks relevant to the poster type.

### `_meta` (always required)

| Field | Allowed values |
| --- | --- |
| `game` | `league_of_legends`, `valorant` |
| `poster_type` | `gameday`, `game_results`, `roster_reveal`, `tournament_announcement`, `tournament_banner` |
| `mode` | `fresh` (standalone) or `consistency` (match a saved style — see §7) |
| `output_format` | `portrait_1080x1920`, `square_1080x1080`, `landscape_1920x1080` |

### Connecting your uploaded logos

Wherever a block has a `logo_path` or `image_path`, put the **`storage_key`** you got back from `POST /v1/assets`. The worker resolves it to the actual image. (Fields can be `null` to omit them.)

### Example — Gameday (match announcement)

```json
{
  "_meta": { "game": "league_of_legends", "poster_type": "gameday",
             "mode": "fresh", "output_format": "portrait_1080x1920" },
  "tournament": { "name": "EWC 2026", "logo_path": null, "phase": null },
  "match": {
    "team1": { "name": "FNATIC", "short_name": "FNC",
               "logo_path": "<team1 storage_key>" },
    "team2": { "name": "T1", "short_name": "T1",
               "logo_path": "<team2 storage_key>" },
    "format": "bo5", "date": "2026-07-04", "time": "17:00", "timezone": "CET"
  },
  "stream": { "platform": "Twitch", "url": "twitch.tv/yourchannel" },
  "player_feature": { "enabled": false, "image_path": null },
  "sponsors": { "enabled": false, "logos": [] },
  "design": { "vibe": "cyberpunk", "primary_color": "#7B2FFF", "energy": "intense" }
}
```

### Example — Game results

```json
{
  "_meta": { "game": "league_of_legends", "poster_type": "game_results",
             "mode": "fresh", "output_format": "square_1080x1080" },
  "tournament": { "name": "EWC 2026", "phase": "playoffs" },
  "match": {
    "team1": { "name": "GNG", "short_name": "GNG", "logo_path": "<key>", "score": 2 },
    "team2": { "name": "JSK", "short_name": "JSK", "logo_path": "<key>", "score": 3 },
    "format": "bo5"
  },
  "player_feature": { "enabled": true, "image_path": "<player storage_key>" },
  "mvp": { "enabled": false },
  "sponsors": { "enabled": false, "logos": [] },
  "design": { "vibe": "cyberpunk", "primary_color": "#1e6c7b", "energy": "intense" }
}
```

> The winner and each team's W/L are **derived** from the per-team `score` — you never send a separate "winner" field. Scores are validated against `format` (bo1 = 1, bo3 = up to 2, bo5 = up to 3).

### The `design` block (drives the look)

| Field | Notes |
| --- | --- |
| `vibe` | One of: `cyberpunk`, `cinematic`, `dark_fantasy`, `cosmic`, `minimal`, `fire_energy` |
| `primary_color` | Hex string, e.g. `#7B2FFF` |
| `energy` | e.g. `chill`, `balanced`, `intense`, `explosive` |

### Asset types for `POST /v1/assets`

`team-logos`, `player-images`, `sponsor-logos`, `tournament-logos`, `backgrounds`.
(Background uploads are quality-gated: below 720px short edge is rejected; above 2048px long edge is downscaled.)

---

## 6. Rate limits (you control them, per org)

Each org has its own rolling quota — **completed posters** counted over the last **24h / 7d / 30d**. Defaults are conservative; **set whatever you want per org**:

```bash
# Raise team-alpha to 10/day, 50/week, 100/month
curl -X PATCH https://api.YOURDOMAIN.com/v1/orgs/team-alpha \
  -H "Authorization: Bearer $KEY" \
  -d '{"limits": {"day": 10, "week": 50, "month": 100}}'
```

You can also set `limits` at registration time. Omit a window to keep its default.

Every poster response carries the current state in headers:

```
X-RateLimit-Limit-Day: 10
X-RateLimit-Remaining-Day: 7
X-RateLimit-Reset-Day: 1751650000        # unix epoch
```

When an org is over its limit, `POST /v1/posters` returns **`429 Too Many Requests`** with a `Retry-After: <seconds>` header and a JSON body telling you which window is full. Inspect any org's live quota any time with `GET /v1/orgs/{org_id}` or `GET /v1/usage/quota?org_id=...`.

---

## 7. Optional — consistent styling across a series (Style DNA)

Keep every poster in a tournament visually coherent:

1. Generate and approve a first poster you like.
2. Extract its style:
   `POST /v1/style-dnas/{tournament_id}` with `{ "source_job_id": "<that job>" }` → saves a **draft**.
3. Approve it: `POST /v1/style-dnas/{tournament_id}/approve`.
4. Generate the rest with `_meta.mode = "consistency"` and the same `tournament_id` — the saved style is applied automatically.

`GET /v1/style-dnas?org_id=...` lists all styles you've saved; `GET /v1/style-dnas/{tournament_id}` returns one.

---

## 8. Optional — other endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/posters?org_id=&tournament_id=&limit=` | List an org's posters (history), newest first. |
| `POST /v1/posters/{job_id}/refine` | Apply a freeform visual edit (`{"prompt": "make it darker"}`) → new job. Best for visual tweaks; for factual changes (score, time) regenerate instead. |
| `POST /v1/posters/{job_id}/caption` | Get an AI social caption for the poster (if enabled on the server). |
| `GET /v1/usage?org_id=` | Poster counts + estimated cost over a period. |

---

## 9. Recommended integration pattern

```javascript
// Pseudocode for your backend.
const API = "https://api.YOURDOMAIN.com";
const HEADERS = { Authorization: `Bearer ${KEY}`, "Content-Type": "application/json" };

async function generatePoster(orgId, tournamentId, input) {
  // 1. enqueue
  const res = await fetch(`${API}/v1/posters`, {
    method: "POST", headers: HEADERS,
    body: JSON.stringify({ org_id: orgId, tournament_id: tournamentId, input }),
  });
  if (res.status === 429) throw new Error(`Rate limited: retry after ${res.headers.get("Retry-After")}s`);
  const { job_id } = await res.json();

  // 2. poll
  while (true) {
    await sleep(2500);
    const job = await (await fetch(`${API}/v1/posters/${job_id}`, { headers: HEADERS })).json();
    if (job.status === "completed") return job.signed_url;
    if (job.status === "failed")    throw new Error(job.error);
  }
}
```

> Polling is the simplest approach and always works. For a push-based flow (your backend gets notified instead of polling), use **webhooks** — see §9.5. A generation takes roughly 20–60 seconds.

---

## 9.5 Webhooks (push instead of poll)

Instead of polling, we can **POST a signed event to your URL** the moment a poster finishes. (Webhooks must be enabled for your account — ask us if you'd like them on.)

### Register your endpoint

```bash
curl -X PUT https://api.YOURDOMAIN.com/v1/webhook \
  -H "Authorization: Bearer $KEY" \
  -d '{"url": "https://your-app.com/hooks/epai",
       "events": ["poster.completed", "poster.failed"]}'
# → returns a "secret" (whsec_...) ONCE — store it securely.
```

| Endpoint | Purpose |
| --- | --- |
| `PUT /v1/webhook` | Set/replace your callback URL + events. Returns the secret on first creation. |
| `GET /v1/webhook` | Your current config (no secret). |
| `POST /v1/webhook/rotate-secret` | Get a new signing secret. |
| `POST /v1/webhook/test` | Send a synthetic `ping` to your URL right now. |
| `GET /v1/webhook/deliveries` | Recent delivery attempts (status, response code) for debugging. |
| `POST /v1/webhook/deliveries/{id}/replay` | Re-send a past delivery. |
| `DELETE /v1/webhook` | Turn webhooks off. |

URLs must be **HTTPS** and public (we reject internal/loopback addresses).

### What you receive

```jsonc
POST https://your-app.com/hooks/epai
Headers:
  X-EPAI-Event: poster.completed
  X-EPAI-Delivery: evt_abc123
  X-EPAI-Signature: t=1751650000,v1=<hmac-sha256 hex>
Body:
{
  "id": "evt_abc123",                 // unique — dedupe on this (we may retry)
  "event": "poster.completed",
  "created_at": "2026-07-04T12:00:00Z",
  "data": {
    "job_id": "...", "org_id": "team-alpha", "tournament_id": "spring-2026",
    "status": "completed", "storage_key": "...", "signed_url": "https://...",
    "caption": "..."
  }
}
```

### Verify every request (important)

Compute `HMAC-SHA256(secret, "<t>.<raw_request_body>")` and compare to the `v1`
value in `X-EPAI-Signature`. Reject if it doesn't match or if `t` is older than
~5 minutes. Example (Node):

```javascript
const crypto = require("crypto");
function verify(rawBody, header, secret) {
  const { t, v1 } = Object.fromEntries(header.split(",").map(p => p.split("=")));
  if (Math.abs(Date.now()/1000 - Number(t)) > 300) return false;        // replay guard
  const expected = crypto.createHmac("sha256", secret)
                         .update(`${t}.${rawBody}`).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(v1));
}
```

Respond with any **2xx** to acknowledge. Non-2xx or a timeout triggers automatic
retries with exponential backoff (a few attempts over ~minutes), after which the
delivery is marked failed — visible in `GET /v1/webhook/deliveries` and re-sendable.

> Signed image URLs in `signed_url` expire (~1h). For anything you store long-term, keep the `storage_key` and fetch a fresh link via `GET /v1/posters/{job_id}` or `/download`.

---

## 10. Status & error reference

| Code | Meaning |
| --- | --- |
| `202` | Poster accepted and queued. |
| `200` | Read succeeded. |
| `400` | Bad request (e.g. job isn't a completed poster for refine/caption). |
| `401` | Missing or invalid API key. |
| `404` | Not found, **or** the `org_id` isn't registered under your platform, **or** the resource belongs to another platform. |
| `409` | Org id already exists (on register). |
| `422` | Validation error — `org_id` missing, or the `input` JSON is malformed. |
| `429` | Rate limit reached for that org (see `Retry-After`). |
| `503` | An optional feature (e.g. captions) isn't enabled on the server. |

---

## 11. Good to know

- **Keep the key server-side.** It authenticates your whole platform.
- **Signed image URLs expire (~1h).** Re-fetch the job (or use `/download`) to get a fresh link; don't store the signed URL long-term — store the `job_id` (or `storage_key`).
- **Backgrounds:** by default the system picks a background from a shared pool. To supply your own, upload it as `asset_type=backgrounds` and reference its `storage_key` in `input.background.image_path`. List the shared pool with `GET /v1/backgrounds`.
- **Org ids are yours and private to your platform** — two different customers of the service can both use `team-alpha` with no conflict.

Questions or a higher quota for a specific org? Contact us — quotas are adjustable per org at any time.
