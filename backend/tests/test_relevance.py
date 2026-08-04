"""Tests for shared keyword relevance filtering.

Run with:
    .venv/bin/python -m unittest discover -s backend/tests -t .
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers.helpers.relevance import is_relevant


def job(title: str) -> dict:
    return {"title": title}


class TestLooseMode(unittest.TestCase):
    def test_multi_word_keyword_matches_on_the_specific_token(self):
        # The regression: "Angular Developer" used to be substring-matched as a
        # whole phrase and rejected all of these.
        for title in [
            "Senior Angular Engineer",
            "Frontend Engineer (Angular)",
            "Software Developer Angular/Java",
            "angular developer",
        ]:
            with self.subTest(title=title):
                self.assertTrue(is_relevant(job(title), "Angular Developer"))

    def test_generic_token_alone_does_not_match(self):
        # "Developer" is generic; a Java role is not an Angular role.
        self.assertFalse(is_relevant(job("Java Developer"), "Angular Developer"))
        self.assertFalse(is_relevant(job("Embedded Developer"), "Angular Developer"))

    def test_unrelated_titles_are_rejected(self):
        for title in ["Marketing Manager", "Accountant", "Sales Representative"]:
            with self.subTest(title=title):
                self.assertFalse(is_relevant(job(title), "Angular Developer"))

    def test_related_keywords_still_expand(self):
        self.assertTrue(is_relevant(job("Frontend Engineer"), "angular"))
        self.assertTrue(is_relevant(job("Spring Boot Engineer"), "java"))

    def test_all_generic_keyword_falls_back_to_its_own_tokens(self):
        # "software engineer" is entirely generic, so it must still match.
        self.assertTrue(is_relevant(job("Software Engineer"), "software engineer"))
        self.assertTrue(is_relevant(job("Java Developer"), "software engineer"))
        self.assertFalse(is_relevant(job("Marketing Manager"), "software engineer"))

    def test_word_boundaries_prevent_substring_false_positives(self):
        # "java" must not match "javascript".
        self.assertFalse(is_relevant(job("JavaScript Developer"), "java"))
        self.assertTrue(is_relevant(job("Java Developer"), "java"))

    def test_symbol_heavy_keywords_are_kept_intact(self):
        self.assertTrue(is_relevant(job("C++ Developer"), "C++"))
        self.assertFalse(is_relevant(job("C++ Developer"), ".NET"))
        self.assertTrue(is_relevant(job(".NET Developer"), ".NET"))

    def test_diacritics_are_normalized(self):
        self.assertTrue(is_relevant(job("Dezvoltator Angular"), "angular"))


class TestStrictMode(unittest.TestCase):
    def test_requires_every_token(self):
        self.assertTrue(is_relevant(job("Angular Developer"), "Angular Developer", "strict"))
        self.assertTrue(
            is_relevant(job("Software Developer Angular/Java"), "Angular Developer", "strict")
        )
        self.assertFalse(
            is_relevant(job("Senior Angular Engineer"), "Angular Developer", "strict")
        )

    def test_token_order_does_not_matter(self):
        self.assertTrue(is_relevant(job("Developer, Angular"), "Angular Developer", "strict"))


class TestNoneModeAndEdges(unittest.TestCase):
    def test_none_mode_keeps_everything(self):
        self.assertTrue(is_relevant(job("Marketing Manager"), "Angular", "none"))

    def test_missing_keyword_keeps_everything(self):
        self.assertTrue(is_relevant(job("Marketing Manager"), None))
        self.assertTrue(is_relevant(job("Marketing Manager"), ""))

    def test_empty_title_is_rejected(self):
        self.assertFalse(is_relevant(job(""), "Angular"))
        self.assertFalse(is_relevant({}, "Angular"))


if __name__ == "__main__":
    unittest.main()
