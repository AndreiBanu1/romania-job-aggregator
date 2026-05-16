import { Component, OnInit } from "@angular/core";
import { JobsTableComponent } from "./jobs-table/jobs-table.component";
import { HttpClient } from "@angular/common/http";
import { JobsService } from "./jobs.service";

@Component({
  selector: "app-root",
  imports: [JobsTableComponent],
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
export class AppComponent implements OnInit {
  title = "Find Your Job";
  cities: string[] = [];

  constructor(
    private http: HttpClient,
    private jobsService: JobsService,
  ) {}

  ngOnInit() {
    this.http
      .get<{ cities: string[] }>("http://localhost:3000/cities")
      .subscribe((data) => {
        this.cities = data.cities;
      });
  }

  onSearch(title: string, city: string) {
    this.jobsService.search(title, city);
  }
}
