// app.jsx — Router + tweaks + mount

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#E83A57",
  "aiAccent": "#3AC0E8",
  "density": "comfortable",
  "bgMood": "warm"
}/*EDITMODE-END*/;

const ACCENT_OPTIONS = [
  "#E83A57", // defendr crimson
  "#FF3D71", // hot pink
  "#FF6A1F", // ember orange
  "#A855F7", // royal violet
  "#22D3EE", // electric cyan (mono)
];

const AI_ACCENT_OPTIONS = [
  "#3AC0E8", // electric cyan (default)
  "#7B5CFF", // ultraviolet
  "#22C58A", // matrix green
  "#FFD24B", // warning yellow
];

const BG_MOODS = {
  warm:    { bg: "11% 0.008 350", hint1: "20% 0.04 8", hint2: "25% 0.04 195" },
  cool:    { bg: "11% 0.008 240", hint1: "20% 0.04 240", hint2: "25% 0.04 320" },
  pure:    { bg: "8% 0.003 0",    hint1: "18% 0.03 8",  hint2: "22% 0.03 195" },
};

function App() {
  const [route, setRoute] = React.useState(() => location.hash.replace("#", "") || "/");
  const [tw, setTweak] = useTweaks(TWEAK_DEFAULTS);

  React.useEffect(() => {
    const onHash = () => {
      setRoute(location.hash.replace("#", "") || "/");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (h) => { location.hash = h.replace("#", ""); };

  // Apply tweaks
  React.useEffect(() => {
    const r = document.documentElement;
    // Translate hex to oklch-friendly css var (just use hex, we use CSS vars elsewhere)
    r.style.setProperty("--crim", tw.accent);
    r.style.setProperty("--crim-2", tw.accent);
    r.style.setProperty("--crim-soft", tw.accent + "26");
    r.style.setProperty("--crim-line", tw.accent + "66");
    r.style.setProperty("--cy", tw.aiAccent);
    r.style.setProperty("--cy-2", tw.aiAccent);
    r.style.setProperty("--cy-soft", tw.aiAccent + "1f");
    r.style.setProperty("--cy-line", tw.aiAccent + "66");

    const mood = BG_MOODS[tw.bgMood] || BG_MOODS.warm;
    r.style.setProperty("--bg", `oklch(${mood.bg})`);
    document.body.style.background = `
      radial-gradient(800px 600px at 10% -10%, oklch(${mood.hint1} / 0.35), transparent 60%),
      radial-gradient(900px 700px at 110% 10%, oklch(${mood.hint2} / 0.18), transparent 60%),
      oklch(${mood.bg})
    `;

    if (tw.density === "compact") {
      r.style.setProperty("--sidebar-w", "200px");
      r.style.fontSize = "13px";
    } else {
      r.style.setProperty("--sidebar-w", "232px");
      r.style.fontSize = "14px";
    }
  }, [tw]);

  let content = null;
  let crumbs = ["POSTER/AI"];

  const jobMatch = route.match(/^\/job(?:\/([^/?#]+))?/);
  const resultMatch = route.match(/^\/result(?:\/([^/?#]+))?/);

  if (route === "/" || route === "") {
    content = <Dashboard navigate={navigate} />;
    crumbs = ["POSTER/AI", "DASHBOARD"];
  } else if (route.startsWith("/create")) {
    content = <Wizard navigate={navigate} />;
    crumbs = ["POSTER/AI", "CREATE POSTER"];
  } else if (route.startsWith("/history")) {
    content = <History navigate={navigate} />;
    crumbs = ["POSTER/AI", "HISTORY"];
  } else if (route.startsWith("/brand")) {
    content = <BrandLibrary navigate={navigate} />;
    crumbs = ["POSTER/AI", "BRAND LIBRARY"];
  } else if (route.startsWith("/admin/usage")) {
    content = <AdminUsage navigate={navigate} />;
    crumbs = ["POSTER/AI", "ADMIN", "USAGE & BILLING"];
  } else if (jobMatch) {
    const jobId = jobMatch[1] || null;
    content = <JobProgress navigate={navigate} jobId={jobId} />;
    crumbs = ["POSTER/AI", "CREATE POSTER", "GENERATING"];
  } else if (resultMatch) {
    const jobId = resultMatch[1] || null;
    content = <PosterResult navigate={navigate} jobId={jobId} />;
    crumbs = ["POSTER/AI", "POSTERS", jobId ? jobId.slice(0, 8) : "—"];
  } else {
    content = <ComingSoon route={route} navigate={navigate} />;
    crumbs = ["POSTER/AI", route.replace("/", "").toUpperCase().replace("/", " · ")];
  }

  return (
    <>
      <Shell route={route} navigate={navigate} crumbs={crumbs}>
        {content}
      </Shell>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Brand accents" />
        <TweakColor label="Primary" value={tw.accent} options={ACCENT_OPTIONS}
                    onChange={(v) => setTweak("accent", v)} />
        <TweakColor label="AI accent" value={tw.aiAccent} options={AI_ACCENT_OPTIONS}
                    onChange={(v) => setTweak("aiAccent", v)} />

        <TweakSection label="Atmosphere" />
        <TweakRadio label="Background" value={tw.bgMood}
                    options={[{value:"warm",label:"Warm"},{value:"cool",label:"Cool"},{value:"pure",label:"Pure"}]}
                    onChange={(v) => setTweak("bgMood", v)} />
        <TweakRadio label="Density" value={tw.density}
                    options={[{value:"comfortable",label:"Roomy"},{value:"compact",label:"Compact"}]}
                    onChange={(v) => setTweak("density", v)} />

        <TweakSection label="Jump to screen" />
        <TweakButton label="Dashboard" onClick={() => navigate("#/")} secondary />
        <TweakButton label="Wizard" onClick={() => navigate("#/create")} secondary />
        <TweakButton label="Job progress" onClick={() => navigate("#/job")} secondary />
        <TweakButton label="Poster result" onClick={() => navigate("#/result")} secondary />
      </TweaksPanel>
    </>
  );
}

function ComingSoon({ route, navigate }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>{route}</div>
          <h1>Coming up next.</h1>
          <p>This pass covers the hero flow: Dashboard → Wizard → Job → Result. The full IA (history, brand library, tournaments, admin) ships in the next round.</p>
        </div>
      </div>
      <div className="card" style={{ padding: 40, textAlign: "center" }}>
        <button className="btn btn-primary" onClick={() => navigate("#/")}>← Back to dashboard</button>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
