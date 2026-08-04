# Feature guides: saved searches & saved results

These are **learning guides, not specs to hand to an implementer.** They describe
the decisions, the order to work in, and how to check yourself. The code is
yours to write — where you see a snippet, it's a shape to react to, not something
to paste.

## The two features

1. **Saved search criteria** — store "Angular Developer / Bucharest" so you can
   re-run it with one click. Small feature, and the natural place to learn the
   full stack slice: schema → API → service → component.
2. **Saved search results** — store the *jobs a run returned*, so you can look at
   last Tuesday's results and see what's new since. Substantially harder, and
   the interesting part isn't storage, it's identity and time.

Read them in order. Feature 2 assumes the storage layer and routing you build in
feature 1.

| Guide | What you'll build | Hardest idea |
|---|---|---|
| [00-foundation.md](00-foundation.md) | SQLite layer, config, routing shell | Where state belongs |
| [01-saved-searches.md](01-saved-searches.md) | CRUD for search criteria | Duplicate criteria |
| [02-saved-results.md](02-saved-results.md) | Runs, job identity, diffing | Job vs. sighting |

For everything *outside* these two features — code-quality findings across the
backend and frontend, plus other feature ideas — see
[../improvements/](../improvements/README.md). A few items there are worth doing
first; they're called out in its triage table.

## Where you're starting from

Worth being honest about the current state, since both features push on its
weak points:

- **No persistence at all.** The backend writes a temp JSON file per request and
  deletes it. There is no database, no migration story, nothing that survives a
  restart. Feature 1 introduces the first durable state in the project.
- **`backend/api.js` is 100 lines with three endpoints** and no router split, no
  validation layer beyond hand-written `if` checks, no error middleware. It will
  not stay readable if you add eight endpoints to it as-is.
- **The frontend has one route** — `app.routes.ts` is literally `[]`, and
  `left-navbar.component.html` already links to "Saved job lists" and "Saved
  searches" with `href="#"`. You planned this; the nav is waiting for it.
- **`JobsService` has `localhost:3000` hardcoded** — it now posts to the real
  `/jobs` (toggle `USE_LIVE_SEARCH` for the mock) and `Job` has `id` and
  `description`, but the base URL still belongs in an environment file.
- **A search takes ~9 seconds** through the API in the best case, and minutes
  when several scrapers page deeply. The request is held open the whole time.
  Feature 2 makes this untenable and forces the async question.

## How to use these guides

Each guide is split into **milestones**. A milestone is a stopping point where
something works end to end and you could commit. Inside each you'll find:

- **Decide** — a real choice, with the tradeoff and my recommendation. Don't
  skip these; they're the part that transfers to other projects.
- **Build** — what to write, with signatures or schema but not bodies.
- **Check** — how to know it works, usually a `curl` or a test to write.
- **Exercise** — an extension to do on your own, no solution given.

Two rules that will make this worth more than reading a tutorial:

1. **Write the check before the code** where you can. You have a working
   `unittest` setup in `backend/tests/` (53 tests, run with
   `.venv/bin/python -m unittest discover -s backend/tests -t .`). Feature 1 has
   an obvious first test: "saving the same criteria twice doesn't create two
   rows."
2. **When a guide says "decide," write your answer down** in a comment or a
   commit message before you build. Then see if you still agree afterwards.
   That gap is the lesson.

## Suggested sequencing

Feature 1 is roughly an evening if you already know Angular forms. Feature 2 is
several sessions, and milestone 2.3 (diffing) is where most of the learning is.

```
Foundation ──> 1.1 schema ──> 1.2 API ──> 1.3 UI ──> 1.4 re-run
                                                       │
                                                       ▼
               2.1 runs table ──> 2.2 async runs ──> 2.3 diffing ──> 2.4 UI
```

Don't start feature 2 until re-running a saved search works. The re-run button
is what makes the runs table obviously necessary, and building it in that order
means you'll feel the need before you write the schema.

## One thing to fix before either feature

`extract_jobs_from_html` in `backend/scrappers/linkedin_scrapper.py` currently
drops two fields you will want and cannot backfill later:

- **`<time class="job-search-card__listdate" datetime="2026-07-23">`** — the
  posting date is right there in the HTML and gets thrown away. Without it,
  saved results can't be sorted by recency or aged out.
- **Canonical URL.** Stored `href` values carry
  `?position=1&pageNum=0&refId=…&trackingId=…`. Since `_dedupe_jobs` keys on the
  full lowercased href, the same job seen at two list positions survives
  deduplication as two rows.

Adding these is ~10 lines and there's already a fixture-based test file to
extend (`backend/tests/test_linkedin_scrapper.py`). Do it first — every job you
save before then is missing data you'll wish you had. See "Milestone 0.3" in the
foundation guide.
