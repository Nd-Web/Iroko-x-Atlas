import { readStream } from "./stream";
import type { AtlasAskRequest, SseCompleteEvent, SseEvent } from "./types";

/** One submission, one model request. Never retry a POST behind the user's back. */
export async function streamChat(
  body: AtlasAskRequest,
  signal: AbortSignal,
  onEvent: (event: SseEvent) => void,
): Promise<SseCompleteEvent> {
  const deadline = AbortSignal.timeout(150_000);
  try {
    const response = await fetch("/api/atlas/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.any([signal, deadline]),
    });
    if (!response.ok) {
      let message = response.status === 401
        ? "Your session has expired. Please sign in again."
        : "The AI service is unavailable. Please try again.";
      try {
        const data = await response.json();
        if (typeof data.error === "string") message = data.error;
      } catch { /* Never show gateway HTML or an upstream traceback. */ }
      throw Object.assign(new Error(message), { status: response.status });
    }
    if (!response.body || !response.headers.get("content-type")?.includes("text/event-stream")) {
      throw new Error("The AI service returned an invalid response. Please try again.");
    }
    for await (const event of readStream(response)) {
      if (event.type === "error") throw new Error(event.message || "The AI request failed. Please try again.");
      onEvent(event);
      if (event.type === "complete") return event;
    }
    throw new Error("The connection closed before the answer was complete. Please try again.");
  } catch (error) {
    if (deadline.aborted && !signal.aborted) {
      throw new Error("This question took too long to answer. Please try a more specific question.");
    }
    throw error;
  }
}
