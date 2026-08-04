# backend/scrappers/fetch_description.py
"""Fetch a single job description and print it as JSON on stdout.

Exists so the API can serve a description on demand when the user opens one
row, instead of paying ~1.5s per job to fetch all of them up front.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers.helpers.job_desc_fetcher import get_job_description

# Only hosts we actually scrape. Without this the endpoint would fetch any URL
# the caller sends, which turns the API into an SSRF proxy.
ALLOWED_HOSTS = {
    "linkedin.com",
    "ejobs.ro",
    "bestjobs.eu",
    "jooble.org",
}


def is_allowed(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").lower()
    if not host:
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch one job description")
    parser.add_argument("--url", required=True, help="Job posting URL")
    args = parser.parse_args()

    if not is_allowed(args.url):
        print(json.dumps({"error": "url host is not an allowed job source"}))
        return 2

    description = get_job_description(args.url)
    print(json.dumps({"url": args.url, "description": description}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
