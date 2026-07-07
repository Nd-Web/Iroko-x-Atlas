/**
 * app/api/insights/[[...path]]/route.ts
 *
 * Catch-all proxy: forwards /api/insights and /api/insights/* (review,
 * dismiss, delete) to the FastAPI backend with cookie-based Bearer auth.
 */

import { makeProxyHandlers } from "@/lib/proxy";

export const { GET, POST, PUT, PATCH, DELETE } = makeProxyHandlers("/api/insights");
