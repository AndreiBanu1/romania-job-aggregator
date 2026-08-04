# Frontend improvements

Angular 21 with Material 21, signals used well, standalone components. The
foundations are current and correct — most of what follows is about things that
don't exist yet rather than things done wrong.

---

## 1. `npm test` does not run

```
$ npx ng test --watch=false
✘ [ERROR] TS18003: No inputs were found in config file 'tsconfig.spec.json'.
  Specified 'include' paths were '["src/**/*.spec.ts","src/**/*.d.ts"]'
Application bundle generation failed.
```

Zero spec files exist, so the test config has nothing to compile and the command
fails rather than reporting "0 tests." Meanwhile the backend has 53 passing tests.

**Why it matters:** you have a two-tier project where one half is tested and the
other has a broken test command. The asymmetry compounds — as the frontend grows,
each new component makes the first test harder to write.

**How to approach it.** Don't try to test everything. Write **one** test to unblock
the command, then add tests where logic (not markup) lives. The best first
candidate is `AppComponent.normalize()` plus the `filteredCities` computed — pure
logic, no HTTP, no template:

- `normalize("București")` should equal `normalize("bucuresti")`
- typing `"bucur"` should surface `"București"` in `filteredCities()`
- an empty query should return all cities

That's testable with `TestBed` and no HTTP mocking at all. Then, when you have the
services from feature 1, learn `HttpTestingController` — service tests with faked
responses are where the real value is, and they'd have caught the swallowed-error
problem in §3.

**Worth knowing:** `angular.json` configures the `@angular/build:karma` builder
with `zone.js/testing`, so you're on Karma/Jasmine — write `describe`/`it`/`expect`
specs, not Vitest ones. Angular also supports Vitest now if you'd rather switch,
but don't mix the two.

---

## 2. Accessibility is absent

```
$ grep -rn 'aria-' frontend/src/app/ | wc -l
0
```

Zero ARIA attributes across all four templates. Concrete consequences:

- **The results table** has `mat-sort-header` on four columns but no
  `aria-sort` state and no `<caption>` or `aria-label` on the table. A screen
  reader user can't tell what the table contains or how it's sorted.
- **The "View" links** in the href column read as "View, link" — repeated 25
  times, with no indication of *which* job. This is the single worst one; the link
  text needs the job title, via `aria-label` or visually-hidden text.
  *Fixed* — they now read "Open {title} on {source}", and the new expand toggles
  carry `aria-label` + `aria-expanded`. The rest of this list is still open.
- **The `mat-icon` elements** (`search`, `inbox`, `open_in_new`) are announced as
  their ligature text. Decorative icons need `aria-hidden="true"`.
- **The loading spinner** doesn't announce. A screen reader user clicks Search and
  gets silence; the state region wants `role="status"` / `aria-live="polite"`.
- **`left-navbar.component.html`** uses a bare `<div class="navbar">` with an
  `<h2>` and a `<ul>` — it should be `<nav>`, which gives free landmark
  navigation.

**How to approach it.** Angular Material handles a lot of this for you *if* you
give it labels — `matInput` inside `mat-form-field` with `mat-label` already
produces correct labelling, which you've done. The gap is everything you built by
hand.

Practical order: run Chrome DevTools Lighthouse for the automated pass (it catches
the icon and link-text issues), then tab through the page with a keyboard only,
then try VoiceOver (Cmd+F5 on macOS) on the results table. The keyboard pass takes
two minutes and will find things Lighthouse can't — like whether focus is visible
on the sort headers.

**The thing worth internalizing:** semantic HTML plus real labels gets you most of
the way; ARIA is for the gaps. Reaching for `aria-*` first usually means the markup
is wrong.

---

## 3. Errors are invisible to the user

> **Partly fixed.** Level 1 below is done for `JobsService` — it now has an
> `error` signal and the table renders a fourth branch for it, verified by
> stopping the API and searching (*"Cannot reach the API. Is it running?"*).
> Levels 2 and 3, and `cities.service.ts`, are still open. The original finding
> is kept below because the reasoning is the point.

`jobs.service.ts:41`:

```ts
error: () => {
  this.loading.set(false);
},
```

The error object isn't even bound. Every failure — backend down, scraper crash,
network drop, malformed JSON — produces exactly the same UI as a successful search
with no results: *"No results yet. Try a search above."*

`cities.service.ts` is worse — `subscribe()` with only a next handler, so a
failure to load cities leaves the autocomplete permanently empty with no
indication why.

**Why it matters:** you will hit this constantly in development. The API takes
~9 seconds; when it fails you'll be guessing whether the search found nothing or
the backend died. You already have a real example: `/jobs` was broken for a while
(system `python3` lacking `bs4`), which is presumably why the service still points
at `/jobs-mock`.

**How to approach it.** Three levels, and I'd do all three eventually:

1. **An `error` signal per service**, set in the error callback, rendered in the
   template as a distinct state alongside loading/empty/data. The table template
   already has that three-state structure — add a fourth branch.
2. **An `HttpInterceptor`** for cross-cutting concerns: log, and translate HTTP
   status into a user-facing message once instead of per-service. This is the
   idiomatic Angular answer and worth learning.
3. **Distinguish "empty" from "not yet searched."** Right now `jobs().length === 0`
   means both "you haven't searched" and "your search matched nothing" — different
   messages. A `hasSearched` signal fixes it.

**Check:** stop the backend, click Search, and confirm you see an actionable
message. That's the acceptance test for this entire item.

---

## 4. The bundle is 56% over budget

```
Initial chunk files | Names     | Raw size  | Transfer size
main-NHO4F2EW.js    | main      | 719.52 kB | 151.57 kB
                    | Initial   | 779.59 kB | 166.38 kB
▲ WARNING bundle initial exceeded maximum budget.
  Budget 500.00 kB was not met by 279.58 kB
```

For a two-view app with one table, 719 kB of JS is a lot. The cause is almost
certainly Angular Material: `AppComponent` imports six Material modules and
`JobsTableComponent` imports seven, all eagerly in the initial bundle.

**How to approach it.** The single biggest win is what foundation milestone 0.4
already asks for: **lazy-load routes with `loadComponent`.** Material modules used
only by the saved-searches page then land in that page's chunk instead of `main`.
Right now everything is in one route, so there's nothing to split — this becomes
actionable exactly when you add the second page.

Second: run `ng build --stats-json` and view it in a bundle analyzer to see where
the weight actually is, rather than guessing. That's the transferable skill;
"measure before optimizing" applies here as much as anywhere.

**Honest framing:** 166 kB transfer for a localhost learning app affects nothing
you'll notice. Treat this as a "learn the tooling" item, not a performance
emergency. The budget warning is Angular telling you the *trend* is wrong, not
that the app is slow.

The second warning — `jobs-table.component.css` at 4.35 kB over a 4 kB budget —
points at the same thing as §5.

---

## 5. 743 lines of CSS with no system

```
332  frontend/src/styles.css
259  frontend/src/app/jobs/jobs-table/jobs-table.component.css
 99  frontend/src/app/app.component.css
 53  frontend/src/app/left-navbar/left-navbar.component.css
```

For four components that's a lot, and the recent commits (`More css`,
`Added Angular Material and styling`) suggest it's grown by accretion.

**Two questions worth asking of it.** First, is `styles.css` at 332 lines global
styling or component styling that leaked out? Global should be resets, typography,
design tokens, and Material theme overrides — anything targeting a specific
component's internals belongs with that component or is a sign the component needs
a variant.

Second, colors are repeated as literals — `#ffffff` appears 3 times, `#eef2ff` and
`#94a3b8` twice each, alongside a spread of one-off near-whites (`#fbfbfd`,
`#f6f7fb`, `#f5f3ff`). That's the argument for CSS custom properties in `:root`,
and you already have `material-theme.scss`, so there's a theming system
half-present to build on. The near-white spread is the tell: those are probably
meant to be the same two or three surface colors.

**How to approach it.** Don't refactor CSS for its own sake; do it the next time
you need to change a color and find yourself editing three files. That's the
signal. When you do, custom properties are the smallest change with the biggest
payoff, and they set you up for a dark mode later.

**One thing you got right:** zero uses of `::ng-deep` in the whole codebase. It's
the deprecated escape hatch for piercing Material's internals and the usual reason
Material upgrades break styling. Keep it that way — when you need to restyle a
Material component, reach for its theming API instead.

---

## 6. No linter or formatter

No ESLint config, no Prettier config anywhere in `frontend/`. The code *looks*
consistently formatted (double quotes, trailing commas, 2-space indent), which
suggests you have editor-level Prettier — but it's not in the repo, so it isn't
enforced and isn't reproducible.

**How to approach it.** `ng add @angular-eslint/schematics` wires up ESLint with
Angular-aware rules in one command. Add Prettier separately with a
`.prettierrc` committed so the formatting is a project decision rather than a
per-machine one.

The rules that actually catch bugs in Angular: `@angular-eslint/no-empty-lifecycle-method`,
`@typescript-eslint/no-unused-vars`, and the template rules for accessibility
(`@angular-eslint/template/accessibility-*`) — that last set would have flagged
most of §2 automatically.

**One caveat:** adding a linter to an existing codebase produces a wall of
warnings and the temptation to fix them all in one commit. Better: add it, set the
existing violations to `warn`, and fix them as you touch files. A 200-file
mechanical commit is unreviewable even when it's yours.

---

## 7. Component structure will not survive feature 1

`AppComponent` is currently doing four jobs: app shell, layout, search form, and
cities autocomplete logic. `app.component.html` contains the navbar, the header,
the entire search bar, and the table.

Foundation milestone 0.4 covers the split, but two specifics worth naming:

**`JobsTableComponent` is hard-wired to `JobsService`:**

```ts
jobs = this.jobsService.jobs;
totalJobsFound = this.jobsService.total_jobs_found;
```

It can only ever display the current live search. Feature 2 needs it to display a
saved run. Converting those to `input()` signals makes it reusable and is a good
lesson in why presentational components shouldn't reach for global state.

**There's a stray `console.log` in an effect** (`jobs-table.component.ts:43`)
inside the effect that syncs `dataSource.data`. Beyond being debug output, it
means the effect has two unrelated jobs. Worth noticing that effects should do one
thing — it makes their dependencies obvious.

**Naming inconsistency:** the `Job` interface uses `snake_case` for
`total_jobs_found` and `sources_summary` (mirroring the Python API) but camelCase
elsewhere. Pick one for the TypeScript layer — conventionally camelCase — and
translate at the HTTP boundary. Otherwise the convention is "whatever the backend
happened to send," which gets confusing when two endpoints disagree.

---

## 8. `Job` is missing fields the backend already sends

```ts
export interface Job {
  title: string; company: string; location: string;
  href: string; source: string;
}
```

The backend sends `id` for every job, and after foundation milestone 0.3 it'll
send `posted_at` and a canonical URL too. The interface silently drops them.

**Why it matters now:** no `id` means no stable key for rows. `MatTableDataSource`
doesn't need one, but the moment you add row selection, a save-this-job button, or
diff highlighting, you need identity — and you'll be reaching for `href` as a
substitute, which is exactly the tracking-parameter bug from the backend review
resurfacing in the UI.

**The deeper point:** a hand-written interface can't tell you it's out of date. It
compiles fine while being wrong. Options: generate types from the API (OpenAPI
schema → types), or validate responses at runtime with `zod` and derive the type
from the schema. The second is more practical here and catches backend changes at
runtime instead of never.

---

## 9. Smaller things

**Cities are fetched on `AppComponent.ngOnInit`.** Once there's routing, the shell
may not remount, so this happens to work — but consider whether cities belong in a
service with caching, so navigating back doesn't re-request. Related: nothing
handles the fetch failing (see §3).

**`provideZoneChangeDetection({ eventCoalescing: true })`** — with signals
throughout, you're a candidate for `provideExperimentalZonelessChangeDetection()`.
Worth trying once tests exist, since zoneless changes test semantics.

**The search button is disabled while invalid** (`[disabled]="titleControl.invalid || cityControl.invalid"`),
*and* `onSearch()` re-checks and calls `markAsTouched()`. The `markAsTouched` path
is now unreachable via the button. Not a bug — defensive, and it'd matter if
Enter-to-submit were added (which it should be; the form isn't keyboard-submittable
right now).

**No `<form>` element.** The search bar is inputs and a button in a div, so
pressing Enter does nothing. Wrapping in a `<form (ngSubmit)="onSearch()">` gives
you Enter-to-search for free and is better semantics.

**`index.html` still has `<title>Frontend</title>`** and the default Angular
favicon. Sixty seconds to change, and it's what shows in the browser tab and
bookmarks every time you use the app.
