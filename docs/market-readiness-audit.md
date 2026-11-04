# Market-readiness audit & plan

*Audited 2026-11-04 against `master` @ `920651e`. Every number below was measured on
the committed code and data, not estimated.*

## TL;DR

The engineering is careful for a portfolio project: a clean scraper layering, a real rate
limiter with a circuit breaker, an SSRF allowlist, 74 passing backend tests, and a smart
static-hosting setup. **It is not a product yet**, and the gap is not mostly code:

1. **The data isn't good enough to compete.** In the live snapshots, **88% of BestJobs rows
   don't match the query** and BestJobs makes up 85% of all rows. **eJobs returns 0 jobs in
   all 6 snapshots.** Only 6 of roughly 360 rows per query have a description. There are no
   posting dates, salaries, seniority or remote flags.
2. **The core architecture doesn't scale past one user.** Each search spawns 3–4 Python
   processes and takes 15–30 seconds. It can't run from a server because job boards block
   datacenter IPs, which is why the public site is a static demo.
3. **There's legal exposure that blocks commercial use.** Scraping LinkedIn breaches its
   terms. Under the EU *sui generis* database right, the CJEU has ruled specifically on
   job-ad aggregators (*CV-Online Latvia v Melons*, C-762/19, 2021).
4. **There's no retention loop or business model**: no accounts, no alerts, no SEO, no
   monetisation, no brand or domain. Jooble, Careerjet and Indeed already aggregate
   Romanian jobs for free.

**Recommendation:** reposition from "search three boards at once" to **the most complete,
deduplicated and salary-transparent feed of tech jobs in Romania, with alerts**. Source it
mainly from employers' own ATS feeds, which are legal, fresh and unique. Rebuild the
backend as an ingestion pipeline plus a database, so search takes milliseconds rather than
a 30-second live scrape. A solo developer can get to a launchable MVP in roughly **10–12
weeks** (plan at the end).

---

## 1. Business audit

### What exists today

| Dimension | State |
|---|---|
| Positioning | "One search, three sources." The README calls it *"a portfolio project, not a commercial service."* |
| Users | Anonymous, single-session. State lives in `localStorage` only. |
| Retention | None: no accounts, alerts, email or notifications. |
| Acquisition | None: a `*.workers.dev` URL, page title "Frontend", no meta tags, no SEO pages. |
| Monetisation | None. |
| Brand / legal | No domain, name, Terms, Privacy Policy, cookie banner or imprint. |

### Market reality (Romania)

- **Incumbent boards**: eJobs, BestJobs, Hipo, OLX Locuri de muncă and LinkedIn. They own
  employers and their listings.
- **Existing aggregators**: Jooble, Careerjet, Indeed RO and Glassdoor. They already do
  "search many boards at once", for free, with alerts and SEO. **"Search 3 boards at once"
  is therefore not a defensible value proposition.**
- **A real opening is pay transparency.** EU Directive 2023/970 had to be transposed by
  **7 June 2026**. Employers must give a pay range before the interview. Romanian
  transposition status needs checking, but salary data is becoming available and no
  aggregator surfaces it well.
- **Another opening is tech-specific search.** Generic boards are noisy for developers.
  This shows in our own data: BestJobs answers "Angular developer" with .NET, support and
  sales roles. A curated tech feed with stack tags, seniority, remote type and salary is a
  credible niche. Every demo query is already a tech role.

### Legal risk (must be resolved before any commercial launch)

| Risk | Detail | Mitigation |
|---|---|---|
| LinkedIn ToS | The guest endpoint `jobs-guest/.../seeMoreJobPostings` is scraped with a spoofed UA. That breaches the User Agreement and invites IP or legal action. | **Drop LinkedIn** as a scraped source in a commercial product. |
| EU database right | *Innoweb v Wegener* (C-202/12) and *CV-Online v Melons* (C-762/19) say a meta-search engine that re-uses a substantial part of a job board's database can infringe if it harms the maker's investment. | Use **partner feeds** (XML/API agreements; boards often want the traffic), **employer ATS feeds** and direct employer posting. Always deep-link to the original. |
| GDPR | Accounts and alerts mean personal data. Descriptions can contain recruiter names and emails. Google Fonts are loaded from Google's CDN (a German court fined this in 2022). | Privacy policy, DPA with processors, self-hosted fonts, consent-free analytics, retention rules, a deletion endpoint. |
| Pay data | Salary extraction may be wrong. | Label it "as stated by employer" and keep provenance. |

**Get one hour of advice from a Romanian IP/GDPR lawyer before launch.** This audit isn't
legal advice.

### Monetisation options (in order of fit)

1. **Employer side (main revenue):** featured or sponsored listings, then direct job
   posting at a price below eJobs/BestJobs. Tech employers pay for reach to qualified
   developers.
2. **Pay-per-click or affiliate from boards:** Jooble's model. It needs partner feeds,
   which also fixes the legal problem.
3. **B2B data:** salary and demand reports for HR and recruiters ("Angular demand in Cluj,
   Q1 2027"). This is the existing `analyze_jobs.py` idea turned into a product.
4. **B2C premium:** instant alerts, application tracker, salary insights. The lowest
   willingness to pay, so keep it as an add-on.

### KPIs to instrument from day one

Weekly active searchers, alert sign-ups, alert open/click rate, click-outs to postings
(the core value event), 4-week return rate, index freshness (median job age, percentage
seen in the last 24 hours) and source health (jobs per source per day).

---

## 2. Data quality audit (the biggest product problem)

Measured on `frontend/public/demo-data/*.json`:

| Query | Rows | BestJobs rows | BestJobs actually relevant | eJobs |
|---|---|---|---|---|
| Angular dev, Bucharest | 360 | 317 | 38 (12%) | 0 |
| Python dev, Bucharest | 396 | 307 | 26 (8%) | 0 |
| React dev, Bucharest | 254 | 209 | 48 (23%) | 0 |
| Java dev, Cluj | 180 | 151 | 19 (13%) | 0 |
| DevOps, Timișoara | 221 | 215 | 27 (13%) | 0 |
| QA, Iași | 51 | 45 | 20 (44%) | 0 |

Root causes:

- **BestJobs never applies the relevance filter.** `collect_all_jobs` in
  [bestjobs_scrapper.py](../backend/scrappers/bestjobs_scrapper.py) has no `mode` and
  never calls `is_relevant`, and the aggregator passes `supports_mode=False`. This is a
  roughly one-line fix that removes about 85% of the noise.
- **eJobs is dead in production.** All snapshots show 0. It's likely blocked from GitHub
  runners, or a city lookup raises `ValueError` (in `collect_all_jobs`), which kills the
  whole source. Nothing alerts on this: snapshots aren't flagged `stale` because the query
  as a whole wasn't empty.
- **Locations aren't normalised.** The same city appears as "Bucharest, Romania",
  "Bucharest" and "Strada București 16, Romania". "Remote" makes up 40–90% of BestJobs
  rows, with no remote or hybrid field.
- **Cross-source dedupe only works by URL.** The same role posted on LinkedIn and BestJobs
  never merges. BestJobs `ownApplyUrl` points off-site, so the description allowlist
  rejects it too.
- **The schema is too thin**: `id, title, company, location, href, source`. There's no
  `posted_at`, `first_seen`/`last_seen`, salary, seniority, employment type, remote type,
  stack tags or canonical company.
- **Description coverage is 1.7%** (12 per query, about 6 populated).

---

## 3. Technology & architecture audit

### Current architecture

```
Angular SPA ──HTTP──▶ Express ──spawn──▶ aggregate_scrappers.py ──spawn×3──▶ scraper.py
                                                    (live scrape per search, 15–30 s)
Hosted: static bundle + nightly GitHub Action that commits JSON into git
```

| Problem | Consequence |
|---|---|
| Live scraping per request | 15–30 s latency, and it can't run from a datacenter IP (blocked). The public site can only be a demo of 6 fixed queries. |
| Node → Python → Python process chain | About 4 processes per search. No timeout, no concurrency cap and no cancellation when the client disconnects. A few concurrent users can exhaust a small VM. |
| Two backend languages for one thin API | Express does nothing except spawn Python. |
| Data stored in git | 70+ bot commits of about 620 KB of JSON each. The repo history grows forever, and deploys are coupled to data refreshes. The Nov 4 run failed on a GitHub 500 during push, with no retry. |
| Corpus search downloads every snapshot | Any non-exact search fetches all ~620 KB of JSON to filter client-side. It doesn't scale beyond a handful of queries. |
| No persistence or identity | Alerts, history, cross-device saves and analytics are all impossible. |

### Target architecture

```
                ┌──────────── scheduler (cron / queue) ────────────┐
                ▼                                                  ▼
  Source adapters (Python, one contract)               Enrichment workers
  • ATS feeds: Greenhouse, Lever, Workable,           • normalise location / remote
    SmartRecruiters, Teamtailor, Personio XML          • salary extraction
  • Partner XML feeds (boards)                         • seniority + stack tagging
  • Scrapers only where permitted                      • cross-source dedupe (fingerprint)
                │                                                  │
                └──────────────▶ PostgreSQL (jobs, companies, sources, runs,
                                  users, alerts) + full-text / trigram search
                                               │
                                   FastAPI (read API, auth, alerts)
                                               │
              Angular SSR/prerender (SEO job pages, JSON-LD JobPosting) on Cloudflare
                                               │
                                   Email (alerts digest) · Sentry · metrics
```

Key decisions:

- **Ingest ahead of time and serve from a database.** Search drops to under 100 ms, and
  scraping becomes a background concern with its own retries and health checks.
- **One backend language.** Python with FastAPI reuses all the scraper and normaliser code
  and removes Express and the `spawn` layer.
- **Postgres** (Neon or Supabase managed) with `pg_trgm` and `tsvector`. Add
  Typesense/Meilisearch only if facets outgrow it.
- **Workers on a cheap VM** (Hetzner or Fly) that isn't on GitHub's IP ranges. Most ATS
  APIs are public JSON and don't block.
- **Data out of git.** Snapshots, if still needed, go to Cloudflare R2.
- **Job detail pages rendered for SEO** with `JobPosting` structured data. That makes them
  eligible for Google for Jobs, the largest free acquisition channel for a job site.

---

## 4. Code & implementation audit

What's good and worth keeping: the layering in `linkedin_scrapper.py`;
`helpers/rate_limiter.py` (a thread-safe limiter, circuit breaker and jittered backoff,
all tested); `location_normalizer.py` (418 cities with aliases); the SSRF allowlist in
`fetch_description.py`; `spawn` with an argument array; per-request temp files; the stale
snapshot fallback; the typed `Environment` contract; signals used idiomatically; and
saved-list fingerprinting with quota handling.

### Backend: correctness and security

| # | Finding | Location | Severity |
|---|---|---|---|
| B1 | BestJobs skips relevance filtering (85% noise) | `bestjobs_scrapper.py` `collect_all_jobs`, `aggregate_scrappers.py` scraper table | **High** |
| B2 | eJobs yields 0 in production, with no per-source alerting | `ejobs_scrapper.py`, `build_demo_data.py` | **High** |
| B3 | No timeout on spawned scrapers, no concurrency cap, no kill on client disconnect | `backend/api.js` `/jobs` | **High** (DoS) |
| B4 | Raw scraper `stderr` returned to the client, which leaks paths and tracebacks | `backend/api.js` `close` handler | Medium |
| B5 | `cors()` open to all origins; no rate limiting; no `helmet`; hard-coded `PORT` | `backend/api.js` top | Medium |
| B6 | Unguarded `JSON.parse` in `/jobs-mock` throws inside a callback, which crashes the process | `backend/api.js` `/jobs-mock` | Low |
| B7 | eJobs raises `ValueError` on an unknown city and loses the whole source; no 429/backoff (LinkedIn has some) | `ejobs_scrapper.py` | Medium |
| B8 | LinkedIn UA is Chrome 91 (2021), trivially fingerprinted. (Moot if LinkedIn is dropped.) | `linkedin_scrapper.py` `HEADERS` | Low |
| B9 | Dead code: `count_keywords`, `aggregate_jobs`, `unified_scrapper.py`, `analyze_jobs.py`; committed `backend/__pycache__/*.pyc` | various | Low |
| B10 | `sys.path.insert` hacks in every module; no `pyproject.toml`; no dev deps; "scrappers" misspelled in paths | backend | Low |
| B11 | No scraper contract (a common return type and error type). Adding a source means reading 3 files. | backend | Medium |
| B12 | Cross-source dedupe is URL-only | `_dedupe_jobs` | Medium |

### Frontend

| # | Finding | Location | Severity |
|---|---|---|---|
| F1 | `<title>Frontend</title>`, no meta description, no Open Graph, no `lang="ro"` | `frontend/src/index.html` | **High** for launch |
| F2 | English-only UI for a Romanian market; no i18n | app-wide | **High** |
| F3 | No result filters (source, remote, date, seniority) or in-table text filter | `jobs-table` | High |
| F4 | Pure client-side SPA, so job content can't be indexed | architecture | High |
| F5 | Google Fonts and Material Icons loaded from Google's CDN (GDPR) | `index.html` | Medium |
| F6 | Global singleton state in `JobsService`; mixes constructor DI and `inject()` | `jobs.service.ts`, `home.component.ts` | Low |
| F7 | Corpus search downloads every snapshot (~620 KB) | `demo-jobs.service.ts` `corpus()` | Medium (goes away with the API) |
| F8 | Stray `next-env.d.ts` referencing Next.js in an Angular project | `frontend/` | Low |
| F9 | Accessibility only partly done (per existing docs) | app-wide | Medium |
| F10 | No analytics, error reporting, cookie notice or legal pages | app-wide | High for launch |

### Engineering process

| # | Finding | Severity |
|---|---|---|
| P1 | No CI on pushes or PRs: no lint, test or build check. The only workflow is the data refresh. | **High** |
| P2 | No linter or formatter (ESLint, Prettier, Ruff) | Medium |
| P3 | Tests: 74 backend unit tests pass (0.6 s) and there are 20 frontend specs. There are no API tests, no e2e tests and no **scraper canary tests** against live sites, which is how you'd have caught B2. | Medium |
| P4 | Refresh workflow: no push retry (that caused the Nov 4 failure); actions on deprecated Node 20; cron 03:17 actually starts around 10:00 UTC because of GitHub queueing | Low |
| P5 | No observability: no Sentry, no structured logs, no per-source metrics | High once there are users |
| P6 | `docs/improvements/` is partly stale (it says `npm test` has zero specs, which is no longer true) | Low |

---

## 5. The plan

A realistic estimate assuming one developer working about 25 h/week. Each phase ends in
something shippable.

### Phase 0: Decide & de-risk (weeks 1–2)

- [ ] **Positioning:** commit to the "tech jobs in Romania, deduped, salary-transparent,
      with alerts" niche (or pick another deliberately). Write a one-page value
      proposition.
- [ ] **Legal:** a lawyer consult on the database right, ToS and GDPR. Decide the LinkedIn
      exit.
- [ ] **Partnerships:** email eJobs, BestJobs and Hipo about XML or affiliate feeds.
- [ ] **Brand:** name, `.ro` domain, Cloudflare custom domain.
- [ ] **Quick wins on the current code** (1–2 days in total): B1 BestJobs relevance, B2
      eJobs diagnosis plus per-source "0 results" alert, B3/B4 API hardening, P4 push
      retry and action bumps, F8 and B9 cleanup.
- [ ] **CI** (P1/P2): GitHub Action on PRs running Ruff, `unittest`, `ng build` and
      `ng test --watch=false`.

**Exit:** the demo shows only relevant results, eJobs is fixed or dropped knowingly, CI is
green, and the legal direction is decided.

### Phase 1: Data platform (weeks 3–6)

- [ ] `pyproject.toml`, a proper package (`jobagg/`) and removal of the `sys.path` hacks
      (B10).
- [ ] A **source adapter contract** (`fetch() -> Iterable[RawJob]`, typed errors, health
      status) (B11).
- [ ] **Postgres schema:** `sources`, `companies`, `jobs` (with `posted_at`, `first_seen`,
      `last_seen`, `salary_min/max/currency/period`, `seniority`, `remote_type`,
      `employment_type`, `tags[]`, `fingerprint`), `ingest_runs`.
- [ ] **ATS adapters:** Greenhouse, Lever, Workable, SmartRecruiters, Teamtailor and
      Personio, seeded with about 150 Romanian tech employers' career-page tokens. This is
      the differentiating dataset.
- [ ] Port the BestJobs and eJobs adapters, and keep them behind a feature flag pending
      the legal decision or partner feeds.
- [ ] **Enrichment:** location normalisation (reuse `location_normalizer`), remote
      detection, salary regex (RON/EUR, gross/net, month/year), seniority and stack
      tagging.
- [ ] **Cross-source dedupe:** fingerprint on normalised company, title and city, plus
      fuzzy title matching (B12).
- [ ] **Expiry:** mark a job closed when `last_seen` is more than 48 hours ago.
- [ ] Scheduler on a small VM: hourly for ATS, daily for boards. **Canary checks** alert
      when a source returns 0 or drops more than 50% day over day.

**Exit:** 5,000+ live tech jobs in the database, refreshed daily, each with source,
freshness and normalised fields, plus source health visible.

### Phase 2: Product MVP (weeks 6–10)

- [ ] **FastAPI** read API: `/jobs` search with facets, `/jobs/{id}`, `/companies/{slug}`
      and `/health`. Rate limiting, a CORS allowlist and pagination. Retire Express.
- [ ] **Frontend rebuilt on the API:** instant search; facets for city, remote,
      seniority, stack, salary range, posted date and source; sort by newest. Remove demo
      mode.
- [ ] **Accounts:** email magic link (Supabase Auth or similar). Move saved searches and
      lists server-side, with `localStorage` import.
- [ ] **Alerts:** a daily or instant email digest per saved search (Postmark/Resend) and a
      one-click unsubscribe. *This is the retention loop.*
- [ ] **Job and company pages** prerendered or SSR, with `JobPosting` JSON-LD, canonical
      links to the source and `sitemap.xml`.
- [ ] **Romanian-first i18n** (RO default, EN secondary), real `<title>` and meta tags
      (F1/F2).
- [ ] **Compliance:** Terms, Privacy Policy, cookie policy, self-hosted fonts (F5),
      account deletion and export.
- [ ] **Observability:** Sentry (frontend and API), Plausible/Umami analytics, uptime
      checks.
- [ ] Tests: API integration tests, Playwright e2e for search → open → click-out, and the
      alert flow.

**Exit:** a public beta on its own domain where a user can search, filter, sign up and
receive a useful alert email.

### Phase 3: Launch & growth (weeks 10–14)

- [ ] **Launch:** Romanian dev communities (r/programare, r/Romania, tech Facebook and
      LinkedIn groups, Discord), Product Hunt, a newsletter.
- [ ] **Programmatic SEO** landing pages ("Joburi React Cluj", "Joburi remote Python
      România") backed by real counts.
- [ ] **Salary insights page** by stack, city and seniority, built from the extracted
      ranges. It's a shareable, linkable asset.
- [ ] Weekly KPI review (section 1) and a feedback widget.

### Phase 4: Monetise (month 4+)

- [ ] Sponsored or featured listings with a Stripe checkout and an employer dashboard.
- [ ] Direct job posting for employers, priced below the incumbents.
- [ ] Affiliate/CPC on partner-feed click-outs.
- [ ] Quarterly paid salary and demand report for HR teams.

### Rough running costs at MVP scale

| Item | Monthly |
|---|---|
| VM for workers + API (Hetzner CX22 or similar) | ~€5–10 |
| Managed Postgres (Neon/Supabase free → paid tier) | €0–25 |
| Cloudflare (Workers/Pages, R2) | €0–5 |
| Email (Postmark/Resend, ~10k emails) | €0–15 |
| Sentry + Plausible | €0–15 |
| Domain | ~€1 |
| **Total** | **≈ €10–70** |

### Launch-readiness checklist

- [ ] Relevance at or above 90% on a 100-row manual sample per top query
- [ ] Median job age under 7 days; no closed jobs shown
- [ ] Every source has a health check and an alert
- [ ] p95 search latency under 300 ms
- [ ] Legal pages live; lawyer sign-off on sourcing
- [ ] CI green; e2e test of the core journey
- [ ] Error tracking and analytics live
- [ ] Alerts deliver, render in Gmail and Outlook, and unsubscribe works
- [ ] RO and EN copy reviewed; mobile layout checked on a real phone
