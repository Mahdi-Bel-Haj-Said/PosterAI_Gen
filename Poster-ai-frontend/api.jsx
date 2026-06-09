// api.jsx — thin fetch wrapper around the FastAPI backend.
// Base URL is overridable via window.API_BASE (set in EsportsPostAI.html).

const API_BASE = (window.API_BASE || "http://localhost:8000").replace(/\/+$/, "");
const DEFAULT_ORG_ID = "1";

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
