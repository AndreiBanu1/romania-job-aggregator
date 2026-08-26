import { Injectable, signal } from "@angular/core";
import { Job } from "../jobs/jobs.service";

export interface SavedJobList {
  /** Stable key for tracking and removal; snapshots are otherwise identical. */
  id: string;
  /** The query that produced the snapshot, kept for display only. */
  title: string;
  city: string;
  date: string;
  jobs: Job[];
}

const STORAGE_KEY = "saved-job-lists";

@Injectable({
  providedIn: "root",
})
export class SavedJobListsService {
  private _lists = signal<SavedJobList[]>(this.readLists());

  lists = this._lists.asReadonly();

  /** Snapshots the given rows. Duplicates are allowed: each is a point in time. */
  saveList(title: string, city: string, jobs: Job[]) {
    if (!jobs.length) return;

    const now = new Date();
    const list: SavedJobList = {
      id: `${now.toISOString()}-${jobs.length}`,
      title,
      city,
      date: now.toISOString(),
      // Copy the rows so later searches cannot mutate the snapshot.
      jobs: jobs.map((job) => ({ ...job })),
    };

    this.persist([...this._lists(), list]);
  }

  readLists(): SavedJobList[] {
    const raw = localStorage.getItem(STORAGE_KEY);
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

  remove(list: SavedJobList) {
    this.persist(this._lists().filter((l) => l.id !== list.id));
  }

  private persist(next: SavedJobList[]) {
    this._lists.set(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Quota exceeded — keep the in-memory state so the UI stays consistent.
    }
  }
}
