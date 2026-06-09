// toast.jsx — lightweight top-right notification stack.
//
// One <Toaster /> instance mounts inside <Shell> so every route gets it.
// Anything in the app can push a toast via the global:
//
//   window.toast.error("Upload failed: ...")
//   window.toast.success("Saved!")
//   window.toast.info("Something happened.", { ttl: 4000 })
//
// Why not React context? Toasts are fired from event handlers and async
// .catch() blocks deep in components that have no business holding a
// context provider above them (or being class components). A single
// process-global API is the simplest thing that works and matches how
// the existing window.api and window.Icon are exposed.
//
// Toasts auto-dismiss after a type-dependent TTL (errors stay longer);
// the user can also click them to dismiss immediately. Stack is capped
// to 5 so a runaway loop can't paper the whole screen.

(function () {
  // The Toaster registers its setter here when it mounts; window.toast pushes
  // through it. Tearing it down (component unmount) sets this back to null so
  // late events become no-ops instead of crashes.
  let _push = null;

  const make = (type) => (message, opts = {}) => {
    if (!_push) {
      // Helpful in dev — surfaces "toast called before Toaster mounted" in
      // the console without throwing. Falls back to the browser's alert so
      // the user still sees something critical.
      console.warn("[toast] no Toaster mounted; falling back to console:", type, message);
      if (type === "error") {
        try { window.alert(message); } catch (_) {}
      }
      return;
    }
    _push({ type, message: String(message || ""), ttl: opts.ttl, mono: !!opts.mono });
  };

  window.toast = {
    error:   make("error"),
    success: make("success"),
    info:    make("info"),
    _register: (fn) => { _push = fn; },
    _unregister: () => { _push = null; },
  };
})();


// --- visual config ----------------------------------------------------------
// Color tokens use the existing CSS variables so the toaster matches whichever
// accent theme the user has picked via the tweaks panel.

const _TOAST_STYLES = {
  error:   { accent: "var(--crim)", bg: "var(--crim-soft, rgba(229,62,90,.15))", icon: "cross",    label: "Error",   ttl: 6000 },
  success: { accent: "var(--ok, #34c759)", bg: "rgba(52,199,89,0.12)",            icon: "check",    label: "Success", ttl: 3200 },
  info:    { accent: "var(--cy, #2dd4ff)",  bg: "var(--cy-soft, rgba(45,212,255,.12))", icon: "bell", label: "Info",    ttl: 4000 },
};


// --- component --------------------------------------------------------------

function Toaster() {
  const [toasts, setToasts] = React.useState([]);
  // Refs to per-toast timeout handles so we can clear them on manual dismiss
  // (prevents a phantom second removal once the TTL elapses).
  const timers = React.useRef({});

  const dismiss = React.useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    if (timers.current[id]) {
      clearTimeout(timers.current[id]);
      delete timers.current[id];
    }
  }, []);

  React.useEffect(() => {
    const handler = ({ type, message, ttl, mono }) => {
      const cfg = _TOAST_STYLES[type] || _TOAST_STYLES.info;
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const effectiveTtl = typeof ttl === "number" ? ttl : cfg.ttl;
      setToasts((prev) => {
        // Newest on top; cap stack at 5 to avoid flooding the screen.
        const next = [{ id, type, message, mono, cfg }, ...prev];
        return next.slice(0, 5);
      });
      if (effectiveTtl > 0) {
        timers.current[id] = setTimeout(() => dismiss(id), effectiveTtl);
      }
    };
    window.toast._register(handler);
    return () => {
      window.toast._unregister();
      // Clear any in-flight timers so unmount doesn't leak setState callbacks.
      Object.values(timers.current).forEach(clearTimeout);
      timers.current = {};
    };
  }, [dismiss]);

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      style={{
        position: "fixed",
        top: 18,
        right: 18,
        zIndex: 2000,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        maxWidth: "min(92vw, 420px)",
        pointerEvents: "none", // children re-enable so empty container is click-through
      }}
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>
  );
}


function ToastCard({ toast, onDismiss }) {
  const { cfg, message, mono, type } = toast;
  return (
    <div
      role={type === "error" ? "alert" : "status"}
      onClick={onDismiss}
      title="Click to dismiss"
      style={{
        pointerEvents: "auto",
        display: "flex",
        gap: 10,
        alignItems: "flex-start",
        padding: "10px 12px 10px 10px",
        borderRadius: 10,
        background: "var(--surface, #15161b)",
        color: "var(--fg, #e7e7ea)",
        border: "1px solid var(--line, rgba(255,255,255,0.08))",
        borderLeft: `3px solid ${cfg.accent}`,
        boxShadow: "0 12px 30px -10px rgba(0,0,0,0.55), 0 0 0 1px rgba(0,0,0,0.2)",
        fontSize: 12.5,
        lineHeight: 1.45,
        cursor: "pointer",
        animation: "toast-in 180ms ease-out",
      }}
    >
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: 6,
          background: cfg.bg,
          color: cfg.accent,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        <Icon name={cfg.icon} size={12} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          className="mono"
          style={{
            fontSize: 10,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: cfg.accent,
            marginBottom: 2,
          }}
        >
          {cfg.label}
        </div>
        <div
          style={{
            fontFamily: mono ? "var(--f-mono, ui-monospace, monospace)" : "inherit",
            wordBreak: "break-word",
            whiteSpace: "pre-wrap",
          }}
        >
          {message}
        </div>
      </div>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onDismiss(); }}
        aria-label="Dismiss notification"
        style={{
          background: "transparent",
          border: 0,
          color: "var(--fg-3, #8a8a92)",
          cursor: "pointer",
          padding: 2,
          marginTop: -2,
          marginRight: -2,
          flexShrink: 0,
          display: "flex",
        }}
      >
        <Icon name="cross" size={11} />
      </button>

      <style>{`
        @keyframes toast-in {
          0%   { opacity: 0; transform: translateX(16px) scale(0.98); }
          100% { opacity: 1; transform: translateX(0)    scale(1); }
        }
      `}</style>
    </div>
  );
}


Object.assign(window, { Toaster });
