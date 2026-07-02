// job-progress.jsx — Generation in flight (polls real job status)

const STAGES = [
  { id: "queued",                label: "Queued",              detail: "Job accepted by orchestrator" },
  { id: "generating_prompt",     label: "Generating prompt",   detail: "Translating your inputs into AI prompt" },
  { id: "generating_poster",     label: "Generating poster",   detail: "Diffusion model composing the image" },
  { id: "applying_sponsor_bar",  label: "Applying sponsor bar",detail: "Compositing logos into the final layout" },
  { id: "completed",             label: "Done",                detail: "Poster ready" },
];

const STATUS_TO_INDEX = STAGES.reduce((acc, s, i) => { acc[s.id] = i; return acc; }, {});

function JobProgress({ navigate, jobId }) {
  const [job, setJob] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [elapsed, setElapsed] = React.useState(0);

  // wall clock
  React.useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // poll the job
  React.useEffect(() => {
    if (!jobId) {
      setError("Missing job id. Go back to the dashboard and try again.");
      return;
    }
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      try {
        const j = await window.api.getPoster(jobId);
        if (cancelled) return;
        setJob(j);
        if (j.status === "completed") {
          // The submitted job succeeded — the wizard draft is no longer needed.
          if (window.clearWizardDraft) window.clearWizardDraft();
          setTimeout(() => navigate(`#/result/${jobId}`), 600);
          return;
        }
        if (j.status === "failed") {
          setError(j.error || "Generation failed.");
          return;
        }
        timer = setTimeout(tick, 2000);
      } catch (e) {
        if (cancelled) return;
        setError(e.message || "Couldn't fetch job status");
        timer = setTimeout(tick, 4000);
      }
    };
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [jobId]);

  const status = job?.status || "queued";
  const stageIdx = STATUS_TO_INDEX[status] ?? 0;
  const current = STAGES[stageIdx];

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 28 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>JOB <span className="mono" style={{ color: "var(--fg-2)" }}>{jobId ? jobId.slice(0, 10) : "—"}</span></div>
          <h1>{status === "failed" ? "Generation failed" : "Generating your poster"}</h1>
          <p>{status === "failed" ? "Something went wrong — see the error below." : "Usually 20–60 seconds. You can navigate away — the dashboard will show it when ready."}</p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24 }}>
        {/* Generator viz */}
        <div className="card" style={{
          padding: 0, overflow: "hidden", position: "relative",
          aspectRatio: "9 / 16", maxHeight: 620, justifySelf: "center", width: "100%", maxWidth: 360,
          background: "linear-gradient(160deg, oklch(15% 0.04 8) 0%, oklch(10% 0.012 350) 50%, oklch(13% 0.06 195) 100%)",
        }}>
          <GeneratorViz stageIdx={stageIdx} label={current?.label || "Working"} />
        </div>

        {/* Stages + Summary */}
        <div className="col" style={{ gap: 18 }}>
          <div className="card" style={{ padding: 20 }}>
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 18 }}>
              <span className="mono" style={{ fontSize: 11, letterSpacing: "0.12em", color: "var(--cy)", textTransform: "uppercase" }}>● Pipeline</span>
              <span className="mono" style={{ fontSize: 12, color: "var(--fg-2)" }}>{String(Math.floor(elapsed/60)).padStart(2,"0")}:{String(elapsed%60).padStart(2,"0")}</span>
            </div>
            <div className="col" style={{ gap: 14 }}>
              {STAGES.map((s, i) => {
                const done = i < stageIdx;
                const active = i === stageIdx && status !== "failed";
                return (
                  <div key={s.id} className="row" style={{ gap: 14, alignItems: "flex-start" }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: "50%",
                      background: done ? "var(--crim)" : active ? "transparent" : "var(--surface-3)",
                      border: active ? "2px solid var(--cy)" : "0",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0,
                      animation: active ? "pulse 1.4s ease-in-out infinite" : "none",
                    }}>
                      {done ? <Icon name="check" size={12}/> :
                       active ? <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--cy)" }} /> :
                       <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)" }}>{i+1}</span>}
                    </div>
                    <div style={{ flex: 1, paddingTop: 2 }}>
                      <div style={{
                        fontWeight: active ? 600 : 500, fontSize: 13.5,
                        color: done ? "var(--fg-2)" : active ? "var(--fg)" : "var(--fg-4)",
                      }}>{s.label}</div>
                      <div style={{ fontSize: 11.5, color: active ? "var(--fg-3)" : "var(--fg-4)", marginTop: 2 }}>{s.detail}</div>
                      {active && (
                        <div style={{ marginTop: 8, height: 2, background: "var(--surface-3)", borderRadius: 999, overflow: "hidden" }}>
                          <div style={{
                            height: "100%",
                            background: "linear-gradient(90deg, var(--crim), var(--cy))",
                            animation: "fill 1.6s ease-out infinite",
                          }} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {error && (
            <div className="card" style={{ padding: 16, borderColor: "var(--crim)", background: "var(--crim-soft)" }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Error</div>
              <div className="mono" style={{ fontSize: 11.5, whiteSpace: "pre-wrap" }}>{error}</div>
            </div>
          )}

          {job && (
            <div className="card" style={{ padding: 18 }}>
              <div className="eyebrow" style={{ marginBottom: 12 }}>Summary</div>
              <div className="col" style={{ gap: 10 }}>
                <SumRow label="Mode" value={job.mode} />
                <SumRow label="Tournament" value={job.tournament_id} />
                <SumRow label="Org" value={job.org_id} />
                <SumRow label="Status" value={job.status} />
                <SumRow label="Created" value={new Date(job.created_at).toLocaleString()} />
              </div>
            </div>
          )}

          <div className="row" style={{ gap: 10 }}>
            {status === "failed" ? (
              <>
                {/* Reopen the wizard at the background step with all inputs still
                    filled in, so the user just swaps the background and retries. */}
                <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => {
                  if (window.setWizardDraftStep) window.setWizardDraftStep(window.WIZARD_BACKGROUND_STEP || 4);
                  navigate("#/create");
                }}>
                  <Icon name="image" size={14} /> Change background &amp; retry
                </button>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => navigate("#/")}>
                  <Icon name="home" size={14} /> Back to dashboard
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => navigate("#/")}>
                  <Icon name="home" size={14} /> Back to dashboard
                </button>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => navigate("#/create")}>
                  <Icon name="plus" size={14} /> Start another
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 oklch(82% 0.155 195 / 0.5); }
          50% { box-shadow: 0 0 0 8px oklch(82% 0.155 195 / 0); }
        }
        @keyframes fill {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}

function SumRow({ label, value }) {
  return (
    <div className="row" style={{ justifyContent: "space-between", gap: 12 }}>
      <span className="mono" style={{ fontSize: 10.5, letterSpacing: "0.1em", color: "var(--fg-3)", textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontSize: 12.5, fontWeight: 500, textAlign: "right" }}>{value}</span>
    </div>
  );
}

function GeneratorViz({ stageIdx, label }) {
  const reveal = stageIdx >= 3 ? 1 : stageIdx / 3.5;
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div className="ai-grid" style={{ position: "absolute", inset: 0, opacity: 0.4 }} />

      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{
            position: "absolute",
            width: 200 + i * 60, height: 200 + i * 60,
            border: "1px solid var(--cy-line)",
            borderRadius: "50%",
            opacity: stageIdx < 4 ? 0.4 - i * 0.1 : 0,
            animation: `ring 3s ease-out ${i * 0.5}s infinite`,
            transition: "opacity .6s",
          }} />
        ))}
      </div>

      <div style={{
        position: "absolute",
        inset: "16% 14%",
        borderRadius: 8,
        overflow: "hidden",
        background: `linear-gradient(140deg, oklch(40% 0.20 15), oklch(15% 0.06 280))`,
        opacity: stageIdx >= 1 ? 1 : 0,
        transition: "opacity .6s",
        boxShadow: "0 30px 80px -20px oklch(65% 0.230 8 / 0.5)",
      }}>
        <div style={{
          position: "absolute", inset: 0,
          background: `repeating-conic-gradient(from 0deg, rgba(255,255,255,0.05) 0deg 3deg, rgba(0,0,0,0.05) 3deg 6deg)`,
          mixBlendMode: "overlay",
          opacity: 1 - reveal,
          transition: "opacity .8s",
        }} />
        {stageIdx >= 1 && stageIdx < 4 && (
          <div style={{
            position: "absolute", left: 0, right: 0, height: 2,
            background: "linear-gradient(90deg, transparent, var(--cy), transparent)",
            boxShadow: "0 0 20px var(--cy)",
            animation: "scan 2.4s ease-in-out infinite",
            top: 0,
          }} />
        )}
      </div>

      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: 20, textAlign: "center" }}>
        <div className="mono" style={{ fontSize: 10.5, letterSpacing: "0.16em", color: "var(--cy)", textTransform: "uppercase" }}>
          ● {label}
        </div>
      </div>

      <style>{`
        @keyframes ring {
          0% { transform: scale(0.6); opacity: 0.5; }
          100% { transform: scale(1.4); opacity: 0; }
        }
        @keyframes scan {
          0% { top: -2px; }
          50% { top: calc(100% - 2px); }
          100% { top: -2px; }
        }
      `}</style>
    </div>
  );
}

Object.assign(window, { JobProgress });
