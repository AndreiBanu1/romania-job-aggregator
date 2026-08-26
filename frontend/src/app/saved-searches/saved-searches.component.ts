import { Component, effect, inject, viewChild } from "@angular/core";
import { MatTableDataSource, MatTableModule } from "@angular/material/table";
import { MatPaginator, MatPaginatorModule } from "@angular/material/paginator";
import { MatSort, MatSortModule } from "@angular/material/sort";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatTooltipModule } from "@angular/material/tooltip";
import { DatePipe } from "@angular/common";
import { Router } from "@angular/router";
import {
  SavedSearch,
  SavedSearchesService,
} from "./saved-searches.service";
import { JobsService } from "../jobs/jobs.service";

@Component({
  selector: "app-saved-searches",
  imports: [
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatIconModule,
    MatButtonModule,
    MatTooltipModule,
    DatePipe,
  ],
  templateUrl: "./saved-searches.component.html",
  styleUrls: ["../shared/data-table.css", "./saved-searches.component.css"],
})
export class SavedSearchesComponent {
  private savedSearchesService = inject(SavedSearchesService);
  private jobsService = inject(JobsService);
  private router = inject(Router);

  searches = this.savedSearchesService.searches;

  dataSource = new MatTableDataSource<SavedSearch>([]);
  displayedColumns = ["title", "city", "date", "actions"];

  paginator = viewChild(MatPaginator);
  sort = viewChild(MatSort);

  constructor() {
    effect(() => {
      this.dataSource.data = this.searches();
    });

    effect(() => {
      const paginator = this.paginator();
      const sort = this.sort();
      if (paginator) this.dataSource.paginator = paginator;
      if (sort) this.dataSource.sort = sort;
    });
  }

  run(search: SavedSearch) {
    // Start the search here, then hand the query to the jobs page in the URL:
    // the results table lives there, and without navigating the scrape would run
    // while the user stares at an unchanged list of saved searches. The page
    // sees the query it is already running and does not start a second one.
    this.jobsService.search(search.title, search.city);
    this.router.navigate(["/"], {
      queryParams: { title: search.title, city: search.city },
    });
  }

  remove(search: SavedSearch) {
    this.savedSearchesService.remove(search);
  }
}
