import json
import argparse
import re
from pathlib import Path


# -----------------------------------
# CONFIG
# -----------------------------------
TECH_KEYWORDS = {
    "react": {
        "title_strict": ["react", "reactjs", "react.js", "next.js", "nextjs"],
        "title_loose": ["frontend", "web developer"],
        "desc": ["react", "javascript", "typescript"],
        "negative": []
    },
    "angular": {
        "title_strict": ["angular"],
        "title_loose": ["frontend", "web developer"],
        "desc": ["angular", "typescript", "frontend"],
        "negative": ["java", "spring", "backend"]
    },
    "java": {
        "title_strict": ["java", "spring", "springboot", "spring boot"],
        "title_loose": [],
        "desc": ["java", "spring"],
        "negative": []
    },
    "python": {
        "title_strict": ["python", "django", "flask"],
        "title_loose": [],
        "desc": ["python"],
        "negative": []
    },
    "qa": {
        "title_strict": ["qa", "quality assurance", "tester", "testing"],
        "title_loose": [],
        "desc": ["selenium", "playwright", "cypress"],
        "negative": []
    },
}


# -----------------------------------
# HELPERS
# -----------------------------------
def normalize_text(text: str) -> str:
    return text.lower() if text else ""


def match_keywords(text: str, keywords: list[str]) -> int:
    """Return number of keyword matches using word boundaries"""
    matches = 0
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            matches += 1
    return matches


# -----------------------------------
# SCORING
# -----------------------------------
def score_job_for_tech(job: dict, tech: str) -> int:
    config = TECH_KEYWORDS[tech]

    title = normalize_text(job.get("title", ""))
    desc = normalize_text(job.get("description", ""))

    score = 0

    # 🔥 Strong signals (title exact)
    score += match_keywords(title, config.get("title_strict", [])) * 10

    # 🟡 Medium signals (title loose)
    score += match_keywords(title, config.get("title_loose", [])) * 4

    # 🔵 Weak signals (description)
    score += match_keywords(desc, config.get("desc", [])) * 2

    # 🔴 Negative signals
    score -= match_keywords(title, config.get("negative", [])) * 5

    return score


def classify_job(job: dict) -> dict[str, int]:
    scores = {}
    for tech in TECH_KEYWORDS:
        scores[tech] = score_job_for_tech(job, tech)
    return scores


# -----------------------------------
# ANALYSIS
# -----------------------------------
def analyze_jobs(jobs: list[dict]) -> dict:
    results = {
        tech: {"high": 0, "medium": 0, "low": 0, "total": 0}
        for tech in TECH_KEYWORDS
    }

    for job in jobs:
        scores = classify_job(job)

        for tech, score in scores.items():
            if score >= 10:
                results[tech]["high"] += 1
                results[tech]["total"] += 1
            elif score >= 6:
                results[tech]["medium"] += 1
                results[tech]["total"] += 1
            elif score >= 3:
                results[tech]["low"] += 1
                results[tech]["total"] += 1

    return results


# -----------------------------------
# MAIN
# -----------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Job market analyzer (weighted)")
    parser.add_argument("--input", required=True,
                        help="Input JSON file with jobs")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(f"File not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    total_jobs = len(jobs)

    results = analyze_jobs(jobs)

    print("\n📊 Job Market Analysis (Weighted)\n")
    print(f"Total jobs analyzed: {total_jobs}\n")

    for tech, stats in results.items():
        total = stats["total"]
        pct = (total / total_jobs * 100) if total_jobs else 0

        print(f"{tech.capitalize():<10}: {total:>5} jobs ({pct:>5.2f}%)")
        print(f"   ├─ High   : {stats['high']}")
        print(f"   ├─ Medium : {stats['medium']}")
        print(f"   └─ Low    : {stats['low']}\n")


if __name__ == "__main__":
    main()
