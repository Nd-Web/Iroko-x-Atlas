/**
 * hooks/useChat.ts
 *
 * React hook for managing the AI chat conversation.
 *
 * - Manages messages (user + assistant), loading state, and errors.
 * - Streams SSE tokens from POST /api/atlas/ask/stream (Next.js proxy).
 * - On completion, attaches citations, suggested_followups, and agent trace
 *   to the assistant message.
 *
 * FIX (May 2026):
 *   Previously called ${API_BASE}/api/atlas/ask/stream-http directly with a
 *   token from localStorage. That fails because:
 *     1. JWT is stored in an httpOnly cookie — JS cannot read it, so
 *        getStoredToken() always returns null → 401.
 *     2. Direct backend calls bypass CORS/proxy and hit the wrong origin.
 *   Fix: call /api/atlas/ask/stream (Next.js proxy). The proxy reads the
 *   httpOnly cookie server-side and forwards it as a Bearer token.
 *   No Authorization header needed from the browser.
 */

"use client";

import { useState, useCallback, useRef } from "react";
import { readStream } from "@/lib/stream";
import type {
  Citation,
  AgentTraceStep,
  SseEvent,
  SseCompleteEvent,
} from "@/lib/types";

// ── Types ────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citations?: Citation[];
  suggested_followups?: string[];
  trace?: AgentTraceStep[];
}

export interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  clearChat: () => void;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

let _msgSeq = 0;
function msgId(): string {
  return `msg_${Date.now()}_${++_msgSeq}`;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const conversationIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || isLoading) return;

    setError(null);

    // 1. Immediately append the user message
    const userMsg: ChatMessage = {
      id: msgId(),
      role: "user",
      content: trimmed,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // 2. Prepare an assistant message placeholder
    const assistantId = msgId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, assistantMsg]);

    setIsLoading(true);
    abortRef.current = new AbortController();

    try {
      /**
       * CRITICAL FIX: Call the Next.js proxy at /api/atlas/ask/stream
       * — NOT the backend directly at ${API_BASE}/api/atlas/ask/stream-http.
       *
       * The Next.js proxy (app/api/atlas/ask/stream/route.ts) reads the
       * httpOnly JWT cookie server-side and forwards it as Authorization:
       * Bearer <token> to the backend. Calling the backend directly bypasses
       * this, getStoredToken() returns null (httpOnly cookies are invisible
       * to JS), and every request gets a 401.
       */
      const res = await fetch(`/api/atlas/ask/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // No Authorization header — the Next.js proxy handles auth via cookie
        },
        body: JSON.stringify({
          query: trimmed,
          conversation_id: conversationIdRef.current,
        }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `HTTP ${res.status}`);
      }

      // 4. Stream tokens into the assistant message
      let accumulated = "";
      let completionData: SseCompleteEvent | null = null;

      for await (const event of readStream(res)) {
        const evt = event as SseEvent;

        switch (evt.type) {
          case "token":
            accumulated += evt.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: accumulated } : m,
              ),
            );
            break;

          case "complete":
            completionData = evt as SseCompleteEvent;
            break;

          case "agent_action":
            // Agent steps — collected and attached on completion
            break;

          case "start":
            // No-op
            break;
        }
      }

      // 5. Attach final metadata to the assistant message
      if (completionData) {
        conversationIdRef.current =
          completionData.conversation_id ?? conversationIdRef.current;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: completionData!.answer || accumulated,
                  citations: completionData!.citations ?? [],
                  suggested_followups:
                    completionData!.suggested_followups ?? [],
                  trace: completionData!.agent_trace ?? [],
                }
              : m,
          ),
        );
      } else if (accumulated) {
        // Stream closed without a complete event — still show what we got
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: accumulated } : m,
          ),
        );
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") return;
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(message);

      // Remove the empty assistant placeholder on error
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  }, [isLoading]);

  const clearChat = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setIsLoading(false);
    conversationIdRef.current = null;
  }, []);

  return { messages, isLoading, error, sendMessage, clearChat };
}

export default useChat;
