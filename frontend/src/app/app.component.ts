import { Component, OnInit } from "@angular/core";
import { JobsTableComponent } from "./jobs-table/jobs-table.component";
import { HttpClient } from "@angular/common/http";

@Component({
  selector: "app-root",
  imports: [JobsTableComponent],
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
export class AppComponent implements OnInit {
  title = "Find Your Job";
  cities: string[] = [];
  showJobsTable = false;

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.http
      .get<{ cities: string[] }>("http://localhost:3000/cities")
      .subscribe((data) => {
        this.cities = data.cities;
      });
  }

  onSearch() {
    this.showJobsTable = true;
  }
}
