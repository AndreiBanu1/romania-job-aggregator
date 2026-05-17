import { Component, effect, inject, viewChild } from "@angular/core";
import { JobsService } from "../jobs.service";
import { MatTableDataSource, MatTableModule } from "@angular/material/table";
import { MatPaginator, MatPaginatorModule } from "@angular/material/paginator";
import { MatSort, MatSortModule } from "@angular/material/sort";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatIconModule } from "@angular/material/icon";
import { MatChipsModule } from "@angular/material/chips";
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

  dataSource = new MatTableDataSource<Job>([]);
  displayedColumns = ["title", "company", "location", "source", "href"];

  paginator = viewChild(MatPaginator);
  sort = viewChild(MatSort);

  constructor() {
    effect(() => {
      this.dataSource.data = this.jobs();
      console.log(this.sourceSummary());
    });

    effect(() => {
      const paginator = this.paginator();
      const sort = this.sort();
      if (paginator) this.dataSource.paginator = paginator;
      if (sort) this.dataSource.sort = sort;
    });
  }
}
