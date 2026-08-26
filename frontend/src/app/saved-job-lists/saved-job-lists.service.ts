import { Injectable, signal } from "@angular/core";
import { Job } from "../jobs/jobs.service";

export interface SavedJobList {
  /** Stable key for tracking and removal; snapshots are otherwise identical. */
  id: string;
  /** The query that produced the snapshot, kept for display only. */
  title: string;
  city: string;
  date: string;
  /** Hash of query + job hrefs; identifies re-saves of an unchanged result set. */
  fingerprint: string;
  jobs: Job[];
}

export type SaveResult =
  | { status: "saved"; list: SavedJobList }
  | { status: "duplicate" }
  | { status: "empty" }
  | { status: "quota-exceeded" };

const STORAGE_KEY = "saved-job-lists";

@Injectable({
  providedIn: "root",
})
export class SavedJobListsService {
  private _lists = signal<SavedJobList[]>(this.readLists());

  lists = this._lists.asReadonly();

  /**
   * Snapshots the given rows. Re-saving an unchanged result set is refused: two
   * identical snapshots carry no more information than one. A re-run that found
   * different jobs has a different fingerprint and saves normally.
   */
  saveList(title: string, city: string, jobs: Job[]): SaveResult {
    if (!jobs.length) return { status: "empty" };

    const fingerprint = this.fingerprintOf(title, city, jobs);
    if (this._lists().some((l) => l.fingerprint === fingerprint)) {
      return { status: "duplicate" };
    }

    const now = new Date();
    const list: SavedJobList = {
      id: `${now.toISOString()}-${jobs.length}`,
      title,
      city,
      date: now.toISOString(),
      fingerprint,
      // Copy the rows so later searches cannot mutate the snapshot.
      jobs: jobs.map((job) => ({ ...job })),
    };

    if (!this.persist([...this._lists(), list])) {
      return { status: "quota-exceeded" };
    }
    return { status: "saved", list };
  }

  /** Whether this exact result set is already stored. */
  isSaved(title: string, city: string, jobs: Job[]): boolean {
    if (!jobs.length) return false;
    const fingerprint = this.fingerprintOf(title, city, jobs);
    return this._lists().some((l) => l.fingerprint === fingerprint);
  }

  readLists(): SavedJobList[] {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      // Lists saved before fingerprinting existed get one derived on read, so
      // duplicate detection works against them too.
      return parsed.map((list: SavedJobList) => ({
        ...list,
        fingerprint:
          list.fingerprint ??
          this.fingerprintOf(list.title, list.city, list.jobs ?? []),
      }));
    } catch {
      // Stored value was corrupted; start fresh rather than crash.
      return [];
    }
  }

  remove(list: SavedJobList) {
    this.persist(this._lists().filter((l) => l.id !== list.id));
  }

  /**
   * Identifies a result set by its query and the hrefs it contains. Hashed
   * rather than compared directly: the joined hrefs of 150 jobs are ~15 kB, and
   * this is stored on every snapshot.
   */
  private fingerprintOf(title: string, city: string, jobs: Job[]): string {
    const hrefs = jobs
      .map((job) => job.href)
      .sort()
      .join("\n");
    return `${title}|${city}|${jobs.length}|${this.hash(hrefs)}`;
  }

  /** djb2. Not cryptographic — collision here only means a refused re-save. */
  private hash(value: string): string {
    let hash = 5381;
    for (let i = 0; i < value.length; i++) {
      hash = (hash * 33) ^ value.charCodeAt(i);
    }
    return (hash >>> 0).toString(36);
  }

  /**
   * Writes first and only then updates the signal, so the UI never claims to
   * have saved something that did not reach storage. Returns false when the
   * write failed — snapshots with descriptions run to ~1 MB each and the
   * localStorage quota is around 5 MB, so this is reachable, not theoretical.
   */
  private persist(next: SavedJobList[]): boolean {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      return false;
    }
    this._lists.set(next);
    return true;
  }
}
