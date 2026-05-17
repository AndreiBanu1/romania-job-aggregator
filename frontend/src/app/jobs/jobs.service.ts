import { Injectable, signal } from "@angular/core";
import { HttpClient } from "@angular/common/http";

export interface Job {
  title: string;
  company: string;
  location: string;
  href: string;
  source: string;
}

export interface JobsResponse {
  total_jobs_found: number;
  sources_summary: Record<string, number>;
  jobs: Job[];
}

@Injectable({
  providedIn: "root",
})
export class JobsService {
  jobs = signal<Job[]>([]);
  loading = signal(false);
  total_jobs_found = signal(0);
  sources_summary = signal<Record<string, number>>({});

  constructor(private http: HttpClient) {}

  //TODO: Change the endpoint to the real one when ready, and adjust the request/response format if needed
  search(title: string, city: string) {
    this.loading.set(true);
    this.http
      .post<JobsResponse>("http://localhost:3000/jobs-mock", { title, city })
      .subscribe({
        next: (response) => {
          this.jobs.set(response.jobs);
          this.total_jobs_found.set(response.total_jobs_found);
          this.sources_summary.set(response.sources_summary);
          this.loading.set(false);
        },
        error: () => {
          this.loading.set(false);
        },
      });
  }
}
