import { Component } from "@angular/core";
import { RouterOutlet } from "@angular/router";
import { LeftNavbarComponent } from "./left-navbar/left-navbar.component";

@Component({
  selector: "app-root",
  imports: [RouterOutlet, LeftNavbarComponent],
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
export class AppComponent {}
