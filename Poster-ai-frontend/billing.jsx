// billing.jsx — Plans & billing: pick a subscription or buy Red Coins.
//
// The payment step is a STATIC form for now (no provider wired). Confirming
// just calls the backend, which applies the plan / credits the coins in test
// mode. Swap PaymentModal's onConfirm internals for the real charge later.

// Fallback plan defaults. The client's own tier labels/prices (from config)
// and grants (from economics) override name / price / coins at render time.
const PLAN_DEFAULTS = [
  { id: "free",   name: "Free",   price: 0,  coins: 1500,   blurb: "Kick the tyres.",
    perks: ["Standard generation", "Community support"] },
  { id: "pro",    name: "Pro",    price: 3,  coins: 30000,  blurb: "For regular creators.", highlight: true,
    perks: ["All quality tiers", "Priority queue"] },
  { id: "kratos", name: "Kratos", price: 10, coins: 100000, blurb: "For teams & orgs.",
    perks: ["Everything in Pro", "Brand library + Style DNA"] },
];

// Default coin pack sizes; price is computed from the client's top-up rate.
const COIN_PACK_SIZES = [10000, 30000, 100000];
const DEFAULT_TOPUP_USD_PER_10K = 0.80;
// Custom-amount bounds (Red Coins).
const CUSTOM_MIN = 0;
const CUSTOM_MAX = 100000;
const CUSTOM_STEP = 1000;

function _fmt(n) { return Math.round(n || 0).toLocaleString(); }
function coinsToUsd(coins, rate) { return (coins / 10000) * (rate != null ? rate : DEFAULT_TOPUP_USD_PER_10K); }
function clampCoins(n) {
  if (!Number.isFinite(n)) return CUSTOM_MIN;
  return Math.max(CUSTOM_MIN, Math.min(CUSTOM_MAX, Math.round(n / CUSTOM_STEP) * CUSTOM_STEP));
}

function Billing({ navigate }) {
  const orgId = (window.api && window.api.orgId) || "1";
  const [wallet, setWallet] = React.useState(null);   // { balance, tier, ... }
  const [cfg, setCfg] = React.useState(null);          // this client's config (tiers, economics)
  const [pay, setPay] = React.useState(null);          // active payment intent or null
  const [customCoins, setCustomCoins] = React.useState(20000);  // custom top-up amount

  const refresh = React.useCallback(() => {
    window.api.getCoins({ orgId })
      .then((c) => setWallet(c || null))
      .catch(() => { /* non-fatal */ });
  }, [orgId]);

  React.useEffect(() => { refresh(); }, [refresh]);
  React.useEffect(() => { window.api.getMyConfig().then(setCfg).catch(() => {}); }, []);

  const currentTier = wallet ? wallet.tier : null;

  // Plans, grants, and top-up rate come from THIS client's config (fallbacks if absent).
  const econ = (cfg && cfg.economics) || {};
  const tiersCfg = (cfg && cfg.tiers) || {};
  const topupRate = econ.topup_usd_per_10k != null ? econ.topup_usd_per_10k : DEFAULT_TOPUP_USD_PER_10K;
  const plans = PLAN_DEFAULTS.map((p) => ({
    ...p,
    name: (tiersCfg[p.id] && tiersCfg[p.id].label) || p.name,
    price: (tiersCfg[p.id] && tiersCfg[p.id].price_usd != null) ? tiersCfg[p.id].price_usd : p.price,
    coins: econ[`${p.id}_grant`] != null ? econ[`${p.id}_grant`] : p.coins,
  }));

  // Build the payment intents the modal acts on.
  const subscribeIntent = (plan) => ({
    kind: "subscription",
    title: `Subscribe to ${plan.name}`,
    amount: plan.price,
    summary: `${plan.name} plan · ${_fmt(plan.coins)} ${coinName()} / month`,
    run: async () => {
      const res = await window.api.subscribePlan({ orgId, tier: plan.id });
      return `You're on ${plan.name}. Balance: ${_fmt(res.balance)} ${coinSym()}.`;
    },
  });
  const buyCoinsIntent = (coins) => ({
    kind: "topup",
    title: `Buy ${coinName()}`,
    amount: coinsToUsd(coins, topupRate),
    summary: `${_fmt(coins)} ${coinName()}`,
    run: async () => {
      const res = await window.api.purchaseCoins({ orgId, tokens: coins });
      return `Added ${_fmt(coins)} ${coinSym()}. Balance: ${_fmt(res.balance)} ${coinSym()}.`;
    },
  });

  const onPaid = (message) => {
    setPay(null);
    refresh();
    window.dispatchEvent(new Event("epai:coins-changed"));
    window.toast.success(message || "Payment confirmed.");
  };

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>WORKSPACE · BILLING</div>
          <h1>Plans &amp; {coinName()}</h1>
          <p>Pick a monthly plan, or top up {coinName()} any time.</p>
        </div>
        <div className="row" style={{ gap: 10, alignItems: "center" }}>
          {wallet && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 14px", borderRadius: 999, background: "var(--bg-elev)", border: "1px solid var(--line-strong)" }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--crim)", boxShadow: "0 0 6px var(--crim)" }} />
              <span style={{ fontFamily: "var(--f-display)", fontSize: 16 }}>{_fmt(wallet.balance)}</span>
              <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.08em" }}>{coinSym()}</span>
            </div>
          )}
        </div>
      </div>

      {/* Plans */}
      <div className="eyebrow" style={{ marginBottom: 12 }}>Subscription</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 32 }}>
        {plans.map((p) => {
          const current = currentTier === p.id;
          return (
            <div key={p.id} className="card" style={{
              padding: 22, position: "relative", overflow: "hidden",
              borderColor: p.highlight ? "var(--cy-line)" : "var(--line)",
              outline: current ? "2px solid var(--crim)" : "none", outlineOffset: -1,
              background: p.highlight ? "linear-gradient(150deg, var(--surface), oklch(15% 0.04 195))" : "var(--surface)",
            }}>
              {p.highlight && (
                <span className="mono" style={{ position: "absolute", top: 14, right: 14, fontSize: 9.5, letterSpacing: "0.1em", color: "var(--cy)", border: "1px solid var(--cy-line)", borderRadius: 999, padding: "2px 7px" }}>POPULAR</span>
              )}
              <div style={{ fontFamily: "var(--f-display)", fontSize: 22 }}>{p.name}</div>
              <div className="hint" style={{ marginTop: 2, marginBottom: 14 }}>{p.blurb}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 4 }}>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 34 }}>${p.price}</span>
                <span className="muted" style={{ fontSize: 13 }}>/ month</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 16 }}>
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--crim)" }} />
                <span style={{ fontSize: 13, color: "var(--fg-2)" }}>{_fmt(p.coins)} {coinSym()} / month</span>
              </div>
              <div className="col" style={{ gap: 8, marginBottom: 18 }}>
                {p.perks.map((f) => (
                  <div key={f} className="row" style={{ gap: 8, fontSize: 12.5, color: "var(--fg-2)" }}>
                    <Icon name="check" size={13} /> {f}
                  </div>
                ))}
              </div>
              {current ? (
                <button className="btn btn-ghost" style={{ width: "100%" }} disabled>
                  <Icon name="check" size={14} /> Current plan
                </button>
              ) : (
                <button
                  className={p.highlight ? "btn btn-ai" : "btn btn-primary"}
                  style={{ width: "100%" }}
                  onClick={() => (p.price === 0
                    ? window.api.subscribePlan({ orgId, tier: p.id }).then(() => onPaid(`Switched to ${p.name}.`)).catch((e) => window.toast.error(e.message))
                    : setPay(subscribeIntent(p)))}
                >
                  {p.price === 0 ? "Switch to Free" : `Upgrade to ${p.name}`}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Coin packs */}
      <div className="eyebrow" style={{ marginBottom: 12 }}>Buy {coinName()}</div>
      <div className="hint" style={{ marginTop: -4, marginBottom: 12 }}>
        Top up any time — ${topupRate.toFixed(2)} per 10,000 {coinName()}. Added on top of your monthly balance.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        {COIN_PACK_SIZES.map((coins) => (
          <div key={coins} className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="row" style={{ alignItems: "center", gap: 8 }}>
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: "var(--crim)", boxShadow: "0 0 8px var(--crim)" }} />
              <span style={{ fontFamily: "var(--f-display)", fontSize: 24 }}>{_fmt(coins)}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{coinSym()}</span>
            </div>
            <div className="muted" style={{ fontSize: 13 }}>${coinsToUsd(coins, topupRate).toFixed(2)} one-time</div>
            <button className="btn btn-primary" style={{ width: "100%" }} onClick={() => setPay(buyCoinsIntent(coins))}>
              <Icon name="plus" size={14} /> Buy
            </button>
          </div>
        ))}
      </div>

      {/* Custom amount — buy exactly what you want. */}
      <div className="card" style={{ padding: 20, marginTop: 16 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Custom amount</div>
          <div className="row" style={{ gap: 8, alignItems: "baseline" }}>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 22 }}>{_fmt(customCoins)}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>{coinSym()}</span>
            <span className="muted" style={{ fontSize: 13, marginLeft: 8 }}>= ${coinsToUsd(customCoins, topupRate).toFixed(2)}</span>
          </div>
        </div>
        <input
          type="range"
          min={CUSTOM_MIN} max={CUSTOM_MAX} step={CUSTOM_STEP}
          value={customCoins}
          onChange={(e) => setCustomCoins(clampCoins(parseInt(e.target.value, 10)))}
          style={{ width: "100%", accentColor: "var(--crim)" }}
        />
        <div className="row" style={{ gap: 10, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
          <input
            type="number"
            min={CUSTOM_MIN} max={CUSTOM_MAX} step={CUSTOM_STEP}
            value={customCoins}
            onChange={(e) => setCustomCoins(parseInt(e.target.value, 10) || 0)}
            onBlur={(e) => setCustomCoins(clampCoins(parseInt(e.target.value, 10)))}
            style={{ width: 140, boxSizing: "border-box", padding: "9px 12px", borderRadius: 8,
                     background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
                     color: "var(--fg)", fontFamily: "var(--f-mono)", fontSize: 13 }}
          />
          <span className="hint" style={{ margin: 0, flex: 1, minWidth: 160 }}>
            {_fmt(CUSTOM_MIN)}–{_fmt(CUSTOM_MAX)} {coinSym()} · ${topupRate.toFixed(2)} per 10,000.
          </span>
          <button className="btn btn-primary" style={{ minWidth: 160 }}
                  disabled={clampCoins(customCoins) <= 0}
                  onClick={() => setPay(buyCoinsIntent(clampCoins(customCoins)))}>
            <Icon name="plus" size={14} /> Buy {_fmt(clampCoins(customCoins))} {coinSym()}
          </button>
        </div>
      </div>

      {pay && <PaymentModal intent={pay} onPaid={onPaid} onClose={() => setPay(null)} />}
    </div>
  );
}

// Static checkout form. Collects card details for show, then calls intent.run()
// on confirm. No validation / no real charge — the seam for a payment provider.
function PaymentModal({ intent, onPaid, onClose }) {
  const [card, setCard] = React.useState({ name: "", number: "", exp: "", cvc: "" });
  const [busy, setBusy] = React.useState(false);
  const set = (k) => (e) => setCard((c) => ({ ...c, [k]: e.target.value }));

  React.useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const confirm = async () => {
    setBusy(true);
    try {
      const msg = await intent.run();
      onPaid(msg);
    } catch (e) {
      window.toast.error(e.message || "Payment failed.");
      setBusy(false);
    }
  };

  const field = { width: "100%", boxSizing: "border-box", padding: "10px 12px", borderRadius: 8,
                  background: "var(--bg-elev)", border: "1px solid var(--line-strong)", color: "var(--fg)",
                  fontFamily: "var(--f-body)", fontSize: 13 };

  return (
    <div onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}
      style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(8,8,10,0.72)", backdropFilter: "blur(4px)",
               display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div className="card" style={{ width: "min(100%, 440px)", padding: 24, position: "relative" }}>
        <button onClick={() => !busy && onClose()} className="btn btn-ghost" style={{ position: "absolute", top: 12, right: 12, padding: "4px 6px" }} title="Close (Esc)">
          <Icon name="cross" size={12} />
        </button>

        <div style={{ fontWeight: 600, fontSize: 16 }}>{intent.title}</div>
        <div className="hint" style={{ marginTop: 2, marginBottom: 4 }}>{intent.summary}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6, margin: "10px 0 16px" }}>
          <span style={{ fontFamily: "var(--f-display)", fontSize: 30 }}>${intent.amount.toFixed(2)}</span>
          {intent.kind === "subscription" && <span className="muted" style={{ fontSize: 13 }}>/ month</span>}
        </div>

        <div className="col" style={{ gap: 10 }}>
          <input style={field} placeholder="Name on card" value={card.name} onChange={set("name")} disabled={busy} />
          <input style={field} placeholder="Card number  ····  ····  ····  ····" value={card.number} onChange={set("number")} disabled={busy} />
          <div className="row" style={{ gap: 10 }}>
            <input style={{ ...field, flex: 1 }} placeholder="MM / YY" value={card.exp} onChange={set("exp")} disabled={busy} />
            <input style={{ ...field, flex: 1 }} placeholder="CVC" value={card.cvc} onChange={set("cvc")} disabled={busy} />
          </div>
        </div>

        <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", margin: "12px 0 16px", letterSpacing: "0.04em" }}>
          ● TEST MODE — no real charge. Confirming applies it instantly.
        </div>

        <div className="row" style={{ gap: 10 }}>
          <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => !busy && onClose()} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={confirm} disabled={busy}>
            {busy ? "Processing…" : <><Icon name="check" size={14} /> Confirm payment</>}
          </button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Billing });
