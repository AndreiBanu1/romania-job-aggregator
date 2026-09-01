# Romania Job Aggregator

Searches several Romanian job boards at once and shows the combined, deduplicated
results in one sortable table — instead of running the same query on three sites
and comparing tabs by hand.

**Live demo:** [🚀 Open the live demo](https://romania-job-aggregator.andreibanu97.workers.dev/)

---

## What it does

Type a job title and a city, and the app queries **LinkedIn**, **eJobs** and
**BestJobs** in parallel, merges the results, drops duplicates, and presents them
as one table you can sort, page through and expand.

- **One search, three sources.** Each scraper runs concurrently; results are
  tagged with their origin and deduplicated by URL (falling back to
  title + company + location when a posting has no stable link).
- **Relevance filtering.** Job boards answer "Angular developer" with anything
  containing "developer", so titles are filtered server-side in `strict`
  (every keyword token must appear), `loose` (any distinctive token or a related
  term) or `none` mode.
- **Descriptions on demand.** Full descriptions are fetched only when you expand
  a row, because the fetch is rate limited to roughly one request per 1.5s per
  host — fetching all of them would turn a 15s search into several minutes.
- **Saved searches.** Store a title + city pair and re-run it in one click.
- **Saved job lists.** Snapshot the actual results of a search, so a set of
  postings stays readable after the listings are taken down. Each snapshot is
  fingerprinted by its contents, so the same result set cannot be saved twice.
- **Shareable queries.** The active search lives in the URL
  (`/?title=Angular%20developer&city=Bucharest`), so a reload, a bookmark or a
  pasted link restores it.

Saved searches and saved job lists live in `localStorage` — there is no account
system and no server-side state.

---

## How it works

```
┌──────────────────────────┐
│  Angular 21 frontend     │   standalone components + signals
│  :4200                   │   Angular Material table, localStorage
└────────────┬─────────────┘
             │  HTTP (JSON)
┌────────────▼─────────────┐
│  Express 5 API           │   validates input, spawns the scrapers,
│  :3000  (backend/api.js) │   reads their JSON back, cleans up temp files
└────────────┬─────────────┘
             │  child process (argument array, never a shell)
┌────────────▼──────────────────────────────────────────────┐
│  Python scrapers (requests + BeautifulSoup)               │
│  aggregate_scrappers.py  ──┬── linkedin_scrapper.py       │
│    ThreadPoolExecutor,     ├── ejobs_scrapper.py          │
│    dedupe, sort, summarise └── bestjobs_scrapper.py       │
│  helpers/: relevance, rate_limiter, descriptions,         │
│            location_normalizer                            │
└───────────────────────────────────────────────────────────┘
```

The API is a thin layer: it validates the request, runs
`aggregate_scrappers.py` as a child process with an argument array (so user
input can never be interpreted as a shell command), writes to a per-request temp
file (so concurrent searches cannot overwrite each other), and returns the JSON.

Every layer speaks the same payload shape:

```json
{
  "total_jobs_found": 422,
  "sources_summary": { "bestjobs": 359, "ejobs": 2, "linkedin": 61 },
  "jobs": [{ "id": "...", "title": "...", "company": "...",
             "location": "...", "href": "...", "source": "bestjobs" }]
}
```

That consistency is what makes the static demo possible: the scrapers' output
file *is* a valid API response, so it can be served as a plain `.json` asset.

### API endpoints

| Method | Path                | Purpose                                              |
| ------ | ------------------- | ---------------------------------------------------- |
| `POST` | `/jobs`             | Run all scrapers. Body: `title`, `city`, optional `mode`, `descriptions`, `descLimit`. Takes 15–30s. |
| `POST` | `/job-description`  | Fetch one description. Body: `href`.                 |
| `POST` | `/jobs-mock`        | Return a canned response instantly, for UI work.     |
| `GET`  | `/cities`           | Romanian cities, for the autocomplete.               |

---

## Hosting

The deployed site is **static** — a plain Angular bundle served by a
**Cloudflare Worker with static assets**, with no server-side code behind it.

That is a deliberate trade-off. The obvious alternative is to host the Express
API and let visitors trigger real scrapes, but:

- **Job boards block datacenter IPs.** A scraper that works from a laptop
  returns empty results or Cloudflare challenges from a cloud host. The demo
  would look broken through no fault of the code.
- **A scrape takes 15–30 seconds.** On a free tier that also sleeps when idle,
  a visitor's first click can mean well over a minute of spinner.

So the scraping happens ahead of time instead:

```
 nightly (03:17 UTC)                    on push
┌────────────────────────┐        ┌──────────────────────────┐
│ GitHub Actions         │        │ Cloudflare Workers Builds│
│ runs the real scrapers │──────▶ │ builds Angular, deploys  │
│ commits the JSON       │ commit │ the assets-only Worker   │
└────────────────────────┘        └──────────────────────────┘
        │                                      │
        ▼                                      ▼
 frontend/public/demo-data/*.json    visitor gets a 1s page load
```

- `.github/workflows/refresh-demo-data.yml` runs
  `backend/scrappers/build_demo_data.py` on a schedule. It scrapes each query in
  `backend/demo_queries.json` and commits the results to
  `frontend/public/demo-data/`.
- Committing the data means Cloudflare redeploys automatically, and the data is
  **real output from the real scrapers** — just collected last night rather than
  on demand.
- **A failed scrape never breaks the demo.** If a query comes back empty (a
  source blocked the runner), the builder keeps the previously committed
  snapshot and flags it `stale` in the manifest instead of overwriting good data
  with nothing.

### What the demo build does differently

`environment.demo` (see `frontend/src/environments/`) switches three things:

| | Local (`ng serve`) | Hosted (`ng build`) |
| --- | --- | --- |
| Search | `POST /jobs` or `/jobs-mock` | reads `demo-data/*.json` |
| Cities | `GET /cities` | reads `demo-data/cities.json` |
| Descriptions | fetched live per row | only those baked into the snapshot |

A search that matches one of the scraped queries is served **verbatim** from its
snapshot. Any other search filters the whole snapshot corpus client-side, so the
search box stays usable instead of answering only a fixed menu. The page says
which it is doing, so nothing is passed off as a live scrape.

### Deploying it yourself

The Angular app lives in `frontend/`, but Cloudflare Workers Builds runs its
commands at the **repository root**. Two root-level files bridge that gap, so
there is nothing to configure in the dashboard beyond the commands:

- **`package.json`** — its `build` script installs and builds the frontend
  (`npm ci --prefix frontend && npm run build --prefix frontend`), and it carries
  `wrangler` as the only root dependency.
- **`wrangler.jsonc`** — declares the Worker. `assets.directory` points at
  `./frontend/dist/frontend/browser`, which is why no "root directory" or "output
  directory" dashboard field is needed. There is no `main`, so the Worker serves
  assets and runs no code.

1. **Cloudflare dashboard** → Workers → connect this GitHub repo, then set:
   - Project name: `romania-job-aggregator` (must match `name` in `wrangler.jsonc`)
   - Install command: `npm install`
   - Build command: `npm run build`
   - Deploy command: `npx wrangler deploy`

   `.node-version` pins Node 22 for the build; Angular 21 needs 20.19+.

2. **Seed the data** — in the Actions tab, run **Refresh demo data** manually
   once (`workflow_dispatch`) so `demo-data/` is populated before the first
   visitor. It needs no secrets; the default `GITHUB_TOKEN` is enough for the
   commit, via `permissions: contents: write`.

Deep links work through `assets.not_found_handling: "single-page-application"`:
an unmatched path such as `/saved-job-lists` gets `index.html` and the Angular
router takes over, while real files (`/demo-data/*.json`, JS, CSS) are still
served directly.

To check the deployed behaviour before pushing:

```bash
npm run preview     # builds, then serves the Worker locally via wrangler dev
```

Other static hosts work too, but each wants the SPA fallback expressed its own
way — Netlify via a `_redirects` file, GitHub Pages via a `404.html` copy of
`index.html`. (Do not add a `_redirects` file here: wrangler uploads it as
Worker configuration, and Cloudflare rejects `/* /index.html 200` as a
redirect loop.) The one real assumption is that the site is served from the
domain root, because the demo data is fetched from `/demo-data/...`. A GitHub
Pages *project* site is served from `/<repo>/`, which would also need a
`--base-href`.

> **Note:** GitHub disables scheduled workflows after 60 days without repository
> activity. If the demo data goes stale, re-enable the workflow from the Actions
> tab.

---

## Running locally

Requires **Node 22+** and **Python 3.10+** (CI uses 3.12).

```bash
git clone https://github.com/AndreiBanu1/romania-job-aggregator.git
cd romania-job-aggregator

# Scrapers
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# API on :3000
cd backend && npm install && npm start

# Frontend on :4200, in a second terminal
cd frontend && npm install && npm start
```

Open http://localhost:4200.

By default the frontend calls `/jobs-mock`, which returns a canned response
instantly — the right setting for UI work. To exercise the real scrapers, set
`liveSearch: true` in `frontend/src/environments/environment.development.ts` and
expect each search to take 15–30 seconds.

The scrapers also run standalone, without the API or the frontend:

```bash
.venv/bin/python backend/scrappers/aggregate_scrappers.py \
  --title "Angular developer" --location "Bucharest" \
  --mode loose --output job-results/jobs.json
```

See [`backend/readme.md`](backend/readme.md) for the individual scrapers.

### Regenerating the demo data locally

```bash
.venv/bin/python backend/scrappers/build_demo_data.py            # all configured queries
.venv/bin/python backend/scrappers/build_demo_data.py --desc-limit 0   # skip descriptions (much faster)
```

Then `cd frontend && npm run build` and serve `dist/frontend/browser` to see
exactly what the hosted site does.

---

## Tests

```bash
cd frontend && npm test                                  # 20 Karma/Jasmine specs
.venv/bin/python -m unittest discover -s backend/tests -t .   # 74 unittest tests
```

The frontend specs cover the two pieces of logic with real invariants: snapshot
storage (`saved-job-lists.service.spec.ts` — duplicate rejection, order-insensitive
fingerprints, quota failures that must not report success) and the demo data
loader (`demo-jobs.service.spec.ts` — verbatim snapshots, corpus filtering,
deduplication, request caching).

The backend tests cover relevance filtering, rate limiting, description fetching
and the LinkedIn scraper's parsing, against fixtures in `backend/tests/fixtures/`.

---

## Layout

```
backend/
  api.js                     Express API; spawns the scrapers
  demo_queries.json          which queries the nightly workflow scrapes
  jobs_response_example.json canned response behind /jobs-mock
  scrappers/
    aggregate_scrappers.py   runs every scraper, dedupes, summarises
    build_demo_data.py       writes the static snapshots for the hosted demo
    {linkedin,ejobs,bestjobs,jooble}_scrapper.py
    helpers/                 relevance, rate limiting, descriptions, locations
    romanian_cities.json
  tests/                     unittest suite + fixtures
frontend/
  src/app/
    home/                    search form, demo notice
    jobs/                    JobsService, DemoJobsService, the results table
    saved-searches/          stored title + city pairs
    saved-job-lists/         stored result snapshots
    shared/                  CSS shared by the three tables
  src/environments/          demo vs local API switch
  public/demo-data/          committed scraper output (generated)
docs/                        feature notes and an improvement backlog
.github/workflows/           nightly demo-data refresh
package.json                 root entry point for Cloudflare Workers Builds
wrangler.jsonc               the assets-only Worker (output dir, SPA fallback)
.node-version                Node version for the Cloudflare build
```

---

## Known limitations

- **`jooble_scrapper.py` is not wired in.** It exists and works with a browser
  cookie, but `aggregate_scrappers.py` does not call it (Jooble answers `403`
  without one).
- **No linter or formatter** is configured, and there is no CI check on pull
  requests — only the scheduled data refresh.
- **Scraping is inherently brittle.** Each scraper depends on a site's current
  markup or internal JSON; sources change without notice. The per-source failure
  handling means one broken scraper degrades the results rather than failing the
  search.
- **`localStorage` has a ~5 MB budget.** Saving a very large job list can exceed
  it; the app reports the failure instead of silently losing the list.
- Anything scraped here is public listing data, collected at a deliberately
  polite request rate. This is a portfolio project, not a commercial service.

## License

MIT — see [LICENSE](LICENSE).
