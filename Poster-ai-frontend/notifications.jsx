// notifications.jsx — global notification center + background job watcher.
//
// Three pieces:
//   1. window.notifications — a tiny persisted store (localStorage) that any
//      code can push to, mirroring the window.toast pattern.
//   2. <NotificationBell navigate={...} /> — the topbar bell: unread badge +
//      a dropdown list. Clicking an item opens the related poster.
//   3. <JobWatcher /> — mounted once in <Shell>, polls the user's jobs on
//      EVERY route. When a job finishes (or fails) it fires a 2s toast and
//      drops a notification, so the user gets told even after navigating away.

(function () {
  const KEY = "epai_notifications_v1";
  const MAX = 30;
  const listeners = new Set();

  const load = () => {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (_) { return []; }
  };

  let state = load();

  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state.slice(0, MAX))); } catch (_) {} };
  const emit = () => listeners.forEach((fn) => fn(state));

  window.notifications = {
    get: () => state,
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    add({ title, body, jobId, status }) {
      const n = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        title: String(title || ""),
        body: String(body || ""),
        jobId: jobId || null,
        status: status || null,
        ts: Date.now(),
        read: false,
      };
      state = [n, ...state].slice(0, MAX);
      save(); emit();
      return n;
    },
    markRead(id) { state = state.map((n) => (n.id === id ? { ...n, read: true } : n)); save(); emit(); },
    markAllRead() { state = state.map((n) => ({ ...n, read: true })); save(); emit(); },
    remove(id) { state = state.filter((n) => n.id !== id); save(); emit(); },
    clear() { state = []; save(); emit(); },
  };
})();


function useNotifications() {
  const [items, setItems] = React.useState(() => window.notifications.get());
  React.useEffect(() => window.notifications.subscribe(setItems), []);
  return items;
}


function _notifTimeAgo(ts) {
  const s = Math.max(1, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}


function NotificationBell({ navigate }) {
  const items = useNotifications();
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  const unread = items.filter((n) => !n.read).length;

  // Close on outside click + Escape.
  React.useEffect(() => {
    if (!open) return;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("mousedown", onDown); window.removeEventListener("keydown", onKey); };
  }, [open]);

  const openItem = (n) => {
    window.notifications.markRead(n.id);
    setOpen(false);
    if (n.jobId) navigate(n.status === "failed" ? `#/job/${n.jobId}` : `#/result/${n.jobId}`);
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div className="icon-btn" onClick={() => setOpen((o) => !o)} title="Notifications" style={{ position: "relative" }}>
        <Icon name="bell" />
        {unread > 0 && (
          <span style={{
            position: "absolute", top: -2, right: -2,
            minWidth: 16, height: 16, padding: "0 4px", borderRadius: 999,
            background: "var(--crim)", color: "#fff", fontSize: 9.5, fontWeight: 700,
            display: "flex", alignItems: "center", justifyContent: "center", lineHeight: 1,
            boxShadow: "0 0 0 2px var(--bg)",
          }}>{unread > 9 ? "9+" : unread}</span>
        )}
      </div>

      {open && (
        <div className="card" style={{
          position: "absolute", top: "calc(100% + 10px)", right: 0,
          width: 330, maxHeight: 440, overflow: "auto", padding: 0, zIndex: 1500,
          boxShadow: "0 24px 70px -24px rgba(0,0,0,0.65)",
          animation: "notif-pop 150ms ease-out",
        }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center", padding: "12px 14px", borderBottom: "1px solid var(--line)", position: "sticky", top: 0, background: "var(--surface)" }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>Notifications</span>
            {items.length > 0 && (
              <div className="row" style={{ gap: 4 }}>
                <button className="btn btn-ghost" style={{ padding: "2px 8px", fontSize: 11 }} onClick={() => window.notifications.markAllRead()}>Mark all read</button>
                <button className="btn btn-ghost" style={{ padding: "2px 8px", fontSize: 11 }} onClick={() => window.notifications.clear()}>Clear</button>
              </div>
            )}
          </div>

          {items.length === 0 ? (
            <div style={{ padding: "28px 16px", textAlign: "center", color: "var(--fg-3)", fontSize: 12.5 }}>
              No notifications yet.
            </div>
          ) : items.map((n) => (
            <div key={n.id} onClick={() => openItem(n)} style={{
              padding: "11px 14px", borderBottom: "1px solid var(--line)",
              cursor: n.jobId ? "pointer" : "default",
              background: n.read ? "transparent" : "var(--crim-soft)",
              display: "flex", gap: 10, alignItems: "flex-start",
            }}>
              <div style={{
                width: 30, height: 30, borderRadius: 7, flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: n.status === "failed" ? "var(--crim-soft)" : "var(--cy-soft)",
                color: n.status === "failed" ? "var(--crim)" : "var(--cy)",
              }}>
                <Icon name={n.status === "failed" ? "cross" : "sparkles"} size={14} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600 }}>{n.title}</div>
                {n.body && <div style={{ fontSize: 11.5, color: "var(--fg-2)", marginTop: 2, wordBreak: "break-word" }}>{n.body}</div>}
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", marginTop: 4, letterSpacing: "0.04em" }}>
                  {_notifTimeAgo(n.ts)}{n.jobId ? " · click to view" : ""}
                </div>
              </div>
              {!n.read && <span style={{ width: 7, height: 7, borderRadius: 999, background: "var(--crim)", flexShrink: 0, marginTop: 5 }} />}
            </div>
          ))}

          <style>{`@keyframes notif-pop { 0% { opacity: 0; transform: translateY(-6px) scale(0.98); } 100% { opacity: 1; transform: translateY(0) scale(1); } }`}</style>
        </div>
      )}
    </div>
  );
}


// Polls the user's jobs on every route and announces transitions to a terminal
// state. Renders nothing. One instance lives in <Shell>.
function JobWatcher({ navigate }) {
  const watchRef = React.useRef({}); // { [jobId]: lastStatus }

  React.useEffect(() => {
    const ACTIVE = new Set(["queued", "generating_prompt", "generating_poster", "applying_sponsor_bar"]);
    const orgId = (window.api && window.api.orgId) || "1";
    // Use the app router when available; fall back to the hash directly so the
    // toast/notification clicks still work if navigate wasn't passed.
    const go = (h) => {
      if (typeof navigate === "function") navigate(h);
      else window.location.hash = h.replace(/^#/, "");
    };
    let cancelled = false;

    const poll = async () => {
      let jobs;
      try {
        const data = await window.api.listPosters({ orgId, limit: 30 });
        jobs = (data && data.jobs) || [];
      } catch (_) {
        return; // network blip — try again next tick
      }
      if (cancelled) return;

      const watch = watchRef.current;
      for (const j of jobs) {
        const prev = watch[j.job_id];
        if (ACTIVE.has(j.status)) {
          watch[j.job_id] = j.status;
        } else if (j.status === "completed" || j.status === "failed") {
          // Only announce a job we previously saw IN PROGRESS — never the
          // already-finished jobs sitting in history when the page first loads.
          const wasActive = prev && prev !== "completed" && prev !== "failed";
          if (wasActive) {
            if (j.status === "completed") {
              // A completed poster just spent Red Coins — refresh the balance pill.
              window.dispatchEvent(new Event("epai:coins-changed"));
              window.toast.success("Your poster is ready 🎉", {
                ttl: 2000,
                onClick: () => go(`#/result/${j.job_id}`),
              });
              window.notifications.add({
                title: "Poster ready",
                body: `${j.tournament_id || "Your poster"} finished generating.`,
                jobId: j.job_id,
                status: "completed",
              });
            } else {
              window.toast.error("A poster failed to generate.", {
                ttl: 2000,
                onClick: () => go(`#/job/${j.job_id}`),
              });
              window.notifications.add({
                title: "Poster failed",
                body: j.error ? String(j.error).slice(0, 140) : `${j.tournament_id || "Your poster"} failed to generate.`,
                jobId: j.job_id,
                status: "failed",
              });
            }
          }
          watch[j.job_id] = j.status; // remember terminal so we don't re-announce
        }
      }

      // Keep the watch map bounded to the jobs currently in the recent list.
      const seen = new Set(jobs.map((j) => j.job_id));
      for (const k of Object.keys(watch)) if (!seen.has(k)) delete watch[k];
    };

    poll();
    const t = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  return null;
}


Object.assign(window, { NotificationBell, JobWatcher, useNotifications });
