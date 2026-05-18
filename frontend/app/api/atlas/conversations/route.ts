/**
 * app/api/atlas/conversations/route.ts
 *
 * GET — Return all conversations for the current authenticated user.
 * Proxies to GET /api/atlas/conversations on the AtlasCore backend.
 */

import { apiRequest } from "@/lib/api-client";
import type { ConversationsResponse } from "@/lib/types";

export async function GET() {
  const { data, error, status } = await apiRequest<ConversationsResponse>(
    "/api/atlas/conversations"
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
