"""
Webhook signing + callback-URL safety. Pure functions, standard library only.

Signature scheme (Stripe-style): the `X-EPAI-Signature` header is
`t=<unix_ts>,v1=<hex>` where `v1 = HMAC_SHA256(secret, "<t>.<raw_body>")`. The
client recomputes it over the exact bytes it received and rejects a stale `t`.

URL safety guards against SSRF: callback URLs must be https and must not resolve
to loopback/private/link-local/reserved address space — otherwise a platform (or
an attacker who stole a key) could make us POST to internal services. The
`allow_insecure` flag relaxes this for local development only.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import socket
from urllib.parse import urlparse


SECRET_PREFIX = "whsec_"


def generate_secret() -> str:
    """A fresh signing secret. High entropy → safe to HMAC without salting."""
    return f"{SECRET_PREFIX}{secrets.token_urlsafe(32)}"


def sign(secret: str, timestamp: int, body: bytes) -> str:
    """Return the hex HMAC-SHA256 of `"<timestamp>.<body>"` under `secret`."""
    signed_payload = f"{timestamp}.".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()


def signature_header(secret: str, timestamp: int, body: bytes) -> str:
    """Build the value for the `X-EPAI-Signature` header."""
    return f"t={timestamp},v1={sign(secret, timestamp, body)}"


def verify(secret: str, header: str, body: bytes, *, tolerance_seconds: int = 300,
           now: int) -> bool:
    """
    Verify a received signature header (reference impl — mirrors what a client does).

    Returns True iff the v1 signature matches AND the timestamp is within
    `tolerance_seconds` of `now`. Constant-time comparison.
    """
    parts = dict(
        p.split("=", 1) for p in header.split(",") if "=" in p
    )
    try:
        ts = int(parts.get("t", ""))
    except ValueError:
        return False
    if abs(now - ts) > tolerance_seconds:
        return False
    expected = sign(secret, ts, body)
    return hmac.compare_digest(expected, parts.get("v1", ""))


def is_safe_callback_url(url: str, *, allow_insecure: bool = False) -> bool:
    """
    True if `url` is an acceptable callback target.

    Production rule: https only, with a host that does not resolve into
    loopback/private/link-local/reserved ranges (SSRF guard). When
    `allow_insecure` is set (dev), http and private/loopback hosts are allowed
    so you can test against a local listener — but malformed urls still fail.
    """
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    if allow_insecure:
        return True
    if parsed.scheme != "https":
        return False
    # Resolve every address the host maps to and reject any non-public one.
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if (
            ip.is_loopback or ip.is_private or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        ):
            return False
    return True


__all__ = [
    "SECRET_PREFIX",
    "generate_secret",
    "sign",
    "signature_header",
    "verify",
    "is_safe_callback_url",
]
