"""Tests for the BestJobs scraper's collection and relevance filtering.

Run with:
    .venv/bin/python -m unittest discover -s backend/tests -t .
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers import bestjobs_scrapper as bj


def _item(job_id: str, title: str) -> dict:
    return {
        "id": job_id,
        "title": title,
        "companyName": "ACME",
        "slug": f"job-{job_id}",
        "locations": [{"name": "București"}],
    }


# What BestJobs actually answers for "Angular developer": a few real matches
# buried in generic developer and support roles.
PAGE = [
    _item("1", "Angular Developer"),
    _item("2", ".NET Software Engineer"),
    _item("3", "(Fluent English) Technical Support Engineer"),
    _item("4", "Senior Frontend Engineer (Angular)"),
    _item("5", "Java Backend Developer"),
]


class TestCollectAllJobs(unittest.TestCase):
    def collect(self, mode: str):
        with mock.patch.object(bj, "_fetch_jobs_page", return_value=(PAGE, None)), \
                mock.patch.object(bj.time, "sleep"):
            return bj.collect_all_jobs("Angular developer", "Bucharest", mode=mode)

    def test_loose_mode_drops_unrelated_titles(self):
        titles = [job["title"] for job in self.collect("loose")]
        self.assertEqual(titles, ["Angular Developer", "Senior Frontend Engineer (Angular)"])

    def test_none_mode_keeps_everything(self):
        self.assertEqual(len(self.collect("none")), len(PAGE))

    def test_strict_mode_requires_every_token(self):
        titles = [job["title"] for job in self.collect("strict")]
        self.assertEqual(titles, ["Angular Developer"])

    def test_default_mode_filters(self):
        with mock.patch.object(bj, "_fetch_jobs_page", return_value=(PAGE, None)), \
                mock.patch.object(bj.time, "sleep"):
            jobs = bj.collect_all_jobs("Angular developer", "Bucharest")
        self.assertEqual(len(jobs), 2)


if __name__ == "__main__":
    unittest.main()
