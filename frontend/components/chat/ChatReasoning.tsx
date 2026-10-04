"use client";

import type { ChatMessage } from "@/hooks/useChat";

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
      {loading && <p className="flex items-center gap-2 text-gray-600"><span className="h-3 w-3 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />Checking source evidence and validating the answer…</p>}
      {error && <p className="rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}
      {!loading && !error && message?.content && <p className="text-brand-600">Answer complete. Source citations are shown with the reply.</p>}
    </div>
  );
}
