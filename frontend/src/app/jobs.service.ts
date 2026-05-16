import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface Job {
  title: string;
  company: string;
  location: string;
  href: string;
  source: string;
}

export interface JobsResponse {
    total_jobs_found: number;
    source_summary: Record<string, number>;
    jobs: Job[];
}

@Injectable({
  providedIn: 'root'
})
export class JobsService {
    jobs = signal<Job[]>([]);
    loading = signal(false);
  
    constructor(private http: HttpClient) {}

    search(title: string, city: string) {
        this.loading.set(true);
        this.http
            .post<JobsResponse>("http://localhost:3000/jobs", { title, city })
            .subscribe({
                next: (response) => {
                    this.jobs.set(response.jobs);
                    this.loading.set(false);
                },
                error: () => {
                    this.loading.set(false);
                }
            });
    }

}