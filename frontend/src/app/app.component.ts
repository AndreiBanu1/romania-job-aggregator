import { Component, OnInit, signal, computed } from "@angular/core";
import { JobsTableComponent } from "./jobs-table/jobs-table.component";
import { HttpClient } from "@angular/common/http";
import { JobsService } from "./jobs.service";
import { FormControl, ReactiveFormsModule } from "@angular/forms";
import { toSignal } from "@angular/core/rxjs-interop";

import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatAutocompleteModule } from "@angular/material/autocomplete";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

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
  ],
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
export class AppComponent implements OnInit {
  title = "Find Your Job";
  cities = signal<string[]>([]);

  titleControl = new FormControl("", { nonNullable: true });
  cityControl = new FormControl("", { nonNullable: true });

  private cityQuery = toSignal(this.cityControl.valueChanges, {
    initialValue: "",
  });

  filteredCities = computed(() => {
    const q = this.normalize(this.cityQuery());
    return this.cities().filter((c) => this.normalize(c).includes(q));
  });

  constructor(
    private http: HttpClient,
    private jobsService: JobsService,
  ) {}

  ngOnInit() {
    this.http
      .get<{ cities: string[] }>("http://localhost:3000/cities")
      .subscribe((data) => {
        this.cities.set(data.cities);
      });
  }

  onSearch() {
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
