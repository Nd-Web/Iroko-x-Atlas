/**
 * app/api/atlas/conversations/[id]/messages/route.ts
 *
 * GET — Return all messages in a given conversation.
 * Proxies to GET /api/atlas/conversations/{conversation_id}/messages on AtlasCore.
 */

import { apiRequest } from "@/lib/api-client";

export const maxDuration = 60;
const headers = { "Cache-Control": "private, no-store" };

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const { data, error, status } = await apiRequest(
    `/api/atlas/conversations/${encodeURIComponent(id)}/messages`, { timeoutMs: 45000 }
  );

  if (error) {
    return Response.json({ error }, { status: status || 500, headers });
  }

  return Response.json(data, { status: 200, headers });
}
