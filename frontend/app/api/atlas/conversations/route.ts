/**
 * app/api/atlas/conversations/route.ts
 *
 * GET — Return all conversations for the current authenticated user.
 * Proxies to GET /api/atlas/conversations on the AtlasCore backend.
 */

import { apiRequest } from "@/lib/api-client";
import type { ConversationsResponse } from "@/lib/types";

export const maxDuration = 60;
const headers = { "Cache-Control": "private, no-store" };

export async function GET() {
  const { data, error, status } = await apiRequest<ConversationsResponse>(
    "/api/atlas/conversations", { timeoutMs: 45000 }
  );

  if (error) {
    return Response.json({ error }, { status: status || 500, headers });
  }

  return Response.json(data, { status: 200, headers });
}
