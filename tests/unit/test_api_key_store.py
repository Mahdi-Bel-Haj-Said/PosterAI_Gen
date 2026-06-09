"""Tests for ApiKeyStore + key generation / verification."""

from __future__ import annotations

import mongomock
import pytest

from esports_poster_ai.auth.store import (
    KEY_TOKEN_PREFIX,
    ApiKeyStore,
    generate_key,
    hash_key,
)


@pytest.fixture
def store() -> ApiKeyStore:
    return ApiKeyStore(collection=mongomock.MongoClient()["testdb"]["api_keys"])


# ----------------------------------------------------------------- helpers
def test_generate_key_returns_prefixed_plaintext_and_consistent_hash():
    plaintext, prefix, h = generate_key()
    assert plaintext.startswith(KEY_TOKEN_PREFIX)
    assert plaintext.startswith(prefix)
    assert len(prefix) == 12
    assert hash_key(plaintext) == h
    # Hashes are deterministic.
    p2, _, h2 = generate_key()
    assert plaintext != p2  # secrets gives different tokens
    assert hash_key(p2) == h2


# ----------------------------------------------------------------- issue
def test_issue_returns_plaintext_once_and_stores_only_hash(store: ApiKeyStore):
    api_key, plaintext = store.issue(org_id="1", name="prod")
    assert plaintext.startswith(KEY_TOKEN_PREFIX)
    assert api_key.org_id == "1"
    assert api_key.name == "prod"
    assert api_key.revoked is False

    loaded = store.get(api_key.key_id)
    assert loaded is not None
    assert loaded.key_hash == hash_key(plaintext)
    # The plaintext is NOT recoverable from the record.
    assert plaintext not in loaded.model_dump_json()


# ----------------------------------------------------------------- verify
def test_verify_resolves_a_valid_key(store: ApiKeyStore):
    api_key, plaintext = store.issue(org_id="1")
    resolved = store.verify(plaintext)
    assert resolved is not None
    assert resolved.key_id == api_key.key_id


def test_verify_returns_none_for_unknown_key(store: ApiKeyStore):
    store.issue(org_id="1")
    assert store.verify("epai_totally-fake-key") is None
    assert store.verify("not-an-epai-prefix") is None
    assert store.verify("") is None


def test_verify_updates_last_used_at(store: ApiKeyStore):
    api_key, plaintext = store.issue(org_id="1")
    assert api_key.last_used_at is None
    store.verify(plaintext)
    assert store.get(api_key.key_id).last_used_at is not None


# ----------------------------------------------------------------- list
def test_list_filters_by_org_and_excludes_revoked_by_default(store: ApiKeyStore):
    a, _ = store.issue(org_id="1")
    b, _ = store.issue(org_id="1")
    c, _ = store.issue(org_id="2")
    store.revoke(b.key_id)

    org1 = store.list_for_org("1")
    assert {k.key_id for k in org1} == {a.key_id}

    with_revoked = store.list_for_org("1", include_revoked=True)
    assert {k.key_id for k in with_revoked} == {a.key_id, b.key_id}

    assert {k.key_id for k in store.list_for_org("2")} == {c.key_id}


# ----------------------------------------------------------------- revoke
def test_revoke_blocks_verify(store: ApiKeyStore):
    api_key, plaintext = store.issue(org_id="1")
    assert store.revoke(api_key.key_id) is True
    assert store.verify(plaintext) is None
    # Idempotent — second revoke is a no-op.
    assert store.revoke(api_key.key_id) is False


def test_revoke_unknown_returns_false(store: ApiKeyStore):
    assert store.revoke("nope") is False
