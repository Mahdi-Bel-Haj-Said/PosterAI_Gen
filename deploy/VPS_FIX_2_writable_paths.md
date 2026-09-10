# Fix #2: the service has nowhere to write

**For the VPS administrator.** Follow-up to `VPS_FIX_project_root.md`.

**The first fix worked.** Poster generation now runs the whole pipeline instead
of failing instantly. It gets as far as producing the image, then dies on the
last step because the service has no writable directory.

This document covers **everything** still missing, so this should be the last
round. The code was audited end to end for filesystem access — the findings and
what was ruled out are listed at the bottom.

---

## What to change

Two edits, then restart. Roughly five minutes.

### 1. Give both services a writable state directory

Add this line to the `[Service]` section of **both** unit files
(`epai-api.service` and `epai-worker.service`):

```ini
StateDirectory=epai
```

systemd creates `/var/lib/epai`, owns it to the service user, and makes it
writable even under `ProtectSystem=strict`. No `mkdir` or `chown` needed, and it
survives restarts and reboots.

### 2. Point the service at it

Add these two lines to the `EnvironmentFile` (the `.env` the units load):

```bash
OUTPUTS_DIR=/var/lib/epai/outputs
U2NET_HOME=/var/lib/epai/u2net
```

### 3. Apply

```bash
sudo systemctl daemon-reload
sudo systemctl restart epai-api epai-worker
```

### 4. Pre-download the background-removal model

Optional but recommended — it turns a slow, failure-prone first upload into a
one-off step you can watch:

```bash
cd /home/defendr/AI_POSTER_GENERATION
sudo -u $(stat -c '%U' .venv) U2NET_HOME=/var/lib/epai/u2net \
  .venv/bin/python -c "from rembg import new_session; new_session('u2netp'); print('rembg ok')"
```

Prints `rembg ok` and leaves a ~4 MB model file in `/var/lib/epai/u2net`.

---

## Why

### Problem 1 — the generated poster cannot be saved (confirmed, blocking)

A test job ran the full pipeline and failed at the very end:

```
generating_prompt -> generating_poster -> failed
OSError: [Errno 30] Read-only file system:
'/home/defendr/AI_POSTER_GENERATION/outputs'
```

The image had already been generated successfully. The code writes a local copy
before uploading to Cloudflare R2, and that write is what failed — so a poster
that cost real money to produce was thrown away one line before it would have
been stored.

The cause is the unit files' own sandboxing:

```ini
ProtectSystem=strict
ReadWritePaths=/opt/epai/scratch
```

`ProtectSystem=strict` makes the entire filesystem read-only except what
`ReadWritePaths` lists — and that list points at `/opt/epai`, which is not where
the service is installed. So nothing under `/home/defendr/AI_POSTER_GENERATION`
is writable.

Note this only surfaced now. Before the first fix the path resolved to somewhere
inside the virtualenv and the job never got far enough to attempt the write.

### Problem 2 — brand-library uploads will fail (not yet triggered)

Uploading a team or sponsor logo runs a background remover (`rembg`), and the
web UI has that switched **on by default**. On first use the library downloads
its model to `~/.u2net`.

The unit files set `ProtectHome=true`, which makes the service user's home
directory unreadable — so that download cannot happen and the upload fails.
`U2NET_HOME` redirects it to the writable state directory instead.

Nobody has hit this yet only because no logo has been uploaded since deployment.
It would have been the next thing to break.

---

## Verifying it worked

```bash
# 1. both services came back
systemctl is-active epai-api epai-worker      # active, active

# 2. the state directory exists and belongs to the service user
ls -ld /var/lib/epai

# 3. the service resolves outputs to the writable location
cd /home/defendr/AI_POSTER_GENERATION
sudo -u $(stat -c '%U' .venv) .venv/bin/python -c \
  "from esports_poster_ai.config import get_settings as g; print('outputs:', g().outputs_dir)"
# expected: outputs: /var/lib/epai/outputs

# 4. still healthy
curl -s localhost:8010/health
# {"status":"ok","mongodb":"ok","redis":"ok"}
```

Mahdi will then submit a test poster and can confirm it reaches `completed`.

---

## Rollback

Remove the two `.env` lines and the `StateDirectory=epai` line from both units,
then:

```bash
sudo systemctl daemon-reload && sudo systemctl restart epai-api epai-worker
```

`/var/lib/epai` can be left in place; it is inert once nothing points at it.

---

## What was audited and found safe

The whole codebase was checked for filesystem access, so this should be the last
of these. Everything below needs no action:

| Area | Finding |
| --- | --- |
| Image resizing / quality processing | writes to in-memory buffers (`io.BytesIO`), never disk |
| Fonts | none are loaded — the image model renders all text; no font files to install |
| `backgrounds/`, `styles/`, `Prompts/` | read-only, and all three ship in the git repo |
| Game-logo lookup | guarded — logs a warning and continues if a file is absent |
| Subprocess use | only in the background-bank tooling, which the poster pipeline never calls |
| Generated posters | authoritative copy goes to Cloudflare R2; the local copy is a leftover and is not needed |

**One latent risk, no action needed today.** If any of the four R2 environment
variables were ever missing or misspelled, the code silently falls back to
storing posters on local disk under the install directory — which is read-only,
so generation would start failing with no obvious link to R2. R2 is correctly
configured right now. Worth knowing if posters ever start failing after an
`.env` edit.

---

## Also worth correcting while you are in these files

The unit files in the repo still describe the old layout, which is how problem 1
arose:

- `WorkingDirectory=/opt/epai` and `ReadWritePaths=/opt/epai/scratch` — both
  point at a directory that does not exist on this server.
- `ProtectHome=true` — the service lives under `/home/defendr`, so this cannot
  be set as shipped; your working copies must already differ.

If you can share your edited unit files, they will be committed to the repo so
the next deployment starts from what actually runs here.
