import requests
import argparse
import json
import time
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from backend.scrappers.helpers.location_normalizer import alias_candidates, normalize_text, translate_location_to_english

BASE_URL = "https://api.ejobs.ro"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "user-agent": "Mozilla/5.0"
}

RELATED_KEYWORDS = {
    "react": ["react", "frontend", "javascript", "web developer", "ui"],
    "angular": ["angular", "frontend", "typescript"],
    "java": ["java", "spring", "backend"],
    "python": ["python", "django", "flask"],
    "software engineer": ["developer", "engineer", "programmer", "it"],
}

def is_relevant(job: dict, keyword: str, mode: str = "loose") -> bool:
    job_title = job.get("title", "").lower()
    keyword = keyword.lower()

    if mode == "none":
        return True

    if mode == "strict":
        return keyword in job_title

    if mode == "loose":
        related = RELATED_KEYWORDS.get(keyword, [])
        return (
            keyword in job_title
            or any(term in job_title for term in related)
        )

    return True

def get_locations() -> list[dict]:
    url = f"{BASE_URL}/locations"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data.get("locations", [])


def _build_location_index(locations: list[dict]) -> dict[int, str]:
    return {
        int(location["id"]): location["name"]
        for location in locations
        if "id" in location and "name" in location
    }


def _resolve_city_id(location_query: str, locations: list[dict]) -> int | None:
    by_name: dict[str, int] = {}
    by_slug: dict[str, int] = {}

    for location in locations:
        location_id = location.get("id")
        location_name = location.get("name", "")
        location_slug = location.get("slug", "")
        if location_id is None:
            continue

        normalized_name = normalize_text(location_name)
        normalized_slug = normalize_text(location_slug.replace("-", " "))
        by_name[normalized_name] = int(location_id)
        by_slug[normalized_slug] = int(location_id)

    candidates = alias_candidates(location_query)
    for candidate in candidates:
        if candidate in by_name:
            return by_name[candidate]
        if candidate in by_slug:
            return by_slug[candidate]

    return None


def _extract_location_name(job: dict, location_index: dict[int, str]) -> str:
    locations = job.get("locations") or []
    if not locations:
        return ""

    first_location = locations[0]
    explicit_address = first_location.get("address")
    if explicit_address:
        return explicit_address

    city_id = first_location.get("cityId")
    if city_id is None:
        return ""

    return location_index.get(city_id, str(city_id))


def get_jobs(
    city_id: int | None = None,
    keyword: str | None = None,
    page_size: int = 40,
    max_pages: int = 0,
    mode: str = "loose",
) -> list[dict[str, str]]:

    jobs: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    location_index = _build_location_index(get_locations())

    page = 1
    while max_pages <= 0 or page <= max_pages:
        params = {
            "page": page,
            "pageSize": page_size,
            "sort": "suitability",
        }

        if city_id:
            params["filters.cities"] = city_id

        if keyword:
            params["q"] = keyword

        response = requests.get(
            f"{BASE_URL}/jobs",
            headers=HEADERS,
            params=params,
            timeout=20,
        )
        if response.status_code == 404:
            break
        response.raise_for_status()
        data = response.json()

        page_jobs = data.get("jobs", [])
        if not page_jobs:
            break

        for job in page_jobs:
            job_id = str(job.get("id", "")).strip()
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            company_data = job.get("company") or {}
            href = job.get("externalUrl")
            if not href and job.get("slug"):
                href = f"https://www.ejobs.ro/user/locuri-de-munca/{job['slug']}/{job_id}"

            job_data = {
                "id": job_id,
                "company": company_data.get("name", ""),
                "title": job.get("title", ""),
                "location": translate_location_to_english(_extract_location_name(job, location_index)),
                "href": href or "",
            }

            if not is_relevant(job_data, keyword, mode="loose"):
                continue

            jobs.append(job_data)

        print(f"Page {page} scraped")

        time.sleep(1)
        page += 1

    return jobs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="eJobs job listings scraper")
    parser.add_argument("--title", required=True, help="Job title, e.g. 'Angular Developer'")
    parser.add_argument("--location", required=True, help="Location in English, e.g. 'Bucharest'")
    parser.add_argument("--page-size", type=int, default=40, help="Listings page size")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages to fetch (0 = no limit)")
    parser.add_argument("--output", default="job-results/ejobs-results.json", help="Output JSON file path")
    parser.add_argument(
    "--mode",
    choices=["strict", "loose", "none"],
    default="loose",
    help="Filtering mode"
)
    args = parser.parse_args()

    locations = get_locations()
    city_id = _resolve_city_id(args.location, locations)
    if city_id is None:
        available = ", ".join(sorted(location.get("name", "") for location in locations if location.get("name"))[:15])
        raise ValueError(f"Unknown location '{args.location}'. Example valid values: {available}")

    jobs = get_jobs(
        city_id=city_id,
        keyword=args.title,
        page_size=args.page_size,
        max_pages=args.max_pages,
        mode=args.mode,
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