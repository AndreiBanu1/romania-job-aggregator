import { Component, effect, inject, viewChild } from "@angular/core";
import { MatTableDataSource, MatTableModule } from "@angular/material/table";
import { MatPaginator, MatPaginatorModule } from "@angular/material/paginator";
import { MatSort, MatSortModule } from "@angular/material/sort";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatTooltipModule } from "@angular/material/tooltip";
import { DatePipe } from "@angular/common";
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
  styleUrl: "./saved-searches.component.css",
})
export class SavedSearchesComponent {
  private savedSearchesService = inject(SavedSearchesService);
  private jobsService = inject(JobsService);

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
    this.jobsService.search(search.title, search.city);
  }

  remove(search: SavedSearch) {
    this.savedSearchesService.remove(search);
  }
}
