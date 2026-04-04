import argparse
import json
import re
import time
import urllib.parse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers.helpers.location_normalizer import romanian_city, translate_location_with_city_scan

BASE_URL = "https://www.bestjobs.eu"

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.bestjobs.eu/locuri-de-munca/angular",
    "user-agent": "Mozilla/5.0",
    "x-nextjs-data": "1",
    "cookie": "NEXT_LOCALE=ro; cc_ads=granted; cc_analytics=granted",
}


def _fetch_jobs_page(
    title: str,
    location: str,
    page_size: int,
    cursor: str | None = None,
) -> tuple[list[dict], str | None]:
    qs = [
        ("location", location),
        ("limit", str(page_size)),
    ]
    if cursor:
        qs.append(("cursor", cursor))

    encoded_title = urllib.parse.quote(title)
    query = urllib.parse.urlencode(qs)
    url = f"{BASE_URL}/locuri-de-munca/{encoded_title}?{query}"

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text

    marker = '"jobListCardsFromServer":'
    start = html.find(marker)
    if start == -1:
        return [], None

    start = html.find('{', start)
    if start == -1:
        return [], None

    depth = 0
    end = None
    for idx in range(start, len(html)):
        if html[idx] == '{':
            depth += 1
        elif html[idx] == '}':
            depth -= 1
            if depth == 0:
                end = idx + 1
                break

    if end is None:
        return [], None

    try:
        cards = json.loads(html[start:end])
    except json.JSONDecodeError:
        return [], None

    items = cards.get("items", [])
    next_cursor = cards.get("nextCursor")

    if not isinstance(items, list):
        return [], None

    return items, next_cursor


def _bestjobs_href(job: dict) -> str:
    own_apply_url = str(job.get("ownApplyUrl", "")).strip()
    if own_apply_url:
        return own_apply_url

    slug = str(job.get("slug", "")).strip()
    job_id = str(job.get("id", "")).strip()
    if slug and job_id:
        return f"{BASE_URL}/locuri-de-munca/{slug}/{job_id}"

    if slug:
        return f"{BASE_URL}/locuri-de-munca/{slug}"

    return ""


def _normalize_bestjobs_location(raw_location: str) -> str:
    return translate_location_with_city_scan(raw_location)


def _extract_location(job: dict) -> str:
    locations = job.get("locations")
    if not isinstance(locations, list) or not locations:
        return ""

    first = locations[0]
    if not isinstance(first, dict):
        return ""

    name = str(first.get("name", "")).strip()
    return _normalize_bestjobs_location(name)


def collect_all_jobs(title, location, page_size=25, max_pages=0, mode="loose") -> list[dict[str, str]]:
    all_jobs: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    next_cursor: str | None = None

    page = 1
    while max_pages <= 0 or page <= max_pages:
        items, next_cursor = _fetch_jobs_page(
            title=title,
            location=romanian_city(location),
            page_size=page_size,
            cursor=next_cursor,
        )

        if not items:
            break

        new_jobs = 0
        for job in items:
            if not isinstance(job, dict):
                continue

            job_id = str(job.get("id", "")).strip()
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            all_jobs.append(
                {
                    "id": job_id,
                    "company": str(job.get("companyName", "")).strip(),
                    "title": str(job.get("title", "")).strip(),
                    "location": _extract_location(job),
                    "href": _bestjobs_href(job),
                }
            )
            new_jobs += 1

        print(f"Page {page} scraped")

        if not next_cursor or new_jobs == 0:
            break

        time.sleep(0.5)
        page += 1

    return all_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="BestJobs job listings scraper")
    parser.add_argument("--title", required=True, help="Job title, e.g. 'Angular Developer'")
    parser.add_argument("--location", required=True, help="Location in English, e.g. 'Bucharest'")
    parser.add_argument("--page-size", type=int, default=24, help="Listings page size")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages to fetch (0 = no limit)")
    parser.add_argument("--output", default="job-results/bestjobs-results.json", help="Output JSON file path")
    args = parser.parse_args()

    jobs = collect_all_jobs(
        title=args.title,
        location=args.location,
        page_size=args.page_size,
        max_pages=args.max_pages,
    )
    output_payload = {
        "total_jobs_found": len(jobs),
        "jobs": jobs,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output_payload, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(jobs)} jobs to {output_path}")


if __name__ == "__main__":
    main()