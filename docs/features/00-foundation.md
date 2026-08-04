# Foundation: storage, config, and the shell both features need

Neither feature is hard. What makes them feel hard is that the project has no
place to put durable state and no second page to put a UI on. Build that first,
in small pieces, so features 1 and 2 are about *their own* logic.

Budget: one session. Nothing here is user-visible, which is exactly why it's
tempting to skip and then regret.

---

## Milestone 0.1 — Choose and wire up storage

### Decide: what stores the data?

| Option | Why you'd pick it | Why you wouldn't |
|---|---|---|
| **SQLite** (recommended) | One file, no daemon, real SQL and constraints, ships with Node via `better-sqlite3`. Teaches schema design, which is the transferable skill here. | Slightly more setup than JSON. |
| JSON files | Zero setup, you already read/write JSON. | No constraints, no atomic writes, no queries. You'd hand-roll "find the run for this search" as a `.filter()`. Concurrent writes corrupt it — and you *already* hit this class of bug with the shared temp file. |
| Postgres | Realistic for production. | A daemon to run and a connection pool to manage for a single-user learning app. Save it for when you deploy. |

Go with SQLite. The reason isn't "it's easier" — it's that feature 2 needs a
`UNIQUE(source, external_id)` constraint and a join, and the moment you write
those by hand over JSON arrays you're writing a bad database instead of learning
a good one.

```
cd backend && npm install better-sqlite3
```

`better-sqlite3` is synchronous. That sounds wrong for Node, but for a local
single-user app it's *simpler* and genuinely fast — no `await` on every query, no
callback nesting. Know that this is a deliberate tradeoff you're making, not an
oversight: under real concurrent load you'd want the async driver.

### Decide: how does the schema get created?

You need the tables to exist on a fresh clone. Options, in increasing order of
ceremony: a `schema.sql` run at boot with `CREATE TABLE IF NOT EXISTS`; a
hand-rolled migration runner with a `schema_version` table; a library like
`node-pg-migrate`.

For learning, do the middle one — but only when you hit your first schema
*change*. Start with `CREATE TABLE IF NOT EXISTS` in a `schema.sql`, and when
feature 2 forces you to add a column, feel the pain of "how do I apply this to my
existing database?" and *then* write the migration runner. Inventing migrations
before you need them teaches nothing; inventing them the moment you have data you
don't want to lose teaches everything.

### Build

```
backend/
  db/
    index.js        # opens the database, exports the connection
    schema.sql      # CREATE TABLE IF NOT EXISTS statements
```

`db/index.js` needs to: resolve a path for the file (`backend/data/app.db` — add
`backend/data/` to `.gitignore`), open it, run the schema, and enable two pragmas
most tutorials forget:

```js
db.pragma('journal_mode = WAL')   // readers don't block the writer
db.pragma('foreign_keys = ON')    // OFF by default in SQLite - your FKs are
                                  // decorative without this
```

That second one matters. SQLite silently ignores foreign key constraints unless
you turn them on per connection. If you skip it, the `ON DELETE CASCADE` you
write in feature 2 will do nothing and you'll be confused about orphaned rows.

### Check

Write a throwaway script that opens the db, inserts a row into a scratch table,
closes, reopens, and reads it back. You're verifying the file persists and the
path resolves the same way regardless of the working directory you launch from —
which is a real hazard here, since `api.js` uses `cwd: projectRoot` when it
spawns Python.

---

## Milestone 0.2 — Split the API before it needs splitting

`api.js` is at the size where adding endpoints is still comfortable and *will
stop being* around endpoint six. Both features add several.

### Decide: how much structure?

Don't build a full layered architecture for a learning app — you'll spend the
session on folders. Do the one split that pays for itself immediately:

```
backend/
  api.js               # app setup, middleware, mounts routers, starts listening
  routes/
    jobs.js            # existing /jobs, /jobs-mock, /cities
    saved-searches.js  # feature 1
    runs.js            # feature 2
```

The rule to internalize: **a route handler should validate input, call something
that does the work, and shape the response.** When a handler starts containing
business logic — deciding what counts as a duplicate, diffing two runs — that
logic wants to move to a plain module you can unit test without HTTP. You'll feel
this acutely in milestone 2.3.

### Decide: validation

You're hand-writing `typeof title !== 'string'` checks in `/jobs` right now. That
was fine for two fields. With saved searches you'll have create and update bodies,
optional fields, and enums (`mode` must be one of three values).

Either keep hand-writing them in a small shared `validate.js`, or add `zod`.
I'd add `zod` — one dependency, and it teaches you schema-as-value, which is the
same idea you'll meet in typed API clients and form validation. But hand-rolling
first and *then* replacing it is a legitimately better lesson if you have the
patience.

Whichever you pick, put validation at the edge and let everything inward assume
clean data. Mixed validation — some in the handler, some in the service, some in
SQL — is how you end up with three inconsistent rules for what a valid title is.

### Check

`curl` every existing endpoint after the split and confirm identical responses.
This is a refactor; behavior must not change. If you have no test, that `curl`
comparison *is* your test — save the outputs to files before and after and `diff`
them.

---

## Milestone 0.3 — Capture the two fields you can't backfill

Do this before you save a single job. Explained in the [README](README.md), but
concretely:

**Posting date.** In `extract_jobs_from_html`
(`backend/scrappers/linkedin_scrapper.py`), the card contains:

```html
<time class="job-search-card__listdate" datetime="2026-07-23">6 days ago</time>
```

Select it, read the `datetime` attribute (not the text — "6 days ago" is relative
to when you scraped), and add it to the dict as `posted_at`. All 10 cards in the
committed fixture carry `class="job-search-card__listdate"`, but LinkedIn also
serves a `job-search-card__listdate--new` variant for recent postings, so select
on `time[datetime]` rather than the class to catch both.

Cards without a date should get `None`, not today's date — absent and "posted
today" are different facts, and conflating them will quietly corrupt your
recency sorting.

**Canonical URL.** Build `https://www.linkedin.com/jobs/view/<id>` from the id you
already extract. Keep the raw `href` too if you like, but the canonical form is
what identity and dedup should use.

### Decide: where does normalization live?

You could canonicalize in the scraper, in the aggregator's `_dedupe_jobs`, or at
the point of DB insert. Pick one and be consistent. My argument for the scraper:
it's the only layer that knows LinkedIn's URL structure, and putting
site-specific knowledge anywhere else spreads it. The aggregator should be able
to treat all sources uniformly — that's its job.

### Check

`backend/tests/test_linkedin_scrapper.py` already parses a committed HTML
fixture. Extend `test_every_job_has_the_core_fields_populated` to assert
`posted_at` parses as a date and `canonical_url` matches
`https://www.linkedin.com/jobs/view/<digits>`. The fixture is real captured HTML,
so if your selector is wrong the test tells you immediately — no network needed.

Then add a test that two hrefs for the same job id — differing only in
`?position=1` vs `?position=7` — produce the same canonical URL. That's the
dedup bug in test form.

### Exercise

`_dedupe_jobs` in `aggregate_scrappers.py` keys on the full href. Change it to
key on `(source, external_id)` and predict, before you run it, whether your job
counts go up or down. Then run a real search and see. Explain the direction of
the change to yourself — if it surprised you, your model of the data was wrong
somewhere, and that's worth chasing.

---

## Milestone 0.4 — Frontend shell

### Build

Three small things, none of which need a backend:

1. **Routes.** `app.routes.ts` is `[]`. Add routes for the search page, saved
   searches, and (later) a run detail page. Use `loadComponent` for lazy loading
   — it's the current idiom and costs nothing to learn now.
2. **Move the layout.** `app.component.html` currently *is* the search page:
   navbar, search bar, and table all inline. Extract the search page into its own
   component so `AppComponent` holds only the shell (navbar + `<router-outlet />`).
3. **Kill the hardcoded URLs.** `JobsService` and `CitiesService` both hardcode
   `http://localhost:3000`. Move it to `environment.ts` and inject it, or define
   an `API_BASE` token. You'll add several more endpoints; three files with the
   same literal is where the bug that costs you an hour lives.

Also: `left-navbar.component.html` uses `href="#"`. Those need to become
`routerLink` or they'll do a full page reload and blow away your app state.

### Decide: signals or observables for the new services?

`JobsService` already uses signals holding state (`jobs`, `loading`,
`total_jobs_found`) with `.subscribe()` inside the service. That's a reasonable
pattern and you should stay consistent with it rather than mixing paradigms.

But notice what it costs: the service swallows errors (`error: () => { this.loading.set(false) }`
— the error is discarded entirely, so the UI can't distinguish "no jobs found"
from "the backend is down"). As you add features, decide deliberately whether
each service exposes an error signal, and make the UI show it. "Nothing happened
when I clicked" is the worst failure mode you can ship to yourself.

### Check

Navigate between routes with the network tab open. Confirm no full page reloads
(the nav bar shouldn't flash) and that route changes don't re-fetch cities every
time — if they do, you've put the fetch in the wrong lifecycle spot.

---

## Where you are now

Storage that persists, an API you can grow, scrapers capturing the fields you'll
need, and a frontend with more than one page. None of it is a feature, all of it
is load-bearing.

Next: [01-saved-searches.md](01-saved-searches.md).
