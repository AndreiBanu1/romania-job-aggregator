"""Tests for the LinkedIn scraper's parsing and pagination.

Run with:
    .venv/bin/python -m unittest discover -s backend/tests -t .
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers import linkedin_scrapper as li

FIXTURE = Path(__file__).parent / "fixtures" / "linkedin_listings_page.html"


def _fake_card(job_id: str, title: str = "Angular Developer") -> str:
    return f"""
    <div class="base-search-card">
      <a class="base-card__full-link" href="https://ro.linkedin.com/jobs/view/x-{job_id}?position=1&amp;refId=abc"></a>
      <h3 class="base-search-card__title">{title}</h3>
      <h4 class="base-search-card__subtitle"><a>ACME</a></h4>
      <span class="job-search-card__location">Bucharest, Romania</span>
    </div>
    """


def _fake_page(job_ids, title="Angular Developer") -> str:
    return "".join(_fake_card(job_id, title) for job_id in job_ids)


class TestExtractJobsFromHtml(unittest.TestCase):
    """Guards against LinkedIn silently changing its markup: if these
    selectors break, extract_jobs_from_html returns [] forever."""

    @classmethod
    def setUpClass(cls):
        cls.jobs = li.extract_jobs_from_html(FIXTURE.read_text(encoding="utf-8"))

    def test_parses_ten_cards_from_a_real_response(self):
        self.assertEqual(len(self.jobs), 10)

    def test_every_job_has_the_core_fields_populated(self):
        for job in self.jobs:
            self.assertTrue(job["id"].isdigit(), f"bad id: {job['id']!r}")
            self.assertTrue(job["title"], f"empty title in {job}")
            self.assertTrue(job["company"], f"empty company in {job}")
            self.assertTrue(job["location"], f"empty location in {job}")
            self.assertTrue(job["href"].startswith("http"), f"bad href in {job}")

    def test_ids_are_unique_within_a_page(self):
        ids = [job["id"] for job in self.jobs]
        self.assertEqual(len(ids), len(set(ids)))


class TestPagination(unittest.TestCase):
    def setUp(self):
        sleep_patch = mock.patch.object(li.time, "sleep")
        sleep_patch.start()
        self.addCleanup(sleep_patch.stop)

    def _run_with_pages(self, pages, **kwargs):
        """pages: dict of start-offset -> html. Records requested offsets."""
        requested = []

        def fake_get(title, location, start=0, retries=3):
            requested.append(start)
            return pages.get(start)

        with mock.patch.object(li, "get_listings_html", side_effect=fake_get):
            jobs = li.collect_all_jobs("Angular", "Bucharest", **kwargs)
        return jobs, requested

    def test_advances_by_cards_returned_not_by_requested_page_size(self):
        # The endpoint returns 10 per call regardless of page_size, so offsets
        # must step 0, 10, 20 - never 0, 25, 50 (which skips 10-24, 35-49).
        pages = {
            0: _fake_page(range(100, 110)),
            10: _fake_page(range(110, 120)),
            20: _fake_page(range(120, 130)),
            30: "",
        }
        jobs, requested = self._run_with_pages(pages, page_size=25, mode="none")

        self.assertEqual(requested, [0, 10, 20, 30])
        self.assertEqual(len(jobs), 30)

    def test_irrelevant_page_does_not_stop_pagination(self):
        # Page 1 is all off-target; the crawl must continue to page 2, which
        # holds the matches. Filtering happens after collection.
        pages = {
            0: _fake_page(range(200, 210), title="Marketing Manager"),
            10: _fake_page(range(210, 220), title="Angular Developer"),
            20: "",
        }
        jobs, requested = self._run_with_pages(pages, mode="strict")

        self.assertEqual(requested, [0, 10, 20])
        self.assertEqual(len(jobs), 10)
        self.assertTrue(all("Angular" in job["title"] for job in jobs))

    def test_stops_when_a_page_yields_no_new_ids(self):
        repeated = _fake_page(range(300, 310))
        pages = {0: repeated, 10: repeated}
        jobs, requested = self._run_with_pages(pages, mode="none")

        self.assertEqual(requested, [0, 10])
        self.assertEqual(len(jobs), 10)

    def test_deduplicates_ids_across_overlapping_pages(self):
        # Real responses overlap between offsets; overlap must not duplicate.
        pages = {
            0: _fake_page(range(400, 410)),
            10: _fake_page(range(408, 418)),
            20: "",
        }
        jobs, _ = self._run_with_pages(pages, mode="none")

        ids = [job["id"] for job in jobs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 18)

    def test_max_pages_is_respected(self):
        pages = {start: _fake_page(range(500 + start, 510 + start)) for start in (0, 10, 20, 30)}
        _, requested = self._run_with_pages(pages, max_pages=2, mode="none")

        self.assertEqual(requested, [0, 10])

    def test_blocked_first_request_returns_empty(self):
        jobs, _ = self._run_with_pages({}, mode="none")
        self.assertEqual(jobs, [])


if __name__ == "__main__":
    unittest.main()
