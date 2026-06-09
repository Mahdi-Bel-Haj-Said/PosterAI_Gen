"""
Postiz Public-API client.

We use Postiz as a self-hosted social-posting aggregator: instead of
implementing OAuth + native upload for Twitter / Facebook / Instagram /
LinkedIn ourselves (and waiting weeks for Meta app review), the user runs
Postiz, connects their accounts there once, and we drive it via three REST
calls:

    GET  /public/v1/integrations   — list the user's connected accounts
    POST /public/v1/upload         — multipart upload of the poster image
    POST /public/v1/posts          — schedule or publish-now a post

Auth is a single header: ``Authorization: <api-key>`` (key generated in the
Postiz UI under Settings → Public API).

The client is intentionally a thin wrapper — it does not retry, does not
cache integrations, and does not interpret post-status. The route layer
above owns business logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import httpx

from esports_poster_ai.config import Settings, get_settings

logger = logging.getLogger(__name__)


class PostizError(RuntimeError):
    """Raised when a Postiz API call fails (network, 4xx, or 5xx)."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class PostizClient:
    """Synchronous HTTP client for the Postiz Public API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url:
            raise ValueError("PostizClient requires a base_url.")
        if not api_key:
            raise ValueError("PostizClient requires an api_key.")
        # Self-hosted Postiz routes the Public API under /api/public/v1/...
        # (nginx in front of the Nest backend strips the /api prefix before
        # forwarding). The docs quote /public/v1 which only works against
        # api.postiz.com cloud; against the docker-compose image we'd get a
        # 307 redirect to /auth. Append both segments here so callers don't
        # have to think about it.
        self._root = base_url.rstrip("/") + "/api/public/v1"
        self._headers = {"Authorization": api_key}
        self._timeout = timeout_seconds

    # ---- low-level ----------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        files: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Any:
        url = f"{self._root}{path}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.request(
                    method,
                    url,
                    headers=self._headers,
                    json=json,
                    files=files,
                    data=data,
                )
        except httpx.HTTPError as exc:
            raise PostizError(f"Postiz request failed: {exc}") from exc

        if resp.status_code >= 400:
            # Surface the server message so the API consumer sees a useful 502.
            body_preview = resp.text[:500] if resp.text else "<empty body>"
            raise PostizError(
                f"Postiz {method} {path} → {resp.status_code}: {body_preview}",
                status_code=resp.status_code,
            )

        # Some endpoints (upload) return JSON, some posts may return empty.
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise PostizError(
                f"Postiz returned non-JSON body for {method} {path}"
            ) from exc

    # ---- public surface -----------------------------------------------------

    def list_integrations(self) -> list[dict]:
        """
        Return the user's connected social accounts.

        Each integration carries at least ``id``, ``name`` (handle), and the
        platform identifier Postiz uses in ``settings.__type`` (e.g. "x",
        "facebook", "instagram", "linkedin"). The exact shape can shift between
        Postiz versions, so we keep it as a list of dicts and let the caller
        pick what to render.
        """
        body = self._request("GET", "/integrations")
        if isinstance(body, list):
            return body
        # Some Postiz builds wrap it in {"integrations": [...]}
        if isinstance(body, dict) and isinstance(body.get("integrations"), list):
            return body["integrations"]
        return []

    def upload_media(self, filename: str, data: bytes, content_type: str) -> dict:
        """
        Upload a media file to Postiz's storage.

        Returns ``{"id": "...", "path": "https://..."}`` — the ``id`` is what
        gets attached to a post's ``image`` array.
        """
        if len(data) > 50 * 1024 * 1024:
            raise PostizError("Asset exceeds Postiz's 50 MB upload limit.")
        files = {"file": (filename, data, content_type)}
        body = self._request("POST", "/upload", files=files)
        if not isinstance(body, dict) or "id" not in body:
            raise PostizError(f"Unexpected upload response: {body!r}")
        return body

    def create_post(
        self,
        *,
        integration_ids: Iterable[str],
        content: str,
        media_id: Optional[str] = None,
        schedule_at: Optional[datetime] = None,
    ) -> dict:
        """
        Schedule (or immediately publish) the same content to N integrations.

        Args:
            integration_ids: Postiz integration ids returned by list_integrations().
            content: Caption text. Per-platform char limits are enforced by Postiz,
                not by us — let it return a 4xx if the user over-shoots Twitter's
                280-char cap, etc.
            media_id: Optional uploaded-media id from upload_media().
            schedule_at: If None, post immediately ("now"). If provided, must be
                a timezone-aware datetime (we convert to UTC ISO-8601).
        """
        ids = list(integration_ids)
        if not ids:
            raise PostizError("create_post requires at least one integration_id.")

        # Build one post entry per integration. Each entry carries the same
        # content but a distinct integration target.
        value_block = {"content": content}
        if media_id:
            value_block["image"] = [{"id": media_id}]

        posts = [
            {
                "integration": {"id": iid},
                "value": [value_block],
                # Postiz needs a per-platform "settings.__type" tag; we don't know
                # the platform here without re-fetching integrations. The Postiz
                # UI populates this on its end when "__type" is omitted on most
                # builds — if your version requires it, swap to a 2-step where
                # the route layer maps integration_id -> platform first.
                "settings": {},
            }
            for iid in ids
        ]

        if schedule_at is None:
            post_type = "now"
            date_iso = datetime.now(tz=timezone.utc).isoformat()
        else:
            if schedule_at.tzinfo is None:
                raise PostizError("schedule_at must be timezone-aware.")
            post_type = "schedule"
            date_iso = schedule_at.astimezone(timezone.utc).isoformat()

        body = {
            "type": post_type,
            "date": date_iso,
            "shortLink": False,
            "tags": [],
            "posts": posts,
        }

        result = self._request("POST", "/posts", json=body)
        return result or {"ok": True}


# ---- singleton accessor -----------------------------------------------------


_client_cache: Optional[PostizClient] = None


def get_postiz_client(settings: Optional[Settings] = None) -> Optional[PostizClient]:
    """
    Return a process-wide PostizClient, or None if the key isn't configured.

    Returning None (rather than raising) lets routes degrade gracefully:
    the UI can hide the native-post panel when Postiz is disabled, and the
    basic Twitter/FB share-intent buttons keep working unchanged.
    """
    global _client_cache
    if _client_cache is not None:
        return _client_cache

    s = settings or get_settings()
    if not s.postiz_api_key or not s.postiz_base_url:
        return None

    _client_cache = PostizClient(
        base_url=s.postiz_base_url,
        api_key=s.postiz_api_key,
    )
    return _client_cache
