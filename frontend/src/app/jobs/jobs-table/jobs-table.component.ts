import { Component, effect, inject, signal, viewChild } from "@angular/core";
import { JobsService } from "../jobs.service";
import { MatTableDataSource, MatTableModule } from "@angular/material/table";
import { MatPaginator, MatPaginatorModule } from "@angular/material/paginator";
import { MatSort, MatSortModule } from "@angular/material/sort";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatIconModule } from "@angular/material/icon";
import { MatChipsModule } from "@angular/material/chips";
import { MatButtonModule } from "@angular/material/button";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatSnackBar } from "@angular/material/snack-bar";
import { Job } from "../jobs.service";
import { KeyValuePipe } from "@angular/common";
import { SavedJobListsService } from "../../saved-job-lists/saved-job-lists.service";

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
    MatTooltipModule,
    KeyValuePipe,
  ],
  templateUrl: "./jobs-table.component.html",
  styleUrl: "./jobs-table.component.css",
})
export class JobsTableComponent {
  private jobsService = inject(JobsService);
  private savedJobListsService = inject(SavedJobListsService);
  private snackBar = inject(MatSnackBar);

  loading = this.jobsService.loading;
  jobs = this.jobsService.jobs;
  totalJobsFound = this.jobsService.total_jobs_found;
  sourceSummary = this.jobsService.sources_summary;
  error = this.jobsService.error;
  lastQuery = this.jobsService.lastQuery;

  listSaved = signal(false);

  dataSource = new MatTableDataSource<Job>([]);
  displayedColumns = [
    "expand",
    "title",
    "company",
    "location",
    "source",
    "href",
  ];

  expandedHref = signal<string | null>(null);

  paginator = viewChild(MatPaginator);
  sort = viewChild(MatSort);

  constructor() {
    effect(() => {
      this.dataSource.data = this.jobs();
      this.expandedHref.set(null);
      this.listSaved.set(false);
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

  isExpandedRow = (_index: number, job: Job): boolean => this.isExpanded(job);

  toggle(job: Job) {
    if (this.isExpanded(job)) {
      this.expandedHref.set(null);
      return;
    }
    this.expandedHref.set(job.href);
    this.jobsService.loadDescription(job);
  }

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

  onSaveJobsList() {
    const jobs = this.jobs();
    if (!jobs.length || this.listSaved()) return;

    const query = this.lastQuery();
    this.savedJobListsService.saveList(
      query?.title ?? "",
      query?.city ?? "",
      jobs,
    );
    this.listSaved.set(true);

    this.snackBar.open(
      `${jobs.length} jobs saved — find them under Saved job lists.`,
      "Close",
      {
        duration: 3000,
        horizontalPosition: "end",
        verticalPosition: "bottom",
      },
    );
  }
}
