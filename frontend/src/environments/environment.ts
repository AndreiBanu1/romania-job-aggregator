import { Environment } from "./environment.type";

/**
 * Production / hosted defaults. The deployed site is a static bundle served by
 * a Cloudflare Worker with no server-side code behind it, so demo mode is the
 * only thing that works there. `environment.development.ts` replaces this file for
 * `ng serve` and `ng build --configuration development`.
 */
export const environment: Environment = {
  demo: true,
  apiBase: "",
  liveSearch: false,
};
