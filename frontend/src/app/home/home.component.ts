import { Component, OnInit, computed } from "@angular/core";
import { JobsTableComponent } from "../jobs/jobs-table/jobs-table.component";
import { JobsService } from "../jobs/jobs.service";
import { CitiesService } from "../cities.service";
import { FormControl, ReactiveFormsModule, Validators } from "@angular/forms";
import { toSignal } from "@angular/core/rxjs-interop";

import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatAutocompleteModule } from "@angular/material/autocomplete";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatSnackBar } from "@angular/material/snack-bar";
import { MatTooltipModule } from "@angular/material/tooltip";
import { normalize } from "../../utils/string.utils";
import { SavedSearchesService } from "../saved-searches/saved-searches.service";

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

  constructor(
    private jobsService: JobsService,
    private citiesService: CitiesService,
    private snackBar: MatSnackBar,
    private savedSearchesService: SavedSearchesService,
  ) {}

  ngOnInit() {
    this.citiesService.getCities();
  }

  onSearch() {
    if (this.titleControl.invalid || this.cityControl.invalid) {
      this.titleControl.markAsTouched();
      this.cityControl.markAsTouched();
      return;
    }
    this.jobsService.search(this.titleControl.value, this.cityControl.value);
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
