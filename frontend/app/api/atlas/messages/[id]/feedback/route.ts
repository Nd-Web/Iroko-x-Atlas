/**
 * app/api/atlas/messages/[id]/feedback/route.ts
 *
 * POST — Record whether one answer was right ({ helpful, reason?, comment? }).
 * Proxies to POST /api/atlas/messages/{message_id}/feedback on AtlasCore with the
 * session cookie; the backend only accepts answers in the user's own conversations.
 */

import { apiRequest } from "@/lib/api-client";

const headers = { "Cache-Control": "private, no-store" };

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid feedback." }, { status: 400, headers });
  }

  const { data, error, status } = await apiRequest(
    `/api/atlas/messages/${encodeURIComponent(id)}/feedback`,
    { method: "POST", body: JSON.stringify(body), timeoutMs: 15000 }
  );

  if (error) {
    return Response.json({ error }, { status: status || 500, headers });
  }

  return Response.json(data, { status: 200, headers });
}
