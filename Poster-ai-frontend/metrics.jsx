// metrics.jsx — Content metrics dashboard.
//
// Renders one /v1/admin/metrics payload: what design choices users make and how
// they rate the results. Sections:
//   1. KPI row (posters, rated, avg rating, AI-vs-upload split).
//   2. Combo matrix — energy × vibe heatmap (share + avg rating per combo).
//   3. Vibe / energy distributions with per-bucket avg rating.
//   4. Background source, poster type, quality, game, color mode bars.
//   5. Rating histogram.
//
// Charts are hand-rolled CSS bars (no chart lib — the SPA has no build step).
// Helper components are uniquely named (Kpi/BarList/…) to avoid colliding with
// admin-usage.jsx in the shared global scope. Ungated, mirroring admin-usage.

// ---- helpers ---------------------------------------------------------------

const _M_INT = new Intl.NumberFormat("en-US");
const _M_PCT = (v) => `${(v ?? 0).toFixed(v >= 100 ? 0 : 1)}%`;

// Stable display order + colors so the dashboard reads consistently.
const M_ENERGIES = ["chill", "balanced", "intense", "explosive"];
const M_VIBES = ["cyberpunk", "cinematic", "dark_fantasy", "cosmic", "minimal", "fire_energy"];
const M_VIBE_COLOR = {
  cyberpunk: "#22D3EE", cinematic: "#E8B84B", dark_fantasy: "#A855F7",
  cosmic: "#7B5CFF", minimal: "#94A3B8", fire_energy: "#FF6A1F",
};
const M_SOURCE_COLOR = { ai_generated: "var(--cy)", upload: "var(--crim)", none: "var(--fg-4)" };
const M_LABEL = (k) => (k == null ? "—" : String(k).replace(/_/g, " "));

function _relTime(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60); if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// Small inline star display for an average rating (0–5, one decimal).
function Stars({ value, size = 12 }) {
  if (value == null) return <span className="mono" style={{ color: "var(--fg-4)", fontSize: 11 }}>—</span>;
  const full = Math.round(value);
  return (
    <span title={`${value.toFixed(2)} / 5`} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span style={{ color: "var(--warn, #FFD24B)", fontSize: size, letterSpacing: 1 }}>
        {"★".repeat(full)}<span style={{ color: "var(--line)" }}>{"★".repeat(5 - full)}</span>
      </span>
      <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>{value.toFixed(1)}</span>
    </span>
  );
}

function Kpi({ label, value, hint, accent }) {
  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.1, color: accent || "var(--fg)" }}>{value}</div>
      {hint && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 6 }}>{hint}</div>}
    </div>
  );
}

// A card of horizontal bars, one per bucket, sorted by share. Optionally shows
// each bucket's average rating on the right.
function BarList({ title, buckets, colorFor, showRating = false, note }) {
  const max = Math.max(1, ...(buckets || []).map((b) => b.pct || 0));
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <div className="eyebrow">{title}</div>
        {note && <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>{note}</div>}
      </div>
      {(!buckets || buckets.length === 0) ? (
        <div style={{ color: "var(--fg-3)", fontSize: 12, padding: "8px 0" }}>No data yet.</div>
      ) : (
        <div className="col" style={{ gap: 10 }}>
          {buckets.map((b) => {
            const color = (colorFor && colorFor(b.key)) || "var(--cy)";
            const w = Math.max(2, Math.round(100 * (b.pct || 0) / max));
            return (
              <div key={b.key}>
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
                  <span style={{ textTransform: "capitalize", fontWeight: 600 }}>{M_LABEL(b.key)}</span>
                  <span className="row" style={{ gap: 10 }}>
                    {showRating && <Stars value={b.avg_rating} />}
                    <span className="mono" style={{ color: "var(--fg-3)", minWidth: 78, textAlign: "right" }}>
                      {_M_PCT(b.pct)} · {_M_INT.format(b.count)}
                    </span>
                  </span>
                </div>
                <div style={{ height: 8, background: "var(--surface-2)", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${w}%`, background: color, transition: "width 420ms ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Energy × vibe heatmap. Cell intensity = share of all combos; shows count and
// avg rating so you can spot popular-but-poorly-rated combos at a glance.
function ComboMatrix({ buckets }) {
  const byKey = {};
  let max = 0, total = 0;
  (buckets || []).forEach((b) => { byKey[b.key] = b; max = Math.max(max, b.count); total += b.count; });
  return (
    <div className="card" style={{ padding: 18, marginBottom: 18 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <div className="eyebrow">Combo popularity · energy × vibe</div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>
          cell = share of all combos · ★ = avg rating · {_M_INT.format(total)} posters
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ padding: 8 }} />
              {M_VIBES.map((v) => (
                <th key={v} style={{ padding: "8px 6px", textTransform: "capitalize", color: M_VIBE_COLOR[v], fontSize: 11, whiteSpace: "nowrap" }}>
                  {M_LABEL(v)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {M_ENERGIES.map((e) => (
              <tr key={e}>
                <td style={{ padding: "8px 10px", textTransform: "capitalize", fontWeight: 700, color: "var(--fg-2)", whiteSpace: "nowrap" }}>{e}</td>
                {M_VIBES.map((v) => {
                  const b = byKey[`${e}_${v}`];
                  const count = b ? b.count : 0;
                  const pct = b ? b.pct : 0;
                  const intensity = max ? count / max : 0;
                  return (
                    <td key={v} style={{ padding: 4 }}>
                      <div title={`${e} · ${v} — ${count} posters (${_M_PCT(pct)})`}
                           style={{
                             borderRadius: 8, padding: "8px 6px", textAlign: "center",
                             background: `color-mix(in oklab, ${M_VIBE_COLOR[v]} ${Math.round(8 + intensity * 62)}%, transparent)`,
                             border: "1px solid var(--line)", minWidth: 74,
                           }}>
                        <div style={{ fontWeight: 700, fontSize: 14 }}>{_M_INT.format(count)}</div>
                        <div className="mono" style={{ fontSize: 9.5, color: "var(--fg-2)" }}>{_M_PCT(pct)}</div>
                        <div style={{ marginTop: 2 }}>
                          {b && b.avg_rating != null
                            ? <span style={{ fontSize: 10, color: "var(--warn, #FFD24B)" }}>★ {b.avg_rating.toFixed(1)}</span>
                            : <span className="mono" style={{ fontSize: 9.5, color: "var(--fg-4)" }}>—</span>}
                        </div>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RatingHistogram({ histogram, count, avg }) {
  const total = Math.max(1, count || 0);
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <div className="eyebrow">Rating distribution</div>
        <div className="row" style={{ gap: 8 }}><Stars value={avg} size={13} /><span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>{_M_INT.format(count || 0)} rated</span></div>
      </div>
      {(count || 0) === 0 ? (
        <div style={{ color: "var(--fg-3)", fontSize: 12 }}>No ratings yet — rate a poster on its result screen.</div>
      ) : (
        <div className="col" style={{ gap: 8 }}>
          {[5, 4, 3, 2, 1].map((star) => {
            const n = (histogram && histogram[String(star)]) || 0;
            const w = Math.round(100 * n / total);
            return (
              <div key={star} className="row" style={{ gap: 10, alignItems: "center" }}>
                <span className="mono" style={{ width: 26, color: "var(--warn, #FFD24B)", fontSize: 12 }}>{star}★</span>
                <div style={{ flex: 1, height: 8, background: "var(--surface-2)", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${w}%`, background: "var(--warn, #FFD24B)", transition: "width 420ms ease" }} />
                </div>
                <span className="mono" style={{ width: 54, textAlign: "right", fontSize: 11, color: "var(--fg-3)" }}>{_M_PCT(100 * n / total)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


// ---- main page -------------------------------------------------------------

function Metrics() {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  const load = React.useCallback(async () => {
    try {
      const res = await window.api.getContentMetrics();
      setData(res); setError(null);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  React.useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  // Share of posters that used an AI-generated background vs an upload.
  const sourceShare = React.useMemo(() => {
    const list = (data && data.by_background_source) || [];
    const pick = (k) => list.find((b) => b.key === k) || { count: 0, pct: 0 };
    return { ai: pick("ai_generated"), up: pick("upload") };
  }, [data]);

  if (loading && !data) {
    return <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--fg-3)" }}>Loading content metrics…</div>;
  }
  if (error && !data) {
    return (
      <div className="card" style={{ padding: 24, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Couldn't load content metrics</div>
        <div className="mono" style={{ fontSize: 12 }}>{error}</div>
      </div>
    );
  }

  const d = data || {};

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="row" style={{ gap: 8, marginBottom: 10 }}>
            <span className="badge"><span className="dot" /> Admin</span>
            <span className="badge ai"><Icon name="chart" size={11} /> Live</span>
          </div>
          <h1>Content metrics</h1>
          <p>What users create and how they rate it — vibe, energy, combo, background source, and satisfaction · refreshed every 30s · generated {_relTime(d.generated_at)}.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost" onClick={load} title="Refresh now"><Icon name="refresh" size={14} /> Refresh</button>
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 18 }}>
        <Kpi label="POSTERS" value={_M_INT.format(d.total_jobs || 0)} hint="All poster requests" />
        <Kpi label="RATED" value={_M_INT.format(d.ratings_count || 0)}
             hint={<span className="hint">{_M_PCT(100 * (d.ratings_count || 0) / Math.max(1, d.total_jobs || 1))} of posters</span>} />
        <Kpi label="AVG RATING" value={d.avg_rating != null ? d.avg_rating.toFixed(2) : "—"}
             accent="var(--warn, #FFD24B)" hint={<Stars value={d.avg_rating} />} />
        <Kpi label="AI BACKGROUND" value={_M_PCT(sourceShare.ai.pct)} accent="var(--cy)"
             hint={<span className="hint">{_M_INT.format(sourceShare.ai.count)} posters</span>} />
        <Kpi label="OWN UPLOAD" value={_M_PCT(sourceShare.up.pct)} accent="var(--crim)"
             hint={<span className="hint">{_M_INT.format(sourceShare.up.count)} posters</span>} />
      </div>

      {/* Combo heatmap — the headline view */}
      <ComboMatrix buckets={d.by_combo} />

      {/* Vibe + energy with ratings */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 18 }}>
        <BarList title="Vibe" buckets={d.by_vibe} showRating note="share · avg rating"
                 colorFor={(k) => M_VIBE_COLOR[k] || "var(--cy)"} />
        <BarList title="Energy (detail density)" buckets={d.by_energy} showRating note="share · avg rating"
                 colorFor={() => "var(--cy)"} />
      </div>

      {/* Source + poster type */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 18 }}>
        <BarList title="Background source" buckets={d.by_background_source}
                 colorFor={(k) => M_SOURCE_COLOR[k] || "var(--fg-3)"} />
        <BarList title="Poster type" buckets={d.by_poster_type} colorFor={() => "oklch(70% 0.15 200)"} />
      </div>

      {/* Quality + game + color mode */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 18 }}>
        <BarList title="Render quality" buckets={d.by_quality} colorFor={() => "oklch(72% 0.16 300)"} />
        <BarList title="Color mode" buckets={d.by_color_mode} colorFor={() => "oklch(72% 0.14 160)"}
                 note="dominant vs auto-from-bg" />
      </div>

      {/* Game split + ratings */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 18 }}>
        <BarList title="Game" buckets={d.by_game} colorFor={() => "var(--crim)"} />
        <RatingHistogram histogram={d.rating_histogram} count={d.ratings_count} avg={d.avg_rating} />
      </div>
    </div>
  );
}

Object.assign(window, { Metrics });
