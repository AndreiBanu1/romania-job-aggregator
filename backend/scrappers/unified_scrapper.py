# backend/scrappers/unified_scrapper.py
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .linkedin_scrapper import collect_all_jobs as linkedin_jobs, is_relevant
# from .ejobs_scrapper import collect_all_jobs as ejobs_jobs
# from .bestjobs_scrapper import collect_all_jobs as bestjobs_jobs
# from .jooble_scrapper import collect_all_jobs as jooble_jobs
from .aggregate_scrappers import aggregate_jobs


def fetch_descriptions(jobs, title_filter=None, max_workers=5, mode="loose"):
    """Fetch job descriptions concurrently with optional title filter."""
    if not jobs:
        return []

    def fetch(job):
        if is_relevant(job, title_filter, mode):
            if "href" in job and job["href"]:
                from .helpers.job_desc_fetcher import get_job_description  # import per-thread safe
                job["description"] = get_job_description(job["href"])
        else:
            job["description"] = ""
        return job

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(fetch, jobs))


def _safe_fetch(source_name: str, fetcher):
    try:
        return fetcher()
    except Exception as exc:
        print(f"[{source_name}] Failed: {exc}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Unified job scraper (all sources)")
    parser.add_argument("--title", required=True,
                        help="Job title, e.g. 'Angular'")
    parser.add_argument("--location", required=True,
                        help="City, e.g. 'Bucharest'")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--output", required=True,
                        help="Output JSON file path")
    parser.add_argument("--desc-workers", type=int, default=5,
                        help="Concurrent description fetch threads")
    parser.add_argument("--mode", choices=["strict", "loose", "none"], default="loose",
                        help="Job filtering mode")
    args = parser.parse_args()

    all_jobs = {}

    print("[linkedin] Fetching jobs...")
    jobs = _safe_fetch(
        "linkedin",
        lambda: linkedin_jobs(args.title, args.location, args.page_size, args.max_pages, mode=args.mode),
    )
    all_jobs["linkedin"] = fetch_descriptions(jobs, args.title, args.desc_workers, args.mode)
    print(f"[linkedin] Fetched {len(all_jobs['linkedin'])} jobs.")

    # print("[ejobs] Fetching jobs...")
    # jobs = _safe_fetch(
    #     "ejobs",
    #     lambda: ejobs_jobs(args.title, args.location, args.page_size, args.max_pages),
    # )
    # all_jobs["ejobs"] = fetch_descriptions(jobs, args.title, args.desc_workers, "none")
    # print(f"[ejobs] Fetched {len(all_jobs['ejobs'])} jobs.")

    # print("[bestjobs] Fetching jobs...")
    # jobs = _safe_fetch(
    #     "bestjobs",
    #     lambda: bestjobs_jobs(args.title, args.location, args.page_size, args.max_pages),
    # )
    # all_jobs["bestjobs"] = fetch_descriptions(jobs, args.title, args.desc_workers, "none")
    # print(f"[bestjobs] Fetched {len(all_jobs['bestjobs'])} jobs.")

    # print("[jooble] Fetching jobs...")
    # jobs = _safe_fetch(
    #     "jooble",
    #     lambda: jooble_jobs(args.title, args.location, args.page_size, args.max_pages),
    # )
    # all_jobs["jooble"] = fetch_descriptions(jobs, args.title, args.desc_workers, "none")
    # print(f"[jooble] Fetched {len(all_jobs['jooble'])} jobs.")

    print("[aggregate] Aggregating jobs...")
    aggregated = aggregate_jobs(all_jobs)
    all_jobs["aggregated"] = aggregated
    print(f"[aggregate] Aggregated {len(aggregated)} jobs.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        output_data = {"total_jobs_found": len(aggregated), **all_jobs}
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ All jobs saved to {output_path}")


if __name__ == "__main__":
    main()
