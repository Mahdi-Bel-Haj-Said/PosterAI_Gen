# Deploying EsportsPostAI on the Defendr VPS

**For the VPS administrator.** Follow the steps in order. Each one ends with a
check; if a check fails, stop and use that step's rollback rather than
continuing.

You do not need to know this codebase. Everything you need is below.

---

## What gets installed

| Thing | Where | Notes |
| --- | --- | --- |
| Database `defendr_poster_ai` | inside the **existing** MongoDB | new database, not a new server |
| Mongo user `poster_ai` | scoped to that database only | cannot read Defendr's data |
| Redis instance | new process on port **6380** | separate from Defendr's Redis |
| Application code | `/opt/epai` | fresh clone, own virtualenv |
| `epai-api` service | systemd | the HTTP API |
| `epai-worker` service | systemd | generates the posters |

Two Python processes, one database, one small Redis. No GPU required — all
model work happens at OpenAI and RunPod, over the network.

**Resource footprint:** roughly 1–2 GB RAM for both processes, and **~1 GB of
disk** for the Python environment. Most of that is the background-removal
library (`rembg`) and its numerical stack — onnxruntime, numpy, scipy, OpenCV.
Generated images go to Cloudflare R2, not local disk.

**No GPU needed.** All model inference happens at OpenAI and RunPod over the
network. The background remover runs on CPU by design (the small `u2netp`
model, ~1–2 s per image).

### On a 4 GB box — please read

This VPS already runs Defendr's production stack, and 4 GB is workable but not
roomy. A realistic split:

| | typical |
| --- | --- |
| MongoDB (WiredTiger cache defaults to ~50% of RAM − 1 GB) | ~1.5 GB |
| Defendr backend + frontend | ~0.5–0.8 GB |
| Nginx, Redis, OS | ~0.4 GB |
| This service, API + worker at peak | ~0.8 GB |

The risk is not slowness, it is the **OOM killer**: if RAM runs out, the kernel
kills whichever process it judges worst, and that is usually the largest — which
is MongoDB. Defendr would go down for a reason that looks nothing to do with
this deployment.

Two mitigations, both included:

1. **The unit files set `MemoryMax`** (512M for the API, 1G for the worker). If
   this service misbehaves, systemd kills *it* and restarts it. It can never be
   the cause of an OOM that takes Mongo down.
2. **Add swap if the box has none** — cheap insurance that turns a hard OOM into
   temporary slowness:

```bash
# check first; if 'Swap' shows 0, create some
free -h

sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**Record free memory in Step 1.** If less than ~1 GB is genuinely free once
Defendr is warm, say so before continuing rather than pressing on.

---

## Rules — please do not deviate

These exist because this service is being installed next to Defendr's
production stack.

1. **Never write to the `defendr` database.** The Mongo user created in Step 2
   is scoped so this is impossible, and Step 2 includes a test that proves it.
2. **Never restart or reconfigure `mongod`.** Creating a user does not require
   a restart. If something appears to need one, stop and ask.
3. **Never modify Defendr's Redis** — not its config file, not its data. Never
   run `FLUSHALL` or `FLUSHDB` on any Redis instance on this box.
4. **Never modify or restart Defendr's services or Nginx.** Everything created
   here is named `epai-*`. Nothing existing is edited.
5. **Do not put this service behind Nginx yet.** Step 8 covers access without
   touching the web server.

Every step below is additive. Nothing existing on the VPS is modified, which is
why each step can be undone with a single command.

---

## Before you start

You will need:

- **root or sudo** on the VPS
- **MongoDB admin credentials** (used once, in Step 2)
- **A way for the VPS to clone a private GitHub repo** — a deploy key or a
  personal access token. The repo is
  `https://github.com/DEFENDR-Esports/AI_POSTER_GENERATION.git`
- **The `.env` credentials file from Mahdi.** It contains the OpenAI, Gemini,
  Cloudflare R2 and RunPod keys. Ask him to send it through a password manager
  or an encrypted channel — not email or chat.

You will **generate two passwords yourself** during this process (one for the
Mongo user, one for Redis). They go into the `.env` on the server. Nobody else
needs them.

---

## Step 0 — System packages

The service needs **Python 3.10 or newer**. Check first — several long-running
distributions still ship 3.8 or 3.9, which will not work:

```bash
python3 --version
```

Install what is missing (Debian/Ubuntu; adjust for RHEL):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev build-essential git

# OpenCV arrives as a dependency of the background remover and needs these
# shared libraries present, even in its headless build.
sudo apt install -y libgl1 libglib2.0-0
```

You will also need two client tools, which are **not** always installed
alongside the servers themselves:

```bash
# the MongoDB shell — needed in Step 2 even though mongod is already running
mongosh --version || echo "install mongodb-mongosh"

# the Redis CLI and server — if Defendr already runs Redis these exist
redis-cli --version || echo "install redis-tools"
redis-server --version || echo "install redis-server"
```

> If Python 3.10+ is unavailable in your distribution's repositories, install it
> from the deadsnakes PPA or use `pyenv`. **Do not replace the system Python** —
> other software on the box may depend on the version that is there.

### Check

```bash
python3 --version        # 3.10 or higher
git --version
mongosh --version
redis-server --version
```

---

## Step 1 — Survey (read only)

Nothing is written in this step. Record the output; later steps refer to it.

```bash
# what is listening, and on which ports
sudo ss -lntp

# what is running
systemctl list-units --type=service --state=running

# free memory and disk
free -h && df -h /

# versions
mongod --version | head -1
redis-server --version
python3 --version
```

**Record these three things:**

1. **A free TCP port** for the API. `8010` is suggested; confirm nothing in the
   `ss` output uses it. You will need this in Step 5.
2. **Whether Redis is already running**, and on which port.
3. **The MongoDB port.** It may not be the default 27017.

**Also capture a baseline** so you can prove later that Defendr is unaffected:

```bash
# note the number this prints — you will compare against it at the end
mongosh "mongodb://<admin>:<pw>@localhost:<mongo-port>/admin" \
  --quiet --eval 'db.getSiblingDB("defendr").getCollectionNames().length'
```

---

## Step 2 — MongoDB: database and user

MongoDB creates a database implicitly, so there is nothing to "create". This
step only adds a restricted user. **No restart is needed and nothing is
interrupted.**

First generate a password and keep it somewhere safe:

```bash
openssl rand -base64 24
```

Then connect as admin and create the user:

```bash
mongosh "mongodb://<admin>:<pw>@localhost:<mongo-port>/admin"
```

```javascript
use defendr_poster_ai

db.createUser({
  user: "poster_ai",
  pwd:  "<the password you just generated>",
  roles: [ { role: "readWrite", db: "defendr_poster_ai" } ]
})
```

> The `use defendr_poster_ai` line before `createUser` matters. It places the
> user inside our database rather than in `admin`, which is what makes
> `authSource` work later. And the role is `readWrite` on that one database
> only — not `dbOwner`, not `root`, and nothing at all on `defendr`.

### Check — both must pass

**This must succeed** (our user can write to our database):

```bash
mongosh "mongodb://poster_ai:<password>@localhost:<mongo-port>/defendr_poster_ai?authSource=defendr_poster_ai" \
  --quiet --eval 'db.__probe.insertOne({ok:1}); print("write ok"); db.__probe.drop()'
```

**This must FAIL** (our user cannot see Defendr's data):

```bash
mongosh "mongodb://poster_ai:<password>@localhost:<mongo-port>/defendr_poster_ai?authSource=defendr_poster_ai" \
  --quiet --eval 'db.getSiblingDB("defendr").getCollectionNames()'
```

If the second command succeeds, the role is too broad. **Stop here** and fix it
before going further.

### Rollback

```javascript
use defendr_poster_ai
db.dropUser("poster_ai")
```

---

## Step 3 — Redis: a separate instance

Redis cannot restrict a password to one database, and `FLUSHALL` clears all of
them at once. Sharing Defendr's instance would mean a routine cache clear on
their side silently destroys this service's job queue. A second instance costs
a few megabytes.

```bash
# generate a password and keep it
openssl rand -base64 24

# copy their config — do not edit the original
sudo cp /etc/redis/redis.conf /etc/redis/redis-poster.conf
```

Edit **`/etc/redis/redis-poster.conf`** and set:

```
port 6380
requirepass <the Redis password you generated>
dir /var/lib/redis-poster
dbfilename poster.rdb
appendonly yes
appendfilename "poster.aof"
bind 127.0.0.1 -::1
protected-mode yes
```

> `appendonly yes` matters. This Redis holds a job queue, not a cache. With the
> default snapshot-only persistence, a crash loses the last few minutes of jobs —
> jobs that users have already been charged for.

```bash
sudo mkdir -p /var/lib/redis-poster
sudo chown redis:redis /var/lib/redis-poster
sudo systemctl enable --now redis-server@redis-poster
```

### Check

```bash
# ours answers
redis-cli -p 6380 -a '<redis-password>' ping        # PONG

# theirs is still fine
redis-cli -p <their-redis-port> ping                # PONG
```

### Rollback

```bash
sudo systemctl disable --now redis-server@redis-poster
sudo rm /etc/redis/redis-poster.conf
sudo rm -rf /var/lib/redis-poster
```

---

## Step 4 — Application user and code

Run the service as its own unprivileged user, not root:

```bash
sudo useradd --system --home /opt/epai --shell /usr/sbin/nologin epai

sudo git clone https://github.com/DEFENDR-Esports/AI_POSTER_GENERATION.git /opt/epai
cd /opt/epai

sudo python3 -m venv .venv
sudo .venv/bin/pip install --upgrade pip

# Dependencies are declared in pyproject.toml — there is no requirements.txt.
# This takes several minutes and downloads ~1 GB, mostly onnxruntime and the
# numerical stack behind the background remover.
#
# NOTE THE -e. Install editable, so the package keeps running from this
# directory instead of being copied into the virtualenv. A plain
# `pip install .` also works, but leaves the code in site-packages, where a
# future change to how the service finds its data directories has one less
# way to go wrong. Editable also means a deploy is `git pull` + restart,
# with no reinstall unless dependencies changed.
sudo .venv/bin/pip install -e .

sudo mkdir -p /opt/epai/scratch
sudo chown -R epai:epai /opt/epai
```

### Check

```bash
sudo -u epai /opt/epai/.venv/bin/python -c "import esports_poster_ai; print('imports ok')"
```

### Rollback

```bash
sudo rm -rf /opt/epai && sudo userdel epai
```

---

## Step 5 — Configuration

Put Mahdi's credentials file at `/opt/epai/.env`, then change the values below.
Everything else in that file — OpenAI, Gemini, R2, RunPod — stays as supplied.

```bash
sudo nano /opt/epai/.env
```

Set these:

```bash
# our database and user, on the existing MongoDB
MONGODB_URL=mongodb://poster_ai:<mongo-password>@localhost:<mongo-port>/defendr_poster_ai?authSource=defendr_poster_ai
MONGODB_DB=defendr_poster_ai

# our Redis from Step 3
REDIS_URL=redis://:<redis-password>@localhost:6380/0

# REQUIRED. Defaults to false; left false, the API is open to anyone.
API_KEY_REQUIRED=true

# the free port you found in Step 1
API_PORT=8010

WEBHOOKS_ENABLED=true
WEBHOOK_ALLOW_INSECURE_URLS=false
CORS_ALLOW_ORIGINS=
```

Then lock the file down — it holds every credential this service has:

```bash
sudo chown epai:epai /opt/epai/.env
sudo chmod 600 /opt/epai/.env
```

> **If a password contains `@`, `:`, `/` or `?`**, URL-encode it inside the
> connection string, or the string will not parse. Regenerating a password
> without those characters is easier.

---

## Step 6 — The two services

Both unit files are already in the repo at `/opt/epai/deploy/`.

```bash
sudo cp /opt/epai/deploy/epai-api.service    /etc/systemd/system/
sudo cp /opt/epai/deploy/epai-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now epai-api epai-worker
```

> **Both are required.** The API validates and queues; the worker generates. If
> the worker is not running, requests still return `202 Accepted` and then never
> complete — no error appears anywhere. Treat "is the worker running?" as a
> health check, not an assumption.
>
> **On every future deploy, restart both.** Each loads the pipeline at start-up,
> so restarting only the API leaves the worker running the previous version.

### Check

```bash
systemctl is-active epai-api epai-worker          # active, active

curl -s localhost:8010/health
# expected: {"status":"ok","mongodb":"ok","redis":"ok"}
```

If `/health` reports anything other than `ok` for mongodb or redis, the
connection strings in Step 5 are wrong — check `authSource` first, it is the
most common mistake.

```bash
# if something is not right
sudo journalctl -u epai-api -n 50 --no-pager
sudo journalctl -u epai-worker -n 50 --no-pager
```

### Rollback

```bash
sudo systemctl disable --now epai-api epai-worker
sudo rm /etc/systemd/system/epai-api.service /etc/systemd/system/epai-worker.service
sudo systemctl daemon-reload
```

---

## Step 7 — Create the API key for Defendr

This registers Defendr as a client and prints an API key **once**. It cannot be
recovered afterwards — if it is lost, the fix is to issue a new one.

```bash
cd /opt/epai
sudo -u epai .venv/bin/python scripts/bootstrap_defendr_platform.py --name Defendr
```

**Send the printed key to Mahdi through a password manager or an encrypted
channel.** It authenticates every request Defendr makes to this service.

---

## Step 8 — Give Mahdi access for testing

He will run the Defendr platform on his own machine and point it at this
service, so he needs to reach port 8010. **Please do not expose it publicly** —
pick one of these.

### Option A — SSH tunnel (recommended)

Create a restricted user that can forward a port and nothing else:

```bash
sudo useradd -m -s /usr/sbin/nologin epai-tunnel
sudo mkdir -p /home/epai-tunnel/.ssh
# paste Mahdi's PUBLIC key (safe to send over chat) into:
sudo nano /home/epai-tunnel/.ssh/authorized_keys
sudo chown -R epai-tunnel:epai-tunnel /home/epai-tunnel/.ssh
sudo chmod 700 /home/epai-tunnel/.ssh && sudo chmod 600 /home/epai-tunnel/.ssh/authorized_keys
```

This account cannot open a shell or run commands — only forward a port.

He then runs, on his own machine:

```bash
ssh -N -L 8010:localhost:8010 epai-tunnel@<vps-host>
```

Nothing is exposed to the internet, no certificate is needed, and Nginx is
never touched.

### Option B — firewall rule limited to his IP

```bash
sudo ufw allow from <his-public-ip> to any port 8010 proto tcp
```

Simpler, but the traffic is unencrypted and the rule needs updating whenever
his IP changes. Option A is better.

---

## Step 9 — Confirm Defendr is unaffected

```bash
# their services still running
systemctl is-active <their-service-names>

# their site still responds
curl -s -o /dev/null -w "%{http_code}\n" https://<defendr-domain>

# their database untouched — must equal the number recorded in Step 1
mongosh "mongodb://<admin>:<pw>@localhost:<mongo-port>/admin" \
  --quiet --eval 'db.getSiblingDB("defendr").getCollectionNames().length'

# their Redis still answering
redis-cli -p <their-redis-port> ping
```

---

## What to send back to Mahdi

| Item | How |
| --- | --- |
| **The API key** from Step 7 | password manager / encrypted |
| **The API port** you chose (e.g. 8010) | ordinary channel — not secret |
| **The VPS hostname** and the tunnel username | ordinary channel |
| Confirmation that `/health` returns all `ok` | ordinary channel |

**Not needed by anyone else:** the Mongo password, the Redis password, and the
`.env` contents. Those stay on the server.

---

## Complete removal

If this needs to be undone entirely, in this order:

```bash
sudo systemctl disable --now epai-api epai-worker
sudo rm /etc/systemd/system/epai-api.service /etc/systemd/system/epai-worker.service
sudo systemctl daemon-reload

sudo systemctl disable --now redis-server@redis-poster
sudo rm /etc/redis/redis-poster.conf && sudo rm -rf /var/lib/redis-poster

sudo rm -rf /opt/epai && sudo userdel epai
sudo userdel -r epai-tunnel        # if Option A was used
```

```javascript
// and in mongosh, as admin
use defendr_poster_ai
db.dropDatabase()       // drops OUR database only
db.dropUser("poster_ai")
```

Nothing belonging to Defendr is touched by any of the above.

---

## Troubleshooting

**`/health` shows `mongodb: error`** — the connection string is wrong. Check
`authSource=defendr_poster_ai` is present and matches where the user was
created. Then verify the password has no unencoded `@ : / ?`.

**`/health` shows `redis: error`** — check the instance is running
(`systemctl status redis-server@redis-poster`) and that the password in
`REDIS_URL` matches `requirepass` in `redis-poster.conf`.

**Requests return `202` but posters never finish** — the worker is not running.
`systemctl status epai-worker`, then `journalctl -u epai-worker`.

**The worker keeps stopping** — that is expected behaviour on a Redis
connection timeout; RQ exits rather than reconnecting. `Restart=always` in the
unit file handles it. If it is restarting repeatedly, the Redis connection is
unstable.

**API will not start, port already in use** — pick another port in
`API_PORT` and restart. Step 1's `ss -lntp` shows what is taken.

---

## One thing worth checking first

While testing this integration, the MongoDB port on this VPS answered `ping`
but **refused new TCP connections** from outside. The Defendr backend continued
working only because it had an open connection pool from earlier.

If that is still the case, Defendr will fail on its next restart — and Step 2
needs a working connection. It is worth confirming that the database accepts new
connections before starting.
