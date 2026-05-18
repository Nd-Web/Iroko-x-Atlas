/**
 * app/api/atlas/ask/route.ts
 *
 * POST — Non-streaming Atlas AI query.
 *
 * Returns the full AtlasAskResponse in one shot after the AI finishes
 * generating. Use this for programmatic access (e.g. morning briefing
 * widgets). The chat UI uses the streaming endpoint instead.
 */

import { apiRequest } from "@/lib/api-client";
import type { AtlasAskRequest, AtlasAskResponse } from "@/lib/types";

export async function POST(request: Request) {
  let body: AtlasAskRequest;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid request body." }, { status: 400 });
  }

  const { data, error, status } = await apiRequest<AtlasAskResponse>(
    "/api/atlas/ask",
    { method: "POST", body: JSON.stringify(body) }
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
