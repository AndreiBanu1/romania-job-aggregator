import { TestBed } from "@angular/core/testing";

import { SavedJobListsService } from "./saved-job-lists.service";
import { Job } from "../jobs/jobs.service";

function job(href: string): Job {
  return {
    title: "Angular Developer",
    company: "Acme",
    location: "Bucharest",
    href,
    source: "ejobs",
  };
}

describe("SavedJobListsService", () => {
  const jobs = [job("https://example.test/1"), job("https://example.test/2")];

  function makeService(): SavedJobListsService {
    // Constructed per test so it reads whatever localStorage was seeded with.
    return TestBed.runInInjectionContext(() => new SavedJobListsService());
  }

  beforeEach(() => {
    localStorage.removeItem("saved-job-lists");
    TestBed.configureTestingModule({});
  });

  afterEach(() => {
    localStorage.removeItem("saved-job-lists");
  });

  it("saves a snapshot and copies the rows", () => {
    const service = makeService();
    const mutable = [job("https://example.test/1")];

    expect(service.saveList("Angular", "Bucharest", mutable).status).toBe(
      "saved",
    );

    mutable[0].title = "changed after saving";
    expect(service.lists()[0].jobs[0].title).toBe("Angular Developer");
  });

  it("refuses an unchanged result set, so navigating away and back cannot duplicate it", () => {
    const service = makeService();

    expect(service.saveList("Angular", "Bucharest", jobs).status).toBe("saved");
    expect(service.saveList("Angular", "Bucharest", jobs).status).toBe(
      "duplicate",
    );
    expect(service.lists().length).toBe(1);
  });

  it("treats a result set with different jobs as savable", () => {
    const service = makeService();
    service.saveList("Angular", "Bucharest", jobs);

    const rerun = [...jobs, job("https://example.test/3")];
    expect(service.saveList("Angular", "Bucharest", rerun).status).toBe("saved");
    expect(service.lists().length).toBe(2);
  });

  it("ignores job order when deciding whether a set is already saved", () => {
    const service = makeService();
    service.saveList("Angular", "Bucharest", jobs);

    expect(service.isSaved("Angular", "Bucharest", [...jobs].reverse())).toBe(
      true,
    );
  });

  it("reports a failed write and does not claim the list was saved", () => {
    const service = makeService();
    spyOn(localStorage, "setItem").and.throwError("QuotaExceededError");

    expect(service.saveList("Angular", "Bucharest", jobs).status).toBe(
      "quota-exceeded",
    );
    // The in-memory list must not disagree with what actually reached storage.
    expect(service.lists().length).toBe(0);
    expect(service.isSaved("Angular", "Bucharest", jobs)).toBe(false);
  });

  it("refuses to save an empty result set", () => {
    const service = makeService();
    expect(service.saveList("Angular", "Bucharest", []).status).toBe("empty");
  });

  it("derives a fingerprint for lists stored before fingerprinting existed", () => {
    localStorage.setItem(
      "saved-job-lists",
      JSON.stringify([
        {
          id: "legacy",
          title: "Angular",
          city: "Bucharest",
          date: "2026-08-01T00:00:00.000Z",
          jobs,
        },
      ]),
    );

    const service = makeService();
    expect(service.lists()[0].fingerprint).toBeTruthy();
    expect(service.isSaved("Angular", "Bucharest", jobs)).toBe(true);
  });

  it("removes a list by id and persists the removal", () => {
    const service = makeService();
    service.saveList("Angular", "Bucharest", jobs);

    service.remove(service.lists()[0]);

    expect(service.lists().length).toBe(0);
    expect(makeService().lists().length).toBe(0);
  });
});
