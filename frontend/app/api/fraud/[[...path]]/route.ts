/**
 * app/api/fraud/[[...path]]/route.ts
 *
 * Catch-all proxy: forwards /api/fraud/* (summary, signals) to the
 * FastAPI backend with cookie-based Bearer auth.
 */

import { makeProxyHandlers } from "@/lib/proxy";

export const { GET, POST, PUT, PATCH, DELETE } = makeProxyHandlers("/api/fraud");
