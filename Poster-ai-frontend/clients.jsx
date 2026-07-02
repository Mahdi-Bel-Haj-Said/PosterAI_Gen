// clients.jsx — Provider view: your CLIENTS (integrating platforms).
//
// One level up from Usage & Billing (which is per-org). A row per platform —
// the customer who bought the API and holds a key. The provider <-> client
// relationship is COMMERCIAL ONLY: a service type (Fully hosted / BYOK) and
// money (fee in, cost to serve). Red Coins are an ORG concept and never appear
// here. Built generically from the backend, so any new client shows up with no
// code change.

const _CINT = new Intl.NumberFormat();
const _CUSD = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });

const SERVICE_LABEL = { hosted: "Fully hosted", byok: "BYOK" };

function _cliRel(iso) {
  if (!iso) return "never";
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60); if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function _platformLabel(p) {
  if (p.label) return p.label;
  if (p.platform_id) return p.platform_id;
  return "Default (no API key)";
}

// Editable Red Coins economics fields — label + help text define each one.
const ECON_FIELDS = [
  { k: "tokens_per_usd",          label: "Tokens per $1",        step: 100,   help: "Red Coins that equal $1 of value — your exchange rate." },
  { k: "poster_markup",           label: "Poster markup (×)",     step: 0.1,   help: "Multiplier on real cost → what the org pays. Your margin." },
  { k: "base_cost_per_poster_usd",label: "Base cost / poster ($)",step: 0.001, help: "Cost basis of a medium poster (BYOK clients set their own)." },
  { k: "topup_usd_per_10k",       label: "Top-up $ per 10k",      step: 0.05,  help: "Price an org pays to buy 10,000 coins." },
  { k: "free_grant",              label: "Free grant",            step: 100,   help: "Monthly coins for Free-tier orgs." },
  { k: "pro_grant",               label: "Pro grant",             step: 1000,  help: "Monthly coins for Pro orgs." },
  { k: "kratos_grant",            label: "Kratos grant",          step: 1000,  help: "Monthly coins for Kratos orgs." },
];

function Clients({ navigate }) {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [openEcon, setOpenEcon] = React.useState(null);  // platform key whose editor is open

  const reload = React.useCallback(() => {
    return window.api.getAdminPlatforms()
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(e.message));
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    const tick = () => { if (!cancelled) reload(); };
    tick();
    const t = setInterval(tick, 15000);
    return () => { cancelled = true; clearInterval(t); };
  }, [reload]);

  const save = (p, patch) =>
    window.api.setPlatform({ platformId: p.platform_id, ...patch })
      .then(() => reload())
      .then(() => window.toast.success("Client updated."))
      .catch((e) => window.toast.error(e.message));

  const platforms = (data && data.platforms) || [];
  const totals = platforms.reduce((a, p) => ({
    clients: a.clients + 1,
    orgs: a.orgs + p.orgs,
    completed: a.completed + p.completed,
    fee: a.fee + p.monthly_fee_usd,
    cost: a.cost + p.cost_to_serve_usd,
  }), { clients: 0, orgs: 0, completed: 0, fee: 0, cost: 0 });

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>PROVIDER · CLIENTS</div>
          <h1>Clients</h1>
          <p>Every platform that bought your API — service type and money at a glance.</p>
        </div>
        <button className="btn btn-ghost" onClick={reload}><Icon name="refresh" size={14} /> Refresh</button>
      </div>

      {error && (
        <div className="card" style={{ padding: 16, marginBottom: 16, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
          <div className="mono" style={{ fontSize: 12 }}>Couldn't load clients: {error}</div>
        </div>
      )}

      {/* Headline stats — provider economics. */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 18 }}>
        <StatCardC label="CLIENTS" value={_CINT.format(totals.clients)} hint={`${_CINT.format(totals.orgs)} orgs total`} />
        <StatCardC label="POSTERS" value={_CINT.format(totals.completed)} hint="completed, all clients" />
        <StatCardC label="MRR (FEES)" value={_CUSD.format(totals.fee)} hint="what clients pay you / mo" accent />
        <StatCardC label="COST TO SERVE" value={_CUSD.format(totals.cost)} hint="your spend (hosted only)" />
        <StatCardC label="NET" value={_CUSD.format(totals.fee - totals.cost)} hint="fees − cost to serve" />
      </div>

      {/* Clients table */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div className="row" style={{ padding: "14px 16px", justifyContent: "space-between", borderBottom: "1px solid var(--line)" }}>
          <div className="eyebrow">Clients · {platforms.length}</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>service type &amp; fee are editable</div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
            <thead>
              <tr style={{ color: "var(--fg-3)", textAlign: "left", background: "var(--surface-2)" }}>
                <ThC>Client</ThC>
                <ThC>Service type</ThC>
                <ThC>API keys</ThC>
                <ThC numeric>Orgs</ThC>
                <ThC>Tier mix</ThC>
                <ThC numeric>Posters</ThC>
                <ThC numeric>30d</ThC>
                <ThC numeric>Success</ThC>
                <ThC numeric>Fee / mo</ThC>
                <ThC numeric>Cost to serve</ThC>
                <ThC numeric>Net</ThC>
                <ThC>Last active</ThC>
              </tr>
            </thead>
            <tbody>
              {!data && (
                <tr><td colSpan={12} style={{ padding: 24, textAlign: "center", color: "var(--fg-3)" }}>Loading…</td></tr>
              )}
              {data && platforms.length === 0 && (
                <tr><td colSpan={12} style={{ padding: 24, textAlign: "center", color: "var(--fg-3)" }}>No clients yet.</td></tr>
              )}
              {platforms.map((p) => {
                const key = p.platform_id || "__none__";
                return (
                <React.Fragment key={key}>
                <tr style={{ borderTop: "1px solid var(--line)" }}>
                  <TdC>
                    <div style={{ fontWeight: 600 }}>{_platformLabel(p)}</div>
                    {p.platform_id && <div className="mono" style={{ fontSize: 9.5, color: "var(--fg-4)" }}>{p.platform_id}</div>}
                    <button className="btn btn-ghost" style={{ padding: "1px 7px", fontSize: 10.5, marginTop: 4 }}
                            onClick={() => setOpenEcon(openEcon === key ? null : key)}>
                      <Icon name="settings" size={10} /> Economics {openEcon === key ? "▲" : "▾"}
                    </button>
                  </TdC>
                  <TdC>
                    <select
                      value={p.service_type}
                      onChange={(e) => save(p, { service_type: e.target.value })}
                      style={{
                        padding: "5px 8px", borderRadius: 6, fontSize: 11.5,
                        background: "var(--bg-elev)", border: "1px solid " + (p.service_type === "byok" ? "var(--cy-line)" : "var(--crim-line)"),
                        color: p.service_type === "byok" ? "var(--cy)" : "var(--crim)", fontWeight: 600, cursor: "pointer",
                      }}>
                      <option value="hosted">Fully hosted</option>
                      <option value="byok">BYOK</option>
                    </select>
                  </TdC>
                  <TdC><span className="mono" style={{ fontSize: 11 }}>{p.active_keys}/{p.api_keys}</span></TdC>
                  <TdC numeric>{_CINT.format(p.orgs)}</TdC>
                  <TdC><span className="mono" style={{ fontSize: 10.5, color: "var(--fg-3)" }}>{p.tier_free}F · {p.tier_pro}P · {p.tier_kratos}K</span></TdC>
                  <TdC numeric><strong>{_CINT.format(p.completed)}</strong>{p.failed ? <span className="mono" style={{ fontSize: 9.5, color: "var(--fg-4)", marginLeft: 4 }}>·{p.failed} fail</span> : null}</TdC>
                  <TdC numeric>{_CINT.format(p.completed_30d)}</TdC>
                  <TdC numeric>
                    <span style={{ color: p.success_rate >= 0.9 ? "var(--ok, #34c759)" : p.success_rate >= 0.7 ? "var(--fg-2)" : "var(--crim)" }}>
                      {p.total_jobs ? Math.round(p.success_rate * 100) + "%" : "—"}
                    </span>
                  </TdC>
                  <TdC numeric><FeeCell value={p.monthly_fee_usd} onSave={(v) => save(p, { monthly_fee_usd: v })} /></TdC>
                  <TdC numeric>
                    {p.service_type === "byok"
                      ? <span className="mono" style={{ color: "var(--fg-4)" }}>—</span>
                      : _CUSD.format(p.cost_to_serve_usd)}
                  </TdC>
                  <TdC numeric>
                    <span style={{ color: p.margin_usd >= 0 ? "var(--ok, #34c759)" : "var(--crim)" }}>{_CUSD.format(p.margin_usd)}</span>
                  </TdC>
                  <TdC><span className="mono" style={{ fontSize: 10.5, color: "var(--fg-3)" }}>{_cliRel(p.last_activity_at)}</span></TdC>
                </tr>
                {openEcon === key && (
                  <tr><td colSpan={12} style={{ padding: 0, background: "var(--surface-2)" }}>
                    <EconomicsEditor
                      econ={p.economics || {}}
                      onClose={() => setOpenEcon(null)}
                      onSave={(patch) => save(p, { economics: patch })}
                    />
                  </td></tr>
                )}
                </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="hint" style={{ marginTop: 12 }}>
        Provider-only commercial metadata — never client content, never their orgs' Red Coins. New clients appear automatically.
      </div>
    </div>
  );
}

// Inline-editable monthly fee. Commits on blur / Enter.
function FeeCell({ value, onSave }) {
  const [v, setV] = React.useState(String(value ?? 0));
  React.useEffect(() => { setV(String(value ?? 0)); }, [value]);
  const commit = () => {
    const n = parseFloat(v);
    if (Number.isFinite(n) && n !== Number(value)) onSave(n);
  };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
      <span className="muted" style={{ fontSize: 11 }}>$</span>
      <input
        type="number" min="0" step="0.5" value={v}
        onChange={(e) => setV(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); }}
        style={{ width: 64, textAlign: "right", padding: "4px 6px", borderRadius: 6,
                 background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
                 color: "var(--fg)", fontFamily: "var(--f-mono)", fontSize: 12 }}
      />
    </span>
  );
}

// Per-client Red Coins economics editor (shown in an expanded table row).
function EconomicsEditor({ econ, onSave, onClose }) {
  const [v, setV] = React.useState(() => ({ ...econ }));
  const [busy, setBusy] = React.useState(false);
  const set = (k) => (e) => setV((s) => ({ ...s, [k]: e.target.value }));

  const num = (k) => parseFloat(v[k]);
  // Live preview: what a MEDIUM poster will cost an org under these values.
  const sample = Math.max(1, Math.round((num("base_cost_per_poster_usd") || 0) * (num("poster_markup") || 0) * (num("tokens_per_usd") || 0)));

  const save = async () => {
    setBusy(true);
    const patch = {};
    for (const f of ECON_FIELDS) {
      const n = parseFloat(v[f.k]);
      if (Number.isFinite(n)) patch[f.k] = n;
    }
    try { await onSave(patch); onClose(); } finally { setBusy(false); }
  };

  return (
    <div style={{ padding: 16 }}>
      <div className="eyebrow" style={{ marginBottom: 4 }}>Red Coins economics — how this client prices their orgs</div>
      <div className="hint" style={{ marginTop: 0, marginBottom: 12 }}>
        Changes apply to every estimate, charge, grant and top-up for this client. Defaults match the standard plan.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 14 }}>
        {ECON_FIELDS.map((f) => (
          <div key={f.k}>
            <div className="label" style={{ marginBottom: 4 }}>{f.label}</div>
            <input className="input" type="number" step={f.step} value={v[f.k] ?? ""} onChange={set(f.k)} disabled={busy} />
            <div className="hint" style={{ marginTop: 4 }}>{f.help}</div>
          </div>
        ))}
      </div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center", marginTop: 16, flexWrap: "wrap", gap: 10 }}>
        <span className="mono" style={{ fontSize: 11.5, color: "var(--fg-3)" }}>
          Preview: a medium poster ≈ <b style={{ color: "var(--crim)" }}>{sample.toLocaleString()} RC</b> for the org
        </span>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save economics"}</button>
        </div>
      </div>
    </div>
  );
}

function StatCardC({ label, value, hint, accent }) {
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="eyebrow" style={{ fontSize: 10 }}>{label}</div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 30, marginTop: 8, lineHeight: 1, color: accent ? "var(--crim)" : "var(--fg)" }}>{value}</div>
      <div className="mono" style={{ fontSize: 11, marginTop: 8, color: "var(--fg-4)" }}>{hint}</div>
    </div>
  );
}
function ThC({ children, numeric }) {
  return <th style={{ padding: "10px 12px", fontWeight: 600, fontSize: 10.5, letterSpacing: "0.06em", textTransform: "uppercase", textAlign: numeric ? "right" : "left", whiteSpace: "nowrap" }}>{children}</th>;
}
function TdC({ children, numeric }) {
  return <td style={{ padding: "10px 12px", textAlign: numeric ? "right" : "left", verticalAlign: "middle", whiteSpace: "nowrap" }}>{children}</td>;
}

Object.assign(window, { Clients });
