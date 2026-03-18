import json
import argparse
from pathlib import Path

# Keywords: title-focused first, description keywords optional
TECH_KEYWORDS = {
    "react": {
        "title": ["react", "reactjs", "react.js", "next.js", "nextjs"],
        "desc": ["frontend", "javascript", "typescript" ,"web developer"]
    },
    "angular": {
        "title": ["angular", "angularjs", "angular.js", "nestjs"],
        "desc": ["frontend", "javascript", "typescript", "web developer"]
    },
    "java": {
        "title": ["java", "spring", "springboot", "spring boot"],
        "desc": []
    },
    "python": {
        "title": ["python", "django", "flask"],
        "desc": []
    },
    "qa": {
        "title": ["qa", "quality assurance", "tester", "testing", "selenium", "playwright", "cypress"],
        "desc": []
    },
}

def normalize_text(text: str) -> str:
    return text.lower() if text else ""

def analyze_jobs(jobs: list[dict]) -> dict[str, int]:
    counts = {tech: 0 for tech in TECH_KEYWORDS}

    for job in jobs:
        title_text = normalize_text(job.get("title", ""))
        desc_text = normalize_text(job.get("description", ""))

        for tech, kws in TECH_KEYWORDS.items():
            # ✅ Check title first
            if any(kw in title_text for kw in kws["title"]):
                counts[tech] += 1
            # ✅ Check description only if no title match
            elif any(kw in desc_text for kw in kws["desc"]):
                counts[tech] += 1

    return counts

def main():
    parser = argparse.ArgumentParser(description="Job market analyzer")
    parser.add_argument("--input", required=True, help="Input JSON file with jobs")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        raise FileNotFoundError(f"File not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    total_jobs = len(jobs)

    counts = analyze_jobs(jobs)

    print("\n📊 Job Market Analysis\n")
    print(f"Total jobs analyzed: {total_jobs}\n")

    for tech, count in counts.items():
        pct = (count / total_jobs * 100) if total_jobs else 0
        print(f"{tech.capitalize():<10}: {count:>5} jobs ({pct:>5.2f}%)")

if __name__ == "__main__":
    main()