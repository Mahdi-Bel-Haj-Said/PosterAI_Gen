// shell.jsx — App shell: Sidebar + TopBar + Icons

const Icon = ({ name, size = 16 }) => {
  const paths = {
    home: <><path d="M3 9.5 10 3l7 6.5"/><path d="M5 9v8h10V9"/></>,
    plus: <><path d="M10 4v12M4 10h12"/></>,
    sparkles: <><path d="M10 3l1.6 4.4L16 9l-4.4 1.6L10 15l-1.6-4.4L4 9l4.4-1.6z"/><path d="M15 13l.7 1.8L17.5 15.5 15.7 16.2 15 18l-.7-1.8L12.5 15.5 14.3 14.8z"/></>,
    layers: <><path d="M10 3 3 7l7 4 7-4-7-4z"/><path d="M3 12l7 4 7-4"/></>,
    image: <><rect x="3" y="3" width="14" height="14" rx="2"/><circle cx="7.5" cy="7.5" r="1.5"/><path d="M17 13l-4-4-7 8"/></>,
    trophy: <><path d="M6 4h8v3a4 4 0 0 1-8 0V4z"/><path d="M3 5h3v2a2 2 0 0 1-2-2H3zM14 5h3v0a2 2 0 0 1-2 2V5z"/><path d="M8 12v2H7v2h6v-2h-1v-2"/></>,
    key: <><circle cx="6" cy="10" r="3"/><path d="M9 10h8M14 10v3M17 10v2"/></>,
    chart: <><path d="M3 17V3M3 17h14"/><path d="M6 14V9M10 14V5M14 14v-3"/></>,
    bell: <><path d="M10 3a4 4 0 0 0-4 4v3l-2 3h12l-2-3V7a4 4 0 0 0-4-4z"/><path d="M8 16a2 2 0 0 0 4 0"/></>,
    chat: <path d="M3 4h14v9H8l-4 3v-3H3z"/>,
    search: <><circle cx="9" cy="9" r="5"/><path d="M13 13l4 4"/></>,
    download: <><path d="M10 3v10M5 9l5 5 5-5"/><path d="M3 17h14"/></>,
    link: <><path d="M8 6h-2a4 4 0 0 0 0 8h2M12 14h2a4 4 0 0 0 0-8h-2"/><path d="M7 10h6"/></>,
    arrow_right: <path d="M4 10h12M11 5l5 5-5 5"/>,
    arrow_left: <path d="M16 10H4M9 5 4 10l5 5"/>,
    check: <path d="M4 10l4 4 8-9"/>,
    cross: <path d="M5 5l10 10M15 5L5 15"/>,
    upload: <><path d="M10 13V3M5 8l5-5 5 5"/><path d="M3 17h14"/></>,
    play: <path d="M5 4l11 6-11 6z"/>,
    edit: <><path d="M13 4l3 3-9 9H4v-3z"/></>,
    settings: <><circle cx="10" cy="10" r="2"/><path d="M10 1v3M10 16v3M3.5 6.5l2-2M14.5 15.5l2-2M1 10h3M16 10h3M3.5 13.5l2 2M14.5 4.5l2-2"/></>,
    sponsor: <><rect x="3" y="6" width="14" height="8" rx="1"/><path d="M3 10h14"/></>,
    user: <><circle cx="10" cy="7" r="3"/><path d="M3 17a7 7 0 0 1 14 0"/></>,
    calendar: <><rect x="3" y="4" width="14" height="13" rx="1"/><path d="M3 8h14M7 2v4M13 2v4"/></>,
    clock: <><circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/></>,
    bolt: <path d="M11 2 4 11h5l-1 7 7-9h-5z"/>,
    chevron_down: <path d="M5 8l5 5 5-5"/>,
    chevron_right: <path d="M8 5l5 5-5 5"/>,
    dots: <><circle cx="5" cy="10" r="1"/><circle cx="10" cy="10" r="1"/><circle cx="15" cy="10" r="1"/></>,
    grid: <><rect x="3" y="3" width="6" height="6"/><rect x="11" y="3" width="6" height="6"/><rect x="3" y="11" width="6" height="6"/><rect x="11" y="11" width="6" height="6"/></>,
    target: <><circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="3"/></>,
    refresh: <><path d="M16 5v4h-4"/><path d="M4 11a6 6 0 0 0 11 3l1-2"/><path d="M4 15v-4h4"/><path d="M16 9a6 6 0 0 0-11-3L4 8"/></>,
    copy: <><rect x="6" y="6" width="11" height="11" rx="1"/><path d="M14 6V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h2"/></>,
    twitter: <path d="M3 3l6.5 8.5L3.4 17h1.9l5.1-5.4 4 5.4H17l-6.8-9 6.3-8h-1.9L9.9 9.7 5.6 3z" fill="currentColor" stroke="none"/>,
    facebook: <path d="M12.5 17v-6h2l.3-2.5H12.5V7c0-.7.2-1.2 1.2-1.2h1.3V3.6c-.2 0-1-.1-1.9-.1-1.9 0-3.2 1.2-3.2 3.3v1.7H7.5V11h2.4v6z" fill="currentColor" stroke="none"/>,
    instagram: <><rect x="3" y="3" width="14" height="14" rx="4"/><circle cx="10" cy="10" r="3.5"/><circle cx="14.3" cy="5.7" r="0.7" fill="currentColor" stroke="none"/></>,
    // Filled 5-point star. Rendered solid (fill=currentColor) so the rating UI
    // can toggle "active vs inactive" purely by changing the wrapper's color
    // (bright accent vs dim grey) instead of swapping two icon variants.
    star: <path d="M10 2.2l2.36 4.78 5.27.77-3.81 3.72.9 5.25L10 14.25 5.28 16.72l.9-5.25-3.81-3.72 5.27-.77z" fill="currentColor" stroke="currentColor" strokeWidth="0.5"/>,
    expand: <path d="M8 4H4v4M12 4h4v4M16 12v4h-4M8 16H4v-4"/>,
    coins: <><ellipse cx="8" cy="6" rx="5" ry="2.4"/><path d="M3 6v4c0 1.3 2.2 2.4 5 2.4s5-1.1 5-2.4V6"/><path d="M9 13.6c.6 1 2.5 1.8 4.5 1.8 2.8 0 5-1.1 5-2.4v-4c0-1-1.3-1.9-3.2-2.2"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none"
         stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  );
};

const NAV = [
  { group: "Workspace", items: [
    { id: "dashboard", label: "Dashboard", icon: "home", route: "#/" },
    { id: "create",    label: "Create poster", icon: "sparkles", route: "#/create", accent: true },
    { id: "history",   label: "History",   icon: "layers", route: "#/history", badge: "247" },
    { id: "billing",   label: "Plans & billing", icon: "coins", route: "#/billing" },
    { id: "settings",  label: "Settings", icon: "settings", route: "#/settings" },
  ]},
  { group: "Library", items: [
    { id: "brand",     label: "Brand library", icon: "image", route: "#/brand" },
  ]},
  { group: "Admin", items: [
    { id: "clients",   label: "Clients",    icon: "user",  route: "#/admin/clients" },
    { id: "usage",     label: "Usage & billing", icon: "chart", route: "#/admin/usage" },
    { id: "metrics",   label: "Content metrics", icon: "chart", route: "#/admin/metrics" },
  ]},
];

function Sidebar({ route, navigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="mark" />
        <div>
          <div className="name">POSTER<span style={{ color: "var(--crim)" }}>/AI</span></div>
          <div className="sub">by defendr</div>
        </div>
      </div>

      {NAV.map((group) => (
        <React.Fragment key={group.group}>
          <div className="nav-section">{group.group}</div>
          {group.items.map((item) => {
            const active = route.startsWith(item.route.replace("#", "")) && (item.route !== "#/" || route === "/");
            return (
              <div key={item.id}
                   className={"nav-item" + (active ? " active" : "")}
                   onClick={() => navigate(item.route)}>
                <span className="ico" style={item.accent && !active ? { color: "var(--crim)" } : undefined}>
                  <Icon name={item.icon} />
                </span>
                <span>{item.label}</span>
                {item.badge && <span className="right">{item.badge}</span>}
                {item.accent && !active && <span className="right" style={{ color: "var(--cy)" }}>NEW</span>}
              </div>
            );
          })}
        </React.Fragment>
      ))}

      <div className="org-card">
        <div className="org-avatar">RG</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="org-name">Riot Gauntlet</div>
          <div className="org-role">Organizer · Pro</div>
        </div>
        <Icon name="chevron_down" size={14} />
      </div>
    </aside>
  );
}

function NavQuota() {
  const orgId = (window.api && window.api.orgId) || "1";
  const [quotas, setQuotas] = React.useState([]);
  React.useEffect(() => {
    let cancelled = false;
    const tick = () => window.api.getQuota({ orgId })
      .then((q) => { if (!cancelled) setQuotas(Array.isArray(q) ? q : []); })
      .catch(() => { /* non-fatal — chips just disappear */ });
    tick();
    const t = setInterval(tick, 10000);
    return () => { cancelled = true; clearInterval(t); };
  }, [orgId]);

  if (!quotas.length) return null;

  const LABEL = { day: "D", week: "W", month: "M" };
  const FULL  = { day: "24h window", week: "7-day window", month: "30-day window" };

  const pill = (q) => {
    const full = q.remaining <= 0;
    const high = !full && q.remaining <= Math.max(1, Math.floor(q.limit * 0.2));
    const tone = full ? "var(--crim)" : high ? "#FFD24B" : "var(--ok)";
    const pct = q.limit > 0 ? Math.min(100, Math.round((q.used / q.limit) * 100)) : 0;
    const resetLabel = q.reset_at ? new Date(q.reset_at).toLocaleString() : "—";
    const title = `${FULL[q.window]} — ${q.used}/${q.limit} used. ${full ? "Next slot frees up" : "Resets"}: ${resetLabel}`;
    return (
      <div key={q.window} title={title}
           style={{
             display: "flex", alignItems: "center", gap: 6,
             padding: "4px 8px 4px 6px", borderRadius: 999,
             background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
           }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: tone, flexShrink: 0 }} />
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.06em" }}>
          {LABEL[q.window] || q.window.toUpperCase()}
        </span>
        <span className="mono" style={{ fontSize: 11, color: full ? "var(--crim)" : "var(--fg)" }}>
          {q.used}<span style={{ color: "var(--fg-4)" }}>/{q.limit}</span>
        </span>
        <div style={{ width: 24, height: 3, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden" }}>
          <div style={{ height: "100%", width: pct + "%", background: tone, transition: "width .25s" }} />
        </div>
      </div>
    );
  };

  return <div style={{ display: "flex", gap: 6 }}>{quotas.map(pill)}</div>;
}

// Red Coins balance pill in the topbar. Polls so it reflects spends + grants.
function CoinBalance() {
  const [bal, setBal] = React.useState(null);
  React.useEffect(() => {
    let cancelled = false;
    const orgId = (window.api && window.api.orgId) || "1";
    const tick = () => window.api.getCoins({ orgId })
      .then((c) => { if (!cancelled && c && typeof c.balance === "number") setBal(c.balance); })
      .catch(() => { /* non-fatal */ });
    tick();
    const t = setInterval(tick, 10000);
    const onChange = () => tick();
    window.addEventListener("epai:coins-changed", onChange);
    return () => { cancelled = true; clearInterval(t); window.removeEventListener("epai:coins-changed", onChange); };
  }, []);
  if (bal == null) return null;
  return (
    <div title="Red Coins — open billing" onClick={() => { window.location.hash = "/billing"; }} style={{
      display: "flex", alignItems: "center", gap: 7,
      padding: "7px 12px", borderRadius: 999, cursor: "pointer",
      background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
    }}>
      <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--crim)", boxShadow: "0 0 6px var(--crim)", flexShrink: 0 }} />
      <span style={{ fontFamily: "var(--f-display)", fontSize: 14 }}>{bal.toLocaleString()}</span>
      <span className="mono" style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.08em" }}>{coinSym()}</span>
    </div>
  );
}

function TopBar({ crumbs, navigate }) {
  return (
    <div className="topbar">
      <div className="crumbs">
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="sep">/</span>}
            <span className={i === crumbs.length - 1 ? "here" : ""}>{c}</span>
          </React.Fragment>
        ))}
      </div>
      <div style={{ flex: 1 }} />
      <CoinBalance />
      <NavQuota />
      <div className="icon-btn"><Icon name="search" /></div>
      <NotificationBell navigate={navigate} />
      <div className="icon-btn"><Icon name="settings" /></div>
      <div style={{ width: 1, height: 24, background: "var(--line)" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
        <div className="org-avatar" style={{ width: 30, height: 30, fontSize: 12,
             background: "linear-gradient(135deg, oklch(60% 0.20 30), oklch(50% 0.20 350))" }}>MA</div>
      </div>
    </div>
  );
}

function Shell({ route, navigate, crumbs, children }) {
  return (
    <div className="app">
      <Sidebar route={route} navigate={navigate} />
      <div className="col" style={{ minWidth: 0 }}>
        <TopBar crumbs={crumbs} navigate={navigate} />
        <div className="main">{children}</div>
      </div>
      {/* Global notification stack — anything in the app pushes via
          window.toast.error / .success / .info; the stack is fixed
          top-right and overlays every route. */}
      <Toaster />
      {/* Background watcher: polls jobs on every route and fires a toast +
          notification when one finishes, so the user is told even after
          navigating away from the job page. Renders nothing. */}
      <JobWatcher navigate={navigate} />
    </div>
  );
}

Object.assign(window, { Icon, Sidebar, TopBar, Shell });
