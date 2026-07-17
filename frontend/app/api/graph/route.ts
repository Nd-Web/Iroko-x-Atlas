/**
 * app/api/graph/route.ts
 *
 * Proxy: forwards GET /api/graph (live knowledge graph) to the FastAPI
 * backend with cookie-based Bearer auth.
 */

import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/proxy";

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "/api/graph");
}
