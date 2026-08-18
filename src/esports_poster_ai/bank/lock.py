"""
A tiny Redis mutex for the bank refill.

Only one refill batch may run at a time — concurrent "a combo hit <= threshold"
events must not launch overlapping jobs. Redis `SET key token NX EX ttl` is an
atomic acquire; release is a token-checked delete (via a Lua script) so a caller
can only release the lock it actually holds, and a crashed refill auto-releases
when the TTL expires.

The Redis client is injected (reusing `jobs.queue.get_redis`), so this needs no
new infrastructure and can be faked in tests.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

REFILL_LOCK_KEY = "poster-ai:bank:refill:lock"

# Release only if the stored token matches ours (avoids releasing a lock that a
# later holder acquired after our TTL expired).
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class RefillLock:
    """Token-based Redis lock guarding the single-flight refill."""

    def __init__(self, redis: Any, *, key: str = REFILL_LOCK_KEY, ttl_seconds: int = 1800) -> None:
        self._redis = redis
        self._key = key
        self._ttl = ttl_seconds

    def acquire(self) -> Optional[str]:
        """Try to take the lock. Returns a release token on success, else None."""
        token = uuid.uuid4().hex
        ok = self._redis.set(self._key, token, nx=True, ex=self._ttl)
        return token if ok else None

    def release(self, token: str) -> bool:
        """Release the lock iff `token` still owns it. Best-effort (never raises)."""
        try:
            return bool(self._redis.eval(_RELEASE_LUA, 1, self._key, token))
        except Exception:  # noqa: BLE001 — a failed release just waits out the TTL
            logger.warning("bank.lock.release_failed", extra={"key": self._key})
            return False


__all__ = ["RefillLock", "REFILL_LOCK_KEY"]
