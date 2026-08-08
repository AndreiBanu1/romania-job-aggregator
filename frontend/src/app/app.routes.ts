import { Routes } from "@angular/router";

export const routes: Routes = [
  {
    path: "",
    loadComponent: () =>
      import("./home/home.component").then((m) => m.HomeComponent),
  },
  {
    path: "saved-searches",
    loadComponent: () =>
      import("./saved-searches/saved-searches.component").then(
        (m) => m.SavedSearchesComponent,
      ),
  },
  { path: "**", redirectTo: "" },
];
