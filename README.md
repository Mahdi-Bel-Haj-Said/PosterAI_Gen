# EsportsPostAI

Generative-AI service that turns a single JSON brief into a publish-ready esports poster in under a minute.

Not a wrapper around an image API: the backgrounds come from a **diffusion model I fine-tuned myself**, and the composition is driven by a structured prompt compiler rather than a hand-written prompt string.

```
POST /posters  { tournament, match, design, ... }   ->  job_id
GET  /posters/{job_id}                              ->  signed URL to a 1080x1920 PNG
```

---

## How it works

Two models, each doing the job it is actually good at.

```
 JSON brief
     |
     v
 [ 1 ] Prompt compiler .... 14 composable blocks -> one deterministic prompt
     |                      (poster type, layout pattern, typography,
     |                       fact hierarchy, energy budget, game rules...)
     v
 [ 2 ] Background bank .... fine-tuned Qwen-Image + `lol_keyart` LoRA
     |                      pre-generated on RunPod serverless GPUs,
     |                      served instantly (delete-on-serve)
     v
 [ 3 ] GPT-4o Vision ...... reads the chosen background, writes the image prompt
     |
     v
 [ 4 ] Image model ........ renders the final composed poster
     |
     v
 R2 object storage + signed URL + optional webhook
```

**The interesting problem.** Stage 3 is a "telephone hop": GPT-4o rewrites the brief on the way through, and quietly drops or rewords hard facts — prize pools, team names, the requested emphasis. Stage 4 then renders whatever survived. The fix was to stop arguing with the rewrite and re-inject the non-negotiable facts *directly onto the final image prompt* as a footer the vision model never sees:

- `build_image_factual_footer()` — the values that must appear verbatim
- `build_image_style_footer()` — palette, energy and effect budget
- `build_image_prize_pool_rule()` — explicit visual-hierarchy rule

A related lesson lives in the layout module: offering the model a menu of ten composition patterns produced the *same* composition every time, so the pattern is now **sampled in code** and handed over as already-decided. Structure beats adjectives.

---

## The fine-tuned model

The background library is not stock imagery and not an off-the-shelf checkpoint.

| | |
|---|---|
| Base | Qwen-Image-2512 (20B diffusion transformer) |
| Method | LoRA, trained with [ai-toolkit](https://github.com/ostris/ai-toolkit) |
| Dataset | Curated League of Legends key art, hand-captioned (`Prompts/`) |
| Trigger | `lol_keyart` |
| Serving | Custom RunPod serverless worker (`runpod-worker/`), weights on a network volume |

Backgrounds are generated **ahead of demand** into a bank of 24 combinations (4 energy levels x 6 visual vibes). A request pulls one instantly and deletes it, so no poster reuses a background and the 60-second GPU step never sits on the request path. A locked, single-flight refill tops up any combo that drops below threshold.

---

## Architecture

Multi-tenant from the ground up: **platform -> organisation -> tournament**. An API key authenticates a platform; every stored object is namespaced so two platforms can reuse the same org id with no collision.

```
defendr-poster-ai/system/backgrounds/                              <- shared bank
defendr-poster-ai/platforms/{pid}/orgs/{oid}/assets/{type}/...     <- brand library
defendr-poster-ai/platforms/{pid}/orgs/{oid}/tournaments/{tid}/
        style-dna.json                                             <- visual identity
        posters/{poster_id}.png
```

| Concern | Choice | Why |
|---|---|---|
| API | FastAPI | async, typed, OpenAPI for free |
| Queue | RQ + Redis (`poster-ai`) | generation is 40-90s; never block HTTP |
| System of record | MongoDB | RQ forgets finished jobs; billing must not |
| Object storage | Cloudflare R2 | zero egress — posters get served repeatedly |
| GPU | RunPod serverless | bursty refills; a 24/7 GPU would be dead money |

Consistency across a tournament is handled by a **Style DNA** — a palette and lighting fingerprint extracted once and replayed, so every poster in a series looks related without re-describing the look each time.

---

## Stack

`Python 3.10` · `FastAPI` · `RQ` / `Redis` · `MongoDB` · `Cloudflare R2` · `Diffusers` / `PEFT` · `RunPod` · `React`

**Scope:** 5 poster types · 2 games (LoL, Valorant) · 3 output formats · ~$0.05 per poster
**Tests:** 430+ test functions across 53 files, covering the deterministic layer — prompt assembly, layout selection, storage keys, billing and quota logic

---

## Quick start

```bash
git clone https://github.com/Mahdi-Bel-Haj-Said/PosterAI_Gen.git
cd PosterAI_Gen
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -e .
cp .env.example .env                                 # set OPENAI_API_KEY at minimum
```

Run the API and a worker in two terminals:

```bash
uvicorn esports_poster_ai.api.app:app --reload --port 8000
```

```bash
rq worker poster-ai --worker-class rq.SimpleWorker --url redis://localhost:6379/0
```

Then `http://localhost:8000/docs` for the interactive API, or generate straight from a sample brief:

```bash
python run.py --input inputs/lol/tournament_announcement.json
```

> **Note on assets.** Brand material (team logos, player photos, game key art) is excluded from this repository — it is third-party trademarked content. `assets/` and `backgrounds/` are gitignored; drop your own files in with the same folder layout, or point the service at R2. Sample JSON briefs in `inputs/` and the LoRA caption set in `Prompts/` are included.

---

## Repository map

```
src/esports_poster_ai/
  prompt/blocks/      the 14 prompt blocks + assembler
  stages/             background -> vision -> render pipeline
  bank/               pre-generated background bank, locking, durable drain
  storage/            R2 / local backends, tenant-namespaced key builder
  api/routes/         FastAPI surface
  jobs/ orgs/ auth/   Mongo-backed stores
runpod-worker/        the fine-tuned model's serving container
Poster-ai-frontend/   React demo UI
Prompts/              LoRA training captions
tests/                430+ tests
```

---

## Full documentation

This README is the short version. The complete design record — API reference, prompt-block specification, deployment runbook, integration guide and the reasoning behind each architectural decision — is in **[DOCUMENTATION.md](DOCUMENTATION.md)**.

Additional design documents: [`design.md`](design.md) · [`use_cases.md`](use_cases.md) · [`class_diagram.md`](class_diagram.md) · [`deployment_diagram.md`](deployment_diagram.md)

---

Built by **Mahdi Bel Haj Said**. Developed at and deployed in production for [Defendr.gg](https://defendr.gg).
