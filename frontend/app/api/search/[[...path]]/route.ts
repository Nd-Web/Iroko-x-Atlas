/**
 * app/api/search/[[...path]]/route.ts
 *
 * Catch-all proxy: forwards /api/search and /api/search/* (e.g. /context)
 * to the FastAPI backend with cookie-based Bearer auth.
 */

import { makeProxyHandlers } from "@/lib/proxy";

export const { GET, POST, PUT, PATCH, DELETE } = makeProxyHandlers("/api/search");
