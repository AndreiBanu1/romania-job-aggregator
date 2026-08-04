# backend/scrappers/helpers/job_desc_fetcher.py

import threading
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from .rate_limiter import (
    CircuitBreaker,
    RateLimiter,
    backoff_delay,
    parse_retry_after,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
}

# Pacing per host. The listing scraper waits 1.5-3.5s between pages; fetching a
# description per job is the same kind of traffic, so it gets the same manners
# instead of firing every worker thread at once.
MIN_INTERVAL_SECONDS = 1.5
JITTER_SECONDS = 1.5

# Consecutive blocking responses (429/403) before we stop asking this host.
FAILURE_THRESHOLD = 3

MAX_ATTEMPTS = 3

_registry_lock = threading.Lock()
_limiters: dict[str, RateLimiter] = {}
_breakers: dict[str, CircuitBreaker] = {}


def _host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _limiter_for(host: str) -> RateLimiter:
    with _registry_lock:
        if host not in _limiters:
            _limiters[host] = RateLimiter(MIN_INTERVAL_SECONDS, jitter=JITTER_SECONDS)
        return _limiters[host]


def _breaker_for(host: str) -> CircuitBreaker:
    with _registry_lock:
        if host not in _breakers:
            _breakers[host] = CircuitBreaker(threshold=FAILURE_THRESHOLD)
        return _breakers[host]


def reset_throttling(host: str | None = None) -> None:
    """Clear pacing state. Call between runs; used by the tests."""
    with _registry_lock:
        if host is None:
            _limiters.clear()
            _breakers.clear()
        else:
            _limiters.pop(host, None)
            _breakers.pop(host, None)


# Site-specific first, because they are unambiguous. The generic patterns below
# are a fallback for sources we have not special-cased.
_PRECISE_SELECTORS = (
    "div.show-more-less-html__markup",  # linkedin
    ".description__text",  # linkedin
    ".jobs-show-main-description__content",  # ejobs
)

_GENERIC_SELECTORS = (
    '[class*="description"]',
    '[id*="description"]',
    "article",
    "main",
)

# Below this, we almost certainly grabbed navigation or a sidebar rather than
# the posting itself.
_MIN_DESCRIPTION_CHARS = 200


def _extract_description(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for selector in _PRECISE_SELECTORS:
        block = soup.select_one(selector)
        if block:
            text = block.get_text(separator="\n", strip=True)
            if len(text) >= _MIN_DESCRIPTION_CHARS:
                return text

    # Largest match, not the first one: on ejobs the first [class*="description"]
    # in document order is a small sidebar promo, while the real description sits
    # further down the page.
    best = ""
    for selector in _GENERIC_SELECTORS:
        for block in soup.select(selector):
            text = block.get_text(separator="\n", strip=True)
            if len(text) > len(best):
                best = text

    if len(best) >= _MIN_DESCRIPTION_CHARS:
        return best

    # Nothing description-shaped. Returning page chrome would be worse than
    # admitting we found nothing, since the UI can then say so.
    return ""


def get_job_description(url: str, timeout: int = 10) -> str:
    """
    Fetch job description from the given URL and return plain text.

    Requests are paced per host and retried with backoff. Returns empty string
    on failure, including when the host has started refusing us.
    """
    if not url:
        return ""

    host = _host_of(url)
    if not host:
        return ""

    limiter = _limiter_for(host)
    breaker = _breaker_for(host)

    for attempt in range(MAX_ATTEMPTS):
        # Checked each attempt: another thread may have tripped it while we
        # were waiting for our slot.
        if breaker.is_open:
            return ""

        limiter.acquire()

        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
        except requests.RequestException:
            delay = backoff_delay(attempt)
            limiter.penalise(delay)
            continue

        status = resp.status_code

        if status == 429:
            retry_after = parse_retry_after(
                resp.headers.get("Retry-After"), default=backoff_delay(attempt)
            )
            print(f"[desc] 429 from {host}; backing off {retry_after:.1f}s")
            limiter.penalise(retry_after)
            if breaker.record_failure():
                print(f"[desc] Too many blocks from {host}; skipping descriptions.")
            continue

        if status == 403:
            # Unambiguous block: retrying only makes it worse.
            print(f"[desc] 403 from {host}; skipping descriptions for this run.")
            breaker.trip()
            return ""

        if status >= 500:
            delay = backoff_delay(attempt)
            limiter.penalise(delay)
            continue

        if status >= 400:
            # 404 and friends: the posting is gone, not a throttling problem.
            return ""

        breaker.record_success()

        try:
            return _extract_description(resp.text)
        except Exception:
            return ""

    return ""
