import { Component, OnInit, signal, computed, effect } from "@angular/core";
import { JobsTableComponent } from "./jobs/jobs-table/jobs-table.component";
import { JobsService } from "./jobs/jobs.service";
import { CitiesService } from "./cities.service";
import { FormControl, ReactiveFormsModule, Validators } from "@angular/forms";
import { toSignal } from "@angular/core/rxjs-interop";

import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatAutocompleteModule } from "@angular/material/autocomplete";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { LeftNavbarComponent } from "./left-navbar/left-navbar.component";

@Component({
  selector: "app-root",
  imports: [
    JobsTableComponent,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatAutocompleteModule,
    MatButtonModule,
    MatIconModule,
    LeftNavbarComponent,
  ],
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
export class AppComponent implements OnInit {
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
    const q = this.normalize(this.cityQuery());
    return this.citiesService
      .cities()
      .filter((c) => this.normalize(c).includes(q));
  });

  constructor(
    private jobsService: JobsService,
    private citiesService: CitiesService,
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

  // strip diacritics + lowercase, so "bucur" matches "București"
  private normalize(s: string): string {
    return s
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  }
}
