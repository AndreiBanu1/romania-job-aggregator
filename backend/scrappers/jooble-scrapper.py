import argparse
import json
import sys
import time
import uuid
from urllib.parse import urlencode
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))
from backend.scrappers.helpers.location_normalizer import romanian_city, translate_location_with_city_scan

BASE_URL = "https://ro.jooble.org"
INIT_ENDPOINT = f"{BASE_URL}/api/serp/init"

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.7",
    "content-type": "application/json",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "referer": "https://ro.jooble.org/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
}


def _cookie_header_from_session(session: requests.Session) -> str:
    pairs = [f"{cookie.name}={cookie.value}" for cookie in session.cookies]
    return "; ".join(pairs)


def _bootstrap_session(manual_cookie: str | None = None) -> tuple[requests.Session, str | None]:
    session = requests.Session()
    session.headers.update(HEADERS)

    if manual_cookie:
        return session, manual_cookie

    try:
        response = session.get(BASE_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return session, None

    cookie_header = _cookie_header_from_session(session)
    return session, cookie_header or None


def _to_jooble_romanian_spelling(value: str) -> str:
    return value.replace("ș", "ş").replace("ț", "ţ")


def _build_payload(title: str, location_ro: str, page: int, page_size: int) -> dict:
    encoded_query = urlencode({"ukw": title, "rgns": location_ro})
    return {
        "search": title,
        "region": location_ro,
        "isRemoteItSerp": False,
        "requestPathAndQuery": f"/SearchResult?{encoded_query}",
        "hashtagsBoosters": [],
        "kindOfJobBoosters": [],
        "industryBoosters": [],
        "tagsFilters": [],
        "page": page,
        "perPage": page_size,
    }


def _fetch_jobs_page(
    session: requests.Session,
    title: str,
    location_ro: str,
    page: int,
    page_size: int,
    cookie: str | None = None,
) -> dict:
    params = {
        "rgns": location_ro,
        "sid": "",
        "ukw": title,
    }
    payload = _build_payload(title=title, location_ro=location_ro, page=page, page_size=page_size)
    headers = dict(HEADERS)
    headers["trace-id"] = str(uuid.uuid4())
    headers["referer"] = f"https://ro.jooble.org/SearchResult?{urlencode({'ukw': title, 'rgns': location_ro})}"
    if cookie:
        headers["cookie"] = cookie

    response = session.post(
        INIT_ENDPOINT,
        params=params,
        headers=headers,
        json=payload,
        timeout=30,
    )
    if response.status_code == 403:
        raise RuntimeError(
            "Jooble returned 403 (Cloudflare protection). Re-run with --cookie from a valid browser session."
        )
    response.raise_for_status()
    return response.json()


def _extract_job(job: dict) -> dict[str, str] | None:
    job_id = str(job.get("uid", "")).strip()
    if not job_id:
        return None

    company = job.get("company") or {}
    location = job.get("location") or {}

    return {
        "id": job_id,
        "company": str(company.get("name") or "").strip(),
        "title": str(job.get("position") or "").strip(),
        "location": translate_location_with_city_scan(str(location.get("name") or "").strip()),
        "href": str(job.get("url") or "").strip(),
    }


def collect_all_jobs(title, location, page_size=25, max_pages=0, mode="loose", cookie=None) -> list[dict[str, str]]:
    location_ro = _to_jooble_romanian_spelling(romanian_city(location))
    session, cookie_header = _bootstrap_session(manual_cookie=cookie)

    all_jobs: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    page = 1
    max_allowed_page_amount: int | None = None

    while max_pages <= 0 or page <= max_pages:
        data = _fetch_jobs_page(
            session=session,
            title=title,
            location_ro=location_ro,
            page=page,
            page_size=page_size,
            cookie=cookie_header,
        )

        jobs = data.get("jobs", [])
        if not isinstance(jobs, list) or not jobs:
            break

        if max_allowed_page_amount is None:
            raw_max_allowed = data.get("maxAllowedPageAmount")
            if isinstance(raw_max_allowed, int) and raw_max_allowed > 0:
                max_allowed_page_amount = raw_max_allowed

        new_jobs = 0
        for raw_job in jobs:
            if not isinstance(raw_job, dict):
                continue
            parsed = _extract_job(raw_job)
            if not parsed:
                continue

            job_id = parsed["id"]
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            all_jobs.append(parsed)
            new_jobs += 1

        print(f"Page {page} scraped")

        if new_jobs == 0:
            break
        if max_allowed_page_amount is not None and page >= max_allowed_page_amount:
            break

        page += 1
        time.sleep(0.5)

    return all_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Jooble job listings scraper")
    parser.add_argument("--title", required=True, help="Job title, e.g. 'Angular Developer'")
    parser.add_argument("--location", required=True, help="Location in English, e.g. 'Bucharest'")
    parser.add_argument("--page-size", type=int, default=20, help="Listings page size")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages to fetch (0 = no limit)")
    parser.add_argument("--cookie", default="", help="Optional browser cookie header value (needed when Jooble returns 403)")
    parser.add_argument("--output", default="job-results/jooble-results.json", help="Output JSON file path")
    args = parser.parse_args()

    jobs = collect_all_jobs(
        title=args.title,
        location=args.location,
        page_size=args.page_size,
        max_pages=args.max_pages,
        cookie=args.cookie.strip() or None,
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
