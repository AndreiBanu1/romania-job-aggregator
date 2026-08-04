# Feature 2: saving search results

Goal: store the jobs a search returned, so you can revisit last Tuesday's results
and see what's new since.

This is the harder feature, and the difficulty is not storage. It's **identity**
(when are two scraped rows the same job?) and **time** (a job exists over a
period, a run happens at an instant). Storage is the easy part; get identity
wrong and everything built on top is subtly wrong.

Prerequisite: feature 1 works, including re-run.

---

## Milestone 2.1 — Model runs and jobs

### Decide: one table or three?

The tempting design is one table: every scraped job row gets inserted with a
`run_id`. It works, it's one insert, and it's wrong in a way worth understanding.

Say a job is open for three weeks and you run the search daily. One table gives
you 21 near-identical rows. Now answer these:

- "Show every job I've ever seen" → needs `DISTINCT` over fuzzy columns.
- "How long has this posting been open?" → `MIN`/`MAX` over duplicates.
- "Did this job's title change?" → you can't tell a retitled job from a new one.

The fix is separating **the job** (a posting that exists in the world) from **the
sighting** (this run saw it). Three tables:

```sql
CREATE TABLE IF NOT EXISTS runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  saved_search_id INTEGER REFERENCES saved_searches(id) ON DELETE SET NULL,
  title           TEXT NOT NULL,        -- snapshot of criteria as run
  city            TEXT NOT NULL,
  mode            TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending',
  started_at      TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at     TEXT,
  total_found     INTEGER,
  error           TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source        TEXT NOT NULL,
  external_id   TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  title         TEXT NOT NULL,
  company       TEXT,
  location      TEXT,
  posted_at     TEXT,
  description   TEXT,
  first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen_at  TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS run_jobs (
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  PRIMARY KEY (run_id, job_id)
);
```

`run_jobs` is a join table, and it's the piece that makes "what's new since
Tuesday" a query instead of a script.

### Decide: why snapshot the criteria onto `runs`?

`runs` duplicates `title`/`city`/`mode` from `saved_searches`. That looks like bad
normalization. It's deliberate: if you later edit a saved search from "Angular" to
"React," every historical run would appear to have been a React search. **A
historical record must capture what actually happened, not point at something
mutable.** Same reason invoices copy the price instead of joining to the product.

This also lets ad-hoc searches (no saved search) create runs — hence
`ON DELETE SET NULL` rather than `CASCADE`: deleting a saved search shouldn't
delete its history.

### Decide: what is a job's identity?

The crux. `UNIQUE(source, external_id)` above is a claim: a job is identified by
its source and that source's id. Consequences:

- The same posting on LinkedIn and ejobs = **two rows.** Cross-site identity needs
  fuzzy matching on title+company+location, which is a genuinely hard problem.
  Don't take it on now — but know you've decided not to.
- If LinkedIn recycles ids or the id extraction is wrong, unrelated jobs collide.
  `_extract_job_id_from_href` uses the regex `-(\d+)(?:\?|$)`, so its correctness
  is load-bearing for your entire schema now.

Now the harder question: **on re-seeing a job, do you update it?** The title or
description may have changed. Options:

1. **Ignore changes** — keep first-seen values. Simple; you silently hold stale data.
2. **Overwrite** — always latest. Simple; you lose history of the change.
3. **Version rows** (`job_versions` table) — full history, notably more complexity.

Start with 2 (overwrite, plus bump `last_seen_at`), because it's honest about the
present and cheap. But write a comment saying why, and know that option 3 is what
you'd need to answer "did this company quietly drop the salary?"

Note that overwriting has a subtle cost: an "overwrite" of `description` with
`""` when a fetch failed would *destroy* good data. Guard that — only overwrite
with non-empty values. This kind of thing is why the decision deserves thought
rather than a reflex `INSERT OR REPLACE`.

### Build

Add the three tables. Then write the insert path as a **transaction**: create the
run, upsert each job, insert the `run_jobs` links, update the run's status. If it
fails halfway you want no partial run, and `better-sqlite3`'s `db.transaction()`
gives you that.

`INSERT … ON CONFLICT(source, external_id) DO UPDATE SET …` is the upsert you
want. Look up `excluded.` — it's how you reference the would-be-inserted values
in the update clause, and it's the non-obvious bit of upsert syntax.

### Check

Tests worth writing, because they encode the decisions above:

- Two runs seeing the same job → 1 row in `jobs`, 2 in `run_jobs`.
- `first_seen_at` doesn't change on re-sighting; `last_seen_at` does.
- A failed description fetch doesn't blank an existing description.
- Deleting a run deletes its `run_jobs` but leaves `jobs` intact.
- Deleting a saved search leaves its runs with `saved_search_id IS NULL`.

That fourth test only passes if you enabled `foreign_keys = ON` (milestone 0.1).
If it fails, you've just proved to yourself why that pragma matters.

---

## Milestone 2.2 — Make runs asynchronous

You measured it in feature 1: a search takes ~9 seconds minimum and minutes at
worst, with the HTTP request held open the whole time. Once runs are saved, that
design breaks — a saved-search refresh becomes a multi-minute hanging request.

### Decide: how async?

| Approach | Complexity | What it teaches |
|---|---|---|
| **Return `run_id`, client polls** (recommended) | Low | The core async-job pattern; works everywhere |
| Server-Sent Events | Medium | Streaming progress, one-way push |
| WebSockets | High | Overkill for one-directional status |
| Job queue (BullMQ + Redis) | High | Real infra, but Redis for a single-user app is a lot |

Do polling. The shape:

```
POST /runs                 → 202 Accepted, { run_id, status: 'pending' }
GET  /runs/:id             → { status, total_found, started_at, finished_at, error }
GET  /runs/:id/jobs        → the jobs, once status is 'done'
GET  /saved-searches/:id/runs → history for a saved search
```

202 rather than 200 is the correct status for "accepted, not finished," and using
it deliberately is a small piece of HTTP literacy worth having.

### Decide: what runs the work?

The Python scrape is already a child process. So: return the `run_id` immediately,
keep the `spawn`ed process running, and write results when it exits.

The thing to think hard about is **failure**. If the Node process restarts
mid-scrape, you have a run stuck in `pending` forever. Options: mark stale
`pending` runs as `failed` on boot; store the child PID and check liveness; add a
timeout that kills long-running scrapes.

Do the first — it's five lines at startup and it teaches the general principle:
**any state machine with a non-terminal state needs a recovery path for
processes that die in it.** Most people learn this from a production incident.

Also decide on concurrency: what if a run is triggered while one is in flight for
the same saved search? Refusing (409, "already running") is simplest and usually
right. Allowing it means two scrapes competing for the same rate limiter — worth
reasoning through against `job_desc_fetcher.py`'s per-host module-level registry.

### Build

Keep the existing synchronous `POST /jobs` working while you build this. Being
able to compare old and new paths is worth the small duplication, and you can
delete it once `/runs` is trusted.

### Check

Start a run, immediately `GET /runs/:id` and confirm `pending`. Poll until `done`.
Confirm `finished_at` and `total_found` populate. Then kill the Node process
mid-scrape, restart it, and confirm the stuck run gets marked `failed` rather than
sitting in `pending`.

Finally, make the scrape fail on purpose (unplug the network, or point a scraper
at a bad host) and confirm `status='failed'` with something useful in `error`.
A run that fails silently is worse than one that crashes loudly.

---

## Milestone 2.3 — Diffing runs

The feature that makes saved results worth having, and the best learning in these
guides. Everything so far exists to enable this query.

### Decide: what does "new" mean?

Three plausible definitions, and they disagree:

1. **New to this run** — in run N, not in run N−1. Simple set difference on
   `run_jobs`.
2. **Never seen before in this saved search** — not in *any* prior run of it.
   Different from (1): a job that vanishes from page 2 and comes back looks new
   under (1) but not (2).
3. **Recently posted** — `posted_at` within the last N days, independent of runs.

These answer different questions. (1) is "what changed since I last looked," (2)
is "what have I not evaluated yet," (3) is "what's fresh on the market." (2) is
usually what a job seeker wants. Pick one, name it precisely in the code, and
don't let the meaning drift between backend and UI.

Note that (1) and (2) both depend on your scraper being *stable*. Recall the real
throttling you can hit: one aggregate run collected 10 LinkedIn jobs where a
direct run minutes earlier got 26. Under definition (1), the next run would report
16 jobs as "new" when nothing changed in the world. **Your diff is only as
trustworthy as your collection is complete** — which is why the pagination fix
mattered and why partial runs deserve a flag on the `runs` row.

Consider recording whether a run completed fully or was cut short (blocked,
`max_pages` hit) and excluding incomplete runs from diffs. That's a design insight
most tutorials would skip.

### Build

Start with SQL, not JavaScript. The set difference is a query:

```sql
-- jobs in run :current that were not in run :previous
SELECT j.*
FROM run_jobs rj
JOIN jobs j ON j.id = rj.job_id
WHERE rj.run_id = :current
  AND rj.job_id NOT IN (SELECT job_id FROM run_jobs WHERE run_id = :previous);
```

Then write the "never seen before in this saved search" variant, which needs a
join through `runs` to filter by `saved_search_id` and a date bound. Doing both
teaches you how much cheaper this is in SQL than in application code — and the
version where you fetch both arrays into Node and `filter` is the one to *not*
write, though writing it once to feel the difference is legitimate.

Add the reverse too: jobs in the previous run but not the current one
("disappeared" — likely filled or expired). Same query, arguments swapped. The
symmetry is satisfying and it's genuinely useful information.

### Decide: where does the comparison live?

Once you have SQL for it, the "which two runs do we compare?" logic still needs a
home. That's business logic — put it in a plain module (`db/diff.js` or
`services/runs.js`) that takes ids and returns data, with no `req`/`res` anywhere
near it. Then it's unit testable with a fixture database and no HTTP.

This is the payoff of the milestone 0.2 rule: handlers validate and shape,
modules decide. You'll feel the difference when you write the test.

### Check

Construct the situation deliberately rather than waiting for it:

1. Insert two runs by hand with known overlapping job sets.
2. Assert the diff returns exactly the jobs you expect, in both directions.
3. Include the edge cases: comparing a run to itself (empty diff), the very first
   run (everything is new — or is it an error? decide), an empty run.

Doing this with hand-built fixtures rather than live scrapes is the professional
habit here. Live data is slow, non-deterministic, and can't reproduce the edge
cases you most need to test.

### Exercise

"What's new since I last looked" is subtly different from all three definitions
above — it depends on when *you* last viewed, not when the last run happened. Add
a `viewed_at` or per-job `seen` flag and see how it changes the model. This is
read-state tracking, the same problem email clients and RSS readers solve, and it
generalizes further than anything else in this guide.

---

## Milestone 2.4 — UI

### Build

- **Run history** for a saved search: date, count, status, "12 new" badge.
- **Run detail**: the jobs table you already have, reading a run instead of a live
  search. `JobsTableComponent` reads `JobsService` signals directly
  (`jobs = this.jobsService.jobs`), so it can't currently display anything else.
  Refactor it to take an input instead — this is the good kind of pressure that
  reveals over-coupled components.
- **Polling** while a run is pending, with progress feedback.

### Decide: how to poll without leaking

Naive `setInterval` in a component keeps firing after navigation. Options:
`interval()` + `switchMap` + `takeUntilDestroyed()`, or `resource()`/`httpResource`
in current Angular, or manual `setTimeout` with cleanup in `ngOnDestroy`.

Use the RxJS version with `takeUntilDestroyed()` — you're already using
`toSignal` in `AppComponent`, so the interop is familiar, and unsubscription
hygiene is worth internalizing.

Then decide on backoff: polling every 500ms for a five-minute scrape is 600
pointless requests. Poll fast initially and slow down. You wrote
`backoff_delay()` in `rate_limiter.py` already — same idea, different direction.
Recognizing a pattern you've implemented before in a new context is the sign it
actually landed.

### Decide: what "12 new" links to

A badge implies a destination. Filtered run detail? Separate diff view? Highlighted
rows in the full list? Highlighting in context is usually the most useful — you see
what's new *and* what it sits among — and it's the one that needs no new route.

### Check

Trigger a run from the UI, watch it go pending → done with the table populating.
Navigate away mid-run and confirm in the network tab that polling **stops**. Come
back and confirm it either resumes or shows the finished result. Then check the
first-ever run of a search renders sensibly with no prior run to diff against —
the empty state you designed in 2.3.

---

## What you'll have learned

Worth naming explicitly, since these outlast the project:

- **Entity vs. event.** `jobs` and `run_jobs` are the same distinction as
  products vs. order lines, users vs. sessions.
- **Snapshot vs. reference.** Historical records copy; live views join.
- **Identity is a decision, not a fact.** You chose `(source, external_id)` and
  accepted specific consequences.
- **Constraints in the schema beat checks in the code.** They can't be bypassed by
  the next script you write.
- **Long operations need a state machine, and every non-terminal state needs a
  recovery path.**
- **Derived data is only as good as its inputs.** A diff over incomplete scrapes
  reports fiction confidently.

## Deliberately out of scope

So you know these are choices, not oversights: cross-source job identity
(fuzzy matching), full change history for jobs, multi-user accounts and auth,
scheduled/cron runs, notifications, and full-text search over descriptions. Each
is a reasonable next project. Scheduled runs are the most natural follow-on —
and would immediately make the rate limiting in `job_desc_fetcher.py` matter far
more, since unattended scrapes are exactly how you get IP-banned without
noticing.
