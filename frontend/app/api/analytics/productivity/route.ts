/**
 * app/api/analytics/productivity/route.ts
 *
 * Proxy: forwards GET /api/analytics/productivity (real productivity
 * metrics) to the FastAPI backend with cookie-based Bearer auth.
 */

import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/proxy";

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "/api/analytics/productivity");
}
