"""Tests for the Redis single-flight refill lock (with a fake Redis)."""

from __future__ import annotations

from esports_poster_ai.bank.lock import RefillLock


class FakeRedis:
    """Minimal Redis stand-in supporting SET NX EX and the release Lua."""

    def __init__(self):
        self.store: dict[str, str] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def eval(self, _script, _numkeys, key, arg):
        if self.store.get(key) == arg:
            del self.store[key]
            return 1
        return 0


def test_second_acquire_is_blocked_until_release():
    lock = RefillLock(FakeRedis())
    token = lock.acquire()
    assert token is not None
    assert RefillLock(lock._redis).acquire() is None  # held → blocked
    assert lock.release(token) is True
    assert RefillLock(lock._redis).acquire() is not None  # freed → available again


def test_release_with_wrong_token_is_a_noop():
    redis = FakeRedis()
    lock = RefillLock(redis)
    token = lock.acquire()
    assert lock.release("not-the-token") is False
    assert redis.store  # still locked
    assert lock.release(token) is True


def test_release_never_raises_on_redis_error():
    class BoomRedis(FakeRedis):
        def eval(self, *a, **k):
            raise RuntimeError("redis down")

    lock = RefillLock(BoomRedis())
    lock.acquire()
    assert lock.release("x") is False  # swallowed, waits out the TTL
