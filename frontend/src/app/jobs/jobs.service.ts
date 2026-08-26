import { Injectable, signal } from "@angular/core";
import { HttpClient } from "@angular/common/http";

export interface Job {
  id?: string;
  title: string;
  company: string;
  location: string;
  href: string;
  source: string;
  description?: string;
}

export interface JobsResponse {
  total_jobs_found: number;
  sources_summary: Record<string, number>;
  jobs: Job[];
}

export interface JobDescriptionResponse {
  url: string;
  description: string;
}

export type DescriptionState =
  | { status: "loading" }
  | { status: "loaded"; text: string }
  | { status: "error"; message: string };

const API_BASE = "http://localhost:3000";

/**
 * Flip to false to hit the mock endpoint instead of running real scrapers.
 * The real search takes ~15-30s; the mock returns instantly.
 */
const USE_LIVE_SEARCH = false;

@Injectable({
  providedIn: "root",
})
export class JobsService {
  jobs = signal<Job[]>([]);
  loading = signal(false);
  total_jobs_found = signal(0);
  sources_summary = signal<Record<string, number>>({});
  error = signal<string | null>(null);

  lastQuery = signal<{ title: string; city: string } | null>(null);

  descriptions = signal<Record<string, DescriptionState>>({});

  constructor(private http: HttpClient) {}

  search(title: string, city: string) {
    this.loading.set(true);
    this.error.set(null);
    this.descriptions.set({});
    this.lastQuery.set({ title, city });
    const endpoint = USE_LIVE_SEARCH ? "/jobs" : "/jobs-mock";
    this.http
      .post<JobsResponse>(`${API_BASE}${endpoint}`, { title, city })
      .subscribe({
        next: (response) => {
          this.jobs.set(response.jobs);
          this.total_jobs_found.set(response.total_jobs_found);
          this.sources_summary.set(response.sources_summary);
          this.seedDescriptions(response.jobs);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(this.messageFor(err));
          this.loading.set(false);
        },
      });
  }

  descriptionFor(job: Job): DescriptionState | undefined {
    return this.descriptions()[job.href];
  }

  loadDescription(job: Job) {
    if (!job.href) return;

    const existing = this.descriptions()[job.href];
    if (existing?.status === "loading" || existing?.status === "loaded") return;

    this.setDescription(job.href, { status: "loading" });

    this.http
      .post<JobDescriptionResponse>(`${API_BASE}/job-description`, {
        href: job.href,
      })
      .subscribe({
        next: (response) => {
          const text = (response.description ?? "").trim();
          this.setDescription(
            job.href,
            text
              ? { status: "loaded", text }
              : {
                  status: "error",
                  message:
                    "No description found — the source may have blocked us or the posting is gone.",
                },
          );
        },
        error: (err) => {
          this.setDescription(job.href, {
            status: "error",
            message: this.messageFor(err),
          });
        },
      });
  }

  private seedDescriptions(jobs: Job[]) {
    const seeded: Record<string, DescriptionState> = {};
    for (const job of jobs) {
      const text = job.description?.trim();
      if (job.href && text) seeded[job.href] = { status: "loaded", text };
    }
    if (Object.keys(seeded).length) {
      this.descriptions.update((current) => ({ ...current, ...seeded }));
    }
  }

  private setDescription(href: string, state: DescriptionState) {
    this.descriptions.update((current) => ({ ...current, [href]: state }));
  }

  private messageFor(err: unknown): string {
    const error = err as { error?: { error?: string }; status?: number };
    if (error?.error?.error) return error.error.error;
    if (error?.status === 0) return "Cannot reach the API. Is it running?";
    return "Something went wrong. Please try again.";
  }
}
