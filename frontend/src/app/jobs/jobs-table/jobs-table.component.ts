import {
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from "@angular/core";
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
  // Lets an embedded snapshot drop the page-level padding and elevation.
  host: { "[class.embedded]": "isSnapshot()" },
  templateUrl: "./jobs-table.component.html",
  styleUrls: [
    "../../shared/data-table.css",
    "../../shared/expandable-rows.css",
    "./jobs-table.component.css",
  ],
})
export class JobsTableComponent {
  private jobsService = inject(JobsService);
  private savedJobListsService = inject(SavedJobListsService);
  private snackBar = inject(MatSnackBar);

  /**
   * A fixed set of jobs to display. Left unset, the table follows the live
   * search in JobsService; set, it renders that snapshot read-only, without the
   * search states or the save action.
   */
  snapshot = input<Job[] | null>(null);

  /** True when displaying a snapshot rather than the current search. */
  isSnapshot = computed(() => this.snapshot() !== null);

  loading = this.jobsService.loading;
  totalJobsFound = this.jobsService.total_jobs_found;
  sourceSummary = this.jobsService.sources_summary;
  error = this.jobsService.error;
  lastQuery = this.jobsService.lastQuery;

  /** The rows on screen, from whichever source is driving this instance. */
  jobs = computed(() => this.snapshot() ?? this.jobsService.jobs());

  /**
   * Derived from storage rather than held locally, so it survives navigating
   * away and back — the same result set cannot be snapshotted twice.
   */
  listSaved = computed(() => {
    const query = this.lastQuery();
    return this.savedJobListsService.isSaved(
      query?.title ?? "",
      query?.city ?? "",
      this.jobs(),
    );
  });

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
    if (state?.status === "loaded") return state.text;
    // Snapshots may carry the description they were saved with.
    return job.description?.trim() ?? "";
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
    const query = this.lastQuery();
    const result = this.savedJobListsService.saveList(
      query?.title ?? "",
      query?.city ?? "",
      jobs,
    );

    switch (result.status) {
      case "saved":
        this.notify(`${jobs.length} jobs saved — find them under Saved job lists.`);
        break;
      case "quota-exceeded":
        // The write failed, so listSaved() stays false and the button stays live.
        this.notify(
          "Could not save: browser storage is full. Delete a saved job list and try again.",
        );
        break;
      case "empty":
        this.notify("Nothing to save — run a search first.");
        break;
      case "duplicate":
        break;
    }
  }

  private notify(message: string) {
    this.snackBar.open(message, "Close", {
      duration: 5000,
      horizontalPosition: "end",
      verticalPosition: "bottom",
    });
  }
}
