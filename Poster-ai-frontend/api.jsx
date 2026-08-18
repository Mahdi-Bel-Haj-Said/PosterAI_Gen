// api.jsx — thin fetch wrapper around the FastAPI backend.
// Base URL is overridable via window.API_BASE (set in EsportsPostAI.html).

const API_BASE = (window.API_BASE || "http://localhost:8000").replace(/\/+$/, "");
const DEFAULT_ORG_ID = "1";

// ---- Red Coins (token economy). Users see tokens, never dollars. -----------
// tokens = platform_cost_usd * POSTER_MARKUP * TOKENS_PER_USD. Mirrors
// billing/coins.py on the backend; keep the two in sync.
const TOKENS_PER_USD = 10000;
const POSTER_MARKUP = 2;
// The ACTIVE rate is per-client; getCoins() refreshes it from the backend so the
// whole UI prices in the client's own economics. Defaults match the standard.
let _coinRate = { tokens_per_usd: TOKENS_PER_USD, poster_markup: POSTER_MARKUP };
// Red Coins charged for a poster that costs the platform `usd`.
function tokensForUsd(usd) {
  return Math.max(1, Math.round((usd || 0) * _coinRate.poster_markup * _coinRate.tokens_per_usd));
}
// Format a token amount for display, e.g. 1080 -> "1,080".
function fmtCoins(n) {
  return Math.round(n || 0).toLocaleString();
}

// ---- Per-client white-label branding + feature flags. ----------------------
// Populated by getMyConfig(); org-facing UI reads these so the product reflects
// the client's own naming / colors / enabled features.
let _brand = { coin_name: "Red Coins", coin_symbol: "RC", product_name: null,
               accent_color: null, ai_accent_color: null, powered_by: true };
let _features = { consistency: true, refine: true, sponsor_bar: true, caption: true,
                  social: true, background_upload: true, allowed_qualities: ["low","medium","high"] };
function coinSym() { return _brand.coin_symbol || "RC"; }
function coinName() { return _brand.coin_name || "Red Coins"; }
function brand() { return _brand; }
function features() { return _features; }

// Tiny fetch wrapper that injects the ngrok-skip-browser-warning header on
// every API call. Without it, ngrok-free tunnels intercept browser requests
// (any request with a browser-shaped User-Agent) and serve a "you are about
// to visit a personal site" HTML interstitial instead of proxying through to
// FastAPI — the frontend's fetch then receives HTML, JSON.parse throws, and
// the UI surfaces "Failed to fetch / Couldn't reach API". ngrok accepts ANY
// value for this header, so we just send a sentinel.
//
// Safe no-op against non-ngrok hosts: unknown headers are ignored by FastAPI.
function _fetch(url, init = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has("ngrok-skip-browser-warning")) {
    headers.set("ngrok-skip-browser-warning", "1");
  }
  return fetch(url, { ...init, headers });
}

async function _json(res) {
  const text = await res.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch (_) { body = text; }
  if (!res.ok) {
    const detail = (body && body.detail) ? body.detail : (typeof body === "string" ? body : res.statusText);
    const err = new Error(`HTTP ${res.status} — ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

const api = {
  base: API_BASE,
  orgId: DEFAULT_ORG_ID,

  // ----- posters
  async createPoster({ orgId = DEFAULT_ORG_ID, tournamentId, input }) {
    const res = await _fetch(`${API_BASE}/v1/posters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ org_id: orgId, tournament_id: tournamentId, input }),
    });
    return _json(res);
  },

  // Price a poster without generating it (Red Coins cost + affordability).
  async estimatePoster({ orgId = DEFAULT_ORG_ID, input } = {}) {
    const res = await _fetch(`${API_BASE}/v1/posters/estimate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ org_id: orgId, input }),
    });
    return _json(res);
  },

  async getPoster(jobId) {
    const res = await _fetch(`${API_BASE}/v1/posters/${encodeURIComponent(jobId)}`);
    return _json(res);
  },

  // Same-origin proxy of the poster PNG. We use this instead of the raw R2
  // signed URL for downloads because:
  //   * R2 doesn't set Content-Disposition, so the browser would just open
  //     the image in a new tab rather than save it.
  //   * Cross-origin fetch() from this page to R2 fails CORS — the quick-share
  //     modal needs the bytes as a blob to programmatically trigger download.
  // The endpoint returns the PNG with Content-Disposition: attachment.
  downloadUrl(jobId) {
    return `${API_BASE}/v1/posters/${encodeURIComponent(jobId)}/download`;
  },

  async refinePoster({ jobId, prompt }) {
    const res = await _fetch(`${API_BASE}/v1/posters/${encodeURIComponent(jobId)}/refine`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    return _json(res);
  },

  async getQuota({ orgId = DEFAULT_ORG_ID } = {}) {
    const params = new URLSearchParams({ org_id: orgId });
    const res = await _fetch(`${API_BASE}/v1/usage/quota?${params.toString()}`);
    return _json(res);
  },

  // ----- Red Coins wallet
  async getCoins({ orgId = DEFAULT_ORG_ID } = {}) {
    const params = new URLSearchParams({ org_id: orgId });
    const data = await _json(await _fetch(`${API_BASE}/v1/coins?${params.toString()}`));
    // Adopt this client's exchange rate + markup so estimates everywhere match.
    if (data && typeof data.tokens_per_usd === "number") {
      _coinRate = { tokens_per_usd: data.tokens_per_usd, poster_markup: data.poster_markup };
    }
    return data;
  },

  async purchaseCoins({ orgId = DEFAULT_ORG_ID, tokens, usd } = {}) {
    const res = await _fetch(`${API_BASE}/v1/coins/purchase`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ org_id: orgId, tokens, usd }),
    });
    return _json(res);
  },

  // ----- Self-serve client config (branding, features, economics, tiers, quotas)
  async getMyConfig() {
    const data = await _json(await _fetch(`${API_BASE}/v1/me/config`));
    if (data && data.branding) { _brand = { ..._brand, ...data.branding }; }
    if (data && data.features) { _features = { ..._features, ...data.features }; }
    return data;
  },
  async updateMyConfig(patch) {
    const data = await _json(await _fetch(`${API_BASE}/v1/me/config`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch || {}),
    }));
    if (data && data.branding) { _brand = { ..._brand, ...data.branding }; }
    if (data && data.features) { _features = { ..._features, ...data.features }; }
    return data;
  },

  async subscribePlan({ orgId = DEFAULT_ORG_ID, tier } = {}) {
    const res = await _fetch(`${API_BASE}/v1/coins/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ org_id: orgId, tier }),
    });
    return _json(res);
  },

  // Admin: per-org rollup for the Usage & Billing dashboard. One call returns
  // tier breakdown, totals, and every org's stats in one payload.
  async getAdminOrgUsage() {
    const res = await _fetch(`${API_BASE}/v1/admin/usage/orgs`);
    return _json(res);
  },

  // Provider: per-client (platform) rollup for the Clients view.
  async getAdminPlatforms() {
    const res = await _fetch(`${API_BASE}/v1/admin/platforms`);
    return _json(res);
  },

  // Admin: content analytics — vibe/energy/combo/type/quality/source distribution
  // + ratings. One call drives the whole Metrics dashboard.
  async getContentMetrics() {
    const res = await _fetch(`${API_BASE}/v1/admin/metrics`);
    return _json(res);
  },

  // Save the user's 1–5 rating of a completed poster (feeds content metrics).
  async ratePoster(jobId, rating) {
    const res = await _fetch(`${API_BASE}/v1/posters/${encodeURIComponent(jobId)}/rating`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating }),
    });
    return _json(res);
  },

  // Provider: set a client's commercial metadata (service type, fee, name).
  // Use platformId "__none__" for the dev / no-API-key client.
  async setPlatform({ platformId, name, service_type, monthly_fee_usd, economics } = {}) {
    const id = platformId || "__none__";
    const res = await _fetch(`${API_BASE}/v1/admin/platforms/${encodeURIComponent(id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, service_type, monthly_fee_usd, economics }),
    });
    return _json(res);
  },

  // Curated tagline bank — the "random tagline" button fetches one to fill the
  // field. Static content; no org/auth. Call again to re-roll.
  async randomTagline(posterType = "tournament_announcement") {
    const params = new URLSearchParams({ poster_type: posterType });
    const res = await _fetch(`${API_BASE}/v1/taglines/random?${params.toString()}`);
    return _json(res);
  },

  async listPosters({ orgId = DEFAULT_ORG_ID, tournamentId, limit = 50 } = {}) {
    const params = new URLSearchParams({ org_id: orgId, limit: String(limit) });
    if (tournamentId) params.set("tournament_id", tournamentId);
    const res = await _fetch(`${API_BASE}/v1/posters?${params.toString()}`);
    return _json(res);
  },

  // ----- assets
  async uploadAsset({ orgId = DEFAULT_ORG_ID, assetType, file, name, team, removeBackground }) {
    const fd = new FormData();
    fd.append("org_id", orgId);
    fd.append("asset_type", assetType);
    if (name) fd.append("name", name);
    if (team) fd.append("team", team);
    if (removeBackground !== undefined) fd.append("remove_background", removeBackground ? "true" : "false");
    fd.append("file", file, file.name);
    const res = await _fetch(`${API_BASE}/v1/assets`, { method: "POST", body: fd });
    return _json(res);
  },

  async listAssets({ orgId = DEFAULT_ORG_ID, assetType, limit = 50 } = {}) {
    const params = new URLSearchParams({ org_id: orgId, limit: String(limit) });
    if (assetType) params.set("asset_type", assetType);
    const res = await _fetch(`${API_BASE}/v1/assets?${params.toString()}`);
    return _json(res);
  },

  async deleteAsset(assetId) {
    const res = await _fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}`, { method: "DELETE" });
    if (res.status === 204) return true;
    return _json(res);
  },

  // ----- style DNA
  // One call for the whole org's DNA library (one row per tournament), instead
  // of one request per tournament. Returns { style_dnas: [...], count }.
  async listStyleDnas({ orgId = DEFAULT_ORG_ID } = {}) {
    const params = new URLSearchParams({ org_id: orgId });
    const res = await _fetch(`${API_BASE}/v1/style-dnas?${params.toString()}`);
    return _json(res);
  },

  async getStyleDna({ orgId = DEFAULT_ORG_ID, tournamentId, status }) {
    const params = new URLSearchParams({ org_id: orgId });
    if (status) params.set("status", status);
    const res = await _fetch(
      `${API_BASE}/v1/style-dnas/${encodeURIComponent(tournamentId)}?${params.toString()}`
    );
    if (res.status === 404) return null;
    return _json(res);
  },

  async extractStyleDna({ orgId = DEFAULT_ORG_ID, tournamentId, sourceJobId }) {
    const res = await _fetch(
      `${API_BASE}/v1/style-dnas/${encodeURIComponent(tournamentId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ org_id: orgId, source_job_id: sourceJobId }),
      }
    );
    return _json(res);
  },

  async approveStyleDna({ orgId = DEFAULT_ORG_ID, tournamentId }) {
    const res = await _fetch(
      `${API_BASE}/v1/style-dnas/${encodeURIComponent(tournamentId)}/approve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ org_id: orgId }),
      }
    );
    return _json(res);
  },

  // ----- caption (Gemini). Returns null when GEMINI_API_KEY isn't set (503)
  // so the UI can fall back to the empty textarea silently.
  async generateCaption(jobId, { regenerate = false } = {}) {
    const params = new URLSearchParams();
    if (regenerate) params.set("regenerate", "true");
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await _fetch(
      `${API_BASE}/v1/posters/${encodeURIComponent(jobId)}/caption${qs}`,
      { method: "POST" },
    );
    if (res.status === 503) return null;
    return _json(res);
  },

  // ----- native social posting (via Postiz). Returns null when Postiz isn't
  // configured (503) so the UI can hide the panel cleanly instead of erroring.
  async listSocialIntegrations() {
    const res = await _fetch(`${API_BASE}/v1/social/integrations`);
    if (res.status === 503) return null;
    return _json(res);
  },

  async createSocialPost({ jobId, integrationIds, content, scheduleAt }) {
    const body = { job_id: jobId, integration_ids: integrationIds, content };
    if (scheduleAt) body.schedule_at = scheduleAt;
    const res = await _fetch(`${API_BASE}/v1/social/post`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return _json(res);
  },
};

Object.assign(window, { api });
