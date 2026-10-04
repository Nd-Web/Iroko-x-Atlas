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
  if (!response.body) throw new Error("The chat response has no stream.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let data: string[] = [];
  let stopped = false;
  let exhausted = false;
  function parse(payload: string): SseEvent | undefined {
    if (payload.trim() === "[DONE]") { stopped = true; return; }
    if (!payload.trim()) return;
    try { return JSON.parse(payload) as SseEvent; }
    catch { throw new Error("The AI service returned an unreadable stream. Please try again."); }
  }
  function line(raw: string): SseEvent | undefined {
    const value = raw.replace(/\r$/, "");
    if (value === "") {
      const payload = data.join("\n");
      data = [];
      return parse(payload);
    }
    if (value.startsWith("data:")) {
      data.push(value.slice(5).replace(/^ /, ""));
      return;
    }
    if (value.startsWith(":" ) || /^(event|id|retry):/.test(value)) return;
    return parse(value); // NDJSON fallback.
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const raw of lines) {
        const event = line(raw);
        if (event) yield event;
        if (stopped) return;
      }
      if (done) {
        exhausted = true;
        if (buffer) {
          const event = line(buffer);
          if (event) yield event;
        }
        if (!stopped && data.length) {
          const event = parse(data.join("\n"));
          if (event) yield event;
        }
        return;
      }
    }
  } finally {
    if (!exhausted) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
