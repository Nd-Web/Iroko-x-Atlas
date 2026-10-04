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
import { NextRequest } from "next/server";
import { COOKIE_NAME } from "@/lib/config";
import { proxyChat } from "@/lib/chat-proxy";

export const runtime = "nodejs";
export const maxDuration = 180;

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  return proxyChat(request, token);
}
