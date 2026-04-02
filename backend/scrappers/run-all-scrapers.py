import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run_command(command: list[str], label: str) -> bool:
    print(f"\n[{label}] Running: {' '.join(command)}")
    
    env = os.environ.copy()
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")
    
    result = subprocess.run(command, capture_output=True, text=True, env=env)

    if result.stdout.strip():
        print(result.stdout.strip())

    if result.returncode != 0:
        if result.stderr.strip():
            print(result.stderr.strip())
        print(f"{label} failed with exit code {result.returncode}")
        return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LinkedIn, eJobs, BestJobs scrapers and aggregate results in one command"
    )
    parser.add_argument("--title", required=True, help="Job title, e.g. 'Angular'")
    parser.add_argument("--location", required=True, help="Location, e.g. 'Bucharest'")
    parser.add_argument(
    "--mode",
    choices=["strict", "loose", "none"],
    default="loose",
    help="Filtering mode: strict (title only), loose (smart), none (no filtering)",
)
    parser.add_argument("--page-size", type=int, default=10, help="Page size for all scrapers")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages for all scrapers (0 = no limit)")
    parser.add_argument(
        "--output-dir",
        default="job-results",
        help="Directory where individual and aggregated JSON files are written",
    )
    parser.add_argument(
        "--prefix",
        default="jobs",
        help="Filename prefix for outputs, e.g. 'jobs' => jobs-linkedin.json",
    )
    parser.add_argument(
        "--jooble-cookie",
        default="",
        help="Optional cookie header for Jooble requests (use when Jooble returns 403)",
    )
    args = parser.parse_args()

    root_dir = Path(__file__).parent
    backend_dir = Path(__file__).resolve().parent
    output_dir = root_dir / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    python_exec = sys.executable

    outputs = {
        "linkedin": output_dir / f"{args.prefix}-linkedin.json",
        "ejobs": output_dir / f"{args.prefix}-ejobs.json",
        "bestjobs": output_dir / f"{args.prefix}-bestjobs.json",
        "jooble": output_dir / f"{args.prefix}-jooble.json",
        "aggregated": output_dir / f"{args.prefix}-aggregated.json",
    }

    common_args = [
        "--title",
        args.title,
        "--location",
        args.location,
        "--page-size",
        str(args.page_size),
        "--max-pages",
        str(args.max_pages),
    ]

    failed_labels: list[str] = []

    if not _run_command(
        [
            python_exec,
            str(backend_dir / "linkedin-scrapper.py"),
            *common_args,
            "--output",
            str(outputs["linkedin"]),
        ],
        "linkedin",
    ):
        failed_labels.append("linkedin")

    if not _run_command(
        [
            python_exec,
            str(backend_dir / "ejobs-scrapper.py"),
            *common_args,
            "--output",
            str(outputs["ejobs"]),
        ],
        "ejobs",
    ):
        failed_labels.append("ejobs")

    if not _run_command(
        [
            python_exec,
            str(backend_dir / "bestjobs-scrapper.py"),
            *common_args,
            "--output",
            str(outputs["bestjobs"]),
        ],
        "bestjobs",
    ):
        failed_labels.append("bestjobs")

    jooble_args = []
    if args.jooble_cookie.strip():
        jooble_args.extend(["--cookie", args.jooble_cookie.strip()])

    if not _run_command(
        [
            python_exec,
            str(backend_dir / "jooble-scrapper.py"),
            *common_args,
            *jooble_args,
            "--output",
            str(outputs["jooble"]),
        ],
        "jooble",
    ):
        failed_labels.append("jooble")

    if not _run_command(
        [
            python_exec,
            str(backend_dir / "aggregate-scrapers.py"),
            *common_args,
            "--output",
            str(outputs["aggregated"]),
        ],
        "aggregate",
    ):
        failed_labels.append("aggregate")

    print("\nCompleted successfully. Output files:")
    for name, output_path in outputs.items():
        print(f"- {name}: {output_path}")

    if failed_labels:
        print("\nCompleted with warnings. Failed steps:")
        for label in failed_labels:
            print(f"- {label}")


if __name__ == "__main__":
    main()
