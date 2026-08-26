"""Produce the static snapshots the hosted frontend reads instead of an API.

Run by .github/workflows/refresh-demo-data.yml on a schedule. For each query in
backend/demo_queries.json it runs the normal aggregate scraper and writes the
result to frontend/public/demo-data/<slug>.json, plus an index.json manifest.

A query that comes back empty is treated as a failure, not as a result: the
previously committed snapshot is kept and flagged stale. Source sites block
datacenter IPs intermittently, and serving yesterday's jobs beats replacing a
working demo with an empty table.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRAPER = Path(__file__).resolve().parent / "aggregate_scrappers.py"
CITIES = Path(__file__).resolve().parent / "romanian_cities.json"
OUTPUT_DIR = REPO_ROOT / "frontend" / "public" / "demo-data"
CONFIG = REPO_ROOT / "backend" / "demo_queries.json"


def slugify(*parts: str) -> str:
    """'Angular developer', 'Cluj-Napoca' -> 'angular-developer-cluj-napoca'."""
    raw = " ".join(parts)
    ascii_only = (
        unicodedata.normalize("NFD", raw).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_only.lower())).strip("-")


def scrape(title: str, city: str, desc_limit: int, mode: str) -> dict | None:
    """Run the aggregate scraper for one query. None if it failed outright."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_path = Path(tmp.name)

    command = [
        sys.executable,
        str(SCRAPER),
        "--title", title,
        "--location", city,
        "--page-size", "25",
        "--max-pages", "0",
        "--mode", mode,
        "--output", str(output_path),
    ]
    if desc_limit > 0:
        command += ["--descriptions", "--desc-limit", str(desc_limit)]

    try:
        result = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.returncode != 0:
            print(f"  scraper exited {result.returncode}", file=sys.stderr)
            if result.stderr.strip():
                print(f"  {result.stderr.strip()}", file=sys.stderr)
            return None
        return json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"  could not read scraper output: {error}", file=sys.stderr)
        return None
    finally:
        output_path.unlink(missing_ok=True)


def load_existing(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", default=str(CONFIG), help="Path to demo_queries.json"
    )
    parser.add_argument(
        "--desc-limit",
        type=int,
        default=None,
        help="Override descriptions per query (0 disables description fetching)",
    )
    parser.add_argument(
        "--mode",
        choices=["strict", "loose", "none"],
        default=None,
        help="Override the scrapers' relevance filter",
    )
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    queries = config.get("queries", [])
    desc_limit = (
        args.desc_limit if args.desc_limit is not None else config.get("desc_limit", 0)
    )
    # Matches api.js's default, so the demo shows the same results the live app
    # would. Tighten it to "strict" here if loose matching looks too noisy.
    mode = args.mode or config.get("mode", "loose")

    if not queries:
        print("No queries configured.", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    manifest_entries = []
    failures = 0

    for query in queries:
        title, city = query["title"], query["city"]
        slug = slugify(title, city)
        target = OUTPUT_DIR / f"{slug}.json"
        print(f"Scraping {title} in {city} -> {target.name}")

        payload = scrape(title, city, desc_limit, mode)
        jobs = (payload or {}).get("jobs") or []
        previous = load_existing(target)

        if not jobs:
            failures += 1
            if previous and previous.get("jobs"):
                print("  empty result; keeping the previous snapshot")
                manifest_entries.append(
                    {
                        "title": title,
                        "city": city,
                        "slug": slug,
                        "total": previous.get("total_jobs_found", 0),
                        "scrapedAt": previous.get("scraped_at", now),
                        "stale": True,
                    }
                )
            else:
                print("  empty result and nothing to fall back on; skipping")
            continue

        payload["scraped_at"] = now
        payload["query"] = {"title": title, "city": city}
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        manifest_entries.append(
            {
                "title": title,
                "city": city,
                "slug": slug,
                "total": payload.get("total_jobs_found", len(jobs)),
                "scrapedAt": now,
            }
        )
        print(f"  saved {len(jobs)} jobs")

    if not manifest_entries:
        # Leaving the old manifest in place keeps the deployed site working.
        print("Every query failed; manifest left untouched.", file=sys.stderr)
        return 1

    manifest = {"generated": now, "queries": manifest_entries}
    (OUTPUT_DIR / "index.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # The autocomplete needs the same city list the API serves.
    (OUTPUT_DIR / "cities.json").write_text(
        CITIES.read_text(encoding="utf-8"), encoding="utf-8"
    )

    print(
        f"\nWrote {len(manifest_entries)} snapshots to {OUTPUT_DIR.relative_to(REPO_ROOT)}"
        + (f" ({failures} query/queries failed)" if failures else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
