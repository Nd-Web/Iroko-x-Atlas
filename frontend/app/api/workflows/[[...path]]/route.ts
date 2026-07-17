/**
 * app/api/workflows/[[...path]]/route.ts
 *
 * Catch-all proxy: forwards /api/workflows and /api/workflows/* (tasks,
 * stats, generate) to the FastAPI backend with cookie-based Bearer auth.
 */

import { makeProxyHandlers } from "@/lib/proxy";

export const { GET, POST, PUT, PATCH, DELETE } = makeProxyHandlers("/api/workflows");
