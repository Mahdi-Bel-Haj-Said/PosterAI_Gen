// settings.jsx — SELF-SERVE client configuration.
//
// The client (platform) edits their OWN setup here via GET/PATCH /v1/me/config:
// white-label branding, which features their orgs get, per-tier names/prices,
// per-org quota defaults, and the Red Coins economics. Commercial fields
// (service type, fee) are shown read-only — those belong to the provider.

const _QUALS = ["low", "medium", "high"];
const _TIER_IDS = ["free", "pro", "kratos"];

function Settings({ navigate }) {
  const [loaded, setLoaded] = React.useState(false);
  const [ro, setRo] = React.useState({});      // read-only (service_type, fee)
  const [b, setB] = React.useState({});        // branding
  const [f, setF] = React.useState({});        // features
  const [e, setE] = React.useState({});        // economics
  const [q, setQ] = React.useState({});        // quotas
  const [t, setT] = React.useState({});        // tiers
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    window.api.getMyConfig().then((c) => {
      setRo({ service_type: c.service_type, monthly_fee_usd: c.monthly_fee_usd });
      setB(c.branding || {}); setF(c.features || {}); setE(c.economics || {});
      setQ(c.quotas || {}); setT(c.tiers || {});
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  const setBk = (k) => (e2) => setB((s) => ({ ...s, [k]: e2.target.value }));
  const setFk = (k) => (e2) => setF((s) => ({ ...s, [k]: e2.target.checked }));
  const setEk = (k) => (e2) => setE((s) => ({ ...s, [k]: e2.target.value }));
  const setQk = (k) => (e2) => setQ((s) => ({ ...s, [k]: e2.target.value }));
  const setTier = (id, k) => (e2) => setT((s) => ({ ...s, [id]: { ...(s[id] || {}), [k]: e2.target.value } }));

  const toggleQual = (qy) => setF((s) => {
    const cur = new Set(s.allowed_qualities || _QUALS);
    if (cur.has(qy)) cur.delete(qy); else cur.add(qy);
    return { ...s, allowed_qualities: _QUALS.filter((x) => cur.has(x)) };
  });

  const numOrNull = (v) => (v === "" || v == null ? null : Number(v));

  const save = async () => {
    setBusy(true);
    try {
      const economics = {};
      for (const k of ["tokens_per_usd", "poster_markup", "base_cost_per_poster_usd", "topup_usd_per_10k", "free_grant", "pro_grant", "kratos_grant"]) {
        const n = parseFloat(e[k]); if (Number.isFinite(n)) economics[k] = n;
      }
      const quotas = { day: numOrNull(q.day), week: numOrNull(q.week), month: numOrNull(q.month) };
      const tiers = {};
      for (const id of _TIER_IDS) {
        if (t[id]) tiers[id] = { label: t[id].label || null, price_usd: numOrNull(t[id].price_usd) };
      }
      const cfg = await window.api.updateMyConfig({ branding: b, features: f, economics, quotas, tiers });
      // Adopt new branding immediately (coin label etc.).
      if (cfg && cfg.branding) {
        const r = document.documentElement;
        if (cfg.branding.accent_color) r.style.setProperty("--crim", cfg.branding.accent_color);
        if (cfg.branding.ai_accent_color) r.style.setProperty("--cy", cfg.branding.ai_accent_color);
      }
      window.toast.success("Settings saved.");
    } catch (err) {
      window.toast.error(err.message || "Save failed.");
    } finally { setBusy(false); }
  };

  if (!loaded) return <div className="card" style={{ padding: 32 }}>Loading settings…</div>;

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>WORKSPACE · SETTINGS</div>
          <h1>Integration settings</h1>
          <p>Configure your white-label branding, features, plans and Red Coins economics.</p>
        </div>
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          <Icon name="check" size={14} /> {busy ? "Saving…" : "Save changes"}
        </button>
      </div>

      {/* Plan (read-only — set by your provider) */}
      <Section title="Your plan" sub="Set by your provider — read-only.">
        <div className="row" style={{ gap: 24, flexWrap: "wrap" }}>
          <RO label="Service type" value={ro.service_type === "byok" ? "BYOK" : "Fully hosted"} />
          <RO label="Monthly fee" value={"$" + Number(ro.monthly_fee_usd || 0).toFixed(2)} />
        </div>
      </Section>

      {/* Branding */}
      <Section title="Branding" sub="White-label how the app looks to your orgs.">
        <Grid>
          <Fld label="Product name" help="Shown in the app header."><input className="input" value={b.product_name || ""} onChange={setBk("product_name")} placeholder="e.g. Acme Posters" /></Fld>
          <Fld label="Coin name" help="Full name of your token currency."><input className="input" value={b.coin_name || ""} onChange={setBk("coin_name")} placeholder="Red Coins" /></Fld>
          <Fld label="Coin symbol" help="Short label next to amounts."><input className="input" value={b.coin_symbol || ""} onChange={setBk("coin_symbol")} placeholder="RC" /></Fld>
          <Fld label="Logo URL" help="Link to your logo image."><input className="input" value={b.logo_url || ""} onChange={setBk("logo_url")} placeholder="https://…" /></Fld>
          <Fld label="Accent color" help="Primary brand color (hex)."><input className="input" value={b.accent_color || ""} onChange={setBk("accent_color")} placeholder="#E83A57" /></Fld>
          <Fld label="AI accent color" help="Secondary accent (hex)."><input className="input" value={b.ai_accent_color || ""} onChange={setBk("ai_accent_color")} placeholder="#3AC0E8" /></Fld>
        </Grid>
        <label className="row" style={{ gap: 8, marginTop: 12, fontSize: 13, cursor: "pointer" }}>
          <input type="checkbox" checked={b.powered_by !== false} onChange={(e2) => setB((s) => ({ ...s, powered_by: e2.target.checked }))} /> Show "powered by" mark
        </label>
      </Section>

      {/* Features */}
      <Section title="Features" sub="Turn capabilities on/off for your orgs.">
        <div className="row" style={{ gap: 18, flexWrap: "wrap" }}>
          {[["consistency","Consistency (Style DNA)"],["refine","Refine"],["sponsor_bar","Sponsor bar"],["caption","Captions"],["social","Social posting"],["background_upload","Background upload"]].map(([k, lbl]) => (
            <label key={k} className="row" style={{ gap: 8, fontSize: 13, cursor: "pointer" }}>
              <input type="checkbox" checked={f[k] !== false} onChange={setFk(k)} /> {lbl}
            </label>
          ))}
        </div>
        <div style={{ marginTop: 14 }}>
          <div className="label" style={{ marginBottom: 6 }}>Allowed quality tiers</div>
          <div className="row" style={{ gap: 16 }}>
            {_QUALS.map((qy) => (
              <label key={qy} className="row" style={{ gap: 8, fontSize: 13, cursor: "pointer", textTransform: "capitalize" }}>
                <input type="checkbox" checked={(f.allowed_qualities || _QUALS).includes(qy)} onChange={() => toggleQual(qy)} /> {qy}
              </label>
            ))}
          </div>
        </div>
      </Section>

      {/* Plans / tiers */}
      <Section title="Plans" sub="Rename tiers and set what you charge your orgs. (Monthly coin grants are under Economics.)">
        <Grid>
          {_TIER_IDS.map((id) => (
            <div key={id} className="card" style={{ padding: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 8, textTransform: "capitalize" }}>{id}</div>
              <Fld label="Label" help="Display name for this plan."><input className="input" value={(t[id] && t[id].label) || ""} onChange={setTier(id, "label")} placeholder={id} /></Fld>
              <div style={{ height: 8 }} />
              <Fld label="Price to org ($/mo)" help="What you charge an org for this plan."><input className="input" type="number" step="0.5" value={(t[id] && t[id].price_usd) ?? ""} onChange={setTier(id, "price_usd")} /></Fld>
            </div>
          ))}
        </Grid>
      </Section>

      {/* Quotas */}
      <Section title="Per-org quotas" sub="Default rolling caps on completed posters. Leave blank for the service default.">
        <Grid>
          <Fld label="Per day" help="Max posters / 24h per org."><input className="input" type="number" value={q.day ?? ""} onChange={setQk("day")} /></Fld>
          <Fld label="Per week" help="Max posters / 7d per org."><input className="input" type="number" value={q.week ?? ""} onChange={setQk("week")} /></Fld>
          <Fld label="Per month" help="Max posters / 30d per org."><input className="input" type="number" value={q.month ?? ""} onChange={setQk("month")} /></Fld>
        </Grid>
      </Section>

      {/* Economics */}
      <Section title="Red Coins economics" sub="How you price and grant coins to your orgs.">
        <Grid>
          <Fld label="Tokens per $1" help="Coins equal to $1 of value (exchange rate)."><input className="input" type="number" step="100" value={e.tokens_per_usd ?? ""} onChange={setEk("tokens_per_usd")} /></Fld>
          <Fld label="Poster markup (×)" help="Multiplier on real cost → what the org pays (margin)."><input className="input" type="number" step="0.1" value={e.poster_markup ?? ""} onChange={setEk("poster_markup")} /></Fld>
          <Fld label="Base cost / poster ($)" help="Cost basis of a medium poster."><input className="input" type="number" step="0.001" value={e.base_cost_per_poster_usd ?? ""} onChange={setEk("base_cost_per_poster_usd")} /></Fld>
          <Fld label="Top-up $ per 10k" help="Price an org pays to buy 10,000 coins."><input className="input" type="number" step="0.05" value={e.topup_usd_per_10k ?? ""} onChange={setEk("topup_usd_per_10k")} /></Fld>
          <Fld label="Free grant" help="Monthly coins for Free orgs."><input className="input" type="number" step="100" value={e.free_grant ?? ""} onChange={setEk("free_grant")} /></Fld>
          <Fld label="Pro grant" help="Monthly coins for Pro orgs."><input className="input" type="number" step="1000" value={e.pro_grant ?? ""} onChange={setEk("pro_grant")} /></Fld>
          <Fld label="Kratos grant" help="Monthly coins for Kratos orgs."><input className="input" type="number" step="1000" value={e.kratos_grant ?? ""} onChange={setEk("kratos_grant")} /></Fld>
        </Grid>
        <div className="hint" style={{ marginTop: 10 }}>
          Preview: a medium poster ≈ <b style={{ color: "var(--crim)" }}>
          {Math.max(1, Math.round((parseFloat(e.base_cost_per_poster_usd) || 0) * (parseFloat(e.poster_markup) || 0) * (parseFloat(e.tokens_per_usd) || 0))).toLocaleString()} {b.coin_symbol || "RC"}</b> for an org.
        </div>
      </Section>

      <div className="row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          <Icon name="check" size={14} /> {busy ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}

function Section({ title, sub, children }) {
  return (
    <div className="card" style={{ padding: 20, marginBottom: 16 }}>
      <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
      {sub && <div className="hint" style={{ marginTop: 2, marginBottom: 14 }}>{sub}</div>}
      {children}
    </div>
  );
}
function Grid({ children }) {
  return <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 14 }}>{children}</div>;
}
function Fld({ label, help, children }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 4 }}>{label}</div>
      {children}
      {help && <div className="hint" style={{ marginTop: 4 }}>{help}</div>}
    </div>
  );
}
function RO({ label, value }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>{value}</div>
    </div>
  );
}

Object.assign(window, { Settings });
