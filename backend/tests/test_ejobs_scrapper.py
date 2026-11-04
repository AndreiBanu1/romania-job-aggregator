"""Tests for the eJobs scraper's handling of blocks and rate limits.

Run with:
    .venv/bin/python -m unittest discover -s backend/tests -t .
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers import ejobs_scrapper as ej


def _response(status: int, headers: dict | None = None) -> mock.Mock:
    response = mock.Mock(status_code=status, headers=headers or {}, url="https://api.ejobs.ro/x")
    return response


class TestGet(unittest.TestCase):
    def test_403_raises_source_blocked(self):
        with mock.patch.object(ej.requests, "get", return_value=_response(403)):
            with self.assertRaises(ej.SourceBlocked):
                ej._get("https://api.ejobs.ro/locations")

    def test_429_backs_off_then_succeeds(self):
        responses = [_response(429, {"Retry-After": "2"}), _response(200)]
        with mock.patch.object(ej.requests, "get", side_effect=responses), \
                mock.patch.object(ej.time, "sleep") as sleep:
            result = ej._get("https://api.ejobs.ro/jobs")
        self.assertEqual(result.status_code, 200)
        sleep.assert_called_once_with(2.0)

    def test_429_gives_up_after_retries(self):
        with mock.patch.object(ej.requests, "get", return_value=_response(429)), \
                mock.patch.object(ej.time, "sleep") as sleep:
            result = ej._get("https://api.ejobs.ro/jobs", retries=2)
        self.assertEqual(result.status_code, 429)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
