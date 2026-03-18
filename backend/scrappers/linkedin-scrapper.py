import requests
from bs4 import BeautifulSoup
import re
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote_plus
import time
import random

sys.path.append(str(Path(__file__).resolve().parent.parent))
from location_normalizer import english_city


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}


# -------------------------------
# NETWORK LAYER
# -------------------------------
def get_listings_html(title: str, location: str, start: int = 0, retries: int = 3) -> str | None:
    encoded_title = quote_plus(title)
    encoded_location = quote_plus(location)

    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={encoded_title}&location={encoded_location}&start={start}"
    )

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)

            if response.status_code == 429:
                wait = (attempt + 1) * random.uniform(2, 5)
                print(f"[LinkedIn] 429 rate limit. Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue

            if response.status_code == 403:
                print("[LinkedIn] 403 blocked (bot detection). Stopping.")
                return None

            response.raise_for_status()
            return response.text

        except requests.RequestException as e:
            wait = (attempt + 1) * random.uniform(1, 3)
            print(f"[LinkedIn] Request failed ({e}). Retrying in {wait:.1f}s...")
            time.sleep(wait)

    print("[LinkedIn] Failed after retries.")
    return None


# -------------------------------
# PARSING LAYER
# -------------------------------
def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_job_id_from_href(href: str) -> str | None:
    match = re.search(r"-(\d+)(?:\?|$)", href)
    return match.group(1) if match else None


def extract_jobs_from_html(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.base-search-card")

    jobs: list[dict[str, str]] = []

    for card in cards:
        anchor = card.select_one("a.base-card__full-link[href]")
        if not anchor:
            continue

        href = anchor.get("href", "")
        job_id = _extract_job_id_from_href(href)
        if not job_id:
            continue

        title_element = card.select_one("h3.base-search-card__title")
        company_element = card.select_one("h4.base-search-card__subtitle a") \
            or card.select_one("h4.base-search-card__subtitle")
        location_element = card.select_one("span.job-search-card__location")

        job_title = _clean_text(title_element.get_text(" ", strip=True)) if title_element else ""
        company = _clean_text(company_element.get_text(" ", strip=True)) if company_element else ""
        location = _clean_text(location_element.get_text(" ", strip=True)) if location_element else ""

        jobs.append({
            "id": job_id,
            "company": company,
            "title": job_title,
            "location": location,
            "href": href,
            # "description": ""  # 🔥 future use
        })

    return jobs


# -------------------------------
# OPTIONAL: JOB DESCRIPTION (DISABLED FOR NOW)
# -------------------------------
# ⚠️ This is powerful but slower + more detectable
# Enable later when needed

def get_job_description(href: str) -> str:
    try:
        response = requests.get(href, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")
        desc = soup.select_one(".description__text")
        return desc.get_text(" ", strip=True) if desc else ""
    except:
        return ""


# -------------------------------
# COLLECTION LAYER (NO FILTERING)
# -------------------------------
def collect_all_jobs(title: str, location: str, page_size: int = 25, max_pages: int = 0) -> list[dict[str, str]]:
    start = 0
    page = 0
    seen_ids: set[str] = set()
    all_jobs: list[dict[str, str]] = []

    while max_pages <= 0 or page < max_pages:
        print(f"[LinkedIn] Fetching page {page + 1} (start={start})")

        html = get_listings_html(title, location, start)
        if not html:
            print("[LinkedIn] Stopping due to empty/blocked response.")
            break

        page_jobs = extract_jobs_from_html(html)

        if not page_jobs:
            print("[LinkedIn] No more jobs found.")
            break

        new_jobs = 0

        for job in page_jobs:
            job_id = job["id"]

            if job_id in seen_ids:
                continue

            seen_ids.add(job_id)

            # 🔥 OPTIONAL: enrich with description
            job["description"] = get_job_description(job["href"])

            all_jobs.append(job)
            new_jobs += 1

        print(f"[LinkedIn] Found {len(page_jobs)} jobs, {new_jobs} new")

        if new_jobs == 0:
            print("[LinkedIn] Only duplicates found, stopping.")
            break

        # polite delay
        sleep_time = random.uniform(1.5, 3.5)
        time.sleep(sleep_time)

        start += page_size
        page += 1

    return all_jobs


# -------------------------------
# MAIN
# -------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn job listings scraper (UNBIASED)")
    parser.add_argument("--title", required=True, help="Job title, e.g. 'Software Engineer'")
    parser.add_argument("--location", required=True, help="Location, e.g. 'Bucharest'")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--output", default="job-results/linkedin-results.json")

    args = parser.parse_args()

    jobs = collect_all_jobs(
        title=args.title,
        location=english_city(args.location),
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