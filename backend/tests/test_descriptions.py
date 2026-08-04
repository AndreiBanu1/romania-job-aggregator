"""Tests for bulk description fetching and the single-URL entry point.

Run with:
    .venv/bin/python -m unittest discover -s backend/tests -t .
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers import fetch_description
from backend.scrappers.helpers import descriptions as desc


def job(title, href="https://ro.linkedin.com/jobs/view/1", **extra):
    return {"title": title, "href": href, "company": "Acme", "location": "Bucharest", **extra}


class FetchDescriptionsTestCase(unittest.TestCase):
    def patch_fetch(self, text="a description"):
        self.fetched = []

        def fake(url):
            self.fetched.append(url)
            return text

        patcher = mock.patch.object(desc, "get_job_description", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestPopulation(FetchDescriptionsTestCase):
    def test_populates_in_place_and_returns_same_list(self):
        self.patch_fetch("Angular work")
        jobs = [job("Angular Developer", href="https://x.test/1")]

        result = desc.fetch_descriptions(jobs, "Angular Developer")

        self.assertIs(result, jobs)
        self.assertEqual(jobs[0]["description"], "Angular work")

    def test_every_job_gets_a_description_key(self):
        # The frontend reads job.description; a missing key is worse than "".
        self.patch_fetch()
        jobs = [job("Java Developer", href="https://x.test/1")]

        desc.fetch_descriptions(jobs, "Angular Developer")

        self.assertIn("description", jobs[0])
        self.assertEqual(jobs[0]["description"], "")

    def test_empty_list_is_handled(self):
        self.patch_fetch()
        self.assertEqual(desc.fetch_descriptions([]), [])
        self.assertEqual(self.fetched, [])


class TestEligibility(FetchDescriptionsTestCase):
    def test_jobs_without_href_are_skipped(self):
        self.patch_fetch()
        jobs = [job("Angular Developer", href="")]

        desc.fetch_descriptions(jobs, "Angular Developer")

        self.assertEqual(self.fetched, [])

    def test_irrelevant_jobs_are_skipped_but_kept(self):
        self.patch_fetch()
        jobs = [
            job("Angular Developer", href="https://x.test/1"),
            job("Truck Driver", href="https://x.test/2"),
        ]

        desc.fetch_descriptions(jobs, "Angular Developer")

        self.assertEqual(self.fetched, ["https://x.test/1"])
        self.assertEqual(len(jobs), 2, "skipped jobs must not be dropped")

    def test_mode_none_fetches_everything(self):
        self.patch_fetch()
        jobs = [
            job("Angular Developer", href="https://x.test/1"),
            job("Truck Driver", href="https://x.test/2"),
        ]

        desc.fetch_descriptions(jobs, "Angular Developer", mode="none")

        self.assertEqual(len(self.fetched), 2)


class TestLimit(FetchDescriptionsTestCase):
    def test_limit_caps_the_number_of_fetches(self):
        self.patch_fetch()
        jobs = [job("Angular Developer", href=f"https://x.test/{i}") for i in range(10)]

        desc.fetch_descriptions(jobs, "Angular Developer", limit=3)

        self.assertEqual(len(self.fetched), 3)

    def test_jobs_beyond_the_limit_survive_with_empty_descriptions(self):
        self.patch_fetch()
        jobs = [job("Angular Developer", href=f"https://x.test/{i}") for i in range(5)]

        desc.fetch_descriptions(jobs, "Angular Developer", limit=2)

        self.assertEqual(len(jobs), 5)
        self.assertEqual(sum(1 for j in jobs if j["description"]), 2)
        self.assertTrue(all("description" in j for j in jobs))

    def test_limit_zero_means_no_cap(self):
        self.patch_fetch()
        jobs = [job("Angular Developer", href=f"https://x.test/{i}") for i in range(4)]

        desc.fetch_descriptions(jobs, "Angular Developer", limit=0)

        self.assertEqual(len(self.fetched), 4)

    def test_limit_is_spread_across_sources(self):
        # Jobs arrive grouped by source. A head-slice would spend the whole
        # budget on the first source and leave the others with nothing.
        self.patch_fetch()
        jobs = [
            job("Angular Developer", href=f"https://a.test/{i}", source="bestjobs")
            for i in range(10)
        ] + [
            job("Angular Developer", href=f"https://b.test/{i}", source="linkedin")
            for i in range(10)
        ]

        desc.fetch_descriptions(jobs, "Angular Developer", limit=4)

        hosts = {url.split("/")[2] for url in self.fetched}
        self.assertEqual(len(self.fetched), 4)
        self.assertEqual(hosts, {"a.test", "b.test"})

    def test_uneven_sources_still_use_the_full_budget(self):
        self.patch_fetch()
        jobs = [job("Angular Developer", href="https://a.test/0", source="ejobs")] + [
            job("Angular Developer", href=f"https://b.test/{i}", source="linkedin")
            for i in range(10)
        ]

        desc.fetch_descriptions(jobs, "Angular Developer", limit=5)

        self.assertEqual(len(self.fetched), 5)

    def test_limit_above_the_job_count_is_harmless(self):
        self.patch_fetch()
        jobs = [job("Angular Developer", href="https://x.test/1")]

        desc.fetch_descriptions(jobs, "Angular Developer", limit=100)

        self.assertEqual(len(self.fetched), 1)


class TestUrlAllowList(unittest.TestCase):
    """The on-demand endpoint takes a URL from the client, so it must not be
    usable as a proxy for arbitrary hosts."""

    def test_known_job_sources_are_allowed(self):
        for url in [
            "https://ro.linkedin.com/jobs/view/1",
            "https://www.bestjobs.eu/locuri-de-munca/x/1",
            "https://www.ejobs.ro/user/locuri-de-munca/x/1",
            "https://ro.jooble.org/jdp/1",
        ]:
            with self.subTest(url=url):
                self.assertTrue(fetch_description.is_allowed(url))

    def test_unknown_hosts_are_rejected(self):
        for url in [
            "https://evil.example/x",
            "http://169.254.169.254/latest/meta-data/",
            "http://localhost:3000/cities",
        ]:
            with self.subTest(url=url):
                self.assertFalse(fetch_description.is_allowed(url))

    def test_lookalike_domains_are_rejected(self):
        # endswith("linkedin.com") without the dot would let this through.
        self.assertFalse(fetch_description.is_allowed("https://notlinkedin.com/x"))
        self.assertFalse(fetch_description.is_allowed("https://linkedin.com.evil.test/x"))

    def test_non_http_schemes_are_rejected(self):
        self.assertFalse(fetch_description.is_allowed("file:///etc/passwd"))
        self.assertFalse(fetch_description.is_allowed("ftp://linkedin.com/x"))

    def test_empty_url_is_rejected(self):
        self.assertFalse(fetch_description.is_allowed(""))


if __name__ == "__main__":
    unittest.main()
