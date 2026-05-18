/**
 * app/api/atlas/ask/stream/route.ts
 *
 * POST — SSE streaming proxy for the Atlas AI.
 *
 * Reads the JWT from the httpOnly cookie, forwards the request to the
 * AtlasCore streaming endpoint, and pipes the SSE response straight
 * through to the browser.
 *
 * The client consumes this with fetch + ReadableStream (not EventSource,
 * because EventSource only supports GET and cannot send a JSON body).
 *
 * SSE event shapes emitted by AtlasCore:
 *   {"type":"start",        "message":"...", "timestamp":"..."}
 *   {"type":"agent_action", "agent":"...", "tool":"...", "description":"...", "timestamp":"..."}
 *   {"type":"token",        "content":"..."}
 *   {"type":"complete",     "answer":"...", "citations":[...], ...}
 *   data: [DONE]
 */

import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { API_BASE, COOKIE_NAME } from "@/lib/config";
import type { AtlasAskRequest } from "@/lib/types";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: AtlasAskRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  // Forward to AtlasCore's SSE endpoint
  const upstream = await fetch(`${API_BASE}/api/atlas/ask/stream-http`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    // @ts-expect-error — Node 18+ fetch supports duplex for streaming
    duplex: "half",
  });

  if (!upstream.ok || !upstream.body) {
    return NextResponse.json(
      { error: "Upstream stream request failed." },
      { status: upstream.status }
    );
  }

  // Pipe the upstream SSE stream directly to the browser
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
