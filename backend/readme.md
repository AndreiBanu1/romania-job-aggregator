```bash
source .venv/bin/activate
python -m backend.scrappers.unified_scrapper --title "Angular" --location "Bucharest" --mode "strict" --output "job-results/jobs-angular.json"
```

If `jooble` returns `403`, pass a valid browser cookie:

```bash
source .venv/bin/activate
python -m backend.scrappers.jooble_scrapper \
  --title "Angular" \
  --location "Bucharest" \
  --page-size 25 \
  --max-pages 0 \
  --cookie "<PASTE_BROWSER_COOKIE_HERE>" \
  --output backend/scrappers/job-results/test-jooble.json
```

Individual scraper commands:

```bash
source .venv/bin/activate
python -m backend.scrappers.linkedin_scrapper \
  --title "Angular" \
  --location "Bucharest" \
  --page-size 25 \
  --max-pages 0 \
  --output backend/scrappers/job-results/test-linkedin.json

python -m backend.scrappers.ejobs_scrapper \
  --title "Angular" \
  --location "Bucharest" \
  --page-size 25 \
  --max-pages 0 \
  --output backend/scrappers/job-results/test-ejobs.json

python -m backend.scrappers.bestjobs_scrapper \
  --title "Angular" \
  --location "Bucharest" \
  --page-size 25 \
  --max-pages 0 \
  --output backend/scrappers/job-results/test-bestjobs.json
```

Generated files:
- `backend/scrappers/job-results/jobs-test-unified.json`
- `backend/scrappers/job-results/test-linkedin.json`
- `backend/scrappers/job-results/test-ejobs.json`
- `backend/scrappers/job-results/test-bestjobs.json`
- `backend/scrappers/job-results/test-jooble.json`

Optional analysis flow:

```bash
source .venv/bin/activate
python -m backend.scrappers.unified_scrapper \
  --title "Software Engineer" \
  --location "Bucharest" \
  --mode none \
  --output backend/scrappers/job-results/jobs-aggregated.json

python backend/scrappers/helpers/analyze_jobs.py --input backend/scrappers/job-results/jobs-aggregated.json
```