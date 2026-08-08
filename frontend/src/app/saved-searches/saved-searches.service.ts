import { Injectable, signal } from "@angular/core";

export interface SavedSearch {
  title: string;
  city: string;
  date: string;
}

@Injectable({
  providedIn: "root",
})
export class SavedSearchesService {
  private _searches = signal<SavedSearch[]>(this.readSavedSearches());

  searches = this._searches.asReadonly();

  saveSearch(title: string, city: string) {
    if (title && city) {
      const newSearch: SavedSearch = {
        title: title,
        city: city,
        date: new Date().toISOString(),
      };

      const next = [...this._searches(), newSearch];
      this._searches.set(next);
      localStorage.setItem("saved-searches", JSON.stringify(next));
    }
  }

  readSavedSearches(): SavedSearch[] {
    const raw = localStorage.getItem("saved-searches");
    if (!raw) {
      return [];
    }
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      // Stored value was corrupted; start fresh rather than crash.
      return [];
    }
  }

  remove(search: SavedSearch) {
    const next = this._searches().filter((s) => s !== search);
    this._searches.set(next);
    localStorage.setItem("saved-searches", JSON.stringify(next));
  }
}
