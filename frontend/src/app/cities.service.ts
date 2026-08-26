import { HttpClient } from "@angular/common/http";
import { Injectable, signal } from "@angular/core";
import { environment } from "../environments/environment";

@Injectable({
  providedIn: "root",
})
export class CitiesService {
  cities = signal<string[]>([]);

  constructor(private http: HttpClient) {}

  getCities() {
    // The demo build has no API; the workflow copies the same city list into
    // demo-data/ so the autocomplete behaves identically.
    const url = environment.demo
      ? "/demo-data/cities.json"
      : `${environment.apiBase}/cities`;

    this.http.get<{ cities: string[] }>(url).subscribe((data) => {
      this.cities.set(data.cities);
    });
  }
}
