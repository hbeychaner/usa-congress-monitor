"""Thread-safe token bucket rate limiter.

Usage::

    limiter = TokenBucket(rate_per_hour=4800)

    # In each worker thread before making an HTTP request:
    limiter.acquire()   # blocks until a token is available

Design
──────
Tokens refill continuously at ``rate_per_hour / 3600`` tokens/second.
The bucket capacity is set to 1 second of tokens (small burst allowance).
``acquire()`` is thread-safe via a ``threading.Lock``.
"""

from __future__ import annotations

import threading
import time
from typing import cast

from redis import Redis


class TokenBucket:
    """Thread-safe token bucket rate limiter.

    Parameters
    ----------
    rate_per_hour:
        Maximum requests allowed per hour (e.g. 4800 gives 200 headroom
        below the Congress.gov 5000/hour limit).
    """

    def __init__(self, rate_per_hour: float = 4800.0) -> None:
        self.rate_per_sec: float = rate_per_hour / 3600.0
        # Bucket capacity = 1 second of tokens (allow short bursts)
        self._capacity: float = max(1.0, self.rate_per_sec)
        self._tokens: float = self._capacity
        self._last: float = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available, then consume it."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(
                    self._capacity, self._tokens + elapsed * self.rate_per_sec
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Calculate how long until next token arrives
                wait = (1.0 - self._tokens) / self.rate_per_sec
            # Sleep outside the lock so other threads can check
            time.sleep(min(wait, 0.05))

    @property
    def rate_per_hour(self) -> float:
        return self.rate_per_sec * 3600.0


class SharedTokenBucket(TokenBucket):
    """Token bucket whose state lives in Redis so every worker process shares one budget."""

    _SCRIPT = """
local now = tonumber(redis.call('TIME')[1]) + tonumber(redis.call('TIME')[2]) / 1e6
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local state = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1]) or capacity
local ts = tonumber(state[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - ts) * rate)
local wait = 0
if tokens >= 1 then
  tokens = tokens - 1
else
  wait = math.ceil((1 - tokens) / rate * 1000)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], 3600)
return wait
"""

    def __init__(
        self, redis_client: Redis, key: str, rate_per_hour: float = 4800.0
    ) -> None:
        super().__init__(rate_per_hour)
        self._key = key
        self._acquire_script = redis_client.register_script(self._SCRIPT)

    def acquire(self) -> None:
        while True:
            wait_ms = int(
                cast(
                    str | int,
                    self._acquire_script(
                        keys=[self._key], args=[self.rate_per_sec, self._capacity]
                    ),
                )
            )
            if wait_ms <= 0:
                return
            time.sleep(min(wait_ms / 1000.0 + 0.01, 1.0))
