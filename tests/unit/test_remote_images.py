"""
Caller-supplied image URLs.

The express endpoint lets integrators pass logo URLs instead of pre-uploading
assets, which means the service makes HTTP requests to addresses a caller chose.
These tests pin the guard rails: what must never be fetched, and what must
degrade quietly rather than failing a generation.

No network: `httpx` is stubbed, so only our own logic is under test.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List, Optional

import pytest

from esports_poster_ai.processing import remote_images
from esports_poster_ai.processing.remote_images import (
    MAX_IMAGE_BYTES,
    fetch_image_bytes,
    looks_like_url,
)


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        chunks: Optional[List[bytes]] = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {"content-type": "image/png"}
        self._chunks = chunks if chunks is not None else [b"\x89PNG", b"payload"]

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    def iter_bytes(self):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _install_fake_httpx(monkeypatch, responses: List[_FakeResponse]) -> List[str]:
    """Stub httpx.stream, returning `responses` in order. Records URLs called."""
    called: List[str] = []
    queue = list(responses)

    class _URL:
        def __init__(self, raw: str) -> None:
            self._raw = raw

        def join(self, other: str) -> str:
            if other.startswith(("http://", "https://")):
                return other
            base = self._raw.rsplit("/", 1)[0]
            return f"{base}/{other.lstrip('/')}"

    def _stream(_method: str, url: str, **_kwargs: Any):
        called.append(url)
        if not queue:
            raise AssertionError(f"unexpected extra request to {url}")
        return queue.pop(0)

    fake = types.ModuleType("httpx")
    fake.stream = _stream  # type: ignore[attr-defined]
    fake.URL = _URL  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)
    return called


# --------------------------------------------------------------- detection

@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://cdn.example.com/logo.png", True),
        ("http://cdn.example.com/logo.png", True),
        ("HTTPS://CDN.EXAMPLE.COM/L.PNG", True),
        ("assets/logos/T1.png", False),
        ("defendr-poster-ai/orgs/1/assets/x.png", False),
        ("", False),
        (None, False),
        (123, False),
    ],
)
def test_looks_like_url(value, expected) -> None:
    assert looks_like_url(value) is expected


# ------------------------------------------------------------------ ssrf

@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/logo.png",
        "http://localhost/logo.png",
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata
        "http://10.0.0.5/logo.png",
        "http://192.168.1.1/logo.png",
        "file:///etc/passwd",
        "gopher://example.com/x",
        "not-a-url-at-all",
    ],
)
def test_unsafe_urls_are_never_fetched(url, monkeypatch) -> None:
    """The guard must reject before any HTTP call is made."""
    called = _install_fake_httpx(monkeypatch, [])

    assert fetch_image_bytes(url, allow_insecure=False) is None
    assert called == [], f"guard let a request through to {url}"


def _allow_public_only(monkeypatch) -> None:
    """
    Replace the SSRF guard with a hermetic stand-in.

    The real guard resolves DNS, which would make these tests network-dependent
    and fail on hosts that do not resolve. The redirect tests are about *our*
    per-hop re-validation, not about the guard's own address classification —
    that is covered by `test_unsafe_urls_are_never_fetched`, which uses the real
    implementation.
    """
    private_markers = ("127.0.0.1", "localhost", "169.254.", "10.", "192.168.")

    def _fake(url: str, *, allow_insecure: bool = False) -> bool:
        if not url.startswith(("http://", "https://")):
            return False
        host = url.split("//", 1)[1].split("/", 1)[0]
        return not any(host.startswith(m) for m in private_markers)

    monkeypatch.setattr(remote_images, "is_safe_callback_url", _fake)


# -------------------------------------------------------------- redirects

def test_redirect_is_followed_when_target_is_safe(monkeypatch) -> None:
    _allow_public_only(monkeypatch)
    called = _install_fake_httpx(
        monkeypatch,
        [
            _FakeResponse(status_code=302, headers={"location": "https://cdn.example.com/real.png"}),
            _FakeResponse(chunks=[b"\x89PNG", b"ok"]),
        ],
    )

    assert fetch_image_bytes("https://example.com/logo.png") == b"\x89PNGok"
    assert called == ["https://example.com/logo.png", "https://cdn.example.com/real.png"]


def test_redirect_to_private_address_is_blocked(monkeypatch) -> None:
    """
    The classic SSRF bypass: a public host 302s to the metadata endpoint. Each
    hop is re-validated, so the second request must never happen.
    """
    _allow_public_only(monkeypatch)
    called = _install_fake_httpx(
        monkeypatch,
        [
            _FakeResponse(
                status_code=302,
                headers={"location": "http://169.254.169.254/latest/meta-data/"},
            ),
            _FakeResponse(chunks=[b"secrets"]),  # must never be reached
        ],
    )

    assert fetch_image_bytes("https://example.com/logo.png") is None
    assert called == ["https://example.com/logo.png"]


def test_redirect_loop_gives_up(monkeypatch) -> None:
    _allow_public_only(monkeypatch)
    loop = [
        _FakeResponse(status_code=302, headers={"location": "https://example.com/next.png"})
        for _ in range(remote_images.MAX_REDIRECTS + 1)
    ]
    _install_fake_httpx(monkeypatch, loop)

    assert fetch_image_bytes("https://example.com/logo.png") is None


# ---------------------------------------------------------------- payload

def test_non_image_content_type_is_rejected(monkeypatch) -> None:
    _allow_public_only(monkeypatch)
    _install_fake_httpx(
        monkeypatch, [_FakeResponse(headers={"content-type": "text/html"}, chunks=[b"<html>"])]
    )
    assert fetch_image_bytes("https://example.com/page") is None


def test_error_status_is_rejected(monkeypatch) -> None:
    _allow_public_only(monkeypatch)
    _install_fake_httpx(monkeypatch, [_FakeResponse(status_code=404)])
    assert fetch_image_bytes("https://example.com/missing.png") is None


def test_oversized_payload_is_aborted(monkeypatch) -> None:
    """Streamed and capped — Content-Length is not trusted."""
    _allow_public_only(monkeypatch)
    oversized = [b"x" * (1024 * 1024)] * ((MAX_IMAGE_BYTES // (1024 * 1024)) + 2)
    _install_fake_httpx(monkeypatch, [_FakeResponse(chunks=oversized)])

    assert fetch_image_bytes("https://example.com/huge.png") is None


def test_empty_body_is_rejected(monkeypatch) -> None:
    _allow_public_only(monkeypatch)
    _install_fake_httpx(monkeypatch, [_FakeResponse(chunks=[])])
    assert fetch_image_bytes("https://example.com/empty.png") is None


def test_transport_error_degrades_to_none(monkeypatch) -> None:
    _allow_public_only(monkeypatch)
    """
    A logo that cannot be fetched must not fail the whole generation — a poster
    without one logo beats no poster at all.
    """
    def _boom(*_args, **_kwargs):
        raise ConnectionError("dns exploded")

    fake = types.ModuleType("httpx")
    fake.stream = _boom  # type: ignore[attr-defined]
    fake.URL = str  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "httpx", fake)

    assert fetch_image_bytes("https://example.com/logo.png") is None


def test_missing_content_type_is_allowed(monkeypatch) -> None:
    _allow_public_only(monkeypatch)
    """Some object stores omit it; absence is not evidence of a non-image."""
    _install_fake_httpx(monkeypatch, [_FakeResponse(headers={}, chunks=[b"\x89PNG"])])
    assert fetch_image_bytes("https://example.com/logo.png") == b"\x89PNG"
