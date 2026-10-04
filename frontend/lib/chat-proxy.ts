import { API_BASE } from "@/lib/config";

export const CHAT_TIMEOUT_MS = 140_000;

export async function proxyChat(request: Request, token?: string): Promise<Response> {
  const fail = (error: string, status: number) => Response.json({ error }, {
    status, headers: { "Cache-Control": "private, no-store" },
  });
  if (!token) return fail("Your session has expired. Please sign in again.", 401);
  let body;
  try { body = await request.json(); }
  catch { return fail("Invalid request body.", 400); }
  if (!body || typeof body.query !== "string" || !body.query.trim() || body.query.length > 2000) {
    return fail("Enter a question of between 1 and 2,000 characters.", 400);
  }
  if (body.conversation_id != null && typeof body.conversation_id !== "string") {
    return fail("Invalid conversation ID.", 400);
  }
  const controller = new AbortController();
  const disconnect = () => controller.abort();
  request.signal.addEventListener("abort", disconnect, { once: true });
  if (request.signal.aborted) disconnect();
  const timer = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
  const cleanup = () => {
    clearTimeout(timer);
    request.signal.removeEventListener("abort", disconnect);
  };
  try {
    const upstream = await fetch(`${API_BASE}/api/atlas/ask/stream-http`, {
      method: "POST", cache: "no-store", redirect: "error",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ query: body.query.trim(), conversation_id: body.conversation_id ?? null }),
      signal: controller.signal,
    });
    if (!upstream.ok || !upstream.body || !upstream.headers.get("content-type")?.includes("text/event-stream")) {
      cleanup();
      await upstream.body?.cancel().catch(() => undefined);
      if (upstream.status === 401) return fail("Your session has expired. Please sign in again.", 401);
      if (upstream.status === 403) return fail("You don't have access to this conversation.", 403);
      if (upstream.status === 429) return fail("Please wait a moment before sending another question.", 429);
      if (upstream.status === 422) return fail("Check your question and try again.", 422);
      return fail("The AI service is temporarily unavailable. Please try again.", 503);
    }
    const reader = upstream.body.getReader();
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      async pull(output) {
        try {
          const { value, done } = await reader.read();
          if (done) { cleanup(); reader.releaseLock(); output.close(); }
          else output.enqueue(value);
        } catch {
          cleanup();
          reader.releaseLock();
          output.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "error", message: "The AI connection was interrupted or timed out. Please try again." })}\n\n`));
          output.close();
        }
      },
      async cancel() {
        controller.abort();
        cleanup();
        await reader.cancel().catch(() => undefined);
        reader.releaseLock();
      },
    });
    return new Response(stream, { headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "private, no-store, no-transform", "X-Accel-Buffering": "no",
    } });
  } catch {
    cleanup();
    return fail("The AI service could not be reached. Please try again.", 503);
  }
}
