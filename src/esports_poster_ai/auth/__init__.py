"""
API key issuance, storage, and verification.

The plaintext key looks like `epai_<urlsafe-base64-token>`. We store the
SHA-256 hash plus a short prefix; the prefix is the fast lookup index, the
hash is the verification.
"""

from __future__ import annotations

from esports_poster_ai.auth.store import (
    ApiKeyStore,
    KEY_PREFIX_LENGTH,
    KEY_TOKEN_PREFIX,
    generate_key,
    hash_key,
)

__all__ = [
    "ApiKeyStore",
    "generate_key",
    "hash_key",
    "KEY_TOKEN_PREFIX",
    "KEY_PREFIX_LENGTH",
]
