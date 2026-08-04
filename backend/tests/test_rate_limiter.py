"""Tests for request pacing primitives.

Run with:
    .venv/bin/python -m unittest discover -s backend/tests -t .
"""

import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers.helpers.rate_limiter import (
    CircuitBreaker,
    RateLimiter,
    backoff_delay,
    parse_retry_after,
)


class FakeClock:
    """Virtual time, so tests never actually block.

    advance_on_sleep=True models elapsed time. Set it False to freeze the
    clock, which is what the concurrency test needs: it checks the slots the
    limiter hands out, and a clock that moved while threads queued would make
    those values racy.
    """

    def __init__(self, advance_on_sleep=True):
        self.now = 0.0
        self.sleeps = []
        self.advance_on_sleep = advance_on_sleep
        self._lock = threading.Lock()

    def time(self):
        with self._lock:
            return self.now

    def sleep(self, seconds):
        with self._lock:
            self.sleeps.append(seconds)
            if self.advance_on_sleep:
                self.now += seconds


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def _limiter(self, interval=1.5, jitter=0.0):
        return RateLimiter(
            interval, jitter=jitter, clock=self.clock.time, sleeper=self.clock.sleep
        )

    def test_first_call_is_not_delayed(self):
        limiter = self._limiter()
        self.assertEqual(limiter.acquire(), 0.0)
        self.assertEqual(self.clock.sleeps, [])

    def test_second_call_waits_the_interval(self):
        limiter = self._limiter(interval=1.5)
        limiter.acquire()
        self.assertAlmostEqual(limiter.acquire(), 1.5)

    def test_no_wait_when_enough_time_already_passed(self):
        limiter = self._limiter(interval=1.5)
        limiter.acquire()
        self.clock.now += 10
        self.assertEqual(limiter.acquire(), 0.0)

    def test_requests_are_spaced_not_stacked_across_threads(self):
        # Five threads must be paced to 0, 1, 2, 3, 4 - the point of the fix:
        # concurrent workers no longer all fire at once.
        self.clock = FakeClock(advance_on_sleep=False)
        limiter = self._limiter(interval=1.0)
        barrier = threading.Barrier(5)
        waits = []
        lock = threading.Lock()

        def worker():
            barrier.wait()
            wait = limiter.acquire()
            with lock:
                waits.append(wait)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(waits), [0.0, 1.0, 2.0, 3.0, 4.0])

    def test_penalise_pushes_the_next_slot_out(self):
        limiter = self._limiter(interval=1.0)
        limiter.acquire()
        limiter.penalise(10.0)
        self.assertAlmostEqual(limiter.acquire(), 10.0)

    def test_penalise_ignores_non_positive_values(self):
        limiter = self._limiter(interval=0.0)
        limiter.acquire()
        limiter.penalise(0)
        limiter.penalise(-5)
        self.assertEqual(limiter.acquire(), 0.0)

    def test_jitter_stays_within_bounds(self):
        limiter = self._limiter(interval=1.0, jitter=0.5)
        limiter.acquire()
        for _ in range(20):
            wait = limiter.acquire()
            self.assertGreaterEqual(wait, 1.0)
            self.assertLessEqual(wait, 1.5)

    def test_negative_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            RateLimiter(-1)


class TestCircuitBreaker(unittest.TestCase):
    def test_opens_after_threshold_failures(self):
        breaker = CircuitBreaker(threshold=3)
        self.assertFalse(breaker.record_failure())
        self.assertFalse(breaker.record_failure())
        self.assertTrue(breaker.record_failure())
        self.assertTrue(breaker.is_open)

    def test_success_resets_the_failure_count(self):
        breaker = CircuitBreaker(threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        self.assertFalse(breaker.record_failure())
        self.assertFalse(breaker.is_open)

    def test_trip_opens_immediately(self):
        breaker = CircuitBreaker(threshold=99)
        breaker.trip()
        self.assertTrue(breaker.is_open)

    def test_stays_open_once_tripped(self):
        breaker = CircuitBreaker(threshold=1)
        breaker.record_failure()
        breaker.record_success()
        self.assertTrue(breaker.is_open)


class TestBackoffHelpers(unittest.TestCase):
    def test_backoff_is_capped(self):
        for attempt in range(10):
            self.assertLessEqual(backoff_delay(attempt, base=2.0, cap=30.0), 30.0)

    def test_backoff_is_at_least_the_base(self):
        for attempt in range(5):
            self.assertGreaterEqual(backoff_delay(attempt, base=2.0), 2.0)

    def test_backoff_grows_with_attempts(self):
        early = max(backoff_delay(0, base=2.0, cap=60.0) for _ in range(30))
        late = max(backoff_delay(4, base=2.0, cap=60.0) for _ in range(30))
        self.assertLess(early, late)

    def test_parse_retry_after_reads_seconds(self):
        self.assertEqual(parse_retry_after("30"), 30.0)
        self.assertEqual(parse_retry_after(" 5 "), 5.0)

    def test_parse_retry_after_falls_back_on_junk(self):
        self.assertEqual(parse_retry_after(None, default=7.0), 7.0)
        self.assertEqual(parse_retry_after("", default=7.0), 7.0)
        self.assertEqual(parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT", default=7.0), 7.0)

    def test_parse_retry_after_never_returns_negative(self):
        self.assertEqual(parse_retry_after("-10"), 0.0)


if __name__ == "__main__":
    unittest.main()
