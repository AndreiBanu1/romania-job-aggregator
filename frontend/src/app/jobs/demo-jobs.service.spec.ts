import { TestBed } from "@angular/core/testing";
import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";

import { DemoJobsService, DemoManifest } from "./demo-jobs.service";
import { Job, JobsResponse } from "./jobs.service";

function job(overrides: Partial<Job>): Job {
  return {
    title: "Angular Developer",
    company: "Acme",
    location: "Bucharest, Romania",
    href: "https://example.test/1",
    source: "ejobs",
    ...overrides,
  };
}

function response(jobs: Job[]): JobsResponse {
  return {
    total_jobs_found: jobs.length,
    sources_summary: {},
    jobs,
  };
}

describe("DemoJobsService", () => {
  const manifest: DemoManifest = {
    generated: "2026-08-26T03:17:00+00:00",
    queries: [
      {
        title: "Angular developer",
        city: "Bucharest",
        slug: "angular-bucharest",
        total: 2,
        scrapedAt: "2026-08-26T03:17:00+00:00",
      },
      {
        title: "Java developer",
        city: "Cluj-Napoca",
        slug: "java-cluj",
        total: 2,
        scrapedAt: "2026-08-26T03:17:00+00:00",
      },
    ],
  };

  const angular = job({ href: "https://example.test/angular" });
  const dotnet = job({
    title: ".NET Developer",
    href: "https://example.test/dotnet",
    source: "bestjobs",
  });
  const java = job({
    title: "Java Developer",
    location: "Cluj-Napoca, Romania",
    href: "https://example.test/java",
    source: "linkedin",
  });
  // The same job as `angular`, as a second snapshot happens to carry it —
  // this copy is the one with a description.
  const angularAgain = job({
    href: "https://example.test/angular",
    description: "Work on an Angular app.",
  });

  let service: DemoJobsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DemoJobsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  /** Answers the manifest request every search starts with. */
  function flushManifest() {
    http.expectOne("/demo-data/index.json").flush(manifest);
  }

  function flushSnapshot(slug: string, jobs: Job[]) {
    http.expectOne(`/demo-data/${slug}.json`).flush(response(jobs));
  }

  it("serves a covered query from its own snapshot, untouched", () => {
    let result: JobsResponse | undefined;
    // Different casing than the manifest: the suggestion chips and a typed
    // query have to land on the same file.
    service.search("angular DEVELOPER", "bucharest").subscribe((r) => {
      result = r;
    });

    flushManifest();
    flushSnapshot("angular-bucharest", [angular, dotnet]);

    expect(result?.total_jobs_found).toBe(2);
    expect(result?.jobs.map((j) => j.title)).toEqual([
      "Angular Developer",
      ".NET Developer",
    ]);
  });

  it("filters the whole corpus for a query the workflow does not cover", () => {
    let result: JobsResponse | undefined;
    service.search("developer", "Bucharest").subscribe((r) => {
      result = r;
    });

    flushManifest();
    flushSnapshot("angular-bucharest", [angular, dotnet]);
    flushSnapshot("java-cluj", [java]);

    // The Cluj job is dropped by the city filter, and the summary is recomputed
    // from what survived rather than copied from a snapshot.
    expect(result?.total_jobs_found).toBe(2);
    expect(result?.sources_summary).toEqual({ ejobs: 1, bestjobs: 1 });
  });

  it("requires every word of the query to match, so one shared word is not enough", () => {
    let result: JobsResponse | undefined;
    service.search("angular developer", "Cluj").subscribe((r) => {
      result = r;
    });

    flushManifest();
    flushSnapshot("angular-bucharest", [angular, dotnet]);
    flushSnapshot("java-cluj", [java]);

    // "Java Developer" shares "developer" but not "angular".
    expect(result?.jobs).toEqual([]);
    expect(result?.total_jobs_found).toBe(0);
  });

  it("dedupes jobs that appear in several snapshots, keeping the described copy", () => {
    let result: JobsResponse | undefined;
    service.search("angular", "Romania").subscribe((r) => {
      result = r;
    });

    flushManifest();
    flushSnapshot("angular-bucharest", [angular, dotnet]);
    flushSnapshot("java-cluj", [java, angularAgain]);

    expect(result?.jobs.length).toBe(1);
    expect(result?.jobs[0].description).toBe("Work on an Angular app.");
  });

  it("downloads each snapshot once, however many searches run", () => {
    service.search("developer", "Bucharest").subscribe();
    flushManifest();
    flushSnapshot("angular-bucharest", [angular, dotnet]);
    flushSnapshot("java-cluj", [java]);

    let second: JobsResponse | undefined;
    service.search("java", "Cluj").subscribe((r) => {
      second = r;
    });

    // No new requests: http.verify() in afterEach fails if any were made.
    expect(second?.jobs.map((j) => j.title)).toEqual(["Java Developer"]);
  });

  it("exposes the manifest for the suggestion chips", () => {
    service.loadManifest().subscribe();
    flushManifest();

    expect(service.queries().map((q) => q.slug)).toEqual([
      "angular-bucharest",
      "java-cluj",
    ]);
    expect(service.generated()).toBe("2026-08-26T03:17:00+00:00");
  });
});
