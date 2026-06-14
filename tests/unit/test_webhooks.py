"""
Tests for outbound webhooks: signing, SSRF guard, the emit hook, the delivery
handler (success / retry / dead-letter), and the management endpoints.

No real network or Redis: HTTP and the queue-enqueue are monkeypatched; stores
use mongomock.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import mongomock
import pytest
from fastapi.testclient import TestClient

from esports_poster_ai.api import deps as api_deps
from esports_poster_ai.api.app import app
from esports_poster_ai.api.routes import webhooks as wh_route
from esports_poster_ai.config import get_settings
from esports_poster_ai.domain.api_key import ApiKey
from esports_poster_ai.domain.webhook import WebhookConfig, WebhookDelivery
from esports_poster_ai.webhooks import delivery as wd
from esports_poster_ai.webhooks import signing
from esports_poster_ai.webhooks.store import WebhookConfigStore, WebhookDeliveryStore


# ============================================================ signing
def test_sign_is_deterministic_and_header_parses():
    body = b'{"hello":"world"}'
    s1 = signing.sign("whsec_abc", 1000, body)
    s2 = signing.sign("whsec_abc", 1000, body)
    assert s1 == s2 and len(s1) == 64  # sha256 hex
    header = signing.signature_header("whsec_abc", 1000, body)
    assert header.startswith("t=1000,v1=")


def test_verify_roundtrip_and_rejections():
    secret, body, now = "whsec_x", b"payload-bytes", 10_000
    header = signing.signature_header(secret, now, body)
    assert signing.verify(secret, header, body, now=now) is True
    # Tampered body fails.
    assert signing.verify(secret, header, b"tampered", now=now) is False
    # Stale timestamp fails.
    assert signing.verify(secret, header, body, now=now + 10_000) is False
    # Wrong secret fails.
    assert signing.verify("whsec_other", header, body, now=now) is False


# ============================================================ SSRF guard
def test_url_safety_rejections():
    assert signing.is_safe_callback_url("http://example.com") is False     # not https
    assert signing.is_safe_callback_url("https://localhost") is False       # loopback
    assert signing.is_safe_callback_url("https://127.0.0.1") is False       # loopback ip
    assert signing.is_safe_callback_url("not-a-url") is False


def test_url_safety_allow_insecure_for_dev():
    assert signing.is_safe_callback_url("http://localhost:9000/hook", allow_insecure=True) is True


def test_url_safety_accepts_public_https(monkeypatch):
    # Avoid real DNS: pretend the host resolves to a public address.
    monkeypatch.setattr(
        signing.socket, "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    assert signing.is_safe_callback_url("https://hooks.example.com/x") is True


# ============================================================ emit hook
def _job(**over):
    base = dict(job_id="j1", platform_id="P1", org_id="o1", tournament_id="t1",
                status="completed", storage_key=None, caption=None, error=None)
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def stores():
    cfg = WebhookConfigStore(collection=mongomock.MongoClient(tz_aware=True)["w"]["cfg"])
    dl = WebhookDeliveryStore(collection=mongomock.MongoClient(tz_aware=True)["w"]["dl"])
    return cfg, dl


def test_emit_noop_when_disabled(stores, monkeypatch):
    cfg, dl = stores
    monkeypatch.setattr(get_settings(), "webhooks_enabled", False)
    enq = []
    monkeypatch.setattr(wd, "_enqueue_delivery", lambda *a, **k: enq.append(a))
    assert wd.emit_job_event(_job(), "poster.completed", config_store=cfg, delivery_store=dl) is None
    assert enq == []


def test_emit_noop_without_platform(stores, monkeypatch):
    cfg, dl = stores
    monkeypatch.setattr(get_settings(), "webhooks_enabled", True)
    monkeypatch.setattr(wd, "_enqueue_delivery", lambda *a, **k: None)
    assert wd.emit_job_event(_job(platform_id=None), "poster.completed",
                             config_store=cfg, delivery_store=dl) is None


def test_emit_noop_without_subscription(stores, monkeypatch):
    cfg, dl = stores
    monkeypatch.setattr(get_settings(), "webhooks_enabled", True)
    monkeypatch.setattr(wd, "_enqueue_delivery", lambda *a, **k: None)
    cfg.upsert(WebhookConfig(platform_id="P1", url="https://x/y", secret="whsec_1",
                             events=["poster.failed"]))   # not subscribed to completed
    assert wd.emit_job_event(_job(), "poster.completed",
                             config_store=cfg, delivery_store=dl) is None


def test_emit_creates_delivery_and_enqueues(stores, monkeypatch):
    cfg, dl = stores
    monkeypatch.setattr(get_settings(), "webhooks_enabled", True)
    enqueued = []
    monkeypatch.setattr(wd, "_enqueue_delivery", lambda did, **k: enqueued.append(did))
    cfg.upsert(WebhookConfig(platform_id="P1", url="https://x/y", secret="whsec_1",
                             events=["poster.completed", "poster.failed"]))

    did = wd.emit_job_event(_job(), "poster.completed", config_store=cfg, delivery_store=dl)
    assert did is not None
    assert enqueued == [did]
    saved = dl.get(did)
    assert saved.status == "pending" and saved.event == "poster.completed"
    assert saved.payload["data"]["job_id"] == "j1"


# ============================================================ delivery handler
@pytest.fixture
def deliver_env(monkeypatch):
    cfg = WebhookConfigStore(collection=mongomock.MongoClient(tz_aware=True)["d"]["cfg"])
    dl = WebhookDeliveryStore(collection=mongomock.MongoClient(tz_aware=True)["d"]["dl"])
    cfg.upsert(WebhookConfig(platform_id="P1", url="https://x/y", secret="whsec_1"))
    # deliver_webhook builds its own stores from settings — point them at ours.
    monkeypatch.setattr(wd, "WebhookConfigStore", lambda **k: cfg)
    monkeypatch.setattr(wd, "WebhookDeliveryStore", lambda **k: dl)
    return cfg, dl


def test_deliver_success_marks_delivered(deliver_env, monkeypatch):
    cfg, dl = deliver_env
    d = dl.create(WebhookDelivery(platform_id="P1", event="ping", url="https://x/y", payload={"a": 1}))
    monkeypatch.setattr(wd, "_http_post", lambda *a, **k: 200)
    assert wd.deliver_webhook(d.delivery_id) is True
    assert dl.get(d.delivery_id).status == "delivered"


def test_deliver_failure_retries_with_backoff(deliver_env, monkeypatch):
    cfg, dl = deliver_env
    d = dl.create(WebhookDelivery(platform_id="P1", event="ping", url="https://x/y", payload={}))
    monkeypatch.setattr(wd, "_http_post", lambda *a, **k: 500)
    re_enq = []
    monkeypatch.setattr(wd, "_enqueue_delivery", lambda did, **k: re_enq.append(k.get("delay_seconds")))
    assert wd.deliver_webhook(d.delivery_id) is False
    saved = dl.get(d.delivery_id)
    assert saved.status == "pending"          # will be retried
    assert re_enq and re_enq[0] > 0           # backoff scheduled


def test_deliver_dead_letters_after_max(deliver_env, monkeypatch):
    cfg, dl = deliver_env
    d = WebhookDelivery(platform_id="P1", event="ping", url="https://x/y", payload={})
    d.attempts = get_settings().webhook_max_attempts - 1   # next attempt is the last
    dl.create(d)
    monkeypatch.setattr(wd, "_http_post", lambda *a, **k: 500)
    re_enq = []
    monkeypatch.setattr(wd, "_enqueue_delivery", lambda *a, **k: re_enq.append(1))
    assert wd.deliver_webhook(d.delivery_id) is False
    assert dl.get(d.delivery_id).status == "failed"   # dead-lettered
    assert re_enq == []                               # no further retry


# ============================================================ management API
@pytest.fixture
def client(monkeypatch):
    cfg = WebhookConfigStore(collection=mongomock.MongoClient(tz_aware=True)["a"]["cfg"])
    dl = WebhookDeliveryStore(collection=mongomock.MongoClient(tz_aware=True)["a"]["dl"])
    app.dependency_overrides[wh_route.get_webhook_config_store] = lambda: cfg
    app.dependency_overrides[wh_route.get_webhook_delivery_store] = lambda: dl

    class _FK:
        def verify(self, t):
            return ApiKey(platform_id="P1", key_prefix=t[:12], key_hash="x") if t == "epai_k" else None

    monkeypatch.setattr(api_deps, "get_api_key_store", lambda: _FK())
    # Let the dev test use an example URL without real DNS.
    monkeypatch.setattr(get_settings(), "webhook_allow_insecure_urls", True)
    yield TestClient(app)
    app.dependency_overrides.clear()


H = {"Authorization": "Bearer epai_k"}


def test_webhook_requires_key(client):
    assert client.put("/v1/webhook", json={"url": "https://x/y"}).status_code == 401


def test_webhook_set_get_rotate_flow(client):
    # First PUT returns the secret once.
    r = client.put("/v1/webhook", json={"url": "https://hooks.example.com/e"}, headers=H)
    assert r.status_code == 200
    secret1 = r.json()["secret"]
    assert secret1 and secret1.startswith("whsec_")

    # GET never exposes the secret.
    g = client.get("/v1/webhook", headers=H).json()
    assert g["secret"] is None and g["url"] == "https://hooks.example.com/e"

    # Update keeps the secret hidden.
    r2 = client.put("/v1/webhook", json={"url": "https://hooks.example.com/e2"}, headers=H)
    assert r2.json()["secret"] is None

    # Rotate returns a new one.
    rot = client.post("/v1/webhook/rotate-secret", headers=H).json()
    assert rot["secret"] and rot["secret"] != secret1


def test_webhook_rejects_unsafe_url_when_strict(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "webhook_allow_insecure_urls", False)
    bad = client.put("/v1/webhook", json={"url": "http://localhost/x"}, headers=H)
    assert bad.status_code == 422


def test_webhook_test_button(client, monkeypatch):
    client.put("/v1/webhook", json={"url": "https://hooks.example.com/e"}, headers=H)
    monkeypatch.setattr(
        wh_route, "deliver_once",
        lambda url, secret, payload, **k: {"ok": True, "status_code": 200, "error": None},
    )
    res = client.post("/v1/webhook/test", headers=H).json()
    assert res["ok"] is True and res["status_code"] == 200
