import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.scrappers.helpers.descriptions import fetch_descriptions


def _run_scraper(
    scraper_path: Path,
    source_name: str,
    title: str,
    location: str,
    page_size: int,
    max_pages: int,
    mode: str = "loose",
    supports_mode: bool = False,
) -> list[dict[str, str]]:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
        output_path = Path(tmp_file.name)

    command = [
        sys.executable,
        str(scraper_path),
        "--title",
        title,
        "--location",
        location,
        "--page-size",
        str(page_size),
        "--max-pages",
        str(max_pages),
        "--output",
        str(output_path),
    ]

    # Not every scraper exposes --mode yet.
    if supports_mode:
        command.extend(["--mode", mode])

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout.strip():
            print(result.stdout.strip())

        with open(output_path, "r", encoding="utf-8") as file:
            payload = json.load(file)
            jobs = payload.get("jobs", [])
            if not isinstance(jobs, list):
                return []

            tagged_jobs: list[dict[str, str]] = []
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                tagged_job = dict(job)
                tagged_job["source"] = source_name
                tagged_jobs.append(tagged_job)

            return tagged_jobs
    finally:
        if output_path.exists():
            output_path.unlink()


def _dedupe_jobs(jobs):
    deduped = []
    seen = set()

    for job in jobs:
        href = str(job.get("href", "")).strip().lower()
        if href:
            key = ("url", href)
        else:
            key = (
                str(job.get("title", "")).strip().lower(),
                str(job.get("company", "")).strip().lower(),
                str(job.get("location", "")).strip().lower(),
            )

        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    return deduped


def _build_sources_summary(jobs: list[dict[str, str]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for job in jobs:
        source = str(job.get("source", "unknown")).strip().lower() or "unknown"
        summary[source] = summary.get(source, 0) + 1
    return summary


def _sort_jobs(jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        jobs,
        key=lambda job: (
            str(job.get("source", "")).strip().lower(),
            str(job.get("title", "")).strip().lower(),
            str(job.get("company", "")).strip().lower(),
            str(job.get("id", "")).strip(),
        ),
    )
    
def count_keywords(jobs):
    counts = {
        "react": 0,
        "angular": 0,
        "java": 0,
        "python": 0,
    }

    for job in jobs:
        text = job["title"].lower()

        for key in counts:
            if key in text:
                counts[key] += 1

    return counts


def aggregate_jobs(all_jobs_dict: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    """Aggregate jobs from multiple sources into a single deduplicated list."""
    all_jobs: list[dict[str, str]] = []
    
    for source_name, jobs in all_jobs_dict.items():
        for job in jobs:
            if not isinstance(job, dict):
                continue
            tagged_job = dict(job)
            tagged_job["source"] = source_name
            all_jobs.append(tagged_job)
    
    merged_jobs = _dedupe_jobs(all_jobs)
    sorted_jobs = _sort_jobs(merged_jobs)
    return sorted_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate jobs from multiple scrapers")
    parser.add_argument("--title", required=True, help="Job title, e.g. 'Angular Developer'")
    parser.add_argument("--location", required=True, help="Location in English, e.g. 'Bucharest'")
    parser.add_argument("--page-size", type=int, default=25, help="Page size passed to scrapers")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages passed to scrapers (0 = no limit)")
    parser.add_argument("--output", default="job-results/jobs-aggregated.json", help="Output JSON file path")
    parser.add_argument("--mode", choices=["strict", "loose", "none"], default="loose",
                        help="Job filtering mode")
    parser.add_argument("--descriptions", action="store_true",
                        help="Fetch full job descriptions (slow: requests are "
                             "rate limited to roughly one per 1.5s per host)")
    parser.add_argument("--desc-limit", type=int, default=25,
                        help="Max descriptions to fetch when --descriptions is set "
                             "(0 = no limit)")
    parser.add_argument("--desc-workers", type=int, default=2,
                        help="Concurrent description fetch threads")
    args = parser.parse_args()

    backend_dir = Path(__file__).parent
    # (source name, script, accepts --mode)
    scrapers = [
        ("linkedin", backend_dir / "linkedin_scrapper.py", True),
        ("ejobs", backend_dir / "ejobs_scrapper.py", True),
        ("bestjobs", backend_dir / "bestjobs_scrapper.py", False),
    ]

    available_scrapers = [
        (name, path, supports_mode) for name, path, supports_mode in scrapers if path.exists()
    ]
    for name, path, _ in scrapers:
        if not path.exists():
            print(f"Skipping missing scraper: {path.name}")

    all_jobs: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=len(available_scrapers) or 1) as executor:
        future_to_source = {
            executor.submit(
                _run_scraper,
                scraper_path=path,
                source_name=name,
                title=args.title,
                location=args.location,
                page_size=args.page_size,
                max_pages=args.max_pages,
                mode=args.mode,
                supports_mode=supports_mode,
            ): (name, path)
            for name, path, supports_mode in available_scrapers
        }

        for future in as_completed(future_to_source):
            source_name, scraper_path = future_to_source[future]
            try:
                all_jobs.extend(future.result())
            except subprocess.CalledProcessError as error:
                stderr = error.stderr.strip() if error.stderr else ""
                print(f"Scraper failed: {scraper_path.name}")
                if stderr:
                    print(stderr)

    merged_jobs = _dedupe_jobs(all_jobs)
    sorted_jobs = _sort_jobs(merged_jobs)

    # After dedupe, so we never fetch the same description twice.
    if args.descriptions:
        fetch_descriptions(
            sorted_jobs,
            title_filter=args.title,
            max_workers=args.desc_workers,
            mode=args.mode,
            limit=args.desc_limit,
        )

    sources_summary = _build_sources_summary(sorted_jobs)
    output_payload = {
        "total_jobs_found": len(sorted_jobs),
        "sources_summary": sources_summary,
        "jobs": sorted_jobs,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output_payload, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(sorted_jobs)} jobs to {output_path}")


if __name__ == "__main__":
    main()
