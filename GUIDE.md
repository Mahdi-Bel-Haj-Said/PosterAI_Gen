# EsportsPostAI — Client Integration Guide

This is the guide for **clients** (platforms) integrating the EsportsPostAI API
into **their own product / UI**. You get an API key, configure your setup once,
then call the REST endpoints from your own frontend or backend. There is no UI to
adopt — the API is the product. (The bundled React app is only a reference/demo
console.)

---

## 1. Concepts

```
Platform  (YOU — your app, authenticated by one API key)
   └── Org        (one of your customers / teams — you register these)
         └── Tournament   (a series of posters that can share one visual style)
```

- **Platform (you, the client)** — authenticated by one **API key**. You own the
  integration and the commercial relationship with the provider. Keep the key
  server-side; never ship it in a browser/mobile app.
- **Org** — a sub-account *under your platform*. Org ids are unique within your
  platform. Almost every call takes an `org_id`.
- **Red Coins** — the token currency your orgs spend per poster. You set the name,
  exchange rate, markup, and monthly grants (see *Configuration*).
- **Job** — one poster generation. You submit it, then poll (or get a webhook).
- Everything you create is **isolated to your platform** — no other client can see
  your data, and you can't see theirs.

Base URL: `https://<your-host>` (dev: `http://localhost:8000`).

---

## 2. Authentication

Send your key as a Bearer token on every request:

```
Authorization: Bearer <your-api-key>
```

The key resolves to your platform; all data is namespaced and isolated to you.
`org_id` is passed per request and must be an org you registered.

> In production set `API_KEY_REQUIRED=true`. In local dev it can be off (a single
> implicit platform, no key required).

Health check (no auth): `GET /health` → `{"status":"ok","mongodb":"ok","redis":"ok"}`.

---

## 3. Quickstart — one call, one poster (recommended)

`POST /v1/posters/express` is the simple integration surface. One call in, a
poster out. **No org registration, no coin balance, no quota tier, no tenancy
model to adopt** — you decide who may generate and what (if anything) it costs
your users, in your own code:

```js
// your rules, your currency, your users
if (user.wallet.balance >= YOUR_PRICE && mayGenerate(user, org)) {
  const poster = await fetch('https://<host>/v1/posters/express?wait=90', {
    method: 'POST',
    headers: { Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ input }),
  }).then(r => r.json())

  await debit(user, YOUR_PRICE)      // only you know what a poster is worth
  return poster.image_url
}
```

```bash
curl -X POST "https://<host>/v1/posters/express?wait=90"   -H "Authorization: Bearer $KEY" -H "Content-Type: application/json"   -d '{"input": '"$(cat gameday.json)"'}'
# -> 200 {"job_id":"...","status":"completed","image_url":"https://...",
#         "cost":{"usd":0.054,"quality":"medium"}}
```

### Waiting, and what happens when your proxy will not

A poster takes **20–90 seconds**. `wait` (0–100s, default 90) is how long we
hold the connection:

| Outcome | Response |
| --- | --- |
| Finished within `wait` | **200** with `image_url` |
| Still generating | **202** with `job_id` + `poll_url` — poll `GET /v1/posters/{job_id}` |
| `wait=0` | **202** immediately — you poll from the start |

Either way the generation continues; a 202 never wastes the work. If your stack
cuts long requests (Heroku at 30s, many nginx setups at 60s), set `wait` below
that limit and take the polling path.

### Logos: pass a URL, no upload step

Logo fields accept a public `https://` URL as well as an uploaded storage key,
so assets already on your CDN need no pre-upload:

```json
{ "match": { "team1": { "name": "Fnatic",
                        "logo_path": "https://your-cdn.com/logos/fnatic.png" } } }
```

URLs are fetched server-side with an SSRF guard (no private/loopback/metadata
addresses, redirects re-validated per hop), a 15 MB cap and a 10s timeout. A
logo that cannot be fetched is skipped — you still get a poster.

### Repeat-safe

Send `X-Idempotency-Key` and a retried request returns the original poster
instead of generating — and billing you for — a second one. Replays answer with
`X-Idempotent-Replay: true`.

### Grouping (optional)

Pass `group_id` to make several posters share a visual identity (Style DNA):
a tournament, a season, a team. It is only a namespace — never an access check,
and it needs no registration. Omit it for a standalone poster.

---

## 3b. The managed flow — orgs, coins and quotas

Use this only if you want the built-in tenancy and billing rather than your own.
It adds an org registry, a Red Coins wallet per org, monthly grants and quota
tiers — and `POST /v1/posters` will answer **402** when an org's balance is short.


```bash
# 1) (optional) price it first
curl -X POST https://<host>/v1/posters/estimate \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"org_id":"1","input": '"$(cat gameday.json)"'}'
# -> {"tokens":1080,"balance":30000,"sufficient":true,"coin_symbol":"RC",...}

# 2) submit
curl -X POST https://<host>/v1/posters \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"org_id":"1","tournament_id":"ewc_2025","input": '"$(cat gameday.json)"'}'
# -> {"job_id":"abc123","status":"queued"}

# 3) poll until completed
curl https://<host>/v1/posters/abc123 -H "Authorization: Bearer $KEY"
# -> {"status":"completed","signed_url":"https://...","storage_key":"..."}

# 4) download the PNG
curl -L https://<host>/v1/posters/abc123/download -H "Authorization: Bearer $KEY" -o poster.png
```

Statuses: `queued → generating_prompt → generating_poster → applying_sponsor_bar → completed` (or `failed`).

### The input document (`input`)

```json
{
  "_meta": {
    "game": "league_of_legends",
    "poster_type": "gameday",
    "mode": "fresh",
    "output_format": "portrait_1080x1920",
    "quality": "medium"
  },
  "tournament": { "name": "EWC 2025" },
  "match": {
    "team1": { "name": "FNATIC", "logo_path": "<asset storage_key>" },
    "team2": { "name": "T1", "logo_path": "<asset storage_key>" },
    "time": "17:00", "timezone": "CET"
  },
  "design": { "vibe": "cyberpunk", "primary_color": "#7B2FFF", "energy": "intense" }
}
```

- `_meta.game`: `league_of_legends` | `valorant`
- `_meta.poster_type`: `gameday` | `game_results` | `roster_reveal` | `tournament_announcement` | `tournament_banner`
- `_meta.mode`: `fresh` | `consistency` | `refine`
- `_meta.output_format`: `portrait_1080x1920` | `square_1080x1080` | `landscape_1920x1080`
- `_meta.quality`: `low` | `medium` | `high` (must be within your `allowed_qualities`)
- `logo_path` / `image_path` are **asset storage keys** returned by the assets API (see §6).

---

## 4. Configure your product (self-serve)

Read/update **your own** configuration. Send only the fields you want to change;
you get the full updated config back.

```bash
curl https://<host>/v1/me/config -H "Authorization: Bearer $KEY"

curl -X PATCH https://<host>/v1/me/config \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{
    "branding":  { "product_name": "Acme Posters", "coin_name": "Gems", "coin_symbol": "GEM",
                   "accent_color": "#E83A57", "ai_accent_color": "#3AC0E8" },
    "economics": { "tokens_per_usd": 10000, "poster_markup": 2.0,
                   "free_grant": 1500, "pro_grant": 30000, "kratos_grant": 100000 },
    "features":  { "consistency": true, "refine": true, "sponsor_bar": true,
                   "caption": true, "social": true, "allowed_qualities": ["low","medium","high"] },
    "tiers":     { "pro": { "label": "Starter", "price_usd": 5 } },
    "quotas":    { "day": 25, "week": 100, "month": 300 }
  }'
```

| Block | Controls |
|---|---|
| `branding` | Coin name/symbol, product name, logo, accent colors shown to your orgs |
| `economics` | `tokens_per_usd` (rate), `poster_markup` (margin), `base_cost_per_poster_usd`, `topup_usd_per_10k`, per-tier monthly grants |
| `features` | Enable/disable consistency, refine, sponsor_bar, caption, social, background_upload; `allowed_qualities` |
| `tiers` | Per-tier display label + the price you charge orgs |
| `quotas` | Default rolling per-org caps (day/week/month) |

> **Read-only** (set by the provider, returned for reference): `service_type`
> (`hosted`/`byok`) and `monthly_fee_usd`. BYOK secrets are never returned.

---

## 5. Red Coins (your orgs' wallets)

```bash
curl "https://<host>/v1/coins?org_id=1" -H "Authorization: Bearer $KEY"
# -> {"balance":30000,"tier":"pro","est_per_poster":{"low":270,"medium":1080,"high":4320},
#     "tokens_per_usd":10000,"poster_markup":2.0,"topup_usd_per_10k":0.80}

# set an org's plan (credits that tier's monthly grant)
curl -X POST https://<host>/v1/coins/subscribe -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -d '{"org_id":"1","tier":"pro"}'

# top up; pass tokens OR usd
curl -X POST https://<host>/v1/coins/purchase -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -d '{"org_id":"1","tokens":10000}'
```

Coins are **charged on success only** — a failed poster costs nothing. A submit is
rejected with `402` if the org's balance can't cover the estimate.

---

## 6. Brand assets

Upload logos / player photos / sponsor logos / backgrounds, then reference the
returned `storage_key` in your input.

```bash
curl -X POST https://<host>/v1/assets -H "Authorization: Bearer $KEY" \
  -F org_id=1 -F asset_type=team-logos -F team=FNATIC -F file=@fnatic.png
# -> { "asset_id":"...", "storage_key":"...", "signed_url":"..." }

curl "https://<host>/v1/assets?org_id=1&asset_type=team-logos" -H "Authorization: Bearer $KEY"
curl -X DELETE https://<host>/v1/assets/<asset_id> -H "Authorization: Bearer $KEY"
```

`asset_type`: `team-logos` | `tournament-logos` | `player-images` | `sponsor-logos` | `backgrounds`.
Background removal + resizing happen automatically on upload. System background
pool: `GET /v1/backgrounds`.

---

## 7. Consistency (Style DNA)

Generate one poster, extract its Style DNA, approve it, then generate the rest in
`consistency` mode with the same `tournament_id`.

```bash
curl -X POST https://<host>/v1/style-dnas/ewc_2025 -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -d '{"org_id":"1","source_job_id":"abc123"}'   # extract draft
curl -X POST https://<host>/v1/style-dnas/ewc_2025/approve -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -d '{"org_id":"1"}'                              # approve
curl "https://<host>/v1/style-dnas?org_id=1" -H "Authorization: Bearer $KEY"          # list
```

---

## 8. Extras

- **Refine**: `POST /v1/posters/{id}/refine` `{ "prompt": "make it darker" }` → a new job.
- **Caption**: `POST /v1/posters/{id}/caption` → AI social caption (503 if Gemini off, 403 if disabled).
- **Orgs**: `POST/GET /v1/orgs`, `GET/PATCH/DELETE /v1/orgs/{id}`.
- **Usage**: `GET /v1/usage?org_id=1`, `GET /v1/usage/quota?org_id=1`.

---

## 9. Webhooks (recommended — skip polling)

```bash
curl -X PUT https://<host>/v1/webhook -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-app.com/hooks/epai","events":["poster.completed","poster.failed"]}'
```

Deliveries are HMAC-SHA256 signed (verify the signature header), retried with
backoff, and dead-lettered. `POST /v1/webhook/test` fires a test event.
(Requires `WEBHOOKS_ENABLED` on the server.)

---

## 10. Errors

| Status | Meaning | What to do |
|---|---|---|
| `402` | Not enough Red Coins | Show balance + top-up; body has `needed` / `balance` |
| `429` | Rolling quota hit | Body has the window + `reset_at`; retry later |
| `422` | Invalid input / quality not allowed on plan | Fix the field named in `detail` |
| `403` | Feature disabled on this plan | The capability is off in your config |
| `404` | Org not registered / not found | Register via `POST /v1/orgs` |
| job `failed` + message | e.g. background rejected (copyright) | Surface `error`; let the user change the background |

A poster job never throws — failures land as `status:"failed"` with a
human-readable `error`.

---

## 11. Endpoint reference

| Method & path | Purpose |
|---|---|
| `GET /v1/me` · `GET/PATCH /v1/me/config` | Identity · self-serve config |
| `POST /v1/posters` | Generate (→ job) |
| `POST /v1/posters/estimate` | Price a poster (no generation) |
| `GET /v1/posters/{id}` · `GET /v1/posters?org_id=` | Poll/result · list |
| `POST /v1/posters/{id}/refine` · `/download` · `/caption` | Refine · download · caption |
| `POST/GET /v1/assets` · `GET/DELETE /v1/assets/{id}` · `GET /v1/backgrounds` | Brand assets · backgrounds |
| `GET /v1/style-dnas` · `GET/POST/PUT/DELETE /v1/style-dnas/{tid}` · `/approve` | Style DNA lifecycle |
| `GET /v1/coins` · `POST /v1/coins/purchase` · `POST /v1/coins/subscribe` | Wallet |
| `GET /v1/usage` · `GET /v1/usage/quota` | Usage / quota |
| `POST/GET /v1/orgs` · `GET/PATCH/DELETE /v1/orgs/{id}` | Org management |
| `PUT /v1/webhook` (+ `/test`, `/replay`) | Completion callbacks |
| `GET/POST /v1/social/*` | Native social posting |
| `GET /p/{job_id}` | Public share page (no auth) |

> Provider-only (not issued to clients): `/v1/admin/*`, `/v1/api-keys`.
