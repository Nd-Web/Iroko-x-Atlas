/**
 * app/api/atlas/briefing/route.ts
 *
 * Proxy: forwards POST /api/atlas/briefing (morning briefing) to the
 * FastAPI backend with cookie-based Bearer auth.
 */

import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/proxy";

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "/api/atlas/briefing");
}
