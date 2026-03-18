```bash
python run-all-scrapers.py --title Angular --location Bucharest --page-size 25 --max-pages 0 --prefix jobs-test
```

If Jooble returns `403`, pass your browser cookie:

```bash
python run-all-scrapers.py --title Angular --location Bucharest --page-size 25 --max-pages 0 --prefix jobs-test --jooble-cookie "<PASTE_BROWSER_COOKIE_HERE>"
```

Generated files:
- `job-results/jobs-test-linkedin.json`
- `job-results/jobs-test-ejobs.json`
- `job-results/jobs-test-bestjobs.json`
- `job-results/jobs-test-jooble.json`
- `job-results/jobs-test-aggregated.json`

Update:

Run first: 
```bash
python run-all-scrapers.py --title "Software Engineer" --location "Bucharest" --mode none
```

then: 
```bash
python analyze_jobs.py --input job-results/jobs-aggregated.json
```