"""
Fetching caller-supplied image URLs.

The express endpoint lets an integrator pass logos as plain URLs
(`"logo_path": "https://their-cdn/logo.png"`) instead of pre-uploading them via
`/v1/assets`. That removes a whole second integration, but it also means the
service performs HTTP requests to addresses a caller chose — so every fetch is
SSRF-guarded and size-capped before a single byte reaches the pipeline.

Guarded against:
  - non-http(s) schemes (file://, gopher://, data:)
  - hosts resolving to loopback / private / link-local / reserved ranges
  - oversized payloads (streamed, aborted past the cap)
  - non-image content types
  - slow-loris style stalls (hard timeout)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from esports_poster_ai.webhooks.signing import is_safe_callback_url

logger = logging.getLogger(__name__)

#: Hard cap on a fetched image. Reference images are resized down to at most
#: 1024px before they reach the model, so anything beyond this is waste.
MAX_IMAGE_BYTES = 15 * 1024 * 1024

#: Per-request timeout. A logo that takes longer than this is not worth the
#: caller's generation slot.
FETCH_TIMEOUT_SECONDS = 10.0

#: Redirect hops allowed. Asset CDNs commonly 302 once to their edge; more than
#: a couple of hops is a sign of something we do not want to be following.
MAX_REDIRECTS = 3

_ALLOWED_CONTENT_PREFIXES = ("image/",)

#: Many CDNs (Wikimedia, some Cloudflare configurations) answer 403 to a request
#: with no User-Agent, so an identifiable one is sent. It also gives a CDN
#: operator something to allowlist, and something to blame when we misbehave.
_HEADERS = {
    "User-Agent": "EsportsPostAI/1.0 (+poster generation; contact: support@defendr.gg)",
    "Accept": "image/*,*/*;q=0.8",
}


def looks_like_url(value: object) -> bool:
    """True when `value` should be treated as a remote URL rather than a key."""
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))


def fetch_image_bytes(url: str, *, allow_insecure: bool = False) -> Optional[bytes]:
    """
    Download an image, or return None if it cannot be fetched safely.

    Never raises: a bad logo URL degrades to "no logo" the same way a missing
    storage key does. Failing the whole generation because one sponsor logo 404'd
    would be a worse outcome than a poster without it.

    Args:
        url: the caller-supplied address.
        allow_insecure: dev-only — permits http:// and private hosts. Mirrors
            the webhook guard's flag so both honour one setting.
    """
    import httpx  # lazy: keeps the CLI import path free of the HTTP stack

    if not is_safe_callback_url(url, allow_insecure=allow_insecure):
        logger.warning("image.fetch.blocked", extra={"reason": "unsafe url", "url": url[:120]})
        return None

    # Redirects are followed manually, one hop at a time, so every intermediate
    # URL passes the same guard as the first. httpx's own follow_redirects would
    # take us wherever a permitted host pointed — including a private address or
    # the cloud metadata endpoint, which is a well-worn SSRF bypass. Redirects
    # cannot simply be refused either: plenty of asset CDNs 302 to their edge.
    current = url

    for _hop in range(MAX_REDIRECTS + 1):
        try:
            with httpx.stream(
                "GET",
                current,
                timeout=FETCH_TIMEOUT_SECONDS,
                follow_redirects=False,
                headers=_HEADERS,
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        logger.warning("image.fetch.failed", extra={"reason": "redirect without location"})
                        return None
                    # Resolve relative Locations against the URL we just called.
                    current = str(httpx.URL(current).join(location))
                    if not is_safe_callback_url(current, allow_insecure=allow_insecure):
                        logger.warning(
                            "image.fetch.blocked",
                            extra={"reason": "unsafe redirect target", "url": current[:120]},
                        )
                        return None
                    continue

                return _read_capped(response, current)

        except Exception as e:  # noqa: BLE001 — a bad URL must not break a generation
            logger.warning(
                "image.fetch.failed",
                extra={"reason": f"{type(e).__name__}: {e}", "url": current[:120]},
            )
            return None

    logger.warning("image.fetch.failed", extra={"reason": "too many redirects", "url": url[:120]})
    return None


def _read_capped(response: Any, url: str) -> Optional[bytes]:
    """Validate the content type, then stream the body and abort past the cap."""
    if response.status_code >= 400:
        logger.warning(
            "image.fetch.failed", extra={"status": response.status_code, "url": url[:120]}
        )
        return None

    content_type = (response.headers.get("content-type") or "").lower()
    if content_type and not content_type.startswith(_ALLOWED_CONTENT_PREFIXES):
        logger.warning(
            "image.fetch.rejected",
            extra={"reason": f"content-type {content_type}", "url": url[:120]},
        )
        return None

    # Streamed rather than read whole: a caller-supplied URL could point at a
    # multi-gigabyte file, and Content-Length can lie.
    chunks = bytearray()
    for chunk in response.iter_bytes():
        chunks.extend(chunk)
        if len(chunks) > MAX_IMAGE_BYTES:
            logger.warning(
                "image.fetch.rejected", extra={"reason": "too large", "url": url[:120]}
            )
            return None

    if not chunks:
        return None

    logger.info("image.fetch.ok", extra={"bytes": len(chunks), "url": url[:120]})
    return bytes(chunks)


__all__ = ["fetch_image_bytes", "looks_like_url", "MAX_IMAGE_BYTES"]
