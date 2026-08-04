# Backend improvements

Ordered by value-per-effort. Each item: what I observed, why it matters, how to
approach it. The fixes are yours to write.

---

## 1. The analysis tool is silently broken

`backend/scrappers/helpers/analyze_jobs.py` reads `data.get("jobs", [])`. But
`unified_scrapper.py` writes `{"total_jobs_found": …, "linkedin": [...], "aggregated": [...]}`
— there is no `"jobs"` key.

The exact flow documented in `backend/readme.md` produces:

```
$ .venv/bin/python backend/scrappers/helpers/analyze_jobs.py --input /tmp/unified_rl.json
📊 Job Market Analysis (Weighted)
Total jobs analyzed: 0
React     :     0 jobs ( 0.00%)
...
```

Four real jobs in that file. `.get("jobs", [])` returns the default, and the tool
reports zeros with no error. `aggregate_scrappers.py` *does* write a `"jobs"` key,
so it works there — which is why this probably went unnoticed.

**Why it matters beyond the bug:** this is the cost of two aggregation paths with
different output shapes. The same input file means different things depending on
which script produced it.

**How to approach it.** Don't just change the key. Decide what the *output
contract* is — one shape, documented, produced by both paths — and make the
consumer validate rather than silently default. `.get(key, default)` is right for
genuinely optional data and wrong for required structure; a missing `jobs` key
should be a loud error.

**Check:** run the readme's documented flow end to end and confirm non-zero
counts. Then feed it `{}` and confirm it complains instead of printing zeros.

### Also in this file

`match_keywords` uses `\b` word boundaries, which silently fails on keywords
starting with punctuation:

```python
match_keywords('.net developer', ['.net'])   # -> 0
match_keywords('next.js developer', ['next.js'])  # -> 1
```

`.net` never matches anything, ever. (`\b` requires a word character on the
boundary; `.` isn't one.) You already solved this in
`helpers/relevance.py` with `(?<![a-z0-9])` lookarounds — the fix is to reuse that
approach. Note that `.net` isn't currently in `TECH_KEYWORDS`, so nothing is
broken *today*; it will break the moment you add it, which is the worst timing.

**Bigger question:** `analyze_jobs.py` has its own `TECH_KEYWORDS`,
its own `normalize_text`, and its own matching — a third copy of relevance logic
after the two you consolidated into `helpers/relevance.py`. Decide whether
scoring is genuinely different from filtering (I think it is — weighted scores vs.
a boolean) or whether one can be built on the other's primitives.

---

## 2. Two scrapers accept `mode` and ignore it

`bestjobs_scrapper.py:118` and `jooble_scrapper.py:123` both have
`mode="loose"` in their signature. Neither uses it. Grep the bodies — no
`is_relevant` call, no reference to `mode` at all.

So a `--mode strict` search returns strictly-filtered LinkedIn and ejobs results
alongside completely unfiltered bestjobs results. In the run I did earlier,
bestjobs contributed 143 of 154 jobs — including *"Analist date"* and
*"Angajam Programator Full Stack"* for an "Angular Developer" search.

**Why it matters:** a parameter that's accepted and ignored is worse than one
that doesn't exist. The caller has no way to know. This is also why
`aggregate_scrappers.py` needed that `supports_mode` flag — the flag documents an
inconsistency instead of fixing it.

**How to approach it.** `helpers/relevance.py` already exists and is tested. Both
scrapers need one line at the end of `collect_all_jobs` — the same
`[job for job in jobs if is_relevant(job, title, mode)]` pattern used in the other
two. Then add `--mode` to their argparse, and delete the `supports_mode`
plumbing from the aggregator since it becomes uniform.

**Check:** run the same search with `--mode strict` and `--mode none` and confirm
the bestjobs count actually differs. Right now it won't.

---

## 3. Jooble is orphaned

`jooble_scrapper.py` is 213 lines with real work in it — session bootstrapping,
Cloudflare cookie handling, `trace-id` headers, `maxAllowedPageAmount` respect.
It is referenced from:

- `aggregate_scrappers.py` — **not at all** (its scraper list is linkedin, ejobs,
  bestjobs)
- `unified_scrapper.py` — commented out
- `backend/readme.md` — documented as usable

So the API can never return Jooble results. Either wire it in or move it out;
"exists but unreachable" is the worst of both, because it rots without anyone
noticing.

**How to decide.** The honest question is whether Jooble is worth the Cloudflare
maintenance. Its `_fetch_jobs_page` raises `RuntimeError` on 403 telling you to
pass a manual browser cookie — that's not something an automated API run can do.
If you keep it, it needs to degrade gracefully (return `[]`, log, move on) rather
than raise, because `aggregate_scrappers` would surface that as a failed scraper.

If you drop it, delete it and note why in the readme. Dead code you're keeping
"just in case" is a maintenance tax you pay in confusion later.

**Also:** the same three commented-out blocks in `unified_scrapper.py` (ejobs,
bestjobs, jooble) mean that script only ever queries LinkedIn, despite being
called "unified." Its name is a lie right now.

---

## 4. The `sys.path` hack in every scraper

Four files start with variations of:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.scrappers.helpers.location_normalizer import english_city
```

There is no `__init__.py` anywhere, no `pyproject.toml`, no `setup.py`. The
project works via implicit namespace packages plus manual path surgery.

Symptoms you've already hit: `unittest discover` refused to run until a
`tests/__init__.py` existed, and imports break depending on which directory you
launch from — which is why `api.js` has to pass `cwd: projectRoot` when spawning.

**How to approach it.** Two levels, pick based on appetite:

*Minimal:* add `__init__.py` to `backend/`, `backend/scrappers/`, and
`backend/scrappers/helpers/`, then always invoke as `python -m backend.scrappers.x`
(which the readme already does) and delete the `sys.path` lines. The catch: the
scrapers are *also* invoked as bare scripts by `aggregate_scrappers._run_scraper`
via `sys.executable str(scraper_path)`, which breaks relative imports. You'd need
to switch that to `-m module` form. Note the coupling — this is why the hack is
there.

*Proper:* add a `pyproject.toml` declaring the package, `pip install -e .` into
the venv, and imports work from anywhere with no path manipulation. This is the
skill worth having; every real Python project does it.

**Check:** after either fix, run each scraper from three different working
directories (repo root, `backend/`, `/tmp`) and confirm identical behavior.

### Related: dependencies aren't pinned honestly

`requirements.txt` lists 6 packages, but `beautifulsoup4==4.13.4` has no trailing
newline and `soupsieve` (bs4's own dependency) isn't listed. It's a
hand-maintained list, not a lock file. Consider `pip freeze > requirements.txt`,
or better, split direct dependencies (`requirements.in`) from the resolved lock.
You have zero test/dev dependencies listed — `pytest` isn't installed, which is
why the test suite uses stdlib `unittest`.

---

## 5. There is no scraper contract

Each scraper independently defines `collect_all_jobs(title, location, page_size,
max_pages, mode)` and returns dicts with `id`/`company`/`title`/`location`/`href`.
That's a real interface — but it exists only as a convention, enforced nowhere and
written down nowhere.

Evidence it's already drifting:

| Scraper | Default `page_size` | Honors `mode` | Location form expected |
|---|---|---|---|
| linkedin | 10 (after the fix) | yes | English (`english_city`) |
| ejobs | 40 in CLI / 25 in function | yes | resolved to a city id |
| bestjobs | 24 in CLI / 25 in function | **no** | Romanian (`romanian_city`) |
| jooble | 20 in CLI / 25 in function | **no** | Romanian, with `ș`→`ş` substitution |

Three different location conventions, four different page sizes, two of which
disagree with their own CLI defaults. Adding a fifth source means reading all four
existing ones to infer the rules.

**How to approach it.** This is a design exercise, and the interesting part is
choosing *how much* structure. Options:

1. **A docstring convention** in a `SCRAPERS.md` — zero code, easily ignored.
2. **An abstract base class** (`abc.ABC` with abstract `collect_all_jobs`) —
   enforced at instantiation, teaches Python's ABC machinery, but arguably heavy
   for four functions.
3. **A `Protocol`** (`typing.Protocol`) — structural typing, checked by mypy
   rather than at runtime. Modern, no inheritance required.
4. **A registry + dataclass** — each scraper registers a
   `ScraperSpec(name, fn, location_form, supports_mode)`, and the aggregator reads
   the registry instead of a hardcoded list with a parallel flags tuple.

I'd go with 4, because it directly deletes code you just wrote (the
`supports_mode` boolean threading in `aggregate_scrappers.py`) and it makes the
location-form difference *data* instead of tribal knowledge. Option 3 is a good
companion for type safety.

Also formalize the job dict — a `dataclass` or `TypedDict` for a scraped job would
have made the missing `posted_at` field obvious, and would catch the case where
one scraper forgets `source`.

---

## 6. `bestjobs` parses JSON out of HTML by brace counting

`_fetch_jobs_page` finds the string `"jobListCardsFromServer":` in the page, then
hand-counts `{` and `}` to find the end of the object:

```python
for idx in range(start, len(html)):
    if html[idx] == '{': depth += 1
    elif html[idx] == '}':
        depth -= 1
        if depth == 0: end = idx + 1; break
```

This breaks on any brace inside a string value — a job description containing `}`
shifts the depth count and either truncates or overruns. It happens to work
because Next.js escapes its embedded JSON, but you're depending on an
implementation detail of *their* serializer.

**How to approach it.** Next.js pages carry a `<script id="__NEXT_DATA__"
type="application/json">` element. Parse the HTML, select that script, and
`json.loads` its contents — then walk to the key you want. That's robust against
string contents and much shorter. You already have BeautifulSoup as a dependency.

**Check:** this is where a saved-HTML fixture pays off, exactly like the one in
`backend/tests/fixtures/`. Capture a bestjobs response, commit it, and test the
extraction offline. Then the day they change their markup, your test tells you
instead of your users.

**Also in this file:** `HEADERS` hardcodes `"referer": ".../locuri-de-munca/angular"`
— every request claims to come from an Angular search page regardless of what
you're actually searching. And a hardcoded `cookie` with consent flags. Both work
until they don't; at minimum the referer should be built from the actual query.

---

## 7. Rate limiting is inconsistent across scrapers

You now have solid per-host pacing in `helpers/job_desc_fetcher.py` with a
limiter, circuit breaker, and backoff. The listing scrapers didn't get any of it:

| Scraper | Delay between pages | Retry on failure | 429 handling |
|---|---|---|---|
| linkedin | `random.uniform(1.5, 3.5)` | 3 attempts, backoff | yes |
| ejobs | `time.sleep(1)` | none | none |
| bestjobs | `time.sleep(0.5)` | none | none |
| jooble | `time.sleep(0.5)` | none | none |

Three of four have no retry at all — a single transient network blip raises out of
`collect_all_jobs`, gets caught by `_safe_fetch`, and that source silently
contributes nothing to the search. You'd see a smaller result count and no error.

**How to approach it.** `helpers/rate_limiter.py` is already generic and tested —
`RateLimiter`, `CircuitBreaker`, `backoff_delay`, `parse_retry_after` know nothing
about descriptions. The work is a shared `fetch_with_retry(url, ...)` helper in
`helpers/` that all scrapers use for their HTTP calls, replacing four different
ad-hoc approaches.

The design question worth thinking about: LinkedIn's listing scraper and the
description fetcher both hit `linkedin.com`. Should they *share* a limiter (safer,
they're the same host) or keep separate ones (faster)? Sharing is more correct.
The registry in `job_desc_fetcher.py` is module-level and keyed by host, so
sharing is nearly free — but note it's currently private to that module, so
extracting it is part of the job.

---

## 8. No CI

You have 53 passing Python tests and no automation running them. Every regression
is caught only if you remember to run the suite.

A GitHub Actions workflow that runs the Python tests and the frontend build on
push is ~30 lines. The learning value is understanding that CI is just "run the
commands you'd run locally, on someone else's machine, on a trigger" — it's much
less mysterious than it looks.

Order of value: Python tests (they exist and pass) → frontend build (catches
compile errors) → frontend tests (once any exist) → linting.

**One caveat:** don't put live-network scraper runs in CI. They're slow,
non-deterministic, and hitting LinkedIn from a cloud IP on every push is a
reliable way to get that IP blocked. The fixture-based tests are the ones that
belong there — which is the argument for adding fixtures for the other three
sources too.

---

## 9. Smaller things

**`api.js` `/jobs-mock` reads from disk on every call** — fine, but it's a
`res.json(JSON.parse(data))` with no try/catch, unlike the real `/jobs` handler
which does have one. Malformed mock JSON crashes the request with an unhandled
throw.

**No request logging.** You can't tell what the frontend actually sent when
something misbehaves. `morgan` is one line, or write a 5-line middleware to
understand what it does.

**No error-handling middleware.** Express 5 forwards async errors to a handler if
you define one; without it you get default HTML error pages from a JSON API.

**`count_keywords` in `aggregate_scrappers.py`** (lines 103–118) is dead code —
defined, never called, and it does `job["title"]` unguarded so it would
`KeyError` on any job missing a title. Delete it or use it.

**`_sort_jobs` sorts by source first**, which is why the earlier API response was
all bestjobs at the top. Reasonable default, but once `posted_at` exists, recency
is almost certainly what you want.

**`jobs_response_example.json` is committed** as the mock, but `job-results/` is
gitignored. So the mock and real output can drift with nothing catching it. If the
mock's shape is a contract, a test should assert the real output matches it.
