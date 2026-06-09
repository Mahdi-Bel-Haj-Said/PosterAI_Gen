// brand-library.jsx — the org's brand assets: team logos, tournament logos,
// player images, sponsor logos. Backed by /v1/assets (R2 + Mongo).

const ASSET_TABS = [
  { id: "team-logos",       label: "Team logos",       icon: "image",   single: "team logo" },
  { id: "tournament-logos", label: "Tournament logos", icon: "trophy",  single: "tournament logo" },
  { id: "player-images",    label: "Player images",    icon: "user",    single: "player image" },
  { id: "sponsor-logos",    label: "Sponsor logos",    icon: "sponsor", single: "sponsor logo" },
  { id: "backgrounds",      label: "Backgrounds",      icon: "image",   single: "background" },
];

function AssetTile({ asset, onDelete }) {
  const [deleting, setDeleting] = React.useState(false);
  const del = async (e) => {
    e.stopPropagation();
    if (!window.confirm(`Delete "${asset.name || asset.filename}"? This removes it from R2.`)) return;
    setDeleting(true);
    try {
      await window.api.deleteAsset(asset.asset_id);
      onDelete(asset.asset_id);
      window.toast.success("Asset deleted.");
    }
    catch (err) { window.toast.error("Delete failed: " + err.message); setDeleting(false); }
  };
  return (
    <div className="card" style={{ padding: 10, position: "relative", opacity: deleting ? 0.5 : 1 }}>
      <div style={{
        aspectRatio: "1 / 1", borderRadius: 6, overflow: "hidden", marginBottom: 8,
        background: "repeating-conic-gradient(var(--surface-2) 0% 25%, var(--surface) 0% 50%) 50% / 16px 16px",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {asset.signed_url
          ? <img src={asset.signed_url} alt={asset.name || asset.filename}
                 style={{ width: "100%", height: "100%", objectFit: "contain" }} />
          : <Icon name="image" size={20} />}
      </div>
      <div style={{ fontSize: 12, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
           title={asset.name || asset.filename}>
        {asset.name || asset.filename || asset.asset_id.slice(0, 8)}
      </div>
      <div className="row" style={{ justifyContent: "space-between", marginTop: 2 }}>
        {asset.team
          ? <span className="mono" style={{ fontSize: 9.5, color: "var(--crim)", letterSpacing: "0.04em" }}>{asset.team}</span>
          : <span />}
        <span className="mono" style={{ fontSize: 9.5, color: "var(--fg-4)" }}>{(asset.size_bytes / 1024).toFixed(0)} KB</span>
      </div>
      <button onClick={del} disabled={deleting} title="Delete"
        style={{
          position: "absolute", top: 6, right: 6, width: 24, height: 24, borderRadius: 6,
          background: "rgba(0,0,0,0.55)", border: "1px solid var(--line)", color: "var(--crim)",
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
        }}>
        <Icon name="cross" size={12} />
      </button>
    </div>
  );
}

function UploadTile({ assetType, orgId, onUploaded, team, removeBackground, disabled, disabledHint }) {
  const inputRef = React.useRef(null);
  const [busy, setBusy] = React.useState(false);
  const handle = async (files) => {
    if (!files || !files.length) return;
    setBusy(true);
    let ok = 0;
    try {
      for (const file of Array.from(files)) {
        try {
          const a = await window.api.uploadAsset({ orgId, assetType, file, name: file.name, team, removeBackground });
          onUploaded(a);
          ok += 1;
        } catch (err) {
          // Per-file error so a bad mixed batch (1 bad file in 5) doesn't
          // abort the whole upload. The toast quotes the filename so the
          // user knows which one bounced.
          window.toast.error(`Couldn't upload "${file.name}": ${err.message}`);
        }
      }
      if (ok > 0) {
        window.toast.success(`${ok} file${ok === 1 ? "" : "s"} uploaded.`);
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <button onClick={() => !disabled && inputRef.current && inputRef.current.click()} disabled={busy || disabled}
      className="card"
      title={disabled ? disabledHint : undefined}
      style={{
        padding: 10, cursor: disabled ? "not-allowed" : "pointer", background: "transparent", borderStyle: "dashed",
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        gap: 8, color: "var(--fg-3)", minHeight: 150, opacity: disabled ? 0.5 : 1,
      }}>
      <Icon name={busy ? "refresh" : "upload"} size={22} />
      <span style={{ fontSize: 12 }}>
        {busy ? "Uploading…" : disabled ? (disabledHint || "Pick a team first") : team ? `Upload to ${team}` : "Upload"}
      </span>
      <span className="mono" style={{ fontSize: 9.5, color: "var(--fg-4)" }}>PNG · JPG · WEBP</span>
      <input ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" multiple
             style={{ display: "none" }} onChange={(e) => handle(e.target.files)} />
    </button>
  );
}

function BrandLibrary({ navigate }) {
  const orgId = (window.api && window.api.orgId) || "1";
  const [assets, setAssets] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [tab, setTab] = React.useState("team-logos");
  const [selectedTeam, setSelectedTeam] = React.useState("");      // "" = all
  const [extraTeams, setExtraTeams] = React.useState([]);          // newly-added, not yet uploaded
  const [removeBg, setRemoveBg] = React.useState(true);            // default ON for logo/photo tabs

  const fetchAssets = React.useCallback(async () => {
    try {
      const data = await window.api.listAssets({ orgId, limit: 200 });
      setAssets(data.assets || []);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  React.useEffect(() => { fetchAssets(); }, [fetchAssets]);

  const countFor = (type) => assets.filter((a) => a.asset_type === type).length;
  const activeTab = ASSET_TABS.find((t) => t.id === tab);
  const teamScoped = tab === "team-logos" || tab === "player-images";

  // Known teams = teams seen on any asset + any just-added (unsaved) ones.
  const teams = React.useMemo(() => {
    const s = new Set(assets.map((a) => a.team).filter(Boolean));
    extraTeams.forEach((t) => s.add(t));
    return Array.from(s).sort();
  }, [assets, extraTeams]);

  // Grid contents: player-images filter by selected team; team-logos show all
  // (one per team already). Other tabs ignore team entirely.
  let current = assets.filter((a) => a.asset_type === tab);
  if (tab === "player-images" && selectedTeam) {
    current = current.filter((a) => (a.team || "").toLowerCase() === selectedTeam.toLowerCase());
  }

  const onUploaded = (a) => setAssets((prev) => [a, ...prev]);
  const onDelete = (id) => setAssets((prev) => prev.filter((a) => a.asset_id !== id));

  const addTeam = () => {
    const name = (window.prompt("New team name (e.g. FNATIC):") || "").trim();
    if (!name) return;
    if (!teams.some((t) => t.toLowerCase() === name.toLowerCase())) setExtraTeams((p) => [...p, name]);
    setSelectedTeam(name);
  };

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>LIBRARY · BRAND ASSETS</div>
          <h1>Brand library</h1>
          <p>Your reusable logos and images. Upload once, pick them in the wizard for every poster.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost" onClick={fetchAssets}><Icon name="refresh" size={14} /> Refresh</button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 24, flexWrap: "wrap" }}>
        {ASSET_TABS.map((t) => {
          const on = tab === t.id;
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "9px 14px", borderRadius: 8, cursor: "pointer",
                background: on ? "var(--surface-3)" : "transparent",
                border: "1px solid " + (on ? "var(--line-strong)" : "var(--line)"),
                color: on ? "var(--fg)" : "var(--fg-3)", fontWeight: on ? 600 : 500, fontSize: 13,
              }}>
              <Icon name={t.icon} size={15} />
              {t.label}
              <span className="mono" style={{ fontSize: 11, color: on ? "var(--crim)" : "var(--fg-4)" }}>{countFor(t.id)}</span>
            </button>
          );
        })}
      </div>

      {error && (
        <div className="card" style={{ padding: 16, marginBottom: 16, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
          <div className="mono" style={{ fontSize: 12 }}>Couldn't load assets: {error}</div>
        </div>
      )}

      {/* Background-removal toggle — applies to logo/portrait uploads.
          Hidden on the Backgrounds tab; backgrounds are the canvas and must
          never have their own background "removed". */}
      {tab !== "backgrounds" && (
        <div className="row" style={{ gap: 14, marginBottom: 14, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 12.5 }}>
            <input type="checkbox" checked={removeBg} onChange={(e) => setRemoveBg(e.target.checked)}
                   style={{ accentColor: "var(--crim)" }} />
            Remove background on upload
          </label>
          <span className="hint" style={{ margin: 0 }}>
            Default ON. Already-transparent images are skipped automatically. Adds ~1-2 s per upload on first run.
          </span>
        </div>
      )}

      {/* Team selector — only for team-scoped tabs */}
      {teamScoped && (
        <div className="row" style={{ gap: 10, marginBottom: 18, alignItems: "center" }}>
          <span className="label" style={{ marginBottom: 0 }}>Team{tab === "team-logos" ? " (one logo each)" : ""}</span>
          <select value={selectedTeam} onChange={(e) => { e.target.value === "__new__" ? addTeam() : setSelectedTeam(e.target.value); }}
            style={{ padding: "8px 12px", borderRadius: 8, background: "var(--bg-elev)", border: "1px solid var(--line-strong)", color: "var(--fg)", fontFamily: "var(--f-mono)", fontSize: 12.5 }}>
            <option value="">{tab === "player-images" ? "All teams" : "— select a team —"}</option>
            {teams.map((t) => <option key={t} value={t}>{t}</option>)}
            <option value="__new__">+ New team…</option>
          </select>
          {selectedTeam && (
            <span className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>
              {tab === "player-images" ? "Showing & uploading to" : "Uploading to"} <b style={{ color: "var(--crim)" }}>{selectedTeam}</b>
            </span>
          )}
        </div>
      )}

      {loading && assets.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--fg-3)" }}>Loading…</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 14 }}>
          <UploadTile assetType={tab} orgId={orgId} onUploaded={onUploaded}
                      team={teamScoped ? selectedTeam : undefined}
                      removeBackground={tab === "backgrounds" ? false : removeBg}
                      disabled={teamScoped && !selectedTeam}
                      disabledHint="Select or add a team first" />
          {current.map((a) => <AssetTile key={a.asset_id} asset={a} onDelete={onDelete} />)}
          {current.length === 0 && !loading && (
            <div className="col" style={{ gridColumn: "1 / -1", color: "var(--fg-4)", fontSize: 12.5, padding: "8px 2px" }}>
              {tab === "player-images" && selectedTeam
                ? `No player images for ${selectedTeam} yet — upload above.`
                : `No ${activeTab ? activeTab.single + "s" : "assets"} yet — upload one above.`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { BrandLibrary });
