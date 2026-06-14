// admin-usage.jsx — Admin Usage & Billing dashboard.
//
// Renders one /v1/admin/usage/orgs payload as:
//   1. A header row with the cross-org totals (orgs, posters, spend, MRR).
//   2. A tier-breakdown chip row.
//   3. A sortable per-org table with subscription tier badges, rolling-window
//      counts, modes, days active, tier-cap utilization bar, and spend.
//   4. A "Top 5 orgs by posters (30d)" bar block.
//
// The page auto-refreshes every 30s so demos look live. Currently surfaces
// to everyone (per the user spec) — when the admin-only flag flips, gate at
// the route layer (app.jsx) and the backend (require_admin dependency) and
// nothing else changes here.


// ---- helpers ---------------------------------------------------------------

const _USD = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const _INT = new Intl.NumberFormat("en-US");
const _PCT = (v) => `${(v ?? 0).toFixed(v >= 100 ? 0 : 1)}%`;

function _fmtRelative(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "—";
  const dt = Date.now() - t;
  const s = Math.floor(dt / 1000);
  if (s < 60)  return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48)  return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30)  return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

// CSS color variable per tier — matches the badge accents we want.
const _TIER_COLOR = {
  free:       "var(--fg-3)",
  pro:        "var(--cy)",
  enterprise: "var(--crim)",
};

const _TIER_SOFT = {
  free:       "var(--surface-2)",
  pro:        "var(--cy-soft, rgba(45,212,255,0.12))",
  enterprise: "var(--crim-soft)",
};

function TierBadge({ tier, tiers }) {
  const info = tiers?.[tier];
  const label = info?.label || (tier || "—").toUpperCase();
  return (
    <span style={{
      padding: "2px 8px", fontSize: 10.5, fontWeight: 700, letterSpacing: "0.08em",
      textTransform: "uppercase", borderRadius: 999,
      background: _TIER_SOFT[tier] || "var(--surface-2)",
      color: _TIER_COLOR[tier] || "var(--fg-2)",
      border: `1px solid ${_TIER_COLOR[tier] || "var(--line)"}`,
    }}>
      {label}
    </span>
  );
}

// Single inline progress bar — tier cap fill or relative-to-leader. The
// width is clamped to 100 % so an over-quota org doesn't blow out the row.
function UtilizationBar({ pct, color = "var(--cy)", height = 4 }) {
  const w = Math.max(0, Math.min(100, pct || 0));
  return (
    <div style={{ height, borderRadius: 4, background: "var(--surface-2)", overflow: "hidden", marginTop: 4 }}>
      <div style={{
        height: "100%", width: `${w}%`,
        background: pct >= 90 ? "var(--crim)" : pct >= 70 ? "oklch(70% 0.18 60)" : color,
        transition: "width 360ms ease",
      }} />
    </div>
  );
}


// ---- main page -------------------------------------------------------------

function AdminUsage() {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  // Sort state for the org table.
  const [sortKey, setSortKey] = React.useState("completed");
  const [sortDir, setSortDir] = React.useState("desc");

  const load = React.useCallback(async () => {
    try {
      const res = await window.api.getAdminOrgUsage();
      setData(res);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  // IMPORTANT: every hook must run on every render and in the same order
  // (React's Rules of Hooks). Compute sortedOrgs / top5 BEFORE the early
  // returns below; they'll just resolve to empty arrays while `data` is null.
  // Moving them after the early returns produces the classic "Rendered more
  // hooks than during the previous render" error.
  const sortedOrgs = React.useMemo(() => {
    const arr = [...((data && data.orgs) || [])];
    arr.sort((a, b) => {
      const av = a?.[sortKey];
      const bv = b?.[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const an = Number(av ?? 0); const bn = Number(bv ?? 0);
      return sortDir === "asc" ? an - bn : bn - an;
    });
    return arr;
  }, [data, sortKey, sortDir]);

  // Top-5 chart data — biggest completed_30d in descending order.
  const top5 = React.useMemo(() => {
    const list = (data && data.orgs) || [];
    return [...list]
      .sort((a, b) => (b.completed_30d || 0) - (a.completed_30d || 0))
      .slice(0, 5);
  }, [data]);

  // ---- early returns (all hooks above this line) ------------------------
  if (loading && !data) {
    return <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--fg-3)" }}>Loading admin usage…</div>;
  }
  if (error && !data) {
    return (
      <div className="card" style={{ padding: 24, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Couldn't load admin usage</div>
        <div className="mono" style={{ fontSize: 12 }}>{error}</div>
      </div>
    );
  }

  const { orgs = [], totals, by_tier, tiers, generated_at } = data || {};

  const toggleSort = (key) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("desc"); }
  };

  const top5Max = top5[0]?.completed_30d || 1;

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="row" style={{ gap: 8, marginBottom: 10 }}>
            <span className="badge"><span className="dot" /> Admin</span>
            <span className="badge ai"><Icon name="chart" size={11} /> Live</span>
          </div>
          <h1>Usage &amp; billing</h1>
          <p>Org-level posters, modes, and spend across the platform · refreshed every 30s · generated {_fmtRelative(generated_at)}.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost" onClick={load} title="Refresh now">
            <Icon name="refresh" size={14}/> Refresh
          </button>
        </div>
      </div>

      {/* Global totals */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 18 }}>
        <StatCard label="ORGS" value={_INT.format(totals?.total_orgs || 0)} hint={
          <span>{by_tier?.free || 0} free · {by_tier?.pro || 0} pro · {by_tier?.enterprise || 0} enterprise</span>
        } />
        <StatCard label="POSTERS COMPLETED" value={_INT.format(totals?.total_completed_posters || 0)}
                  hint={<span style={{ color: "var(--ok, #34c759)" }}>{_INT.format(totals?.total_completed_30d || 0)} in last 30 days</span>} />
        <StatCard label="EST. SPEND" value={_USD.format(totals?.total_estimated_spend_usd || 0)}
                  hint={<span className="hint">Lifetime · ${(totals?.total_estimated_spend_usd / Math.max(1, totals?.total_completed_posters || 1)).toFixed(3)}/poster avg</span>} />
        <StatCard label="MRR (LISTED)" value={_USD.format(totals?.total_monthly_recurring_usd || 0)}
                  hint={<span className="hint">Sum of tier prices · static for now</span>} />
      </div>

      {/* Tier breakdown chips */}
      <div className="card" style={{ padding: 14, marginBottom: 18 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Subscription tiers</div>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          {(["free","pro","enterprise"]).map((t) => {
            const info = tiers?.[t] || {};
            const count = by_tier?.[t] || 0;
            return (
              <div key={t} style={{
                display: "inline-flex", alignItems: "center", gap: 10,
                padding: "8px 12px", borderRadius: 10,
                background: _TIER_SOFT[t], border: `1px solid ${_TIER_COLOR[t]}`,
                color: _TIER_COLOR[t],
              }}>
                <div style={{ fontWeight: 700, fontSize: 12, letterSpacing: "0.08em" }}>{info.label || t.toUpperCase()}</div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{count}</div>
                <div className="mono" style={{ fontSize: 10.5, opacity: 0.85 }}>
                  {info.monthly_poster_cap || 0}/mo cap · {_USD.format(info.monthly_price_usd || 0)}/mo
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Per-org table */}
      <div className="card" style={{ padding: 0, marginBottom: 18, overflow: "hidden" }}>
        <div className="row" style={{ padding: "14px 16px", justifyContent: "space-between", borderBottom: "1px solid var(--line)" }}>
          <div className="eyebrow">Orgs · {orgs.length}</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>
            click a column to sort · {sortKey} {sortDir === "asc" ? "↑" : "↓"}
          </div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
            <thead>
              <tr style={{ color: "var(--fg-3)", textAlign: "left", background: "var(--surface-2)" }}>
                <Th onClick={() => toggleSort("org_id")} active={sortKey==="org_id"}>Org</Th>
                <Th onClick={() => toggleSort("tier")} active={sortKey==="tier"}>Tier</Th>
                <Th onClick={() => toggleSort("completed")} active={sortKey==="completed"} numeric>Posters</Th>
                <Th onClick={() => toggleSort("completed_24h")} active={sortKey==="completed_24h"} numeric>24h</Th>
                <Th onClick={() => toggleSort("completed_7d")} active={sortKey==="completed_7d"} numeric>7d</Th>
                <Th onClick={() => toggleSort("completed_30d")} active={sortKey==="completed_30d"} numeric>30d</Th>
                <Th onClick={() => toggleSort("avg_per_day_30d")} active={sortKey==="avg_per_day_30d"} numeric>/day</Th>
                <Th onClick={() => toggleSort("success_rate")} active={sortKey==="success_rate"} numeric>Success</Th>
                <Th onClick={() => toggleSort("days_active_30d")} active={sortKey==="days_active_30d"} numeric>Days</Th>
                <Th>Mode mix</Th>
                <Th onClick={() => toggleSort("tier_utilization_pct")} active={sortKey==="tier_utilization_pct"} numeric>Tier use</Th>
                <Th onClick={() => toggleSort("estimated_spend_total_usd")} active={sortKey==="estimated_spend_total_usd"} numeric>Spend</Th>
                <Th onClick={() => toggleSort("last_activity_at")} active={sortKey==="last_activity_at"}>Last seen</Th>
              </tr>
            </thead>
            <tbody>
              {sortedOrgs.length === 0 && (
                <tr><td colSpan={13} style={{ padding: 24, textAlign: "center", color: "var(--fg-3)" }}>No orgs yet — generate a poster to seed.</td></tr>
              )}
              {sortedOrgs.map((o) => {
                const completed = o.completed || 0;
                const modeTotal = (o.mode_fresh + o.mode_consistency + o.mode_refine) || 1;
                const freshPct = Math.round(100 * o.mode_fresh / modeTotal);
                const consistencyPct = Math.round(100 * o.mode_consistency / modeTotal);
                const refinePct = Math.round(100 * o.mode_refine / modeTotal);
                return (
                  <tr key={o.org_id} style={{ borderTop: "1px solid var(--line)", background: "transparent" }}>
                    <Td><span className="mono" style={{ fontSize: 11.5, fontWeight: 600 }}>{o.org_id}</span></Td>
                    <Td><TierBadge tier={o.tier} tiers={tiers} /></Td>
                    <Td numeric><strong>{_INT.format(completed)}</strong>{o.failed ? <span className="mono" style={{ fontSize: 9.5, color: "var(--fg-4)", marginLeft: 4 }}>·{o.failed} fail</span> : null}</Td>
                    <Td numeric>{_INT.format(o.completed_24h)}</Td>
                    <Td numeric>{_INT.format(o.completed_7d)}</Td>
                    <Td numeric>{_INT.format(o.completed_30d)}</Td>
                    <Td numeric>{(o.avg_per_day_30d || 0).toFixed(2)}</Td>
                    <Td numeric>
                      <span style={{ color: o.success_rate >= 0.9 ? "var(--ok, #34c759)" : o.success_rate >= 0.7 ? "var(--fg-2)" : "var(--crim)" }}>
                        {_PCT((o.success_rate || 0) * 100)}
                      </span>
                    </Td>
                    <Td numeric>{_INT.format(o.days_active_30d)}</Td>
                    <Td>
                      <div className="row" style={{ gap: 4, alignItems: "center" }}>
                        <ModeChip label="F" pct={freshPct} title={`Fresh: ${o.mode_fresh}`} color="var(--cy)" />
                        <ModeChip label="C" pct={consistencyPct} title={`Consistency: ${o.mode_consistency}`} color="oklch(70% 0.18 290)" />
                        <ModeChip label="R" pct={refinePct} title={`Refine: ${o.mode_refine}`} color="var(--crim)" />
                      </div>
                    </Td>
                    <Td numeric>
                      <div style={{ minWidth: 70 }}>
                        <div className="mono" style={{ fontSize: 10.5 }}>{_PCT(o.tier_utilization_pct)}</div>
                        <UtilizationBar pct={o.tier_utilization_pct} />
                      </div>
                    </Td>
                    <Td numeric>{_USD.format(o.estimated_spend_total_usd || 0)}</Td>
                    <Td><span className="mono" style={{ fontSize: 10.5, color: "var(--fg-3)" }}>{_fmtRelative(o.last_activity_at)}</span></Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top 5 by posters in last 30d */}
      {top5.length > 0 && (
        <div className="card" style={{ padding: 18, marginBottom: 18 }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>Top 5 orgs by posters (last 30 days)</div>
          <div className="col" style={{ gap: 10 }}>
            {top5.map((o, i) => {
              const w = Math.max(2, Math.round(100 * (o.completed_30d || 0) / top5Max));
              return (
                <div key={o.org_id}>
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 12 }}>
                      <span className="mono" style={{ color: "var(--fg-4)", marginRight: 6 }}>#{i + 1}</span>
                      <span className="mono" style={{ fontWeight: 600 }}>{o.org_id}</span>
                      <TierBadge tier={o.tier} tiers={tiers} />
                    </span>
                    <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{_INT.format(o.completed_30d)} posters · {_USD.format(o.estimated_spend_30d_usd)}</span>
                  </div>
                  <div style={{ height: 8, background: "var(--surface-2)", borderRadius: 4, overflow: "hidden" }}>
                    <div style={{
                      height: "100%", width: `${w}%`,
                      background: `linear-gradient(90deg, ${_TIER_COLOR[o.tier]}, oklch(75% 0.18 30))`,
                      transition: "width 480ms ease",
                    }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


// ---- small bits ------------------------------------------------------------

function StatCard({ label, value, hint }) {
  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.1 }}>{value}</div>
      {hint && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 6 }}>{hint}</div>}
    </div>
  );
}

function Th({ children, onClick, active, numeric }) {
  return (
    <th
      onClick={onClick}
      style={{
        padding: "10px 12px",
        fontSize: 10.5, letterSpacing: "0.08em", textTransform: "uppercase",
        fontWeight: 600,
        color: active ? "var(--fg)" : "var(--fg-3)",
        cursor: onClick ? "pointer" : "default",
        textAlign: numeric ? "right" : "left",
        whiteSpace: "nowrap",
        userSelect: "none",
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, numeric }) {
  return (
    <td style={{
      padding: "10px 12px",
      textAlign: numeric ? "right" : "left",
      whiteSpace: "nowrap",
    }}>
      {children}
    </td>
  );
}

// Tiny "F / C / R" pill that shows what fraction of an org's completed posters
// came through each pipeline mode. Hover shows the exact count.
function ModeChip({ label, pct, color, title }) {
  return (
    <span
      title={`${title} · ${pct}%`}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        minWidth: 22, height: 18, padding: "0 4px",
        fontSize: 9.5, fontWeight: 700, letterSpacing: "0.04em",
        background: `color-mix(in oklab, ${color} ${Math.max(8, pct)}%, transparent)`,
        color: color, border: `1px solid ${color}`,
        borderRadius: 4,
      }}
    >
      {label}
    </span>
  );
}


Object.assign(window, { AdminUsage });
