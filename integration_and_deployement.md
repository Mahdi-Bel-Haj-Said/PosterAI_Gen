# Integration & Deployment

How EsportsPostAI runs in production, and how a platform integrates with it.

Defendr is the first platform and the worked example throughout. Everything
described here is deliberately Defendr-*shaped* rather than Defendr-*specific*:
the service knows nothing about Defendr, and a second platform integrates the
same way with a different key.

---

## 1. Deployment

### Topology

The service is deployed on a VPS. Four processes, one bucket:

```
                          VPS
   ┌────────────────────────────────────────────────┐
   │                                                │
   │   FastAPI (uvicorn) ──enqueue──►  Redis        │
   │        │                            │          │
   │        │                       RQ worker       │
   │        ▼                            │          │
   │     MongoDB  ◄──────────────────────┘          │
   │                                                │
   └────────────────────────────────────────────────┘
                          │
                          ▼
                Cloudflare R2 (objects)
```

| Component | Role |
| --- | --- |
| **FastAPI (uvicorn)** | HTTP surface. Validates, enqueues, answers status. Never generates. |
| **RQ worker** | Runs the pipeline. Drains `poster-ai` (generation) and `epai-webhooks` (outbound delivery). |
| **Redis** | The queue, plus locks for background-bank refill. |
| **MongoDB** | Jobs, assets, orgs, platforms, API keys, usage events. |
| **Cloudflare R2** | Every generated poster and uploaded asset. |

Generation takes 20–60 seconds, which is why the API and the worker are separate
processes. The API stays responsive while the worker does the slow work.

### Running the two processes

Both need the same `.env`.

```bash
# 1 — the API
python -m esports_poster_ai.api

# 2 — the worker (add --worker-class rq.SimpleWorker on Windows: RQ's
#     default worker calls os.fork(), which Windows does not have)
rq worker poster-ai epai-webhooks --url redis://localhost:6379/0
```

> **A stopped worker is a silent failure.** Submissions still return `202` and
> then never progress — no error reaches the client, because nothing errored.
> Treat "is the worker alive?" as a health check, not an assumption.
>
> RQ also **exits deliberately** on a Redis connection timeout rather than
> reconnecting. Run it under a supervisor with a restart policy (systemd
> `Restart=always`, or a Docker restart policy). Without one, a brief Redis
> blip stops all generation until someone notices.

### Deploying a change

Both processes import the pipeline at start-up, so a deploy must restart
**both**. Restarting only the API leaves the worker running the previous
revision — and the worker is the half that generates.

### Configuration

Beyond the provider credentials (`OPENAI_API_KEY`, `GEMINI_API_KEY`, the `R2_*`
block, `MONGODB_URL`, `REDIS_URL`), these decide production behaviour:

| Variable | Production value | Why |
| --- | --- | --- |
| `API_KEY_REQUIRED` | **`true`** | Defaults to `false` so localhost dev runs unauthenticated. Left false, the API is open. |
| `API_PORT` | pin explicitly | Defaults to `8000`. Coming up on an unexpected port looks like a network outage to every client. |
| `WEBHOOKS_ENABLED` | `true` | Off by default; required for completion callbacks. |
| `WEBHOOK_ALLOW_INSECURE_URLS` | `false` | Only ever `true` for local testing against `http://`. |
| `PUBLIC_BASE_URL` | the real host | Used to build shareable links. |
| `CORS_ALLOW_ORIGINS` | the integrator's origins | Not needed when the integrator proxies server-side, which is the recommended pattern. |
| `QUOTA_DAY_DEFAULT` / `_WEEK_` / `_MONTH_` | `3` / `15` / `30` | Per-org rolling caps. Raise **per org** via `/v1/orgs`, not globally. |
| `ADMIN_TOKEN` | strong secret | Gates the provider-side admin endpoints. |

### Storage layout

Object keys carry their owner, so isolation is structural rather than a filter
somebody might forget:

```
{prefix}/platforms/{platform_id}/orgs/{org_id}/assets/{asset_type}/{uuid}.png
{prefix}/platforms/{platform_id}/orgs/{org_id}/tournaments/{tid}/posters/…png
{prefix}/platforms/{platform_id}/orgs/{org_id}/tournaments/{tid}/style-dna.json
{prefix}/system/backgrounds/…                      ← shared, outside all tenants
```

`platform_id`, `org_id`, `tournament_id` and `asset_id` are validated as single
path segments (`/`, `\`, `..` rejected), so no id can escape its namespace.
Nothing is provisioned per client — object storage has no real directories, so a
new platform's subtree exists the moment it writes its first object.

### Onboarding a platform

```bash
python scripts/bootstrap_defendr_platform.py --name "Acme Esports"
```

Prints the plaintext key **once**, before anything else can fail. Store it in
the integrator's server-side environment; it is not recoverable afterwards.

---

## 2. Integration

### The rule that shapes everything

**An API key authenticates a *platform*, not an org.** One key covers all of a
platform's orgs, and the platform passes `org_id` per request.

Two consequences an integrator must plan for:

1. **The key never reaches a browser.** It authenticates the whole platform;
   leaking it exposes every org's posters and assets.
2. **Org-to-org isolation is the integrator's job.** Because the key is
   platform-scoped, this service's by-id routes (`GET /v1/assets/{id}`) verify
   *platform* ownership only. Confining one org from another happens in the
   integrator's layer — which is exactly what Defendr's BFF does.

### Two front doors

| | `POST /v1/posters` | `POST /v1/posters/express` |
| --- | --- | --- |
| Org must be registered | yes | no |
| Per-org quota enforced | yes | no |
| Coin balance checked | yes (`402` possible) | no |
| Plan features enforced | yes | no |
| Metering & idempotency | yes | **yes** |
| Runs through the worker queue | yes | **yes** |

**Express** is one call in, a poster out. The integrator decides who may
generate, what it costs, and where the file ends up. Metering is kept — that is
how the provider invoices — but it is a counter, never a gate.

```http
POST /v1/posters/express?wait=90
Authorization: Bearer <key>
X-Idempotency-Key: <caller's request id>

{ "input": { … }, "group_id": "lcs-summer" }
```

`group_id` is free text that namespaces Style DNA and history. It is never
checked for access and needs no registration. Returns `200` with `image_url`
when it finished inside `wait`, otherwise `202` with a `poll_url`.

**Managed** (`POST /v1/posters`) is the full product: sub-accounts, rolling
quotas, a credit economy, brand library, visual consistency. Defendr uses this.

### Assets: no re-upload required

Every logo/image field accepts a **public https URL** as well as an uploaded
storage key, so a platform's existing CDN assets work as-is. Fetches are
SSRF-guarded: private ranges rejected, every redirect hop re-validated, size
capped, content-type checked.

### Taking delivery of the poster

The completion webhook carries a signed URL:

```json
{ "event": "poster.completed",
  "data": { "job_id": "…", "signed_url": "https://…" } }
```

Presigned, **1-hour expiry**, `private` cache-control. `GET /v1/posters/{id}/download`
streams the raw bytes for the same purpose. A platform that wants to own the
file stores it on receipt.

Signature scheme — verify **before parsing**, against the raw body:

```
X-EPAI-Signature: t=<unix>,v1=<hex>
v1 = HMAC-SHA256(secret, "<t>." + raw_body)
```

Reject anything outside a 300-second window.

---

## 3. The Defendr integration, concretely

### Shape

```
browser ──► Defendr backend ──► EsportsPostAI ──► worker ──► R2
            /PosterStudio/*      (key lives here)
                  │                     │
                  └──── webhook ◄───────┘
```

The browser never reaches this API. Defendr exposes **21 routes** under
`/PosterStudio/*`, and `poster-ai.gateway.js` is the only module holding the
key or seeing this service's payload shapes.

| Group | Routes |
| --- | --- |
| Read | `orgs/:orgId/entitlement`, `/posters`, `/assets`, `/tournaments`, `/quota`, `/style-dnas`, `/style-dna/:tid`, `/taglines/random`, `/autofill/tournament/:tid` |
| Poster | `posters/:jobId`, `/download`, `orgs/:orgId/estimate`, `orgs/:orgId/posters`, `posters/:jobId/{caption,rating,refine}` |
| Assets | `POST orgs/:orgId/assets`, `DELETE orgs/:orgId/assets/:assetId` |
| Style DNA | `POST orgs/:orgId/style-dna/:tid`, `…/approve` |
| Inbound | `POST webhook` |

### Defendr-side configuration

```bash
POSTER_STUDIO_ENABLED=true        # one switch disables the whole feature
POSTER_AI_BASE_URL=https://…      # this service
POSTER_AI_API_KEY=…               # server-side only, never NEXT_PUBLIC_*
POSTER_AI_WEBHOOK_SECRET=…        # must match the platform's webhook secret

POSTER_RED_PRICE_LOW=5            # Defendr's own prices, not this service's
POSTER_RED_PRICE_MEDIUM=15
POSTER_RED_PRICE_HIGH=40

POSTER_AI_TIMEOUT_MS=15000        # control-plane calls
POSTER_AI_DOWNLOAD_TIMEOUT_MS=60000
POSTER_AI_MODEL_TIMEOUT_MS=120000 # style-DNA extraction + caption run a model
```

The frontend needs `NEXT_PUBLIC_POSTER_STUDIO_ENABLED=true`. That is the only
poster variable that may be public — it is a boolean, not a credential.

> **Timeouts are not one number.** Style-DNA extraction runs a vision pass and
> only answers when it is done. On the 15s control-plane budget it returned 504
> while the work carried on and *succeeded* — the user saw "timed out" for an
> operation that had worked. Model-backed calls get their own budget, and on
> timeout report "still running, refresh in a moment" rather than failure.

### Billing bridge

Defendr charges its own RED wallet. The service's internal coin economy is
untouched — the two currencies merely share a name.

Ordering:

```
authorize → price → create mirror row → debit → submit → refund on failure
```

The debit is a **conditional atomic update**: match `redCoins >= amount` and
`$inc` in one operation. The platform's own `updateRedCoinsBalance` is
read-check-write, so two concurrent generations could overspend a balance. A
losing request matches nothing and is told it has insufficient funds. Refunds
carry a `refundedAt: null` predicate so they happen at most once.

### Contract checking

Two boundaries cross a type gap, and neither is checked by a compiler:

| Boundary | Checker |
| --- | --- |
| Ported UI → BFF adapter | `defendr-front-new/scripts/check-spa-api-contract.mjs` |
| BFF gateway → this service | `DEFENDR-BACKEND/features/content-management/poster-studio/tools/check-gateway-contract.mjs` |

Both exist because of silent failures, not theory:

- Three adapter methods were **dead** — called positionally while the adapter
  destructured an object, so every argument arrived `undefined`. Rating,
  caption generation and Style DNA extraction did nothing at all, with no error.
- Four gateway payload fields were **wrong** (`user_prompt` vs `prompt`,
  `job_id` vs `source_job_id`, two routes reading `org_id` from the body). A
  field the service does not recognise is ignored, not rejected — so the only
  symptom is `Field required` naming the key you *should* have sent.

Run both in CI. They take seconds and catch a class of bug that testing tends
to miss until a user reports it.

---

## 4. Operational notes

**Rate limits.** Rolling day/week/month windows per org, failed jobs excluded.
Raise per org via `/v1/orgs` rather than moving the global default. Express
deliberately skips per-org quota — a per-platform ceiling is worth adding before
the number of integrators grows.

**Idempotency.** Send `X-Idempotency-Key` on every submit. A poster costs real
money, and a retried call must not produce a second one. Without a key the
service falls back to hashing the input, which still collapses a double-click.

**Cross-tenant isolation** is verified, not assumed. Using one platform's key
against another's data: listing returns 0, and reading or deleting by id
returns **404** with the object intact — 404 rather than 403 throughout, so a
caller never learns that something exists.

**BYOK is modelled, not implemented.** `service_type: "byok"` exists on the
platform record and `/v1/me` reports which credentials are set, but
`get_storage()` never receives a platform and nothing reads those credentials.
Every client's objects land in the provider's bucket regardless of the flag.
Do not sell against it until it is wired.
