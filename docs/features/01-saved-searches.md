# Feature 1: saving search criteria

Goal: save "Angular Developer / Bucharest" and re-run it with one click. Store
*only the criteria*, not results — results are feature 2.

This is a small feature deliberately. Use it to build the full vertical slice
once, cleanly, so feature 2 is only about its own hard parts.

---

## Milestone 1.1 — Schema

### Decide: what is a "search criteria," exactly?

Before writing SQL, list the fields. Your search currently sends `title`, `city`,
and `mode`. So:

```sql
CREATE TABLE IF NOT EXISTS saved_searches (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT,                        -- optional user label
  title       TEXT    NOT NULL,
  city        TEXT    NOT NULL,
  mode        TEXT    NOT NULL DEFAULT 'loose',
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  last_run_at TEXT
);
```

Four things in there are worth arguing about, and the arguing is the point:

**Is `mode` part of the criteria?** It changes which jobs come back, so yes — the
same title and city with `strict` vs `loose` are genuinely different searches. If
you left it out, re-running a saved search couldn't reproduce its own results.

**Should `name` be required?** Requiring it means a dialog every time you save,
which is friction on the main action. Making it optional means you need a display
fallback (`"Angular Developer in Bucharest"`, derived). I'd make it optional and
derive the label — but decide where that derivation lives, because if both the
backend and the frontend do it, they'll drift.

**Why `TEXT` for timestamps?** SQLite has no date type. `datetime('now')` gives
you `'2026-07-30 14:22:01'` in UTC, which sorts lexicographically — that's the
property you want. Storing a Unix integer also works. Storing a localized string
does not; it won't sort and you'll regret it.

**Why `mode TEXT` and not an enum?** SQLite has no enums. If you want the
database to enforce it, add `CHECK (mode IN ('strict','loose','none'))`. Do it —
this is the cheap version of the lesson that constraints in the schema outlive
validation in the application. Your API validates `mode` today; a script you
write in three months won't.

### Decide: what makes two saved searches "the same"?

If you save "Angular Developer / Bucharest" twice, should there be two rows?

Almost certainly not — but "the same" needs defining. Is `angular developer`
the same as `Angular Developer`? Is `Bucuresti` the same as `Bucharest`? You
already have machinery for the second question:
`backend/scrappers/helpers/location_normalizer.py` maps 418 cities and handles
diacritics, and `english_city('Bucuresti')` returns `'Bucharest'`.

Options:

1. **`UNIQUE(title, city, mode)`** — simple, but case- and diacritic-sensitive, so
   "angular" and "Angular" both get rows.
2. **Store a normalized key alongside the display values**, and make *that*
   unique. Two extra columns (`title_key`, `city_key`), lowercase and
   diacritic-stripped, computed on write.
3. **Check for duplicates in application code** before inserting.

Option 2 is the right instinct and the reason is worth internalizing: option 3
has a race — two requests can both check, both find nothing, and both insert. A
unique index makes the database enforce it and you handle the constraint error.
The general lesson is that *"check then act" in application code is not a
constraint*, it's a suggestion.

Note the asymmetry you're building: you keep what the user typed (for display) and
what it means (for identity). That pattern shows up constantly — emails,
usernames, tags.

### Build

Add the table to `schema.sql`. Add the unique index. Decide whether normalization
happens in JS or by calling into the Python normalizer, and notice the tension:
the good city data lives in Python, but the API that needs it is Node. You could
shell out (slow, and you just removed one `exec` for good reasons), reimplement
diacritic stripping in JS (duplicated logic, will drift), or read
`romanian_cities.json` from Node and do simple normalization there (the file is
already loaded by `api.js` for `/cities`).

I'd do the third and accept that JS-side normalization is simpler than the Python
version. Write down why you chose what you chose — this is the kind of decision
that looks arbitrary later.

### Check

Write the test first, in `backend/tests/` if you go Python-side or a new JS test
if not:

- Saving identical criteria twice yields one row.
- Saving with different case/diacritics (`"angular developer"` / `"Bucuresti"`)
  also yields one row.
- Saving with a different `mode` yields *two* rows.
- Inserting an invalid `mode` fails at the database level.

That last one is you verifying the `CHECK` constraint actually fires, which is
the sort of thing everyone assumes and nobody tests.

---

## Milestone 1.2 — API

### Build

```
GET    /saved-searches        list all
POST   /saved-searches        create
DELETE /saved-searches/:id    remove
PATCH  /saved-searches/:id    rename (optional)
```

### Decide: what does POST return on a duplicate?

You have a unique constraint, so a duplicate insert throws. Now choose:

- **409 Conflict** — honest, but the frontend has to handle an error for something
  the user won't consider an error.
- **200 with the existing row** (idempotent create) — clicking Save twice is
  harmless and returns the same thing.
- **`INSERT … ON CONFLICT DO UPDATE`** (upsert) — returns the row either way.

For a save button, idempotent is the kinder design. But understand the tradeoff
you're making: the client can no longer tell "created" from "already existed."
If the UI wants to say "Saved!" vs "Already saved," you need to distinguish them —
either via status code (201 vs 200) or a flag in the body. Pick based on the UI
you actually want, not on abstract correctness.

### Decide: is `last_run_at` this feature's job?

The column is in the schema but nothing sets it yet, because "running" a saved
search is milestone 1.4. Resist the urge to wire it up now. Notice, though, that
it's a hint about feature 2: the moment you want *more* than a single timestamp
per search — a history — you need a separate table. That's exactly the `runs`
table, and you'll build it having felt why.

### Check

`curl` each endpoint. Specifically test the ugly cases, because they're the ones
that break in production:

```bash
# missing fields
curl -s -X POST localhost:3000/saved-searches -H 'Content-Type: application/json' -d '{}'
# invalid mode
curl -s -X POST localhost:3000/saved-searches -H 'Content-Type: application/json' \
  -d '{"title":"Angular","city":"Bucharest","mode":"banana"}'
# duplicate
# (run the same valid POST twice, compare the two responses)
# nonexistent id
curl -s -X DELETE localhost:3000/saved-searches/99999 -o /dev/null -w '%{http_code}\n'
```

That last one has a real answer worth thinking about: is deleting something that
doesn't exist a 404 or a 204? Both are defensible. DELETE is supposed to be
idempotent, which argues for 204.

---

## Milestone 1.3 — UI

### Build

A saved-searches page at the route you added, plus a save affordance on the search
page. `left-navbar.component.html` already has a "Saved searches" link waiting.

Pieces:

- `SavedSearchesService` — mirror the existing `JobsService` shape (signals for
  state) so the codebase stays coherent. Unlike `JobsService`, give it an error
  signal.
- A save button next to the existing Search button in `app.component.html`.
- A list view: each row shows the label, criteria, `last_run_at`, and buttons for
  Run and Delete.

### Decide: where does the list state live?

If the page component owns the array, navigating away and back re-fetches. If the
service owns it (as a signal), the list survives navigation but can go stale
relative to the database.

The existing code puts state in services, so follow that. But now you own a cache
invalidation problem: after `POST /saved-searches`, the list signal must update.
Two ways — re-fetch the list, or optimistically push the new row into the signal.

Try the optimistic version, then deliberately break it: make the backend reject
the save and watch the row appear and then need removing. Now you understand why
optimistic updates need rollback, and why many apps just re-fetch. That's a
five-minute experiment that teaches something no amount of reading will.

### Decide: how much confirmation for Delete?

A `MatDialog` confirm is the reflex. Consider instead a snackbar with Undo —
fewer clicks in the common case, recoverable in the rare one. It requires either
soft deletes (`deleted_at` column) or holding the row in memory until the
snackbar dismisses. Try the snackbar; it's the better pattern and you'll learn
`MatSnackBar` with an action.

### Check

Manually: save, reload the page (state must survive — you now have a database),
delete, reload again. Then stop the backend and click Save. What does the user
see? If the answer is "nothing," fix it — that's the `JobsService` error-swallowing
flaw repeating itself, and catching it in your own new code is the whole point of
having noticed it earlier.

---

## Milestone 1.4 — Re-running a saved search

The payoff. Clicking Run on a saved search should populate the jobs table.

### Decide: does the frontend or the backend do the re-run?

**Frontend**: read the saved criteria, call the existing `POST /jobs` with them.
Zero new backend code. But `last_run_at` doesn't get updated unless you add
another call, and the criteria round-trip through the client, which can mangle
them.

**Backend**: `POST /saved-searches/:id/run` looks up the criteria server-side,
runs the scrape, updates `last_run_at`, returns the jobs. One call, and the
server is the authority on what the criteria are.

Take the backend route. The reasoning generalizes: when an action needs to update
state *and* return data, doing it in one server-side operation avoids a partial
failure where the scrape succeeds but the timestamp update doesn't. You're
learning to notice multi-step operations that want to be atomic.

This endpoint is also the seed of feature 2 — it's `runs` with no history yet.

### Check

Save a search, click Run, confirm the table populates and `last_run_at` updates.
Then time it. You'll see ~9 seconds minimum, longer with deep pagination. Sit
with that number: the HTTP request is open the entire time, there's no progress
indication beyond a spinner, and if the user navigates away the work is wasted.

Feature 2 has to solve this. You've now felt why.

### Exercise

Add a "Run all saved searches" button. It will immediately raise questions this
guide didn't answer: do they run in parallel or sequence? What if one fails
halfway? What does the UI show while five searches are in flight? What happens to
the shared rate limiter in `job_desc_fetcher.py` when several scrapes overlap?

That last one is real — the limiter is keyed per host with a module-level
registry, so concurrent scrapes *share* pacing. Reason about whether that's
correct before you test it, then test it.

---

Next: [02-saved-results.md](02-saved-results.md).
