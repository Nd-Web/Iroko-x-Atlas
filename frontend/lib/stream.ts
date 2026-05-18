/**
 * lib/stream.ts
 *
 * SSE / NDJSON stream reader.
 * Yields parsed SseEvent objects from a ReadableStream (Response body).
 *
 * Usage:
 *   const res = await fetch("/api/atlas/ask/stream-http", { ... });
 *   for await (const event of readStream(res)) { ... }
 */

import type { SseEvent } from "./types";

export type { SseEvent };

/**
 * Async generator that reads a `Response` body as SSE / NDJSON and
 * yields strongly-typed `SseEvent` objects one by one.
 *
 * Handles both SSE format (`data: {...}\n\n`) and raw NDJSON (one JSON
 * object per line) so it works regardless of how the backend serialises
 * its stream.
 *
 * Terminates when the stream closes or a `[DONE]` sentinel is received.
 */
export async function* readStream(response: Response): AsyncGenerator<SseEvent> {
  if (!response.body) return;

  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split on newlines but keep the remainder for the next chunk
      const lines  = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const raw of lines) {
        const line = raw.trim();
        if (!line) continue;           // blank separator line
        if (line === "[DONE]") return; // sentinel

        // SSE format: "data: {...}"
        const payload = line.startsWith("data: ")
          ? line.slice(6).trim()
          : line;                      // raw NDJSON fallback

        if (!payload || payload === "[DONE]") return;

        try {
          yield JSON.parse(payload) as SseEvent;
        } catch {
          // Malformed JSON — skip this line
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
