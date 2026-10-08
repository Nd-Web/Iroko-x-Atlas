"use client";

import type { ChatMessage } from "@/hooks/useChat";

const OUTCOME_LABELS: Record<string, string> = {
  conversational: "Conversation reply complete.",
  needs_clarification: "A detail is needed to identify the right question or document.",
  out_of_scope: "This request is outside Iroko's document and compliance scope.",
  partial: "Supported findings are shown. Some requested details remain unverified.",
  needs_evidence: "The available evidence did not establish the requested answer.",
  retrieval_unavailable: "Document search was unavailable. You can retry the question.",
  access_check_failed: "Document access could not be checked. You can retry the question.",
  reasoning_unavailable: "The answer service was unavailable. You can retry the question.",
  validation_failed: "The draft did not pass the source checks. No unverified findings were approved.",
};

/** Display the actual chat request's trace; this panel never starts a model call. */
export default function ChatReasoning({ query, message, loading, error }: {
  query: string; message?: ChatMessage; loading: boolean; error: string | null;
}) {
  return (
    <div className="space-y-3 text-xs" aria-live="polite">
      <p className="rounded-xl border border-border-default bg-surface-card p-3 text-gray-700">{query}</p>
      {message?.trace?.map((step, index) => (
        <div key={`${step.agent}-${index}`} className="rounded-xl border border-border-default bg-surface-card p-3">
          <p className="mb-1 font-semibold text-brand-600">{step.agent}</p>
          <p className="leading-relaxed text-gray-600">{step.description}</p>
        </div>
      ))}
      {loading && <p className="flex items-center gap-2 text-gray-600"><span className="h-3 w-3 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />{message?.trace?.at(-1)?.description || "Understanding your message…"}</p>}
      {error && <p className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
      {!loading && !error && message?.content && <p className="text-brand-600">{message.interrupted ? "Response stopped. This is an incomplete answer." : OUTCOME_LABELS[message.answer_status ?? ""] ?? "Answer complete. Any source citations are shown with the reply."}</p>}
    </div>
  );
}
