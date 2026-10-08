"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import AppShell from "@/components/layout/AppShell";
import ChatWindow from "./ChatWindow";
import InputBar from "./InputBar";
import ChatReasoning from "./ChatReasoning";
import { useChat } from "@/hooks/useChat";
import { useAuth } from "@/context/AuthContext";
import { formatRelativeTime, cn } from "@/lib/utils";

interface ConvSummary { id: string; title: string; updatedAt: string; }

function ConversationHistory({ conversations, loading, failed, activeId, onSelect, onNew, onRetry, onClose }: {
  conversations: ConvSummary[]; loading: boolean; failed: boolean; activeId: string | null;
  onSelect: (id: string) => void; onNew: () => void; onRetry: () => void; onClose?: () => void;
}) {
  const [search, setSearch] = useState("");
  const filtered = conversations.filter(item => item.title.toLowerCase().includes(search.trim().toLowerCase()));
  return (
    <div className="flex h-full flex-col">
      <div className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-800">Conversations</h2>
          {onClose && <button onClick={onClose} aria-label="Close conversation history" className="h-10 w-10 rounded-lg text-gray-600 hover:bg-gray-50">✕</button>}
        </div>
        <button onClick={onNew} className="flex w-full items-center justify-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-500 hover:bg-brand-100">
          <span aria-hidden="true" className="text-lg leading-none">+</span> New conversation
        </button>
        <input type="search" value={search} onChange={event => setSearch(event.target.value)}
          aria-label="Search conversations" placeholder="Search conversations…"
          className="w-full rounded-lg border border-border-default bg-surface-page px-3 py-2.5 text-sm text-gray-800 outline-none placeholder:text-gray-400 focus:border-brand-300" />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-5">
        {loading && !conversations.length ? <p role="status" className="px-3 py-5 text-sm text-gray-500">Loading conversations…</p> : null}
        {failed && <div role="status" className="mb-3 rounded-xl border border-border-default p-3 text-xs leading-relaxed text-gray-500">
          History couldn’t be refreshed. Your current chat is still available.
          <button onClick={onRetry} className="mt-2 block font-semibold text-brand-500">Try again</button>
        </div>}
        {!loading && !failed && !filtered.length && <p className="px-3 py-5 text-sm leading-relaxed text-gray-500">
          {search ? "No matching conversations. Try a different search." : "Your conversations will appear here after you ask a question."}
        </p>}
        {filtered.map(item => <button key={item.id} onClick={() => onSelect(item.id)} aria-current={activeId === item.id ? "true" : undefined}
          className={cn("mb-1 w-full rounded-xl border px-3 py-3 text-left transition-colors", activeId === item.id ? "border-brand-200 bg-brand-50" : "border-transparent hover:bg-gray-50")}>
          <span className="block truncate text-[13px] font-medium text-gray-700" title={item.title}>{item.title}</span>
          <span className="mt-1 block text-[11px] text-gray-400">{formatRelativeTime(item.updatedAt)}</span>
        </button>)}
      </div>
      <p className="border-t border-border-default px-5 py-4 text-[11px] leading-relaxed text-gray-400">Keep your institution and licence category in the question for more relevant answers.</p>
    </div>
  );
}

const AGENT_PROMPTS: Record<string, string> = {
  compliance: "What evidence do I need to assess my institution’s compliance with the applicable CBN requirements?",
  watchdog: "Summarise the active alerts I can access and show their supporting evidence.",
  noc: "Summarise the network incidents in my accessible records and flag missing information.",
  contracts: "Review the obligations and expiry dates in my accessible vendor contracts.",
  care: "Summarise the customer complaints in my accessible records and identify recurring themes.",
  field: "Which field tasks are outstanding in my accessible records?",
};

export default function ChatWorkspace() {
  const { user, triggerSessionExpiry } = useAuth();
  const { messages, isLoading, isLoadingHistory, error, sendMessage, stopMessage, clearChat, loadConversation, conversationId } = useChat();
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ text: string; version: number }>();
  const [stopped, setStopped] = useState(false);
  const [requestedHistoryId, setRequestedHistoryId] = useState<string | null>(null);
  const historyRef = useRef<HTMLDialogElement>(null);
  const activityRef = useRef<HTMLDialogElement>(null);
  const historyOpenerRef = useRef<HTMLButtonElement>(null);
  const activityOpenerRef = useRef<HTMLButtonElement>(null);
  const convsQuery = useQuery({
    queryKey: ["atlas", "conversations", user?.id],
    enabled: !!user,
    queryFn: async ({ signal }): Promise<ConvSummary[]> => {
      const response = await fetch("/api/atlas/conversations", { cache: "no-store", signal });
      if (response.status === 401) triggerSessionExpiry();
      if (!response.ok) throw new Error("Conversation history could not be loaded.");
      const data = await response.json();
      return (data.conversations ?? []).map((item: { id: string; title: string; updated_at?: string; created_at?: string }) => ({
        id: String(item.id), title: item.title || "Untitled conversation",
        updatedAt: item.updated_at ?? item.created_at ?? new Date().toISOString(),
      }));
    },
    retry: false,
  });
  const refreshConvs = convsQuery.refetch;
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const conv = params.get("conv");
    if (conv) {
      params.delete("conv");
      const remaining = params.toString();
      window.history.replaceState({}, document.title, `${window.location.pathname}${remaining ? `?${remaining}` : ""}`);
      void loadConversation(conv);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const prevLoadingRef = useRef(false);
  useEffect(() => {
    if (prevLoadingRef.current && !isLoading) void refreshConvs();
    prevLoadingRef.current = isLoading;
  }, [isLoading, refreshConvs]);

  const handleSend = useCallback(async (content: string, retry = false) => {
    if (isLoading) return;
    setRequestedHistoryId(null);
    setLastQuery(content);
    setStopped(false);
    await sendMessage(content, { retry });
  }, [sendMessage, isLoading]);
  const handleDraft = useCallback((text: string) => {
    setDraft(previous => ({ text, version: (previous?.version ?? 0) + 1 }));
  }, []);
  const handleSelect = useCallback((id: string) => {
    setRequestedHistoryId(id);
    historyRef.current?.close();
    setLastQuery(null);
    setStopped(false);
    handleDraft("");
    void loadConversation(id);
  }, [loadConversation, handleDraft]);
  const handleNew = useCallback(() => {
    setRequestedHistoryId(null);
    historyRef.current?.close();
    clearChat();
    setLastQuery(null);
    setStopped(false);
    handleDraft("");
  }, [clearChat, handleDraft]);

  const lastUserIndex = messages.map(message => message.role).lastIndexOf("user");
  const latestAssistant = messages.slice(lastUserIndex + 1).find(message => message.role === "assistant");
  const latestQuestion = lastQuery ?? [...messages].reverse().find(message => message.role === "user")?.content;
  const activeTitle = convsQuery.data?.find(item => item.id === conversationId)?.title;
  const isEmpty = messages.length === 0 && !isLoading;
  const chatMessages = messages.map(message => ({
    ...message,
    reasoning_steps: message.trace?.map(step => ({ agent: step.agent, status: "done" as const, message: step.description, timestamp: step.timestamp })),
    citations: message.citations?.map(citation => {
      const item = citation as { document_id?: string; document_title?: string; source?: string; excerpt?: string; source_url?: string | null };
      return { document_id: item.document_id ?? item.source ?? "unknown", document_title: item.document_title ?? item.source ?? "Source document", excerpt: item.excerpt, source_url: item.source_url };
    }),
  }));
  const history = (mobile = false) => <ConversationHistory conversations={convsQuery.data ?? []} loading={convsQuery.isFetching}
    failed={convsQuery.isError} activeId={conversationId} onSelect={handleSelect} onNew={handleNew}
    onRetry={() => void refreshConvs()} onClose={mobile ? () => historyRef.current?.close() : undefined} />;

  return (
    <AppShell title="Iroko Chat" subtitle="Your compliance research workspace" bare>
      <div className="iroko-chat chat-workspace relative flex h-full min-h-0 overflow-hidden">
        <section className="flex min-w-0 flex-1 flex-col" aria-label="Chat workspace">
          <header className="flex min-h-[52px] shrink-0 items-center justify-between gap-2 border-b border-border-default bg-surface-card/40 px-3 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <button ref={historyOpenerRef} onClick={() => { historyRef.current?.showModal(); if (user) void refreshConvs(); }} aria-label="Open conversation history" title="Conversation history" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border-default text-gray-600 hover:border-brand-200 hover:bg-brand-50">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/></svg>
              </button>
              <div className="min-w-0"><p className="truncate text-[13px] font-medium text-gray-700">{activeTitle || (messages.length ? "Current conversation" : "New conversation")}</p></div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {latestQuestion && <button ref={activityOpenerRef} onClick={() => activityRef.current?.showModal()} className="rounded-lg px-3 py-2.5 text-xs font-medium text-gray-600 hover:bg-gray-50">Activity</button>}
              <button onClick={handleNew} aria-label="Start a new conversation" title="New conversation" className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-medium text-brand-500 hover:bg-brand-100"><span aria-hidden="true">+</span><span className="hidden sm:inline"> New chat</span></button>
            </div>
          </header>
          <div className={cn("flex min-h-0 flex-1 flex-col", isEmpty ? "justify-center overflow-y-auto" : "overflow-hidden")}>
          <ChatWindow compact conversationId={conversationId ?? "new"} messages={chatMessages} isStreaming={isLoading && !isLoadingHistory}
            isLoadingHistory={isLoadingHistory} progress={latestAssistant?.trace?.at(-1)?.description} onPrompt={handleDraft} />
          {error && !isLoading && <div role="alert" className="mx-auto w-full max-w-[868px] px-3 pt-2 sm:px-6">
            <div className="flex items-start justify-between gap-3 rounded-xl border border-danger-200 bg-danger-50 p-4">
              <div className="min-w-0"><p className="text-sm font-semibold text-danger-700">We couldn’t complete that request</p><p className="mt-1 break-words text-xs leading-relaxed text-danger-600">{error}</p></div>
              {(requestedHistoryId || lastQuery) && <button onClick={() => { if (requestedHistoryId) void loadConversation(requestedHistoryId); else if (lastQuery) void handleSend(lastQuery, true); }} className="shrink-0 rounded-lg border border-danger-200 px-3 py-2 text-xs font-semibold text-danger-700 hover:bg-danger-100">Try again</button>}
            </div>
          </div>}
          {stopped && !isLoading && <p role="status" className="mx-auto w-full max-w-[820px] px-3 pt-2 text-xs text-gray-500 sm:px-0">Response stopped. You can send another question.</p>}
          <InputBar onSend={content => void handleSend(content)} isStreaming={isLoading && !isLoadingHistory} disabled={isLoadingHistory}
            onStop={() => { stopMessage(); setStopped(true); }} draft={draft} autoSendQuery agentPrompts={AGENT_PROMPTS} />
          </div>
        </section>
        <dialog ref={historyRef} aria-label="Conversation history" onClose={() => historyOpenerRef.current?.focus()}
          onClick={event => { if (event.target === event.currentTarget) historyRef.current?.close(); }}
          className="iroko-chat fixed inset-y-0 left-0 right-auto m-0 h-dvh max-h-dvh w-[min(320px,90vw)] max-w-none border-r border-border-strong bg-surface-page text-gray-800 backdrop:bg-black/60 backdrop:backdrop-blur-sm">
          {history(true)}
        </dialog>
        <dialog ref={activityRef} aria-label="Answer activity" onClose={() => activityOpenerRef.current?.focus()}
          onClick={event => { if (event.target === event.currentTarget) activityRef.current?.close(); }}
          className="iroko-chat fixed inset-0 m-auto max-h-[85dvh] w-[min(480px,calc(100vw-24px))] overflow-y-auto rounded-2xl border border-border-strong bg-surface-page p-5 text-gray-800 shadow-md backdrop:bg-black/60 backdrop:backdrop-blur-sm">
          <div className="mb-4 flex items-center justify-between"><h2 className="text-base font-semibold">Answer activity</h2><button onClick={() => activityRef.current?.close()} aria-label="Close answer activity" className="h-10 w-10 rounded-lg text-gray-600 hover:bg-gray-50">✕</button></div>
          <p className="mb-4 text-xs leading-relaxed text-gray-500">Actual research steps from this request, not the model’s private reasoning.</p>
          {latestQuestion && <ChatReasoning query={latestQuestion} message={latestAssistant} loading={isLoading && !isLoadingHistory} error={error} />}
        </dialog>
      </div>
    </AppShell>
  );
}
