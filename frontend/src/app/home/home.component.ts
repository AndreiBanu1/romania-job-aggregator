import { Component, OnInit, computed, inject } from "@angular/core";
import { JobsTableComponent } from "../jobs/jobs-table/jobs-table.component";
import { JobsService } from "../jobs/jobs.service";
import { CitiesService } from "../cities.service";
import { FormControl, ReactiveFormsModule, Validators } from "@angular/forms";
import { toSignal } from "@angular/core/rxjs-interop";
import { DatePipe } from "@angular/common";
import { ActivatedRoute, Router } from "@angular/router";

import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatAutocompleteModule } from "@angular/material/autocomplete";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatSnackBar } from "@angular/material/snack-bar";
import { MatTooltipModule } from "@angular/material/tooltip";
import { normalize } from "../../utils/string.utils";
import { SavedSearchesService } from "../saved-searches/saved-searches.service";
import { DemoJobsService, DemoQuery } from "../jobs/demo-jobs.service";
import { environment } from "../../environments/environment";

@Component({
  selector: "app-home",
  imports: [
    JobsTableComponent,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatAutocompleteModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    DatePipe,
  ],
  templateUrl: "./home.component.html",
  styleUrl: "./home.component.css",
})
export class HomeComponent implements OnInit {
  title = "Find Your Job";

  titleControl = new FormControl("", {
    nonNullable: true,
    validators: [Validators.required],
  });

  cityControl = new FormControl("", {
    nonNullable: true,
    validators: [Validators.required],
  });

  private cityQuery = toSignal(this.cityControl.valueChanges, {
    initialValue: "",
  });

  filteredCities = computed(() => {
    const q = normalize(this.cityQuery());
    return this.citiesService.cities().filter((c) => normalize(c).includes(q));
  });

  private demoJobs = inject(DemoJobsService);

  /** Hosted build: there is no API, so say so and offer the covered queries. */
  readonly isDemo = environment.demo;
  demoQueries = this.demoJobs.queries;
  demoGenerated = this.demoJobs.generated;

  constructor(
    private jobsService: JobsService,
    private citiesService: CitiesService,
    private snackBar: MatSnackBar,
    private savedSearchesService: SavedSearchesService,
    private router: Router,
    private route: ActivatedRoute,
  ) {}

  ngOnInit() {
    this.citiesService.getCities();
    if (this.isDemo) this.demoJobs.loadManifest();
    this.restoreQuery();
  }

  /** Runs one of the nightly-scraped queries, which is served verbatim. */
  runDemoQuery(query: DemoQuery) {
    this.titleControl.setValue(query.title);
    this.cityControl.setValue(query.city);
    this.onSearch();
  }

  onSearch() {
    if (this.titleControl.invalid || this.cityControl.invalid) {
      this.titleControl.markAsTouched();
      this.cityControl.markAsTouched();
      return;
    }
    const title = this.titleControl.value;
    const city = this.cityControl.value;
    this.jobsService.search(title, city);
    this.syncUrl(title, city);
  }

  /**
   * Repopulates the form on entering the page, from the URL if it carries a
   * query and otherwise from the search this session already ran — the sidebar
   * link is a bare `/`, so in-app navigation arrives with no params.
   */
  private restoreQuery() {
    const params = this.route.snapshot.queryParamMap;
    const title = params.get("title")?.trim();
    const city = params.get("city")?.trim();
    const last = this.jobsService.lastQuery();

    if (!title || !city) {
      if (!last) return;
      this.titleControl.setValue(last.title);
      this.cityControl.setValue(last.city);
      // Its results are already on screen; only the URL needs catching up.
      this.syncUrl(last.title, last.city);
      return;
    }

    this.titleControl.setValue(title);
    this.cityControl.setValue(city);

    // Returning to this page with its results still in memory: re-running would
    // cost another 15-30s scrape for rows already on screen.
    if (last?.title === title && last?.city === city) return;

    this.jobsService.search(title, city);
  }

  /**
   * Keeps the query in the URL so a reload, bookmark or shared link restores it.
   * Replaced rather than pushed: a history entry per search would let the back
   * button show one query in the form and another's results below it.
   */
  private syncUrl(title: string, city: string) {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { title, city },
      replaceUrl: true,
    });
  }

  onSaveSearch() {
    if (this.titleControl.invalid || this.cityControl.invalid) {
      return;
    }

    this.savedSearchesService.saveSearch(
      this.titleControl.value,
      this.cityControl.value,
    );
    // Show notification
    this.snackBar.open("Search saved successfully!", "Close", {
      duration: 3000,
      horizontalPosition: "end",
      verticalPosition: "bottom",
    });
  }
}
