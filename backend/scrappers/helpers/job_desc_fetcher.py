# backend/scrappers/helpers/job_desc_fetcher.py

import requests
from bs4 import BeautifulSoup
from typing import Optional

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )
}

def get_job_description(url: str, timeout: int = 10) -> str:
    """
    Fetch job description from the given URL and return plain text.
    Returns empty string on failure.
    """
    if not url:
        return ""

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException:
        return ""

    try:
        soup = BeautifulSoup(html, "html.parser")
        # Most job description blocks have <div> or <section> with 'description' or 'job' in class
        selectors = [
            '[class*="description"]',
            '[class*="job"]',
            '[id*="description"]',
            '[id*="job"]',
            "article",
        ]
        for sel in selectors:
            block = soup.select_one(sel)
            if block:
                return block.get_text(separator="\n", strip=True)
        # fallback: return all text
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return ""