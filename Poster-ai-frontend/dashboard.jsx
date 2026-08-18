// dashboard.jsx — Landing screen (live data from backend)

const ACTIVE_STATUSES = new Set(["queued", "generating_prompt", "generating_poster", "applying_sponsor_bar"]);
const STAGE_LABEL = {
  queued: "Queued",
  generating_prompt: "Generating prompt",
  generating_poster: "Generating poster",
  applying_sponsor_bar: "Applying sponsor bar",
  completed: "Completed",
  failed: "Failed",
};
const STAGE_PROGRESS = {
  queued: 0.1,
  generating_prompt: 0.3,
  generating_poster: 0.65,
  applying_sponsor_bar: 0.9,
  completed: 1.0,
  failed: 1.0,
};

function PosterThumb({ job, navigate }) {
  const palettes = [
    ["oklch(35% 0.20 15)",  "oklch(15% 0.10 350)"],
    ["oklch(40% 0.18 280)", "oklch(15% 0.08 320)"],
    ["oklch(45% 0.20 145)", "oklch(15% 0.06 200)"],
    ["oklch(50% 0.16 60)",  "oklch(18% 0.08 30)"],
  ];
  // hash for variant
  let h = 0;
  for (const c of (job.job_id || "")) h = (h * 31 + c.charCodeAt(0)) | 0;
  const [a, b] = palettes[Math.abs(h) % palettes.length];

  return (
    <div className="col" style={{ gap: 8, cursor: "pointer" }} onClick={() => navigate(`#/result/${job.job_id}`)}>
      <div style={{
        position: "relative", borderRadius: 8, overflow: "hidden", aspectRatio: "1 / 1",
        background: job.signed_url ? "#000" : `linear-gradient(140deg, ${a} 0%, ${b} 100%)`,
        border: "1px solid var(--line)",
      }}>
        {job.signed_url ? (
          <img src={job.signed_url} alt="" style={{ display: "block", width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                        color: "rgba(255,255,255,0.7)", fontFamily: "var(--f-display)", fontSize: 18, textShadow: "0 2px 8px rgba(0,0,0,0.6)" }}>
            {job.tournament_id?.slice(0, 14) || "—"}
          </div>
        )}
      </div>
      <div style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.2, marginTop: 2 }}>{job.tournament_id || "—"}</div>
      <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
        {(job.mode || "fresh").toUpperCase()} · {timeAgo(job.created_at)}
      </div>
    </div>
  );
}

function QuotaChip({ q }) {
  const pct = q.limit > 0 ? Math.min(100, Math.round((q.used / q.limit) * 100)) : 0;
  const full = q.remaining <= 0;
  const high = !full && q.remaining <= Math.max(1, Math.floor(q.limit * 0.2));
  const tone = full ? "var(--crim)" : high ? "#FFD24B" : "var(--ok)";
  const label = { day: "Day · 24h", week: "Week · 7d", month: "Month · 30d" }[q.window] || q.window;
  const resetLabel = q.reset_at ? new Date(q.reset_at).toLocaleString() : "—";
  return (
    <div title={full ? `Slot frees up ${resetLabel}` : `Resets ${resetLabel}`}
         style={{
           display: "flex", alignItems: "center", gap: 10,
           padding: "8px 14px", borderRadius: 999,
           background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
         }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: tone }} />
      <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-3)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
        {label}
      </span>
      <span style={{ fontFamily: "var(--f-display)", fontSize: 14, color: full ? "var(--crim)" : "var(--fg)" }}>
        {q.used}<span style={{ color: "var(--fg-4)" }}> / {q.limit}</span>
      </span>
      <div style={{ width: 56, height: 4, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ height: "100%", width: pct + "%", background: tone, transition: "width .25s" }} />
      </div>
    </div>
  );
}

function timeAgo(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} hr ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return d.toLocaleDateString();
}

function InProgressCard({ job, navigate }) {
  const progress = STAGE_PROGRESS[job.status] ?? 0.1;
  return (
    <div className="card" style={{ padding: 14, display: "flex", alignItems: "center", gap: 14, position: "relative", overflow: "hidden", borderColor: "var(--cy-line)" }}>
      <div style={{ position: "absolute", inset: 0, opacity: 0.08, pointerEvents: "none" }} className="ai-grid" />
      <div style={{ width: 52, height: 52, position: "relative", flexShrink: 0 }}>
        <svg viewBox="0 0 52 52" width="52" height="52" style={{ transform: "rotate(-90deg)" }}>
          <circle cx="26" cy="26" r="22" stroke="var(--surface-3)" strokeWidth="3" fill="none"/>
          <circle cx="26" cy="26" r="22" stroke="var(--cy)" strokeWidth="3" fill="none"
                  strokeDasharray={`${progress * 138} 138`} strokeLinecap="round"/>
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--cy)" }}>
          {Math.round(progress * 100)}
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{job.tournament_id}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 4, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          <span style={{ color: "var(--cy)" }}>● </span>{STAGE_LABEL[job.status] || job.status}
        </div>
      </div>
      <button className="btn btn-ghost" style={{ height: 32 }} onClick={() => navigate(`#/job/${job.job_id}`)}>View</button>
    </div>
  );
}

// Module-level cache survives route changes (the Dashboard component unmounts
// on navigation, but this module stays loaded). Returning to the dashboard then
// renders instantly from the last data while a background refresh runs — no
// spinner, no image flash. Keyed per org.
const _dashCache = {};
function _cacheFor(orgId) {
  if (!_dashCache[orgId]) _dashCache[orgId] = { jobs: null, quotas: null, dnas: null };
  return _dashCache[orgId];
}

// Preserve already-known signed URLs across refreshes. The backend returns a
// fresh presigned URL on every fetch; swapping it changes the <img> src and
// forces a re-download. Reusing the URL we already rendered keeps the browser's
// cached image (the URL stays valid for the session).
function _mergeStableUrl(prevList, nextList, urlField) {
  const keyOf = (x) => x.job_id || x.tournament_id || x.asset_id;
  const prevUrl = new Map((prevList || []).map((x) => [keyOf(x), x[urlField]]));
  return (nextList || []).map((x) => {
    const u = prevUrl.get(keyOf(x));
    return (u && x[urlField]) ? Object.assign({}, x, { [urlField]: u }) : x;
  });
}

// Hold a live Image() per URL so the decoded bitmap stays in the browser's
// memory cache for the whole session. When the dashboard remounts after
// navigation, a new <img> with the same src paints from memory instead of
// re-fetching over the network — which is the "posters load again" flash.
const _imgKeep = new Map();
function _keepImages(list, urlField) {
  for (const x of list || []) {
    const url = x[urlField];
    if (url && !_imgKeep.has(url)) {
      const im = new Image();
      im.decoding = "async";
      im.src = url;
      _imgKeep.set(url, im);
    }
  }
}

function Dashboard({ navigate }) {
  const cache = _cacheFor((window.api && window.api.orgId) || "1");
  const [jobs, setJobs] = React.useState(() => cache.jobs || []);
  const [loading, setLoading] = React.useState(() => cache.jobs == null);
  const [error, setError] = React.useState(null);
  const orgId = (window.api && window.api.orgId) || "1";

  const fetchJobs = React.useCallback(async () => {
    try {
      const data = await window.api.listPosters({ orgId, limit: 24 });
      const merged = _mergeStableUrl(cache.jobs, data.jobs || [], "signed_url");
      cache.jobs = merged;
      _keepImages(merged, "signed_url");
      setJobs(merged);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  React.useEffect(() => {
    fetchJobs();
    const t = setInterval(fetchJobs, 5000);
    return () => clearInterval(t);
  }, [fetchJobs]);

  // ---- Rate-limit quota (rolling 24h / 7d / 30d).
  const [quotas, setQuotas] = React.useState(() => cache.quotas || []);
  React.useEffect(() => {
    let cancelled = false;
    const tick = () => window.api.getQuota({ orgId })
      .then((q) => { if (!cancelled) { const arr = Array.isArray(q) ? q : []; cache.quotas = arr; setQuotas(arr); } })
      .catch(() => { /* non-fatal */ });
    tick();
    const t = setInterval(tick, 10000);
    return () => { cancelled = true; clearInterval(t); };
  }, [orgId, jobs.length]);   // refresh after a new job lands

  // ---- Style DNA library. One bulk call (GET /v1/style-dnas) instead of a
  // per-tournament request loop — the old version fired N sequential requests
  // (each with its own CORS preflight), which is what made this section crawl.
  const [dnas, setDnas] = React.useState(() => cache.dnas || []);
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await window.api.listStyleDnas({ orgId });
        if (cancelled) return;
        const found = (res && res.style_dnas) || [];
        const merged = _mergeStableUrl(cache.dnas, found, "source_poster_url");
        cache.dnas = merged;
        _keepImages(merged, "source_poster_url");
        setDnas(merged);
      } catch (_) { /* non-fatal */ }
    })();
    return () => { cancelled = true; };
  }, [orgId]);

  // ---- Red Coins balance (users see tokens, never dollars).
  const [coins, setCoins] = React.useState(() => cache.coins || null);
  React.useEffect(() => {
    let cancelled = false;
    const tick = () => window.api.getCoins({ orgId })
      .then((c) => { if (!cancelled && c) { cache.coins = c; setCoins(c); } })
      .catch(() => { /* non-fatal */ });
    tick();
    const onChange = () => tick();
    window.addEventListener("epai:coins-changed", onChange);
    const t = setInterval(tick, 15000);
    return () => { cancelled = true; clearInterval(t); window.removeEventListener("epai:coins-changed", onChange); };
  }, [orgId]);

  const inProgress = jobs.filter((j) => ACTIVE_STATUSES.has(j.status));
  const completed = jobs.filter((j) => j.status === "completed").slice(0, 8);
  const completedCount = jobs.filter((j) => j.status === "completed").length;
  const failedCount = jobs.filter((j) => j.status === "failed").length;
  const totalCount = jobs.length;
  const successRate = totalCount > 0
    ? ((completedCount / Math.max(1, completedCount + failedCount)) * 100).toFixed(1) + "%"
    : "—";
  const coinsLabel = coins ? `${coins.tier} tier` : "balance";

  const stats = [
    { label: "Posters total",       value: String(totalCount),       delta: `${completedCount} done`, positive: true },
    { label: "Success rate",        value: successRate,              delta: `${failedCount} failed`,  positive: failedCount === 0 },
    { label: coinName(),            value: coins ? coins.balance.toLocaleString() : "—", delta: coinsLabel, positive: null },
    { label: "In progress",         value: String(inProgress.length),delta: inProgress.length ? "LIVE" : "idle", positive: inProgress.length > 0 },
  ];

  return (
    <div>
      {/* Hero CTA */}
      <div className="card" style={{
        padding: 32, marginBottom: 28,
        position: "relative", overflow: "hidden",
        background: "linear-gradient(120deg, oklch(18% 0.05 8) 0%, oklch(13% 0.012 350) 60%, oklch(15% 0.04 195) 100%)",
        borderColor: "oklch(28% 0.04 8)",
      }}>
        <div className="ai-grid" style={{ position: "absolute", inset: 0, opacity: 0.4, pointerEvents: "none",
              maskImage: "radial-gradient(circle at 80% 50%, black, transparent 70%)" }} />
        <div style={{ position: "absolute", right: -60, top: -60, width: 280, height: 280, borderRadius: "50%",
              background: "radial-gradient(circle, oklch(65% 0.230 8 / 0.35), transparent 65%)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", right: 80, bottom: -80, width: 200, height: 200, borderRadius: "50%",
              background: "radial-gradient(circle, oklch(82% 0.155 195 / 0.25), transparent 65%)", pointerEvents: "none" }} />

        <div style={{ position: "relative", maxWidth: 580 }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <span className="badge ai"><Icon name="sparkles" size={12} />AI Generation</span>
            <span className="badge">
              <span className="dot" style={{ background: error ? "var(--crim)" : "var(--ok)" }} />
              {error ? "Backend unreachable" : "All systems normal"}
            </span>
          </div>
          <h1 className="h-display" style={{ fontSize: 48, margin: 0 }}>
            Spin up a poster<br/>
            <span style={{
              background: "linear-gradient(90deg, var(--crim) 0%, var(--cy) 100%)",
              WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent"
            }}>in 100 seconds.</span>
          </h1>
          <p style={{ color: "var(--fg-3)", maxWidth: 480, marginTop: 14, fontSize: 15, lineHeight: 1.5 }}>
            Gameday, results, roster reveals — publish-ready socials from a 5-step form.
            No design tools, no waiting on the brand team.
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
            <button className="btn btn-ai btn-lg" onClick={() => navigate("#/create")}>
              <Icon name="sparkles" size={16}/> Create new poster
              <Icon name="arrow_right" size={14}/>
            </button>
          </div>
          {error && (
            <div className="mono" style={{ marginTop: 14, fontSize: 11, color: "var(--crim)" }}>
              Couldn't reach API: {error}
            </div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 28 }}>
        {stats.map((s, i) => (
          <div key={i} className="card" style={{ padding: 18, position: "relative", overflow: "hidden" }}>
            <div className="eyebrow" style={{ fontSize: 10 }}>{s.label}</div>
            <div style={{ fontFamily: "var(--f-display)", fontSize: 36, marginTop: 8, letterSpacing: "-0.02em", lineHeight: 1 }}>{s.value}</div>
            <div className="mono" style={{ fontSize: 11, marginTop: 8, color: s.positive ? "var(--ok)" : s.positive === false ? "var(--crim)" : "var(--fg-4)" }}>
              {s.delta}
            </div>
          </div>
        ))}
      </div>

      {/* Quota chips — per-org rate limits across rolling 24h / 7d / 30d. */}
      {quotas.length > 0 && (
        <div className="card" style={{ padding: 16, marginBottom: 28, display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
          <div>
            <div className="eyebrow" style={{ fontSize: 10 }}>Rate limits</div>
            <div className="hint" style={{ marginTop: 2 }}>Rolling windows. Failed jobs don't count.</div>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {quotas.map((q) => <QuotaChip key={q.window} q={q} />)}
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24 }}>
        <div>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
            <h2 style={{ fontFamily: "var(--f-display)", fontSize: 20, margin: 0, letterSpacing: "-0.01em" }}>Recent posters</h2>
            {loading && <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>Loading…</span>}
          </div>
          {completed.length === 0 && !loading ? (
            <div className="card" style={{ padding: 28, textAlign: "center", color: "var(--fg-3)", borderStyle: "dashed" }}>
              No posters yet. Create your first one →
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {completed.map((j) => <PosterThumb key={j.job_id} job={j} navigate={navigate} />)}
            </div>
          )}
        </div>

        <div>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
            <h2 style={{ fontFamily: "var(--f-display)", fontSize: 20, margin: 0, letterSpacing: "-0.01em" }}>
              In progress{" "}
              {inProgress.length > 0 && (
                <span style={{ color: "var(--cy)", fontFamily: "var(--f-mono)", fontSize: 12, marginLeft: 8, letterSpacing: "0.1em" }}>
                  {inProgress.length} LIVE
                </span>
              )}
            </h2>
          </div>
          <div className="col" style={{ gap: 10 }}>
            {inProgress.map((j) => <InProgressCard key={j.job_id} job={j} navigate={navigate} />)}
            {inProgress.length === 0 && (
              <div className="card" style={{ padding: 14, borderStyle: "dashed", textAlign: "center", color: "var(--fg-4)", fontSize: 12 }}>
                You'll see jobs land here while they generate.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Style DNA library */}
      <div style={{ marginTop: 28 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
          <h2 style={{ fontFamily: "var(--f-display)", fontSize: 20, margin: 0, letterSpacing: "-0.01em" }}>
            Style DNA{" "}
            {dnas.length > 0 && (
              <span style={{ color: "var(--cy)", fontFamily: "var(--f-mono)", fontSize: 12, marginLeft: 8, letterSpacing: "0.1em" }}>
                {dnas.length}
              </span>
            )}
          </h2>
        </div>
        {dnas.length === 0 ? (
          <div className="card" style={{ padding: 24, borderStyle: "dashed", textAlign: "center", color: "var(--fg-4)", fontSize: 12 }}>
            No saved styles yet. Generate a poster, then "Extract & save as draft" on its result page to create one.
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
            {dnas.map((dna) => <StyleDnaCard key={dna.tournament_id} dna={dna} navigate={navigate} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function StyleDnaCard({ dna, navigate }) {
  const approved = dna.status === "approved";
  return (
    <div className="card" style={{ padding: 16, borderColor: "var(--cy-line)" }}>
      <div className="row" style={{ gap: 12, alignItems: "flex-start" }}>
        {dna.source_poster_url && (
          <a href={dna.source_poster_url} target="_blank" rel="noopener"
             style={{ flexShrink: 0, width: 52, height: 52, borderRadius: 8, overflow: "hidden", border: "1px solid var(--line)", background: "var(--surface-2)" }}>
            <img src={dna.source_poster_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </a>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {dna.tournament_id}
            </div>
            <span className={"badge" + (approved ? " ok" : "")} style={{ flexShrink: 0 }}>
              {approved ? <><span className="dot" />Approved</> : "Draft"}
            </span>
          </div>
          <div className="row" style={{ gap: 4, marginTop: 10, flexWrap: "wrap" }}>
            {(dna.palette || []).slice(0, 6).map((c) => (
              <div key={c} title={c} style={{ width: 20, height: 20, borderRadius: 4, background: c, border: "1px solid var(--line)" }} />
            ))}
          </div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-3)", letterSpacing: "0.05em", textTransform: "uppercase", marginTop: 10 }}>
            {[dna.energy, dna.lighting].filter(Boolean).join(" · ") || "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Dashboard });
