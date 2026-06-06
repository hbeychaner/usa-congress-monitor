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
