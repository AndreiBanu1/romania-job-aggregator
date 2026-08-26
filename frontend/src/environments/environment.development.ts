import { Environment } from "./environment.type";

/** Local development against `backend/api.js` on port 3000. */
export const environment: Environment = {
  demo: false,
  apiBase: "http://localhost:3000",
  // Flip to true to exercise the real scrapers; the fixture returns instantly.
  liveSearch: false,
};
