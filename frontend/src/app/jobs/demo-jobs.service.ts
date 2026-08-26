import { HttpClient } from "@angular/common/http";
import { Injectable, inject, signal } from "@angular/core";
import { Observable, forkJoin, map, of, shareReplay, switchMap } from "rxjs";
import { Job, JobsResponse } from "./jobs.service";
import { normalize } from "../../utils/string.utils";

/** One pre-scraped query, as listed in `demo-data/index.json`. */
export interface DemoQuery {
  title: string;
  city: string;
  /** File name (without extension) of this query's snapshot. */
  slug: string;
  total: number;
  /** When the scrapers last produced this snapshot. */
  scrapedAt: string;
  /** The last refresh returned nothing, so this is the previous good data. */
  stale?: boolean;
}

export interface DemoManifest {
  generated: string;
  queries: DemoQuery[];
}

const DEMO_BASE = "/demo-data";

/**
 * Backend stand-in for the hosted build. GitHub Actions runs the Python
 * scrapers on a schedule and commits their output under `public/demo-data/`;
 * this reads those files.
 *
 * A query the workflow already covers is served verbatim, so what a visitor
 * sees is exactly what the scrapers produced. Anything else falls back to
 * filtering the whole snapshot corpus client-side, which keeps the search box
 * usable rather than answering only a fixed menu of queries.
 */
@Injectable({ providedIn: "root" })
export class DemoJobsService {
  private http = inject(HttpClient);

  /** Populated once the manifest loads; drives the suggestions on the search page. */
  queries = signal<DemoQuery[]>([]);
  generated = signal<string | null>(null);

  // shareReplay: the manifest and corpus are immutable per deploy, so every
  // search after the first reuses them instead of re-downloading.
  private manifest$?: Observable<DemoManifest>;
  private corpus$?: Observable<Job[]>;

  loadManifest(): Observable<DemoManifest> {
    if (!this.manifest$) {
      this.manifest$ = this.http
        .get<DemoManifest>(`${DEMO_BASE}/index.json`)
        .pipe(shareReplay({ bufferSize: 1, refCount: false }));

      this.manifest$.subscribe({
        next: (manifest) => {
          this.queries.set(manifest.queries);
          this.generated.set(manifest.generated);
        },
        // The search itself surfaces the failure; the suggestions just stay empty.
        error: () => {},
      });
    }
    return this.manifest$;
  }

  search(title: string, city: string): Observable<JobsResponse> {
    return this.loadManifest().pipe(
      switchMap((manifest) => {
        const exact = manifest.queries.find(
          (query) =>
            normalize(query.title) === normalize(title) &&
            normalize(query.city) === normalize(city),
        );

        return exact
          ? this.snapshot(exact.slug)
          : this.filterCorpus(manifest, title, city);
      }),
    );
  }

  private snapshot(slug: string): Observable<JobsResponse> {
    return this.http.get<JobsResponse>(`${DEMO_BASE}/${slug}.json`);
  }

  private filterCorpus(
    manifest: DemoManifest,
    title: string,
    city: string,
  ): Observable<JobsResponse> {
    return this.corpus(manifest).pipe(
      map((jobs) => {
        const tokens = normalize(title).split(/\s+/).filter(Boolean);
        const wantedCity = normalize(city);

        const matched = jobs.filter((job) => {
          if (!normalize(job.location).includes(wantedCity)) return false;
          // Every word must appear somewhere in the row, the way a table filter
          // behaves: "angular developer" must not match every ".NET developer".
          const haystack = normalize(`${job.title} ${job.company}`);
          return tokens.every((token) => haystack.includes(token));
        });

        return {
          total_jobs_found: matched.length,
          sources_summary: this.summarize(matched),
          jobs: matched,
        };
      }),
    );
  }

  private corpus(manifest: DemoManifest): Observable<Job[]> {
    if (!this.corpus$) {
      const slugs = manifest.queries.map((query) => query.slug);
      this.corpus$ = (
        slugs.length
          ? forkJoin(slugs.map((slug) => this.snapshot(slug)))
          : of([] as JobsResponse[])
      ).pipe(
        map((responses) => this.dedupe(responses.flatMap((r) => r.jobs))),
        shareReplay({ bufferSize: 1, refCount: false }),
      );
    }
    return this.corpus$;
  }

  /** Snapshots overlap (the same job shows up under several queries). */
  private dedupe(jobs: Job[]): Job[] {
    const byHref = new Map<string, Job>();
    for (const job of jobs) {
      const key = job.href || `${job.title}|${job.company}|${job.location}`;
      // Keep the first copy, unless a later one carries a description.
      const existing = byHref.get(key);
      if (!existing || (!existing.description && job.description)) {
        byHref.set(key, job);
      }
    }
    return [...byHref.values()];
  }

  private summarize(jobs: Job[]): Record<string, number> {
    const summary: Record<string, number> = {};
    for (const job of jobs) {
      const source = job.source?.trim().toLowerCase() || "unknown";
      summary[source] = (summary[source] ?? 0) + 1;
    }
    return summary;
  }
}
