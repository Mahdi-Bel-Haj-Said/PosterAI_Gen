// poster-result.jsx — Generated poster reveal (real signed_url image)

function PosterResult({ navigate, jobId }) {
  const [job, setJob] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [copied, setCopied] = React.useState(false);
  const [dnaState, setDnaState] = React.useState({ busy: false, status: null, error: null });
  // Full-screen lightbox for the poster.
  const [zoom, setZoom] = React.useState(false);

  // Caption state — fetched (and persisted) lazily once the job is completed.
  // null = not loaded yet / unavailable; string = ready to use.
  const [caption, setCaption] = React.useState(null);
  const [captionBusy, setCaptionBusy] = React.useState(false);
  const [captionError, setCaptionError] = React.useState(null);

  React.useEffect(() => {
    if (!jobId) { setError("Missing job id."); setLoading(false); return; }
    let cancelled = false;
    (async () => {
      try {
        const j = await window.api.getPoster(jobId);
        if (cancelled) return;
        setJob(j);
        if (j.status !== "completed") {
          // bounce back to progress page
          navigate(`#/job/${jobId}`);
          return;
        }
        if (j.caption) setCaption(j.caption);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [jobId]);

  // Fetch the social caption ON DEMAND — when the user actually opens a share
  // flow — never automatically on load.
  //
  // This used to run for every completed poster, which meant a model call for
  // every poster generated. Most posters are never shared, so the large
  // majority of those calls produced a caption nobody ever read, and each one
  // was billed. Generating at the moment of sharing costs the user nothing in
  // latency they notice (the modal opens immediately and the text fills in)
  // and skips the call entirely for everyone who never shares.
  //
  // Safe to call repeatedly: it no-ops once a caption exists or a request is
  // already in flight, so several share buttons cannot stack up requests.
  const ensureCaption = React.useCallback(async () => {
    if (!job || job.status !== "completed" || caption || captionBusy) return;
    setCaptionBusy(true);
    setCaptionError(null);
    try {
      const res = await window.api.generateCaption(job.job_id);
      // res === null means no API key is configured; silently skip.
      if (res && res.caption) setCaption(res.caption);
    } catch (e) {
      setCaptionError(e.message);
    } finally {
      setCaptionBusy(false);
    }
  }, [job, caption, captionBusy]);

  // Close the lightbox on Escape + lock background scroll while it's open.
  React.useEffect(() => {
    if (!zoom) return;
    const onKey = (e) => { if (e.key === "Escape") setZoom(false); };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [zoom]);

  const regenerateCaption = async () => {
    if (!job?.job_id) return;
    setCaptionBusy(true);
    setCaptionError(null);
    try {
      const res = await window.api.generateCaption(job.job_id, { regenerate: true });
      if (res && res.caption) setCaption(res.caption);
    } catch (e) {
      setCaptionError(e.message);
    } finally {
      setCaptionBusy(false);
    }
  };

  const copyLink = async () => {
    if (!job?.job_id) return;
    try {
      // Copy the public landing-page URL — short, permanent, renders proper
      // image previews when pasted into Discord/Slack/WhatsApp/etc.
      await navigator.clipboard.writeText(shareUrlFor(job.job_id));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_) {}
  };

  // Share buttons point at the public landing page /p/{job_id}, NOT the raw R2
  // signed URL. The landing page carries Twitter Card + OG meta tags so the
  // platforms render proper image previews instead of a bare link. The signed
  // URL is also long-lived only for ~1 hour, while /p/{job_id} is permanent.
  const shareUrlFor = (jobId) => {
    const base = (window.api?.base || window.location.origin).replace(/\/+$/, "");
    return `${base}/p/${encodeURIComponent(jobId)}`;
  };

  // Which Quick Share modal is currently open. null = closed, else the
  // platform identifier the modal is configured for. Owned at the page level
  // so the modal can read the current caption + job in one place.
  const [shareModal, setShareModal] = React.useState(null);

  // Opening a share flow is what triggers caption generation. Deliberately not
  // awaited: the modal should appear instantly rather than waiting on a model
  // call, and the textarea fills in when the text arrives.
  const openShare = (platform) => {
    ensureCaption();
    setShareModal(platform);
  };

  const extractDna = async () => {
    if (!job) return;
    setDnaState({ busy: true, status: null, error: null });
    try {
      const dna = await window.api.extractStyleDna({
        orgId: job.org_id,
        tournamentId: job.tournament_id,
        sourceJobId: job.job_id,
      });
      setDnaState({ busy: false, status: dna.status, error: null });
    } catch (e) {
      setDnaState({ busy: false, status: null, error: e.message });
    }
  };

  const [refinePrompt, setRefinePrompt] = React.useState("");
  const [refineState, setRefineState] = React.useState({ busy: false, error: null });
  const submitRefine = async () => {
    const text = refinePrompt.trim();
    if (!text || !job) return;
    setRefineState({ busy: true, error: null });
    try {
      const newJob = await window.api.refinePoster({ jobId: job.job_id, prompt: text });
      navigate(`#/job/${newJob.job_id}`);
    } catch (e) {
      setRefineState({ busy: false, error: e.message });
    }
  };

  const approveDna = async () => {
    if (!job) return;
    setDnaState((s) => ({ ...s, busy: true, error: null }));
    try {
      const dna = await window.api.approveStyleDna({
        orgId: job.org_id,
        tournamentId: job.tournament_id,
      });
      setDnaState({ busy: false, status: dna.status, error: null });
    } catch (e) {
      setDnaState((s) => ({ ...s, busy: false, error: e.message }));
    }
  };

  if (loading) {
    return <div className="card" style={{ padding: 32 }}>Loading poster…</div>;
  }
  if (error) {
    return (
      <div className="card" style={{ padding: 24, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Couldn't load the poster</div>
        <div className="mono" style={{ fontSize: 12 }}>{error}</div>
        <button className="btn btn-ghost" style={{ marginTop: 12 }} onClick={() => navigate("#/")}>← Back to dashboard</button>
      </div>
    );
  }
  if (!job) return null;

  const created = job.created_at ? new Date(job.created_at) : null;
  const elapsedSec = (created && job.updated_at)
    ? Math.max(0, Math.round((new Date(job.updated_at) - created) / 1000))
    : null;

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 28 }}>
        <div>
          <div className="row" style={{ gap: 8, marginBottom: 10 }}>
            <span className="badge ok"><span className="dot" />
              {elapsedSec != null ? `Completed in ${elapsedSec}s` : "Completed"}
            </span>
            <span className="badge ai"><Icon name="sparkles" size={11} />AI generated</span>
          </div>
          <h1>{job.tournament_id}</h1>
          <p>Job <span className="mono">{job.job_id}</span> · Saved to your history.</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => navigate("#/")}><Icon name="layers" size={14}/> History</button>
          <button className="btn btn-primary" onClick={() => navigate("#/create")}>
            <Icon name="plus" size={14} /> Generate another
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 28 }}>
        {/* align-items:flex-start so the frame hugs the poster's height instead
            of stretching to match the (taller) controls column. The frame is
            sized to the image (fit-content): a landscape poster uses the full
            column width, a tall portrait is bounded by the viewport height so
            it never overflows — the box always follows the poster's shape. */}
        <div style={{ display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
          <div className="poster-frame" style={{
            position: "relative",
            width: "fit-content",
            maxWidth: "100%",
            borderRadius: 14,
            overflow: "hidden",
            animation: "reveal 1s ease-out",
            background: "var(--surface-2)",
            lineHeight: 0,
          }}>
            {job.signed_url ? (
              <React.Fragment>
                <img src={job.signed_url} alt="Generated poster"
                     onClick={() => setZoom(true)}
                     title="Click to view full screen"
                     style={{
                       display: "block",
                       width: "auto",
                       height: "auto",
                       maxWidth: "100%",
                       maxHeight: "calc(100vh - 150px)",
                       cursor: "zoom-in",
                     }} />
                <button
                  type="button"
                  className="poster-expand"
                  onClick={() => setZoom(true)}
                  title="View full screen"
                  aria-label="View poster full screen"
                >
                  <Icon name="expand" size={13} /> Full screen
                </button>
              </React.Fragment>
            ) : (
              <div style={{ padding: 40, textAlign: "center", color: "var(--fg-3)", width: 360 }}>No image URL returned.</div>
            )}
          </div>
        </div>

        <div className="col" style={{ gap: 18 }}>
          <div className="card" style={{ padding: 16 }}>
            <div className="col" style={{ gap: 8 }}>
              {/* Uses the FastAPI proxy so the browser actually saves the PNG
                  instead of just opening it in a new tab (R2 signed URLs don't
                  set Content-Disposition: attachment). */}
              <a className="btn btn-primary btn-lg" style={{ width: "100%", textAlign: "center", textDecoration: "none" }}
                 href={window.api.downloadUrl(job.job_id)}
                 download={`${job.tournament_id || "poster"}_${job.job_id}.png`}
                 rel="noopener">
                <Icon name="download" size={16}/> Download PNG
              </a>
              <div className="row" style={{ gap: 8 }}>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={copyLink} disabled={!job.signed_url}>
                  <Icon name={copied ? "check" : "link"} size={14}/> {copied ? "Copied!" : "Copy share link"}
                </button>
              </div>
              <div className="eyebrow" style={{ marginTop: 8, marginBottom: 4 }}>Quick share</div>
              <div className="row" style={{ gap: 6 }}>
                <button
                  className="btn btn-ghost"
                  style={{ flex: 1, padding: "8px 4px" }}
                  onClick={() => openShare("twitter")}
                  disabled={!job.signed_url}
                  title="Quick share to X / Twitter"
                >
                  <Icon name="twitter" size={14}/>
                  <span style={{ marginLeft: 4 }}>Twitter</span>
                </button>
                <button
                  className="btn btn-ghost"
                  style={{ flex: 1, padding: "8px 4px" }}
                  onClick={() => openShare("facebook")}
                  disabled={!job.signed_url}
                  title="Quick share to Facebook"
                >
                  <Icon name="facebook" size={14}/>
                  <span style={{ marginLeft: 4 }}>Facebook</span>
                </button>
                <button
                  className="btn btn-ghost"
                  style={{ flex: 1, padding: "8px 4px" }}
                  onClick={() => openShare("instagram")}
                  disabled={!job.signed_url}
                  title="Quick share to Instagram"
                >
                  <Icon name="instagram" size={14}/>
                  <span style={{ marginLeft: 4 }}>Instagram</span>
                </button>
              </div>
            </div>
          </div>

          {/* User feedback on output quality — 1–5 stars, persisted server-side
              via /v1/posters/{id}/rating (feeds the Content metrics dashboard).
              `initial` seeds from the job's stored rating so it survives reloads
              and shows across devices. */}
          <RatingCard jobId={job.job_id} initial={job.rating} />

          {/* Native posting — backend (Postiz) is fully wired but the OAuth /
              account-connection UX is being deferred. Render a fully-styled
              preview of the upcoming UI (chips, caption, schedule, post button)
              with everything visually disabled + a COMING SOON tag, so users
              can see exactly what's coming. Swap back to <NativePostPanel /> to
              re-enable. */}
          <NativePostPreviewPanel caption={caption} />

          {/* Refine — apply a freeform image-edit pass to this poster */}
          <div className="card" style={{ padding: 18 }}>
            <div className="row" style={{ gap: 12, marginBottom: 10 }}>
              <div style={{ width: 36, height: 36, borderRadius: 8, background: "var(--crim-soft)", color: "var(--crim)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Icon name="edit" size={16} />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13.5 }}>Refine this poster</div>
                <div className="hint" style={{ marginTop: 2 }}>
                  Tell the model what to change. Best for visual tweaks — factual edits like score/time may not render perfectly.
                </div>
              </div>
            </div>
            <textarea
              value={refinePrompt}
              onChange={(e) => setRefinePrompt(e.target.value)}
              placeholder={'e.g. "make it a bit darker", "use a more dynamic font for the date", "add subtle ember particles"'}
              disabled={refineState.busy}
              rows={3}
              style={{
                width: "100%", boxSizing: "border-box", resize: "vertical",
                padding: "10px 12px", borderRadius: 8,
                background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
                color: "var(--fg)", fontFamily: "var(--f-body)", fontSize: 13, lineHeight: 1.4,
              }}
            />
            <div className="row" style={{ justifyContent: "space-between", marginTop: 10, gap: 8 }}>
              <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", letterSpacing: "0.06em" }}>
                {refinePrompt.length}/2000
              </span>
              <button className="btn btn-primary"
                      onClick={submitRefine}
                      disabled={refineState.busy || !refinePrompt.trim()}>
                {refineState.busy ? "Submitting…" : <><Icon name="sparkles" size={14} /> Refine</>}
              </button>
            </div>
            {refineState.error && (
              <div className="mono" style={{ fontSize: 11, color: "var(--crim)", marginTop: 8, whiteSpace: "pre-wrap" }}>
                {refineState.error}
              </div>
            )}
          </div>

          <div className="card" style={{ padding: 18, borderColor: "var(--cy-line)", background: "linear-gradient(140deg, var(--surface), oklch(15% 0.04 195))" }}>
            <div className="row" style={{ gap: 12, marginBottom: 12 }}>
              <div style={{ width: 36, height: 36, borderRadius: 8, background: "var(--cy-soft)", color: "var(--cy)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Icon name="sparkles" size={16} />
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13.5 }}>Save as Style DNA</div>
                <div className="hint" style={{ marginTop: 2 }}>Lock this look in for future <span className="mono">{job.tournament_id}</span> posters.</div>
              </div>
            </div>
            {dnaState.status !== "approved" && (
              <button className="btn" style={{ width: "100%", background: "var(--cy-soft)", color: "var(--cy)", border: "1px solid var(--cy-line)" }}
                      onClick={extractDna} disabled={dnaState.busy || dnaState.status === "draft"}>
                {dnaState.busy && dnaState.status !== "draft" ? "Extracting…"
                  : dnaState.status === "draft" ? "Draft saved ✓"
                  : "Extract & save as draft"}
              </button>
            )}

            {/* Once a draft exists, offer to lock it in as the approved style. */}
            {dnaState.status === "draft" && (
              <button className="btn btn-primary" style={{ width: "100%", marginTop: 8 }}
                      onClick={approveDna} disabled={dnaState.busy}>
                {dnaState.busy ? "Approving…" : "Approve this style"}
              </button>
            )}

            {dnaState.status === "approved" && (
              <div className="row" style={{ gap: 8, justifyContent: "center", color: "var(--ok)", fontSize: 13, fontWeight: 600 }}>
                <Icon name="check" size={14} /> Approved — locked in for {job.tournament_id}
              </div>
            )}

            {dnaState.status === "draft" && (
              <div className="hint" style={{ marginTop: 8 }}>
                Draft is usable now. Approving locks it in as the official style and clears the draft.
              </div>
            )}

            {dnaState.error && (
              <div className="mono" style={{ fontSize: 11, color: "var(--crim)", marginTop: 8 }}>{dnaState.error}</div>
            )}
          </div>

          <div className="card" style={{ padding: 18 }}>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Metadata</div>
            <div className="col" style={{ gap: 12 }}>
              <MetaRow label="Created" value={created ? created.toLocaleString() : "—"} />
              <MetaRow label="Tournament" value={job.tournament_id} />
              <MetaRow label="Org" value={job.org_id} />
              <MetaRow label="Mode">
                <span className="badge ai" style={{ padding: "2px 6px", fontSize: 9.5 }}>{(job.mode || "").toUpperCase()}</span>
              </MetaRow>
              <MetaRow label="Status" value={job.status} />
              <MetaRow label="Storage">
                <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-2)", textAlign: "right", wordBreak: "break-all" }}>
                  {job.storage_key || "—"}
                </span>
              </MetaRow>
              <MetaRow label="Job ID">
                <span className="mono" style={{ fontSize: 11, color: "var(--fg-2)" }}>{job.job_id}</span>
              </MetaRow>
            </div>
          </div>
        </div>
      </div>

      {shareModal && (
        <QuickShareModal
          platform={shareModal}
          job={job}
          caption={caption}
          onClose={() => setShareModal(null)}
        />
      )}

      {zoom && job.signed_url && (
        <div
          className="poster-lightbox"
          onClick={(e) => { if (e.target === e.currentTarget) setZoom(false); }}
          style={{
            position: "fixed", inset: 0, zIndex: 1100,
            background: "rgba(6,6,8,0.88)", backdropFilter: "blur(10px)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: 28, cursor: "zoom-out",
          }}
        >
          <button
            type="button"
            onClick={() => setZoom(false)}
            className="btn btn-ghost"
            style={{ position: "absolute", top: 18, right: 18, padding: "6px 8px", zIndex: 1 }}
            title="Close (Esc)"
            aria-label="Close full screen"
          >
            <Icon name="cross" size={14} />
          </button>
          <img
            src={job.signed_url}
            alt="Generated poster — full screen"
            onClick={() => setZoom(false)}
            style={{
              maxWidth: "96vw", maxHeight: "92vh",
              width: "auto", height: "auto",
              display: "block", borderRadius: 10, cursor: "zoom-out",
              boxShadow: "0 40px 140px -30px rgba(0,0,0,0.85)",
            }}
          />
        </div>
      )}

      <style>{`
        @keyframes reveal {
          0%   { opacity: 0; transform: translateY(20px) scale(0.96); filter: blur(8px); }
          60%  { filter: blur(0); }
          100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        }
        .poster-frame {
          box-shadow: 0 30px 100px -30px oklch(65% 0.230 8 / 0.5), 0 0 0 1px var(--line);
          transition: transform .4s cubic-bezier(.2,.8,.2,1), box-shadow .4s ease;
          will-change: transform;
        }
        .poster-frame:hover {
          transform: translateY(-6px) scale(1.015);
          box-shadow: 0 44px 130px -26px oklch(65% 0.230 8 / 0.62), 0 0 0 1px var(--line-strong);
        }
        .poster-expand {
          position: absolute; top: 10px; right: 10px;
          display: inline-flex; align-items: center; gap: 6px;
          padding: 7px 11px; border-radius: 9px;
          background: rgba(10,10,12,0.55); color: #fff;
          border: 1px solid rgba(255,255,255,0.18);
          backdrop-filter: blur(6px);
          font-family: var(--f-body); font-size: 11px; font-weight: 600; letter-spacing: .04em;
          line-height: 1; cursor: pointer;
          opacity: 0; transform: translateY(-4px);
          transition: opacity .25s ease, transform .25s ease, background .2s ease;
        }
        .poster-frame:hover .poster-expand,
        .poster-expand:focus-visible { opacity: 1; transform: translateY(0); }
        .poster-expand:hover { background: rgba(22,22,26,0.82); }
        .poster-lightbox { animation: lightboxBackdropIn .22s ease-out; }
        .poster-lightbox img { animation: lightboxImgIn .32s cubic-bezier(.2,.8,.2,1); }
        @keyframes lightboxBackdropIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes lightboxImgIn {
          0%   { opacity: 0; transform: scale(0.86) translateY(14px); }
          100% { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  );
}

function MetaRow({ label, value, children }) {
  return (
    <div className="row" style={{ justifyContent: "space-between", gap: 12 }}>
      <span className="mono" style={{ fontSize: 10.5, letterSpacing: "0.1em", color: "var(--fg-3)", textTransform: "uppercase" }}>{label}</span>
      {children || <span style={{ fontSize: 12.5, fontWeight: 500, textAlign: "right" }}>{value}</span>}
    </div>
  );
}


// ---- RatingCard -------------------------------------------------------------
// 1–5 star rating for the generated poster, persisted server-side via
// POST /v1/posters/{id}/rating (feeds the Content metrics dashboard's avg
// rating per vibe / energy / combo). `initial` seeds from the job's stored
// rating; localStorage is a same-device cache/fallback.
//
// UX:
//   * 5 outline stars in a row.
//   * Hover lights them up to that index (preview, no commit).
//   * Click sets the score, saves it, and shows a "Thanks!" toast.
//   * Clicking a star only ever SETS a rating (1–5). There's no "unrate" on the
//     backend, so we don't send a clear — a re-click of a lower/higher star just
//     overwrites. (The old localStorage-only "click to clear" is dropped.)
//   * Keyboard support: each star is a real <button>, so Tab + Space/Enter works.

function RatingCard({ jobId, initial }) {
  const STORAGE_KEY = jobId ? `poster-rating:${jobId}` : null;
  const MAX = 5;

  // Prefer the server-persisted rating; fall back to a same-device localStorage
  // cache. Bounded to 0..MAX so a tampered entry can't distort the UI.
  const _readStored = () => {
    if (Number.isFinite(initial) && initial >= 1 && initial <= MAX) return initial;
    if (!STORAGE_KEY) return 0;
    try {
      const v = parseInt(window.localStorage.getItem(STORAGE_KEY) || "0", 10);
      return Number.isFinite(v) && v >= 0 && v <= MAX ? v : 0;
    } catch (_) {
      return 0;
    }
  };

  const [rating, setRating] = React.useState(_readStored);
  const [hover, setHover]   = React.useState(0); // 0 = not hovering
  const [saving, setSaving] = React.useState(false);

  // Re-seed if the job (or its server rating) changes under us.
  React.useEffect(() => { setRating(_readStored()); /* eslint-disable-line */ }, [jobId, initial]);

  const commit = async (value) => {
    if (value < 1 || value > MAX || value === rating) return;
    setRating(value);
    try {
      if (STORAGE_KEY) window.localStorage.setItem(STORAGE_KEY, String(value));
    } catch (_) { /* private-mode / quota — non-fatal */ }
    setSaving(true);
    try {
      await window.api.ratePoster(jobId, value);
      window.toast.success(`Thanks! You rated this poster ${value}/${MAX}.`);
    } catch (e) {
      window.toast.error(`Couldn't save rating: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const display = hover || rating;  // hover preview wins while present
  const labelFor = (v) => {
    if (v <= 0) return "Click a star to rate";
    if (v <= 1) return "Needs work";
    if (v <= 2) return "Meh";
    if (v <= 3) return "Decent";
    if (v <= 4) return "Strong";
    return "Excellent";
  };

  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="row" style={{ gap: 12, marginBottom: 12, alignItems: "flex-start" }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: "var(--crim-soft)", color: "var(--crim)",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <Icon name="star" size={16} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>Rate this poster</div>
          <div className="hint" style={{ marginTop: 2 }}>
            Your score helps us tune generation quality. 1 = nope, 5 = nailed it.
          </div>
        </div>
      </div>

      {/* Star row */}
      <div
        role="radiogroup"
        aria-label={`Poster rating, 1 to ${MAX}`}
        onMouseLeave={() => setHover(0)}
        className="row"
        style={{ gap: 6, justifyContent: "center", marginBottom: 10 }}
      >
        {Array.from({ length: MAX }, (_, i) => {
          const value = i + 1;
          const lit = value <= display;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={rating === value}
              aria-label={`${value} out of ${MAX}`}
              title={`${value}/${MAX} — ${labelFor(value)}`}
              disabled={saving}
              onMouseEnter={() => setHover(value)}
              onFocus={() => setHover(value)}
              onBlur={() => setHover(0)}
              onClick={() => commit(value)}
              style={{
                background: "transparent",
                border: 0,
                padding: 2,
                cursor: saving ? "default" : "pointer",
                color: lit ? "var(--crim)" : "var(--fg-4)",
                transition: "color 120ms ease, transform 120ms ease",
                transform: hover === value ? "scale(1.18)" : "scale(1)",
                lineHeight: 0,
              }}
            >
              <Icon name="star" size={28} />
            </button>
          );
        })}
      </div>

      {/* Score readout */}
      <div className="row" style={{ justifyContent: "center", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-3)", letterSpacing: "0.06em" }}>
          {saving ? "SAVING…" : display > 0 ? `${display}/${MAX} · ${labelFor(display).toUpperCase()}` : "AWAITING RATING"}
        </span>
      </div>
    </div>
  );
}




// ---- NativePostPanel --------------------------------------------------------
// Renders the Postiz-backed "post directly" UI on the poster result page.
//
// Lifecycle:
//   - mount: GET /v1/social/integrations
//       * null      → backend reports Postiz is disabled. Render NOTHING.
//       * []        → Postiz is up but no accounts are linked. Render a soft hint.
//       * [...]     → render integration picker + caption + schedule + submit.
//   - submit: POST /v1/social/post. Show busy/success/error inline.
//
// Caption is freeform for now (description-generation comes next via Gemini).

function NativePostPanel({ job, caption, captionBusy, captionError, onRegenerateCaption }) {
  const [integrations, setIntegrations] = React.useState(undefined); // undefined=loading, null=disabled, []=empty, [...]=ready
  const [selected, setSelected] = React.useState(new Set());
  const [content, setContent] = React.useState("");
  const [contentDirty, setContentDirty] = React.useState(false);
  const [scheduleEnabled, setScheduleEnabled] = React.useState(false);
  const [scheduleAt, setScheduleAt] = React.useState("");
  const [state, setState] = React.useState({ busy: false, ok: null, error: null, scheduled: false });

  // Pre-fill the textarea from the Gemini caption — but only if the user
  // hasn't already started typing. Otherwise we'd nuke their edits when
  // the caption arrives or gets regenerated.
  React.useEffect(() => {
    if (!caption) return;
    if (contentDirty) return;
    setContent(caption);
  }, [caption, contentDirty]);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await window.api.listSocialIntegrations();
        if (cancelled) return;
        if (res === null) { setIntegrations(null); return; }      // 503 → hide
        const list = Array.isArray(res?.integrations) ? res.integrations : [];
        setIntegrations(list);
        // Pre-select all integrations by default so the common case is one click.
        setSelected(new Set(list.map((i) => i.id)));
      } catch (e) {
        // Treat any error here as "Postiz isn't usable" → hide the panel rather
        // than scare the user. They still have the share-intent buttons above.
        if (!cancelled) setIntegrations(null);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (integrations === undefined) {
    return (
      <div className="card" style={{ padding: 16, opacity: 0.6 }}>
        <span className="mono" style={{ fontSize: 11 }}>Checking connected accounts…</span>
      </div>
    );
  }
  if (integrations === null) {
    // Postiz disabled — render nothing.
    return null;
  }
  if (integrations.length === 0) {
    return (
      <div className="card" style={{ padding: 18 }}>
        <div className="row" style={{ gap: 12, marginBottom: 8 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: "var(--surface-2)", color: "var(--fg-3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="link" size={16} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13.5 }}>Post directly to your accounts</div>
            <div className="hint" style={{ marginTop: 2 }}>
              Connect Twitter / Facebook / Instagram inside your Postiz dashboard first.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const submit = async () => {
    if (!content.trim() || selected.size === 0 || !job?.job_id) return;
    if (scheduleEnabled && !scheduleAt) return;
    setState({ busy: true, ok: null, error: null, scheduled: false });
    try {
      // The schedule input is a datetime-local string (no timezone). Build a
      // tz-aware ISO timestamp from the browser's local zone so the backend
      // receives an unambiguous moment in time.
      let isoSchedule = null;
      if (scheduleEnabled && scheduleAt) {
        const d = new Date(scheduleAt);
        if (!isNaN(d.getTime())) isoSchedule = d.toISOString();
      }
      const res = await window.api.createSocialPost({
        jobId: job.job_id,
        integrationIds: Array.from(selected),
        content: content.trim(),
        scheduleAt: isoSchedule,
      });
      setState({ busy: false, ok: true, error: null, scheduled: !!res?.scheduled });
    } catch (e) {
      setState({ busy: false, ok: false, error: e.message, scheduled: false });
    }
  };

  const platformLabel = (i) => {
    if (i.platform) return i.platform.toUpperCase();
    return "ACCOUNT";
  };

  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="row" style={{ gap: 12, marginBottom: 12 }}>
        <div style={{ width: 36, height: 36, borderRadius: 8, background: "var(--cy-soft)", color: "var(--cy)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Icon name="upload" size={16} />
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>Post directly to your accounts</div>
          <div className="hint" style={{ marginTop: 2 }}>Image is uploaded natively — no link preview, no expiring URL.</div>
        </div>
      </div>

      {/* Account picker */}
      <div className="eyebrow" style={{ marginBottom: 8 }}>Post to</div>
      <div className="row" style={{ flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
        {integrations.map((i) => {
          const on = selected.has(i.id);
          return (
            <button
              key={i.id}
              type="button"
              onClick={() => toggle(i.id)}
              className="btn"
              style={{
                padding: "4px 10px",
                fontSize: 11,
                background: on ? "var(--cy-soft)" : "var(--surface-2)",
                color: on ? "var(--cy)" : "var(--fg-3)",
                border: `1px solid ${on ? "var(--cy-line)" : "var(--line)"}`,
                borderRadius: 999,
              }}
              title={i.name || i.id}
            >
              {on ? "✓ " : ""}{i.name || platformLabel(i)}
              <span className="mono" style={{ marginLeft: 6, opacity: 0.6, fontSize: 9.5 }}>{platformLabel(i)}</span>
            </button>
          );
        })}
      </div>

      {/* Caption */}
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <span className="eyebrow">Caption</span>
        {onRegenerateCaption && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => { onRegenerateCaption(); setContentDirty(false); }}
            disabled={captionBusy || state.busy}
            style={{ padding: "2px 8px", fontSize: 11 }}
            title="Ask Gemini for a new caption"
          >
            <Icon name="refresh" size={11}/> {captionBusy ? "Regenerating…" : "Regenerate"}
          </button>
        )}
      </div>
      <textarea
        value={content}
        onChange={(e) => { setContent(e.target.value); setContentDirty(true); }}
        placeholder={captionBusy ? "Generating caption…" : "Write a caption…"}
        disabled={state.busy}
        rows={4}
        style={{
          width: "100%", boxSizing: "border-box", resize: "vertical",
          padding: "10px 12px", borderRadius: 8,
          background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
          color: "var(--fg)", fontFamily: "var(--f-body)", fontSize: 13, lineHeight: 1.4,
        }}
      />
      {captionError && (
        <div className="mono" style={{ fontSize: 10.5, color: "var(--crim)", marginTop: 4 }}>
          Caption error: {captionError}
        </div>
      )}

      {/* Schedule toggle + datetime */}
      <div className="row" style={{ justifyContent: "space-between", marginTop: 10, gap: 8, flexWrap: "wrap" }}>
        <label className="row" style={{ gap: 6, fontSize: 12, color: "var(--fg-3)", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={scheduleEnabled}
            onChange={(e) => setScheduleEnabled(e.target.checked)}
            disabled={state.busy}
          />
          Schedule for later
        </label>
        {scheduleEnabled && (
          <input
            type="datetime-local"
            value={scheduleAt}
            onChange={(e) => setScheduleAt(e.target.value)}
            disabled={state.busy}
            style={{
              padding: "6px 8px", borderRadius: 6,
              background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
              color: "var(--fg)", fontSize: 12,
            }}
          />
        )}
      </div>

      <div className="row" style={{ justifyContent: "space-between", marginTop: 12, gap: 8 }}>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", letterSpacing: "0.06em" }}>
          {selected.size} account{selected.size === 1 ? "" : "s"} · {content.length} chars
        </span>
        <button
          className="btn btn-primary"
          onClick={submit}
          disabled={
            state.busy
            || selected.size === 0
            || !content.trim()
            || (scheduleEnabled && !scheduleAt)
          }
        >
          {state.busy
            ? (scheduleEnabled ? "Scheduling…" : "Posting…")
            : (scheduleEnabled
                ? <><Icon name="clock" size={14}/> Schedule</>
                : <><Icon name="upload" size={14}/> Post now</>)}
        </button>
      </div>

      {state.ok === true && (
        <div className="mono" style={{ fontSize: 11, color: "var(--ok)", marginTop: 10 }}>
          {state.scheduled ? "✓ Scheduled" : "✓ Posted"}
        </div>
      )}
      {state.error && (
        <div className="mono" style={{ fontSize: 11, color: "var(--crim)", marginTop: 10, whiteSpace: "pre-wrap" }}>
          {state.error}
        </div>
      )}
    </div>
  );
}


// ---- NativePostPreviewPanel -------------------------------------------------
// A visual preview of the upcoming one-click native-posting UI. The full
// dynamic version (<NativePostPanel />) drives the live Postiz integration
// behind /v1/social/*; we keep that code intact and instead render this
// disabled mirror so users can see exactly what's coming.
//
// Everything inside is non-interactive: pointer-events: none on the controls,
// reduced opacity, mock integration chips ("connected accounts") for visual
// completeness. A prominent COMING SOON pill in the header explains why.
//
// To ship the real thing: replace <NativePostPreviewPanel /> in PosterResult
// with <NativePostPanel job={job} caption={caption} ... />.

function NativePostPreviewPanel({ caption }) {
  // Mock chips so the picker looks "filled in" rather than empty. Pure visuals.
  const mockIntegrations = [
    { name: "@your_twitter",   icon: "twitter",   label: "TWITTER" },
    { name: "Your FB Page",    icon: "facebook",  label: "FACEBOOK" },
    { name: "@your_instagram", icon: "instagram", label: "INSTAGRAM" },
  ];

  return (
    <div
      className="card"
      style={{
        padding: 18,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Header — fully opaque so the COMING SOON badge stays legible. */}
      <div className="row" style={{ gap: 12, marginBottom: 12, alignItems: "flex-start" }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: "var(--cy-soft)", color: "var(--cy)",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <Icon name="upload" size={16} />
        </div>
        <div style={{ flex: 1 }}>
          <div className="row" style={{ gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ fontWeight: 600, fontSize: 13.5 }}>Post directly to your accounts</div>
            <span style={{
              padding: "2px 7px", fontSize: 9.5, fontWeight: 700, letterSpacing: "0.08em",
              background: "var(--cy-soft)", color: "var(--cy)",
              border: "1px solid var(--cy-line)", borderRadius: 999,
            }}>
              COMING SOON
            </span>
          </div>
          <div className="hint" style={{ marginTop: 2 }}>
            Preview of one-click native posting + scheduling. We're polishing the
            account-connection flow — use Quick share above in the meantime.
          </div>
        </div>
      </div>

      {/* Disabled preview body. Everything below is read-only: pointer-events:
          none stops clicks, opacity dims it, and inputs are marked disabled so
          screen readers and keyboard nav also skip them. */}
      <div
        aria-hidden="true"
        style={{
          opacity: 0.55,
          pointerEvents: "none",
          userSelect: "none",
          filter: "saturate(0.85)",
        }}
      >
        {/* Mock integration chips */}
        <div className="eyebrow" style={{ marginBottom: 8 }}>Post to</div>
        <div className="row" style={{ flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
          {mockIntegrations.map((i) => (
            <span
              key={i.label}
              className="btn"
              style={{
                padding: "4px 10px",
                fontSize: 11,
                background: "var(--cy-soft)",
                color: "var(--cy)",
                border: "1px solid var(--cy-line)",
                borderRadius: 999,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Icon name={i.icon} size={11} />
              ✓ {i.name}
              <span className="mono" style={{ opacity: 0.6, fontSize: 9.5 }}>{i.label}</span>
            </span>
          ))}
        </div>

        {/* Caption header */}
        <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
          <div className="eyebrow">Caption</div>
          <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>
            <Icon name="sparkles" size={10}/> AI-generated
          </span>
        </div>

        {/* Caption textarea — disabled, but shows the real caption when we
            have one, so the preview feels live. */}
        <textarea
          value={caption || "Your AI-generated caption will appear here, ready to edit before posting."}
          readOnly
          disabled
          rows={4}
          style={{
            width: "100%", boxSizing: "border-box", resize: "none",
            padding: "10px 12px", borderRadius: 8,
            background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
            color: "var(--fg)", fontFamily: "var(--f-body)", fontSize: 13, lineHeight: 1.45,
            cursor: "not-allowed",
          }}
        />

        {/* Schedule row */}
        <div className="row" style={{ justifyContent: "space-between", marginTop: 10, gap: 8, flexWrap: "wrap" }}>
          <label className="row" style={{ gap: 6, fontSize: 12, color: "var(--fg-3)" }}>
            <input type="checkbox" checked={false} readOnly disabled />
            Schedule for later
          </label>
          <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>
            3 accounts · {(caption || "").length} chars
          </span>
        </div>

        {/* Post button */}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 14 }}>
          <button
            type="button"
            disabled
            className="btn btn-primary"
            style={{ cursor: "not-allowed" }}
          >
            <Icon name="upload" size={14}/> Post now
          </button>
        </div>
      </div>
    </div>
  );
}


// ---- QuickShareModal --------------------------------------------------------
// Guided-share popup. The user can edit the AI caption, copy it, and on Confirm
// we:
//   1) write the (possibly-edited) caption to the clipboard,
//   2) trigger a PNG download of the poster,
//   3) open the target platform's compose / home page in a new tab.
//
// The user then attaches the downloaded image and pastes the caption in the
// native platform UI. No OAuth, no API keys, no link-preview limitations — and
// it's the same UX shape we'll keep when we wire real one-click posting via
// Postiz later (just replace step 3 with an API call).

function QuickShareModal({ platform, job, caption, onClose }) {
  const PLATFORMS = {
    twitter: {
      label: "X / Twitter",
      icon: "twitter",
      // Empty compose modal — user attaches image + pastes caption manually.
      composeUrl: "https://x.com/intent/post",
      steps: [
        "We'll download the poster PNG to your device.",
        "We'll copy your caption to the clipboard.",
        "X opens in a new tab — drag in the downloaded PNG, paste the caption, then post.",
      ],
    },
    facebook: {
      label: "Facebook",
      icon: "facebook",
      // Facebook has no clean web compose URL; the homepage is the closest.
      composeUrl: "https://www.facebook.com/",
      steps: [
        "We'll download the poster PNG to your device.",
        "We'll copy your caption to the clipboard.",
        "Facebook opens — click \"What's on your mind?\", attach the PNG, paste the caption, then post.",
      ],
    },
    instagram: {
      label: "Instagram",
      icon: "instagram",
      composeUrl: "https://www.instagram.com/",
      steps: [
        "We'll download the poster PNG to your device.",
        "We'll copy your caption to the clipboard.",
        "Instagram opens — click the \"+\" / Create button, choose the downloaded PNG, paste the caption, then share.",
      ],
    },
  };
  const cfg = PLATFORMS[platform] || PLATFORMS.twitter;

  const [editedCaption, setEditedCaption] = React.useState(caption || "");
  const [copyStatus, setCopyStatus] = React.useState(null); // null | "ok" | "err"
  const [busy, setBusy] = React.useState(false);

  // Close on Escape.
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copyCaption = async () => {
    try {
      await navigator.clipboard.writeText(editedCaption || "");
      setCopyStatus("ok");
      setTimeout(() => setCopyStatus(null), 1800);
    } catch (_) {
      setCopyStatus("err");
      setTimeout(() => setCopyStatus(null), 1800);
    }
  };

  // Programmatic download via the same-origin FastAPI proxy. We can't fetch
  // the R2 signed URL directly from the browser (CORS), and a plain <a> with
  // a cross-origin href ignores the download attribute. The proxy endpoint
  // sets Content-Disposition: attachment for us, so the blob trick below
  // actually triggers a save dialog in every browser.
  const downloadPoster = async () => {
    if (!job?.job_id) return;
    // Same-origin proxy + ngrok-skip header (the wrapper api functions add it
    // automatically; we replicate the header here because we're calling fetch
    // directly to get the response as a blob).
    const resp = await fetch(window.api.downloadUrl(job.job_id), {
      headers: { "ngrok-skip-browser-warning": "1" },
    });
    if (!resp.ok) throw new Error(`Could not fetch poster (HTTP ${resp.status})`);
    const blob = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    // Filename hint — the server's Content-Disposition takes precedence when
    // present, but we pass one anyway for safety.
    a.download = `${job.tournament_id || "poster"}_${job.job_id}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Defer revoke so the download actually starts in Safari/Firefox.
    setTimeout(() => URL.revokeObjectURL(blobUrl), 4000);
  };

  const confirm = async () => {
    setBusy(true);
    try {
      // Best-effort clipboard copy first — if the user denied permission we
      // still want the download + redirect to proceed.
      try { await navigator.clipboard.writeText(editedCaption || ""); } catch (_) {}
      await downloadPoster();
      window.open(cfg.composeUrl, "_blank", "noopener,noreferrer");
      onClose();
    } catch (e) {
      // Keep the modal open and surface the error so the user can retry.
      window.toast.error(`Couldn't complete share: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      // Backdrop. Clicking outside the panel dismisses the modal.
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(8,8,10,0.72)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20,
      }}
    >
      <div
        className="card"
        style={{
          width: "min(100%, 520px)", maxHeight: "92vh", overflow: "auto",
          padding: 22, position: "relative",
          animation: "modalIn 180ms ease-out",
        }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="btn btn-ghost"
          style={{
            position: "absolute", top: 12, right: 12,
            padding: "4px 6px", fontSize: 12,
          }}
          title="Close (Esc)"
        >
          <Icon name="cross" size={12} />
        </button>

        <div className="row" style={{ gap: 12, marginBottom: 14 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 8,
            background: "var(--surface-2)", color: "var(--fg)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <Icon name={cfg.icon} size={18} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 15 }}>Quick share to {cfg.label}</div>
            <div className="hint" style={{ marginTop: 2 }}>Edit your caption, then confirm — we handle the rest.</div>
          </div>
        </div>

        {/* Steps */}
        <ol style={{ paddingLeft: 18, margin: "0 0 14px", fontSize: 12, color: "var(--fg-3)", lineHeight: 1.55 }}>
          {cfg.steps.map((s, i) => <li key={i} style={{ marginBottom: 2 }}>{s}</li>)}
        </ol>

        {/* Caption editor */}
        <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
          <div className="eyebrow">Description</div>
          <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)" }}>
            {editedCaption.length} chars
          </span>
        </div>
        <textarea
          value={editedCaption}
          onChange={(e) => setEditedCaption(e.target.value)}
          placeholder={caption ? "" : "Caption is still generating — type your own or wait a moment."}
          rows={5}
          disabled={busy}
          style={{
            width: "100%", boxSizing: "border-box", resize: "vertical",
            padding: "10px 12px", borderRadius: 8,
            background: "var(--bg-elev)", border: "1px solid var(--line-strong)",
            color: "var(--fg)", fontFamily: "var(--f-body)", fontSize: 13, lineHeight: 1.45,
          }}
        />

        {/* Copy button */}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
          <button
            className="btn btn-ghost"
            onClick={copyCaption}
            disabled={busy || !editedCaption}
            style={{ padding: "4px 10px", fontSize: 11 }}
          >
            <Icon name={copyStatus === "ok" ? "check" : "copy"} size={12} />
            {copyStatus === "ok" ? "Copied!" : copyStatus === "err" ? "Copy failed" : "Copy caption"}
          </button>
        </div>

        {/* Footer actions */}
        <div className="row" style={{ justifyContent: "space-between", marginTop: 18, gap: 8 }}>
          <button
            className="btn btn-ghost"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={confirm}
            disabled={busy || !job?.signed_url}
          >
            {busy ? "Preparing…" : <>Confirm <Icon name="arrow_right" size={14}/></>}
          </button>
        </div>

        <style>{`
          @keyframes modalIn {
            0%   { opacity: 0; transform: translateY(8px) scale(0.98); }
            100% { opacity: 1; transform: translateY(0)   scale(1); }
          }
        `}</style>
      </div>
    </div>
  );
}


Object.assign(window, { PosterResult, RatingCard });
