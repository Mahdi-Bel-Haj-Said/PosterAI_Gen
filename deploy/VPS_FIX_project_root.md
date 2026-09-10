# Fix: poster generation fails with "Backgrounds directory not found"

**For the VPS administrator.** One command fixes this. You do not need to know
the codebase — everything you need is below.

Nothing is deleted, no configuration changes, no new credentials, and no data
is touched. The database is intact and does not need restoring.

---

## The fix

```bash
cd /home/defendr/AI_POSTER_GENERATION
sudo .venv/bin/pip install -e . --no-deps
sudo chown -R $(stat -c '%U:%G' /home/defendr/AI_POSTER_GENERATION/.venv) /home/defendr/AI_POSTER_GENERATION
sudo systemctl restart epai-api epai-worker
```

That is the whole change: the package is reinstalled in **editable** mode
instead of copied mode. Same code, same `.env`, same database.

- `--no-deps` avoids re-resolving the ~1 GB dependency tree. Everything is
  already installed; only the install *mode* of this one package changes.
- The `chown` line matters because `sudo pip` writes an `egg-info` directory
  into the source tree as root, and the service runs as a different user. The
  `stat` reuses whichever user already owns the deployment, so you do not need
  to look it up.
- **Restart both services.** Each loads the pipeline at start-up, so restarting
  only the API leaves the worker running the old code — and the worker is what
  generates posters.

---

## Why it is failing

Every poster job fails immediately with:

```
FileNotFoundError: Backgrounds directory not found:
/home/defendr/AI_POSTER_GENERATION/.venv/lib/python3.10/backgrounds
```

That directory does not exist, and it should never have been looked for. The
real one is `/home/defendr/AI_POSTER_GENERATION/backgrounds`, which is present
(it ships in the git repo).

The application locates its own files relative to its source file
(`src/esports_poster_ai/config.py`):

```python
# parents[0]=esports_poster_ai, parents[1]=src, parents[2]=repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

That arithmetic is correct **only while the package lives in `src/`**.

Step 4 of `VPS_DEPLOYMENT.md` says `pip install .`, which *copies* the package
into the virtualenv's `site-packages`. From there the same expression walks up
into the venv instead of the repo:

| | installed with `pip install .` (now) | installed with `pip install -e .` (fix) |
| --- | --- | --- |
| file location | `.venv/lib/python3.10/site-packages/esports_poster_ai/` | `<repo>/src/esports_poster_ai/` |
| `parents[1]` | `site-packages` | `src` |
| `parents[2]` | `.venv/lib/python3.10` ✗ | `<repo>` ✓ |
| backgrounds path | `.venv/lib/python3.10/backgrounds` ✗ | `<repo>/backgrounds` ✓ |

So this is not a configuration mistake on your side — the deployment guide's
install command is wrong for how this code resolves its paths. That guide will
be corrected.

### This affects more than backgrounds

Five settings are derived from that root. Only the first fails loudly:

| Setting | Effect while broken |
| --- | --- |
| `backgrounds_dir` | **every job fails** — the error above |
| `styles_dir` | Style DNA source not found |
| `keyart_captions_dir` | prompt exemplars silently unavailable — **no error**, posters are just lower quality |
| `outputs_dir` | writes land inside the virtualenv |
| `.env` file path | the app's own `.env` loader looks in the wrong place |

That last row is worth knowing: the service works today only because the
systemd units supply the environment via `EnvironmentFile=`. The application's
built-in `.env` loading has been inactive since installation. The fix restores
it, so no behaviour is lost either way.

---

## Verifying it worked

```bash
# 1. both services up
systemctl is-active epai-api epai-worker        # active, active

# 2. still healthy
curl -s localhost:8010/health
# {"status":"ok","mongodb":"ok","redis":"ok"}

# 3. the path is now resolved correctly — this is the real check
sudo -u $(stat -c '%U' /home/defendr/AI_POSTER_GENERATION/.venv) \
  /home/defendr/AI_POSTER_GENERATION/.venv/bin/python -c \
  "from esports_poster_ai.config import get_settings as g; s=g(); \
   print('root       :', s.project_root); \
   print('backgrounds:', s.backgrounds_dir, s.backgrounds_dir.exists())"
# expected:
#   root       : /home/defendr/AI_POSTER_GENERATION
#   backgrounds: /home/defendr/AI_POSTER_GENERATION/backgrounds True
```

If step 3 prints `True`, the fix is in and Mahdi can generate a poster.

If a service does not come back `active`, check
`journalctl -u epai-worker -n 50 --no-pager`.

### This fix was tested before being sent

The failure was reproduced in a clean virtualenv against this exact
`pyproject.toml`, then the fix applied on top of the already-installed copy —
the same situation as on the VPS:

```
pip install .    --no-deps   ->  backgrounds_dir = <venv>/Lib/backgrounds     (reproduces the bug)
pip install -e . --no-deps   ->  Found existing installation: esports-poster-ai 0.1.0
                                 Successfully uninstalled esports-poster-ai-0.1.0
                                 Successfully installed esports-poster-ai-0.1.0
                             ->  backgrounds_dir = <repo>/backgrounds  EXISTS
```

pip removes the copied version itself, so the existing installation is not a
problem and no manual uninstall is needed.

---

## Rollback

If anything looks wrong, the previous state is one command away:

```bash
cd /home/defendr/AI_POSTER_GENERATION
sudo .venv/bin/pip install . --no-deps
sudo systemctl restart epai-api epai-worker
```

---

## Not urgent, but worth knowing

These do not block poster generation. No action needed today.

1. **The deployment guide's paths are stale.** `VPS_DEPLOYMENT.md` and both
   unit files in `deploy/` still say `/opt/epai`, while the service actually
   lives in `/home/defendr/AI_POSTER_GENERATION`. The shipped units also carry
   `ProtectHome=true` and `ReadWritePaths=/opt/epai/scratch`, so they have
   clearly been edited already. If you kept your edited copies somewhere, it
   would help to know where, so the repo can be brought in line.

2. **No webhook is registered for the `defendr` platform.** Completion
   callbacks will never be delivered. Polling covers it for now, so this only
   needs doing before real production traffic — and it is Mahdi's call, not a
   server task.

3. **A leftover API key is still active.** A key named `smoke-test`, from
   before multi-tenancy was switched on, is unrevoked in the database. It is a
   live credential nobody is tracking. Mahdi can revoke it via the admin
   endpoint; no server access required.

---

## What you do *not* need to do

- Do not edit `.env` — no variable changes are required.
- Do not re-clone, re-deploy, or pull new code — the code is fine as-is.
- Do not touch MongoDB or Redis — the database is complete and verified.
- Do not reinstall dependencies — `--no-deps` is deliberate.
