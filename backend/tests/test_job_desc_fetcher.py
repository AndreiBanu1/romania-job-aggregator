"""Tests for description fetching: retries, backoff and giving up.

Run with:
    .venv/bin/python -m unittest discover -s backend/tests -t .
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers.helpers import job_desc_fetcher as fetcher

URL = "https://ro.linkedin.com/jobs/view/x-123"
BODY = "We need an Angular dev. " * 20  # comfortably over the minimum length
HTML = f'<div class="show-more-less-html__markup">{BODY}</div>'


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FetcherTestCase(unittest.TestCase):
    def setUp(self):
        fetcher.reset_throttling()
        self.addCleanup(fetcher.reset_throttling)

        # Never actually sleep, but record that pacing was requested.
        self.sleeps = []
        sleep_patch = mock.patch(
            "backend.scrappers.helpers.rate_limiter.time.sleep",
            side_effect=self.sleeps.append,
        )
        sleep_patch.start()
        self.addCleanup(sleep_patch.stop)

    def patch_get(self, *responses):
        """Queue responses/exceptions for successive requests.get calls."""
        mock_get = mock.patch.object(
            fetcher.requests, "get", side_effect=list(responses)
        ).start()
        self.addCleanup(mock.patch.stopall)
        return mock_get


class TestSuccessPath(FetcherTestCase):
    def test_returns_extracted_text(self):
        self.patch_get(FakeResponse(200, HTML))
        self.assertIn("Angular dev", fetcher.get_job_description(URL))

    def test_empty_url_makes_no_request(self):
        mock_get = self.patch_get(FakeResponse(200, HTML))
        self.assertEqual(fetcher.get_job_description(""), "")
        mock_get.assert_not_called()

    def test_consecutive_calls_are_paced(self):
        self.patch_get(FakeResponse(200, HTML), FakeResponse(200, HTML))
        fetcher.get_job_description(URL)
        fetcher.get_job_description(URL)
        # Second call must have waited on the limiter.
        self.assertTrue(self.sleeps, "expected the second request to be paced")
        self.assertGreaterEqual(self.sleeps[0], fetcher.MIN_INTERVAL_SECONDS)


class TestRateLimitHandling(FetcherTestCase):
    def test_429_is_retried_and_then_succeeds(self):
        mock_get = self.patch_get(
            FakeResponse(429, headers={"Retry-After": "3"}),
            FakeResponse(200, HTML),
        )
        result = fetcher.get_job_description(URL)

        self.assertIn("Angular dev", result)
        self.assertEqual(mock_get.call_count, 2)
        # The Retry-After value must actually be honoured before the retry.
        # Real monotonic time elapses between scheduling and waiting, so the
        # observed sleep lands just under the requested 3s.
        self.assertTrue(any(s >= 2.9 for s in self.sleeps), self.sleeps)

    def test_429_without_retry_after_still_backs_off(self):
        self.patch_get(FakeResponse(429), FakeResponse(200, HTML))
        fetcher.get_job_description(URL)
        self.assertTrue(any(s > 0 for s in self.sleeps), self.sleeps)

    def test_repeated_429_gives_up_after_max_attempts(self):
        mock_get = self.patch_get(*[FakeResponse(429) for _ in range(5)])
        self.assertEqual(fetcher.get_job_description(URL), "")
        self.assertEqual(mock_get.call_count, fetcher.MAX_ATTEMPTS)

    def test_403_stops_immediately_without_retrying(self):
        mock_get = self.patch_get(*[FakeResponse(403) for _ in range(5)])
        self.assertEqual(fetcher.get_job_description(URL), "")
        self.assertEqual(mock_get.call_count, 1)

    def test_403_short_circuits_later_jobs_on_the_same_host(self):
        # The whole point: one block must not be followed by 100 more requests.
        mock_get = self.patch_get(*[FakeResponse(403) for _ in range(5)])
        for _ in range(4):
            fetcher.get_job_description(URL)
        self.assertEqual(mock_get.call_count, 1)

    def test_other_hosts_are_unaffected_by_a_block(self):
        mock_get = self.patch_get(
            FakeResponse(403),
            FakeResponse(200, HTML),
        )
        self.assertEqual(fetcher.get_job_description("https://blocked.example/x"), "")
        self.assertIn(
            "Angular dev", fetcher.get_job_description("https://other.example/y")
        )
        self.assertEqual(mock_get.call_count, 2)


class TestExtraction(unittest.TestCase):
    """These are the cases that made real pages come back as navigation text."""

    def test_prefers_the_largest_match_not_the_first(self):
        # ejobs shape: a small promo box appears before the real description.
        html = (
            '<div class="sidebar-description">Get a free job alert</div>'
            f'<div class="jobs-show-main-description__content">{BODY}</div>'
        )
        result = fetcher._extract_description(html)
        self.assertIn("Angular dev", result)
        self.assertNotIn("free job alert", result)

    def test_generic_selector_also_picks_the_largest(self):
        html = (
            '<div class="description">short</div>'
            f'<div class="job-description">{BODY}</div>'
        )
        self.assertIn("Angular dev", fetcher._extract_description(html))

    def test_page_with_no_description_returns_empty(self):
        # bestjobs is client-rendered: the HTML holds only chrome. Returning "" so
        # the UI can say "not found" beats returning the nav bar.
        html = "<body><nav>Home Jobs My applications</nav></body>"
        self.assertEqual(fetcher._extract_description(html), "")

    def test_short_precise_match_falls_through_to_generic(self):
        html = (
            '<div class="show-more-less-html__markup">Sign in</div>'
            f'<article>{BODY}</article>'
        )
        self.assertIn("Angular dev", fetcher._extract_description(html))


class TestOtherFailures(FetcherTestCase):
    def test_network_error_is_retried(self):
        mock_get = self.patch_get(
            requests.ConnectionError("boom"),
            FakeResponse(200, HTML),
        )
        self.assertIn("Angular dev", fetcher.get_job_description(URL))
        self.assertEqual(mock_get.call_count, 2)

    def test_persistent_network_error_returns_empty(self):
        self.patch_get(*[requests.Timeout("slow") for _ in range(5)])
        self.assertEqual(fetcher.get_job_description(URL), "")

    def test_server_error_is_retried(self):
        mock_get = self.patch_get(FakeResponse(500), FakeResponse(200, HTML))
        self.assertIn("Angular dev", fetcher.get_job_description(URL))
        self.assertEqual(mock_get.call_count, 2)

    def test_404_is_not_retried(self):
        mock_get = self.patch_get(*[FakeResponse(404) for _ in range(5)])
        self.assertEqual(fetcher.get_job_description(URL), "")
        self.assertEqual(mock_get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
