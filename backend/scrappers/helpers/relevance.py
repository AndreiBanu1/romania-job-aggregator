# backend/scrappers/helpers/relevance.py
"""Shared job-title relevance filtering for all scrapers."""

import re

from .location_normalizer import normalize_text


RELATED_KEYWORDS = {
    "react": ["react", "frontend", "javascript", "web developer", "ui"],
    "angular": ["angular", "frontend", "typescript"],
    "java": ["java", "spring", "backend"],
    "python": ["python", "django", "flask"],
    "software engineer": ["developer", "engineer", "programmer", "it"],
}

# Tokens too generic to identify a job on their own. "Angular Developer" must
# match on "angular", not on every posting that happens to say "developer".
GENERIC_TOKENS = {
    "developer", "dev", "engineer", "engineering", "programmer", "software",
    "senior", "junior", "mid", "middle", "lead", "specialist", "consultant",
    "it", "full", "time", "remote", "with", "and", "or", "the",
}

_TOKEN_PATTERN = re.compile(r"[a-z0-9+#.]+")


def tokenize(value: str) -> list[str]:
    """Split a phrase into comparable tokens, keeping c++/c#/.net intact."""
    return [token for token in _TOKEN_PATTERN.findall(normalize_text(value)) if token]


def _contains_term(haystack: str, term: str) -> bool:
    """Word-boundary match that tolerates +, # and . in the term."""
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _related_terms(keyword_norm: str, tokens: list[str]) -> set[str]:
    related: set[str] = set()
    related.update(RELATED_KEYWORDS.get(keyword_norm, []))
    for token in tokens:
        related.update(RELATED_KEYWORDS.get(token, []))
    return related


def is_relevant(job: dict, keyword: str | None, mode: str = "loose") -> bool:
    """Decide whether a job title matches the searched keyword.

    strict: every keyword token must appear in the title.
    loose:  any specific keyword token (or a related term) must appear;
            generic tokens like "developer" alone are not enough.
    none:   keep everything.
    """
    if mode == "none" or not keyword:
        return True

    title = normalize_text(job.get("title", "") or "")
    if not title:
        return False

    keyword_norm = normalize_text(keyword)
    tokens = tokenize(keyword_norm)
    if not tokens:
        return True

    if mode == "strict":
        return all(_contains_term(title, token) for token in tokens)

    if mode == "loose":
        specific = [token for token in tokens if token not in GENERIC_TOKENS]
        related = _related_terms(keyword_norm, tokens)

        # Prefer the specific tokens; only fall back to generic ones when the
        # keyword is entirely generic (e.g. "software engineer").
        candidates = set(specific) or set(tokens)
        candidates.update(related)

        return any(_contains_term(title, term) for term in candidates)

    return True
