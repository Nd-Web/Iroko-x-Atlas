/**
 * app/api/atlas/conversations/[id]/messages/route.ts
 *
 * GET — Return all messages in a given conversation.
 * Proxies to GET /api/atlas/conversations/{conversation_id}/messages on AtlasCore.
 */

import { apiRequest } from "@/lib/api-client";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const { data, error, status } = await apiRequest(
    `/api/atlas/conversations/${id}/messages`
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
