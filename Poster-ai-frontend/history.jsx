// history.jsx — full poster history with filters + search.
// Reuses globals from dashboard.jsx: ACTIVE_STATUSES, STAGE_LABEL, timeAgo.

const STATUS_FILTERS = [
  { id: "all",         label: "All" },
  { id: "completed",   label: "Completed" },
  { id: "in_progress", label: "In progress" },
  { id: "failed",      label: "Failed" },
];

function statusBadge(status) {
  if (status === "completed") return { cls: "badge ok", text: "Done", dot: true };
  if (status === "failed")    return { cls: "badge", text: "Failed", color: "var(--crim)" };
  return { cls: "badge", text: STAGE_LABEL[status] || status, color: "var(--cy)" };
}

function HistoryCard({ job, navigate }) {
  const active = ACTIVE_STATUSES.has(job.status);
  const dest = job.status === "completed" ? `#/result/${job.job_id}` : `#/job/${job.job_id}`;
  const b = statusBadge(job.status);

  // deterministic placeholder gradient from job id
  let h = 0;
  for (const c of (job.job_id || "")) h = (h * 31 + c.charCodeAt(0)) | 0;
  const palettes = [
    ["oklch(35% 0.20 15)",  "oklch(15% 0.10 350)"],
    ["oklch(40% 0.18 280)", "oklch(15% 0.08 320)"],
    ["oklch(45% 0.20 145)", "oklch(15% 0.06 200)"],
    ["oklch(50% 0.16 60)",  "oklch(18% 0.08 30)"],
  ];
  const [a, bb] = palettes[Math.abs(h) % palettes.length];

  return (
    <div className="col" style={{ gap: 8, cursor: "pointer" }} onClick={() => navigate(dest)}>
      <div style={{
        position: "relative", borderRadius: 8, overflow: "hidden", aspectRatio: "1 / 1",
        background: job.signed_url ? "#000" : `linear-gradient(140deg, ${a} 0%, ${bb} 100%)`,
        border: "1px solid var(--line)",
      }}>
        {job.signed_url ? (
          <img src={job.signed_url} alt="" style={{ display: "block", width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                        color: "rgba(255,255,255,0.7)", fontFamily: "var(--f-display)", fontSize: 16, textAlign: "center", padding: 8,
                        textShadow: "0 2px 8px rgba(0,0,0,0.6)" }}>
            {active ? "Generating…" : (job.tournament_id || "—")}
          </div>
        )}
        <div style={{ position: "absolute", top: 8, left: 8 }}>
          <span className={b.cls} style={{ fontSize: 9.5, padding: "2px 7px", color: b.color }}>
            {b.dot && <span className="dot" />}{b.text}
          </span>
        </div>
      </div>
      <div style={{ fontSize: 12.5, fontWeight: 500, lineHeight: 1.2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {job.tournament_id || "—"}
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
        {(job.mode || "fresh").toUpperCase()} · {timeAgo(job.created_at)}
      </div>
    </div>
  );
}

// Module-level cache survives navigation (same pattern as the dashboard): a
// return to History renders instantly from the last data while it refreshes in
// the background. Reuses _mergeStableUrl / _keepImages from dashboard.jsx so
// thumbnails keep their cached image instead of re-downloading.
const _histCache = {}; // orgId -> jobs[]

function History({ navigate }) {
  const orgId = (window.api && window.api.orgId) || "1";
  const [jobs, setJobs] = React.useState(() => _histCache[orgId] || []);
  const [loading, setLoading] = React.useState(() => _histCache[orgId] == null);
  const [error, setError] = React.useState(null);
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [tournamentFilter, setTournamentFilter] = React.useState("all");
  const [query, setQuery] = React.useState("");

  const fetchJobs = React.useCallback(async () => {
    try {
      const data = await window.api.listPosters({ orgId, limit: 200 });
      const merged = _mergeStableUrl(_histCache[orgId], data.jobs || [], "signed_url");
      _histCache[orgId] = merged;
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
    const t = setInterval(fetchJobs, 8000);
    return () => clearInterval(t);
  }, [fetchJobs]);

  const tournaments = React.useMemo(
    () => Array.from(new Set(jobs.map((j) => j.tournament_id).filter(Boolean))).sort(),
    [jobs]
  );

  const filtered = jobs.filter((j) => {
    if (statusFilter === "in_progress" && !ACTIVE_STATUSES.has(j.status)) return false;
    if (statusFilter === "completed" && j.status !== "completed") return false;
    if (statusFilter === "failed" && j.status !== "failed") return false;
    if (tournamentFilter !== "all" && j.tournament_id !== tournamentFilter) return false;
    if (query) {
      const q = query.toLowerCase();
      if (!((j.tournament_id || "").toLowerCase().includes(q) || (j.job_id || "").toLowerCase().includes(q))) return false;
    }
    return true;
  });

  const countFor = (id) => {
    if (id === "all") return jobs.length;
    if (id === "in_progress") return jobs.filter((j) => ACTIVE_STATUSES.has(j.status)).length;
    return jobs.filter((j) => j.status === id).length;
  };

  const selectStyle = {
    padding: "8px 12px", borderRadius: 8, background: "var(--bg-elev)",
    border: "1px solid var(--line-strong)", color: "var(--fg)", fontFamily: "var(--f-mono)", fontSize: 12.5,
  };

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>WORKSPACE · HISTORY</div>
          <h1>Poster history</h1>
          <p>Every poster you've generated, newest first.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost" onClick={fetchJobs}><Icon name="refresh" size={14} /> Refresh</button>
          <button className="btn btn-primary" onClick={() => navigate("#/create")}><Icon name="plus" size={14} /> New poster</button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="row" style={{ gap: 10, marginBottom: 24, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 4, background: "var(--surface)", padding: 4, borderRadius: 10, border: "1px solid var(--line)" }}>
          {STATUS_FILTERS.map((f) => {
            const on = statusFilter === f.id;
            return (
              <button key={f.id} onClick={() => setStatusFilter(f.id)}
                style={{
                  padding: "7px 12px", border: 0, borderRadius: 6, cursor: "pointer",
                  background: on ? "var(--surface-3)" : "transparent",
                  color: on ? "var(--fg)" : "var(--fg-3)", fontSize: 12.5, fontWeight: on ? 600 : 500,
                }}>
                {f.label} <span className="mono" style={{ color: "var(--fg-4)", fontSize: 11 }}>{countFor(f.id)}</span>
              </button>
            );
          })}
        </div>

        <select value={tournamentFilter} onChange={(e) => setTournamentFilter(e.target.value)} style={selectStyle}>
          <option value="all">All tournaments</option>
          {tournaments.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        <div style={{ position: "relative", flex: 1, minWidth: 200, maxWidth: 320 }}>
          <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--fg-4)" }}>
            <Icon name="search" size={14} />
          </span>
          <input className="input" value={query} onChange={(e) => setQuery(e.target.value)}
                 placeholder="Search tournament or job id…" style={{ paddingLeft: 32 }} />
        </div>
      </div>

      {error && (
        <div className="card" style={{ padding: 16, marginBottom: 16, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
          <div className="mono" style={{ fontSize: 12 }}>Couldn't load history: {error}</div>
        </div>
      )}

      {loading && jobs.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--fg-3)" }}>Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--fg-3)", borderStyle: "dashed" }}>
          {jobs.length === 0 ? "No posters yet. Create your first one →" : "No posters match these filters."}
        </div>
      ) : (
        <>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-4)", marginBottom: 12, letterSpacing: "0.06em" }}>
            {filtered.length} {filtered.length === 1 ? "POSTER" : "POSTERS"}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 16 }}>
            {filtered.map((j) => <HistoryCard key={j.job_id} job={j} navigate={navigate} />)}
          </div>
        </>
      )}
    </div>
  );
}

Object.assign(window, { History });
