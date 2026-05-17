import { HttpClient } from "@angular/common/http";
import { Injectable, signal } from "@angular/core";

@Injectable({
  providedIn: "root",
})
export class CitiesService {
  cities = signal<string[]>([]);

  constructor(private http: HttpClient) {}

  getCities() {
    this.http
      .get<{ cities: string[] }>("http://localhost:3000/cities")
      .subscribe((data) => {
        this.cities.set(data.cities);
      });
  }
}
