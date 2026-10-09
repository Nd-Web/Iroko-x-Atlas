import type { ChatMessage as StoredMessage } from "@/hooks/useChat";
import type { ChatMessage } from "@/types/chat";

/**
 * Per-workspace, weakly held projections. Streaming replaces only the active
 * message; preserve older message identities so memoized bubbles can skip work.
 * Never key this cache by a server ID: IDs alone aren't a user/access boundary.
 */
export function createChatMessageAdapter() {
  const cache = new WeakMap<StoredMessage, ChatMessage>();
  return (message: StoredMessage): ChatMessage => {
    const existing = cache.get(message);
    if (existing) return existing;
    const result: ChatMessage = {
      ...message,
      reasoning_steps: message.trace?.map(step => ({
        agent: step.agent, status: "done" as const, message: step.description, timestamp: step.timestamp,
      })),
      citations: message.citations?.map(citation => {
        const item = citation as typeof citation & { document_title?: string };
        return {
          document_id: item.document_id ?? item.source ?? "unknown",
          document_title: item.document_title ?? item.source ?? "Source document",
          excerpt: item.excerpt, source_url: item.source_url,
          chunk_id: item.chunk_id, provenance: item.provenance,
        };
      }),
    };
    cache.set(message, result);
    return result;
  };
}
