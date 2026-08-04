# Feature ideas beyond the two planned

Product ideas, not code quality. Each has a rough effort estimate, what it teaches,
and — more usefully — what it *depends on*, since several are much cheaper after
saved searches and saved results exist.

Effort scale: **S** = an evening, **M** = a weekend, **L** = multiple sessions.

---

## Highest value for the effort

### Job descriptions in the UI (S) — **done**

This one is implemented; the notes below record how, since the shape matters for
saved results (feature 2 stores descriptions).

The original problem: descriptions were fetched by `unified_scrapper.py` only, at
3,900–9,100 characters each, and nothing reached the frontend — `Job` had no
`description` field, and `aggregate_scrappers.py` (the path `api.js` calls) never
fetched them at all.

What was built:

- `helpers/descriptions.py` — one `fetch_descriptions` shared by both aggregation
  paths, with a `limit` that spreads the budget round-robin across sources.
  Without the round-robin, a limit of 5 spent everything on `bestjobs` (jobs are
  sorted by source) and populated **zero** descriptions.
- `scrappers/fetch_description.py` + `POST /job-description` — one description on
  demand, with a host allow-list so the endpoint can't be used to fetch arbitrary
  URLs.
- Expandable table row that fetches on open, with loading / error / retry states.

**Why on-demand rather than bulk:** pacing is ~1.5s per description per host, so
173 jobs is over four minutes with the request held open. Bulk is opt-in
(`--descriptions --desc-limit N`, exposed as `descriptions: true` on `POST /jobs`)
and the UI uses the single-URL endpoint instead.

**Known limit:** `bestjobs` renders descriptions client-side — 342 kB of HTML
yields 258 characters of text. `_extract_description` returns `""` for it and the
UI says so. Getting those would mean a headless browser. `linkedin` and `ejobs`
both work.

**What it teaches (still worth reading):** rendering untrusted text safely. Today
descriptions come from `get_text()` and are bound with `{{ }}`, which escapes.
The moment you keep the markup you'll meet `DomSanitizer` and the reason
`innerHTML` is dangerous.

### Filter and search within results (S)

You get 154 jobs back for a broad search. The table paginates but can't filter.
`MatTableDataSource` has a built-in `filter` property, so a text box over
title/company is genuinely ~10 lines.

More useful: filter by source (chips you can toggle), exclude keywords ("no
Java"), or hide companies you're not interested in. Client-side, no backend work.

**What it teaches:** the difference between filtering data you have and re-querying.
And that a `filterPredicate` for multi-field filtering is a function you write, not
a config option — which is the moment `MatTableDataSource` stops looking magic.

### Remember the last search (S)

Every page reload loses your query. `localStorage` for the last title/city, restored
on init. Tiny, and removes the most repeated annoyance in daily use.

**What it teaches:** where "state that outlives a session" belongs, and the
question of whether URL query params (`?title=Angular&city=Bucharest`) are better
than `localStorage` — they are, because they make searches shareable and
bookmarkable, and they work with browser back. Doing it with the router is the
better version of this feature.

---

## After saved searches exist

### Scheduled runs (M)

Once you can save a search and re-run it, running it nightly on a schedule is the
obvious next step — and it's the feature that makes this project genuinely useful
rather than a thing you poke at manually.

`node-cron` in the API process, or a system cron calling a CLI. The interesting
part isn't scheduling; it's everything scheduling exposes:

- **Rate limiting matters much more.** An unattended 3 a.m. scrape hitting
  LinkedIn is exactly how you get IP-banned without noticing. The pacing and
  circuit breaker in `job_desc_fetcher.py` become load-bearing rather than polite.
- **Failures need to be visible.** A scheduled run that fails silently for two
  weeks is worse than no scheduling.
- **Overlapping runs.** What if the 3 a.m. run is still going at 4 a.m.?

**What it teaches:** the operational mindset — anything running unattended needs
observability and a kill switch. This is the highest-learning feature on this
list.

**Depends on:** feature 2 (runs table), and honestly on the notification below,
because a scheduled run nobody looks at is pointless.

### Notifications for new jobs (M)

"3 new Angular jobs since yesterday." Needs feature 2's diffing to know what's new.

Delivery options, cheapest first: a badge in the UI (no infrastructure), a local
desktop notification, email via an SMTP service, or a Telegram bot (surprisingly
easy and free — a bot token and one HTTP POST).

**What it teaches:** idempotency. If the notification job runs twice, you must not
send two emails. That means recording *what you've already notified about*, which
is the same read-state problem as the `viewed_at` exercise in feature 2. Meeting
the same idea in a second context is how it sticks.

### Job status tracking (M)

Mark jobs as *interested / applied / rejected / not a fit*. This turns the app from
a search tool into something you'd actually run a job hunt with.

**Depends on:** the `jobs` table from feature 2. Once jobs are durable rows with
stable identity, per-job state is just another column or a small related table.

**What it teaches:** why feature 2's identity decision matters so much. If job
identity is unstable, your "applied" flag attaches to the wrong posting or vanishes
on the next scrape. This is the feature that punishes a sloppy identity model, so
it's a good forcing function.

**Design question worth sitting with:** is status a column on `jobs` or a separate
`job_status` table with a history? History lets you see "applied on the 12th,
rejected on the 20th," which is genuinely useful in a job hunt.

---

## Bigger, and more interesting

### More sources (M each, and never finished)

You have four scrapers and only three are wired in. Obvious Romanian additions:
Hipo.ro, Undelucram.ro, and company career pages directly. Also: LinkedIn's
`f_TPR` parameter filters by post date, and `f_WT=2` filters for remote — neither
is used today.

**Do this only after backend §5** (the scraper contract). Adding a fifth source to
the current setup means reading four files to infer conventions. Adding one to a
registry with a documented contract is a focused exercise. The order matters more
than the feature.

**Honest caveat:** every scraper is a maintenance liability. Sites change markup,
add Cloudflare, and rate-limit. `jooble_scrapper.py` already needs a manual browser
cookie when Cloudflare blocks it, which is unworkable for automation. Four
well-maintained sources beat eight half-broken ones.

### Salary extraction and normalization (L)

None of your scrapers capture salary. Some listings include it, in wildly
inconsistent forms: "3000-4500 RON net", "€45k", "competitive", "по договоренности".

**What it teaches:** the messy-real-data problem, which is the most transferable
skill on this list. You'll need to parse ranges, normalize currencies (with rates
that change), distinguish gross from net (a big deal in Romania), handle monthly vs.
annual, and decide what to do with "competitive."

Start narrow: parse only unambiguous numeric ranges with an explicit currency,
store `salary_min`, `salary_max`, `currency`, `period`, `is_gross`, and leave
everything else null. Resist the urge to guess — a wrong salary is worse than a
missing one, and that principle generalizes far beyond salaries.

### Deduplicate across sources (L)

Currently the same posting on LinkedIn and ejobs is two rows — an explicit decision
in feature 2's identity model. Fixing it properly is fuzzy matching on
title + company + location, which means normalization, similarity scoring
(Levenshtein, token sort ratio), and a threshold you'll tune by hand.

**What it teaches:** entity resolution, and that there's no threshold that's
right — you're trading false merges against false splits, and you have to decide
which error is worse for your use case. (For a job hunt: a false merge hides a
posting, a false split shows a duplicate. The false merge is worse.)

**Worth trying at a small scale first:** take one real result set, hand-label the
true duplicates, then see how your matcher scores. Building the evaluation before
the algorithm is the professional habit, and it's the whole lesson here.

### Market analytics dashboard (M)

`analyze_jobs.py` already computes weighted tech-demand scores — and it's
CLI-only, currently broken (backend §1), and invisible to the UI.

Once results are saved over time you can chart demand trends: "Angular postings in
Bucharest, weekly, over six months." That's a genuinely interesting dataset that
nobody else has, and it's *your* data.

**Depends on:** feature 2, and a meaningful history — this feature is worthless
until you've collected weeks of runs, which is the argument for building scheduled
runs early even if the analytics come much later.

---

## Deliberately not recommending

Worth saying which ideas I'd skip and why, since "no" is information too:

- **User accounts / multi-user.** You are the only user. Auth adds real complexity
  (sessions, password hashing, per-user data isolation on every query) for zero
  current benefit. Note that if you ever *do* deploy publicly, this stops being
  optional and retrofitting it means touching every query.
- **AI/LLM job matching.** Tempting, and it would work. But it obscures the
  learning: you'd be prompt-tuning instead of understanding your data. Build the
  deterministic version first — `analyze_jobs.py` is already a hand-rolled scoring
  system, and understanding *why* it misclassifies things is more valuable than
  outsourcing the judgment.
- **A mobile app.** The web app is responsive-able. A second client doubles the
  surface area for one user on one device.
- **Real-time updates (WebSockets).** Job postings change hourly at most. Polling
  is correct here; see feature 2 milestone 2.2 for the reasoning.

---

## If I had to pick three

1. ~~**Descriptions in the UI**~~ — done, see above.
2. **Scheduled runs + notifications** — this is what turns the project from a demo
   into a tool you'd actually use, and it teaches the most.
3. **Filter within results** — small, immediately useful every single time you
   search.

Everything else can wait for one of them to make it necessary.
