import { Component, effect, inject, signal, viewChild } from "@angular/core";
import { JobsService } from "../jobs.service";
import { MatTableDataSource, MatTableModule } from "@angular/material/table";
import { MatPaginator, MatPaginatorModule } from "@angular/material/paginator";
import { MatSort, MatSortModule } from "@angular/material/sort";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatIconModule } from "@angular/material/icon";
import { MatChipsModule } from "@angular/material/chips";
import { MatButtonModule } from "@angular/material/button";
import { Job } from "../jobs.service";
import { KeyValuePipe } from "@angular/common";

@Component({
  selector: "app-jobs-table",
  imports: [
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatProgressSpinnerModule,
    MatIconModule,
    MatChipsModule,
    MatButtonModule,
    KeyValuePipe,
  ],
  templateUrl: "./jobs-table.component.html",
  styleUrl: "./jobs-table.component.css",
})
export class JobsTableComponent {
  private jobsService = inject(JobsService);

  loading = this.jobsService.loading;
  jobs = this.jobsService.jobs;
  totalJobsFound = this.jobsService.total_jobs_found;
  sourceSummary = this.jobsService.sources_summary;
  error = this.jobsService.error;

  dataSource = new MatTableDataSource<Job>([]);
  displayedColumns = ["expand", "title", "company", "location", "source", "href"];

  /** href of the open row, or null. One at a time keeps fetches serialised. */
  expandedHref = signal<string | null>(null);

  paginator = viewChild(MatPaginator);
  sort = viewChild(MatSort);

  constructor() {
    effect(() => {
      this.dataSource.data = this.jobs();
      // A new result set invalidates whichever row was open.
      this.expandedHref.set(null);
    });

    effect(() => {
      const paginator = this.paginator();
      const sort = this.sort();
      if (paginator) this.dataSource.paginator = paginator;
      if (sort) this.dataSource.sort = sort;
    });
  }

  isExpanded(job: Job): boolean {
    return this.expandedHref() === job.href;
  }

  // Arrow property: matRowDef's `when` is called unbound.
  isExpandedRow = (_index: number, job: Job): boolean => this.isExpanded(job);

  toggle(job: Job) {
    if (this.isExpanded(job)) {
      this.expandedHref.set(null);
      return;
    }
    this.expandedHref.set(job.href);
    this.jobsService.loadDescription(job);
  }

  // Narrow the union here rather than in the template: the template type
  // checker does not narrow a discriminated union across an @else if chain.
  isDescriptionLoading(job: Job): boolean {
    return this.jobsService.descriptionFor(job)?.status === "loading";
  }

  descriptionText(job: Job): string {
    const state = this.jobsService.descriptionFor(job);
    return state?.status === "loaded" ? state.text : "";
  }

  descriptionError(job: Job): string | null {
    const state = this.jobsService.descriptionFor(job);
    return state?.status === "error" ? state.message : null;
  }

  retry(job: Job) {
    this.jobsService.loadDescription(job);
  }
}
