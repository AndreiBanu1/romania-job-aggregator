# backend/scrappers/helpers/rate_limiter.py
"""Thread-safe request pacing and backoff helpers.

The description fetcher runs several worker threads against a single host, so
pacing has to be shared between them rather than being a per-thread sleep.
"""

import random
import threading
import time


class RateLimiter:
    """Enforces a minimum interval between calls across all threads.

    Sleeps happen outside the lock, so N waiting threads do not serialise into
    N * interval; each one reserves its own slot and then waits for it.
    """

    def __init__(
        self,
        min_interval: float,
        jitter: float = 0.0,
        clock=None,
        sleeper=None,
    ):
        if min_interval < 0:
            raise ValueError("min_interval must be >= 0")
        self.min_interval = min_interval
        self.jitter = jitter
        # Resolved at call time, not bound here, so patching time.sleep in
        # tests actually takes effect.
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def _now(self) -> float:
        return self._clock() if self._clock else time.monotonic()

    def _sleep(self, seconds: float) -> None:
        (self._sleeper or time.sleep)(seconds)

    def acquire(self) -> float:
        """Block until the caller is allowed to make a request.

        Returns the time spent waiting, which the tests assert on.
        """
        extra = random.uniform(0, self.jitter) if self.jitter else 0.0

        with self._lock:
            now = self._now()
            scheduled = max(now, self._next_allowed)
            self._next_allowed = scheduled + self.min_interval + extra

        wait = scheduled - now
        if wait > 0:
            self._sleep(wait)
            return wait
        return 0.0

    def penalise(self, seconds: float) -> None:
        """Push the next allowed slot out, e.g. after a 429."""
        if seconds <= 0:
            return
        with self._lock:
            self._next_allowed = max(self._next_allowed, self._now() + seconds)


class CircuitBreaker:
    """Stops hammering a host that is actively refusing us.

    Once opened it stays open: a scrape run that has been blocked should give
    up on descriptions rather than keep earning a longer ban.
    """

    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self._failures = 0
        self._open = False
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._open

    def record_failure(self) -> bool:
        """Count a blocking failure. Returns True if the circuit is now open."""
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold:
                self._open = True
            return self._open

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0

    def trip(self) -> None:
        """Open immediately, for unambiguous blocks like a 403."""
        with self._lock:
            self._open = True


def backoff_delay(attempt: int, base: float = 2.0, cap: float = 30.0) -> float:
    """Exponential backoff with full jitter, capped."""
    ceiling = min(cap, base * (2 ** attempt))
    return random.uniform(base, ceiling) if ceiling > base else ceiling


def parse_retry_after(value, default: float = 0.0) -> float:
    """Read a Retry-After header value in delta-seconds form."""
    if not value:
        return default
    try:
        seconds = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(0.0, seconds)
