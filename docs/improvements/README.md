# Codebase analysis: backend & frontend

A review of everything outside the two planned features. Each item states what I
observed, why it matters, and how to approach it — the same learning-guide style
as `docs/features/`, so you write the code.

Everything here was checked against the running code, not inferred from reading.
Where I ran something, the observed output is quoted.

## The documents

| File | Scope |
|---|---|
| [01-backend.md](01-backend.md) | Scrapers, aggregation, API, Python packaging |
| [02-frontend.md](02-frontend.md) | Angular structure, state, accessibility, bundle |
| [03-feature-ideas.md](03-feature-ideas.md) | Product features beyond the two planned |

## Triage: what I'd actually do, in order

Sorted by value-per-effort, not by severity. Full detail in the linked sections.

### Fix now (each under an hour, each currently broken)

| # | Issue | Where |
|---|---|---|
| 1 | `analyze_jobs.py` reports **0 jobs** on real scraper output — key mismatch | [BE §1](01-backend.md#1-the-analysis-tool-is-silently-broken) |
| 2 | `npm test` **fails to compile** — zero spec files exist | [FE §1](02-frontend.md#1-npm-test-does-not-run) |
| 3 | `bestjobs`/`jooble` ignore their `mode` parameter entirely | [BE §2](01-backend.md#2-two-scrapers-accept-mode-and-ignore-it) |
| 4 | `jooble` scraper exists but is wired into nothing | [BE §3](01-backend.md#3-jooble-is-orphaned) |

### Fix soon (half a day each, prevents future pain)

| # | Issue | Where |
|---|---|---|
| 5 | No `__init__.py`, no package config — `sys.path` hacks in 4 files | [BE §4](01-backend.md#4-the-syspath-hack-in-every-scraper) |
| 6 | Scraper contract is implicit; adding a source means reading 3 files | [BE §5](01-backend.md#5-there-is-no-scraper-contract) |
| 7 | Zero accessibility attributes; table is not screen-reader navigable *(partly done: link + toggle labels)* | [FE §2](02-frontend.md#2-accessibility-is-absent) |
| 8 | No error surface anywhere in the UI *(partly done: `JobsService` only)* | [FE §3](02-frontend.md#3-errors-are-invisible-to-the-user) |
| 9 | No linter or formatter config | [FE §6](02-frontend.md#6-no-linter-or-formatter) |

### Worth doing when it starts hurting

`bestjobs` HTML-scraping fragility ([BE §6](01-backend.md#6-bestjobs-parses-json-out-of-html-by-brace-counting)),
bundle size 780 kB ([FE §4](02-frontend.md#4-the-bundle-is-56-over-budget)),
CSS duplication across 743 lines ([FE §5](02-frontend.md#5-743-lines-of-css-with-no-system)),
no CI ([BE §8](01-backend.md#8-no-ci)).

## What's already good

Worth knowing what not to change:

- **The scraper layering.** `linkedin_scrapper.py` separates network / parsing /
  collection with explicit section comments. That structure is why the pagination
  bug was a two-line fix rather than a rewrite.
- **`location_normalizer.py`** is genuinely well-built — canonical keys, alias
  sets, diacritic handling, both English and Romanian display forms, 418 cities.
  It does one thing thoroughly.
- **Graceful degradation.** `_safe_fetch` in `unified_scrapper.py` means one dead
  source doesn't kill a search. Correct instinct.
- **Signals used idiomatically** in the frontend — `computed` for filtered
  cities, `toSignal` for form streams, `viewChild` as signal. This is current
  Angular, not 2019 Angular.
- **`@if`/`@for` control flow** with `track`, and the loading/empty/data states
  in the table template are all handled.

## Method note

I ran the analysis tool, the frontend build, the frontend test command, and the
scrapers; and probed `analyze_jobs.match_keywords` directly. Two claims I want to
flag as *unverified* rather than let them read as tested:

- I did not run `bestjobs` or `jooble` against live sites during this review, so
  their current working state is unknown to me. `jooble` in particular is
  documented in `backend/readme.md` as needing a manual browser cookie when
  Cloudflare blocks it.
- Bundle-size and CSS suggestions are based on reading the files and the build
  output, not on profiling actual runtime performance.
