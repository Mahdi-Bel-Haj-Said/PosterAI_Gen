"""
`/p/{job_id}` — public share landing page.

When a user clicks "Share to Twitter/Facebook" in the frontend, we send the
social platform to this page (NOT the raw R2 signed URL). The page returns a
minimal HTML document carrying OpenGraph + Twitter Card meta tags, which the
platforms scrape to build their preview cards (image, title, description).

Why this exists
---------------
Twitter does not render image cards for arbitrary direct image URLs anymore —
it needs an HTML page with `twitter:card` + `twitter:image` meta tags. Our R2
signed URLs are also long and expire, which makes them unusable as long-lived
share links.

This route solves both:
  * Stable URL  — /p/{job_id} never changes for a given job.
  * Fresh image — a new signed URL is generated on every visit, so the og:image
                  link never breaks even after the old presign expires.
  * Rich cards  — proper meta tags so Twitter / Facebook / LinkedIn /
                  WhatsApp / Discord all render the poster as an image card.

Humans hitting the page get redirected (meta refresh) to the poster image;
crawlers (Twitterbot, facebookexternalhit, etc.) ignore the refresh and just
scrape the meta tags.
"""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from esports_poster_ai.api.routes.posters import get_job_store
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.job import Job
from esports_poster_ai.jobs.store import JobStore
from esports_poster_ai.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["share"])


# ---- Title / description helpers -------------------------------------------
# These are placeholders for the Gemini-generated caption that will land in a
# follow-up. Keep them deterministic and cheap; the social-card preview should
# never depend on an LLM call.

_POSTER_TYPE_LABEL = {
    "gameday": "Gameday",
    "roster_reveal": "Roster Reveal",
    "tournament_announcement": "Tournament Announcement",
    "tournament_banner": "Tournament Banner",
    "game_results": "Match Results",
}


def _derive_title(job: Job) -> str:
    """Human-readable title for the share card — e.g. "EWC 2026 — Gameday"."""
    poster_type = ((job.input_data or {}).get("_meta") or {}).get("poster_type", "")
    label = _POSTER_TYPE_LABEL.get(poster_type, "Poster")
    tournament = job.tournament_id or "Esports"
    return f"{tournament} — {label}"


def _derive_description(job: Job) -> str:
    """
    One-line description for the share card.

    Prefers the Gemini-generated caption when it's been produced. Falls back
    to a deterministic placeholder so a never-shared poster still has a
    sensible OG description.
    """
    if getattr(job, "caption", None):
        # Caption may contain newlines / hashtags. OG description should be a
        # single line; collapse whitespace and cap length so we don't push a
        # full Instagram-style caption into a Discord card preview.
        flat = " ".join(job.caption.split())
        return flat[:280]
    poster_type = ((job.input_data or {}).get("_meta") or {}).get("poster_type", "")
    label = _POSTER_TYPE_LABEL.get(poster_type, "poster").lower()
    return f"AI-generated {label} for {job.tournament_id or 'esports'} — made with POSTER/AI."


# ---- Route ------------------------------------------------------------------


@router.get("/p/{job_id}", response_class=HTMLResponse)
def share_landing(
    job_id: str,
    store: JobStore = Depends(get_job_store),
) -> HTMLResponse:
    """
    Public share landing page for a completed poster.

    Returns 404 if the job doesn't exist or hasn't completed. For completed
    jobs, returns an HTML document with OG + Twitter Card meta tags pointing at
    a freshly-signed image URL.
    """
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if job.status != "completed" or not job.storage_key:
        # Not "not found" — the job is real, just not viewable. Crawlers should
        # not cache a preview for an in-flight job, so a 404 is the safest.
        raise HTTPException(
            status_code=404,
            detail=f"Poster not ready (status={job.status}).",
        )

    settings = get_settings()
    storage = get_storage()
    image_url = storage.signed_url(job.storage_key)

    title = _derive_title(job)
    description = _derive_description(job)
    page_url = f"{settings.public_base_url.rstrip('/')}/p/{job.job_id}"

    # html.escape every dynamic value before it lands in the template — the
    # tournament_id is user-controlled and could otherwise break out of an
    # attribute.
    safe_title = html.escape(title, quote=True)
    safe_description = html.escape(description, quote=True)
    safe_image = html.escape(image_url, quote=True)
    safe_page = html.escape(page_url, quote=True)

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{safe_title}</title>
  <meta name="description" content="{safe_description}">

  <!-- OpenGraph — Facebook, LinkedIn, WhatsApp, Discord, Telegram, Slack -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{safe_title}">
  <meta property="og:description" content="{safe_description}">
  <meta property="og:image" content="{safe_image}">
  <meta property="og:image:alt" content="{safe_title}">
  <meta property="og:url" content="{safe_page}">
  <meta property="og:site_name" content="POSTER/AI">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{safe_title}">
  <meta name="twitter:description" content="{safe_description}">
  <meta name="twitter:image" content="{safe_image}">
  <meta name="twitter:image:alt" content="{safe_title}">

  <!-- Humans get bounced to the actual image; crawlers ignore refresh tags. -->
  <meta http-equiv="refresh" content="0; url={safe_image}">

  <style>
    body {{
      margin: 0;
      background: #0c0c0e;
      color: #e7e7ea;
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .wrap {{ text-align: center; padding: 32px; max-width: 560px; }}
    img {{ max-width: 100%; height: auto; border-radius: 12px;
           box-shadow: 0 20px 60px -20px rgba(0,0,0,.7); }}
    h1 {{ font-size: 18px; margin: 20px 0 6px; font-weight: 600; }}
    p  {{ font-size: 13px; color: #9a9aa0; margin: 0; }}
    a  {{ color: #ff5470; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="wrap">
    <img src="{safe_image}" alt="{safe_title}">
    <h1>{safe_title}</h1>
    <p>{safe_description}</p>
    <p style="margin-top:14px"><a href="{safe_image}">Open full image →</a></p>
  </div>
</body>
</html>
"""
    # Short cache so a refresh in Discord/Slack picks up an unstuck signed URL,
    # but long enough that a viral share burst doesn't hammer R2.
    return HTMLResponse(content=body, headers={"Cache-Control": "public, max-age=300"})
