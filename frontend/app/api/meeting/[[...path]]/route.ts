/**
 * app/api/meeting/[[...path]]/route.ts
 *
 * Catch-all proxy: forwards /api/meeting/* (config, join, status, ask,
 * leave) to the FastAPI backend with cookie-based Bearer auth.
 */

import { makeProxyHandlers } from "@/lib/proxy";

export const { GET, POST, PUT, PATCH, DELETE } = makeProxyHandlers("/api/meeting");
