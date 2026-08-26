/**
 * Shared contract for the environment files. Both must satisfy it, so a key
 * added to one and forgotten in the other fails the build instead of failing
 * only in the configuration nobody runs locally.
 */
export interface Environment {
  /**
   * No backend is reachable: searches read the pre-scraped snapshots under
   * `public/demo-data/` instead of calling the API. This is what the hosted
   * build uses.
   */
  demo: boolean;

  /** Origin of the Express API. Empty in demo mode, where nothing calls it. */
  apiBase: string;

  /**
   * Run the real scrapers (~15-30s per search) instead of the API's canned
   * fixture. Ignored when `demo` is true.
   */
  liveSearch: boolean;
}
