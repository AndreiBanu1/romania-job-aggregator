import { Component, effect, inject, signal, viewChild } from "@angular/core";
import { MatTableDataSource, MatTableModule } from "@angular/material/table";
import { MatPaginator, MatPaginatorModule } from "@angular/material/paginator";
import { MatSort, MatSortModule } from "@angular/material/sort";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatChipsModule } from "@angular/material/chips";
import { MatTooltipModule } from "@angular/material/tooltip";
import { DatePipe } from "@angular/common";
import { SavedJobList, SavedJobListsService } from "./saved-job-lists.service";

@Component({
  selector: "app-saved-job-lists",
  imports: [
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatIconModule,
    MatButtonModule,
    MatChipsModule,
    MatTooltipModule,
    DatePipe,
  ],
  templateUrl: "./saved-job-lists.component.html",
  styleUrl: "./saved-job-lists.component.css",
})
export class SavedJobListsComponent {
  private savedJobListsService = inject(SavedJobListsService);

  lists = this.savedJobListsService.lists;

  dataSource = new MatTableDataSource<SavedJobList>([]);
  displayedColumns = ["expand", "name", "count", "date", "actions"];

  /** id of the open snapshot, or null. One at a time keeps the page short. */
  expandedId = signal<string | null>(null);

  paginator = viewChild(MatPaginator);
  sort = viewChild(MatSort);

  constructor() {
    // Derived columns are not properties, so sorting needs an explicit accessor.
    this.dataSource.sortingDataAccessor = (list, column) => {
      switch (column) {
        case "name":
          return `${list.title} ${list.city}`.toLowerCase();
        case "count":
          return list.jobs.length;
        default:
          return list.date;
      }
    };

    effect(() => {
      // Newest first: the most recent snapshot is the one being looked for.
      this.dataSource.data = [...this.lists()].reverse();
      this.expandedId.set(null);
    });

    effect(() => {
      const paginator = this.paginator();
      const sort = this.sort();
      if (paginator) this.dataSource.paginator = paginator;
      if (sort) this.dataSource.sort = sort;
    });
  }

  /** "Angular developer in Bucharest", falling back when the query is unknown. */
  label(list: SavedJobList): string {
    if (list.title && list.city) return `${list.title} in ${list.city}`;
    return list.title || list.city || "Saved jobs";
  }

  isExpanded(list: SavedJobList): boolean {
    return this.expandedId() === list.id;
  }

  // Arrow property: matRowDef's `when` is called unbound.
  isExpandedRow = (_index: number, list: SavedJobList): boolean =>
    this.isExpanded(list);

  toggle(list: SavedJobList) {
    this.expandedId.set(this.isExpanded(list) ? null : list.id);
  }

  remove(list: SavedJobList) {
    this.savedJobListsService.remove(list);
  }
}
