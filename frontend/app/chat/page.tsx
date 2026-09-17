"use client";
/**
 * app/chat/page.tsx — Complete redesign of the main chat interface.
 * Split layout: sidebar | chat area | collapsible reasoning panel.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import AppShell from "@/components/layout/AppShell";
import ChatWindow from "@/components/chat/ChatWindow";
import InputBar from "@/components/chat/InputBar";
import AgentStatusBar from "@/components/agents/AgentStatusBar";
import ReasoningChain from "@/components/ReasoningChain";
import { useChat } from "@/hooks/useChat";
import { formatRelativeTime, cn } from "@/lib/utils";
import { DEFAULT_SUGGESTED_PROMPTS } from "@/types/chat";
import type { ChatMessage } from "@/hooks/useChat";

// ── Conversation list sidebar ─────────────────────────────────────────────────

interface ConvSummary { id: string; title: string; updatedAt: string; pinned?: boolean; }

function ConvSidebar({ convs, convsLoading, activeId, onSelect, onNew }: {
  convs: ConvSummary[]; convsLoading: boolean;
  activeId: string | null; onSelect: (id: string) => void; onNew: () => void;
}) {
  const [search, setSearch] = useState("");
  const filtered = convs.filter(c => c.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="w-[280px] shrink-0 flex flex-col border-r border-border-default h-full bg-surface-page">
      {/* Header */}
      <div className="px-4 pt-4 pb-3 space-y-3">
        <button id="new-chat-btn" onClick={onNew}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-bold text-[#0A0A0B] bg-brand-500 hover:bg-brand-400 transition-all">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v12M1 7h12" stroke="#0A0A0B" strokeWidth="2" strokeLinecap="round"/></svg>
          New Chat
        </button>
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3"/><path d="M11 11l-2.5-2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="w-full pl-8 pr-3 py-2 text-[12px] bg-gray-50 border border-border-default rounded-lg text-gray-800 placeholder-gray-400 outline-none focus:border-brand-500/50 transition-colors" />
        </div>
      </div>
      {/* Conversations */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {filtered.filter(c => c.pinned).length > 0 && (
          <div className="text-[9.5px] font-bold text-gray-400 uppercase tracking-widest px-2 mb-1 mt-2">Pinned</div>
        )}
        {filtered.filter(c => c.pinned).map(c => (
          <ConvItem key={c.id} conv={c} active={activeId === c.id} onClick={() => onSelect(c.id)} />
        ))}
        <div className="text-[9.5px] font-bold text-gray-400 uppercase tracking-widest px-2 mb-1 mt-3">Recent</div>
        {filtered.filter(c => !c.pinned).map(c => (
          <ConvItem key={c.id} conv={c} active={activeId === c.id} onClick={() => onSelect(c.id)} />
        ))}
        {filtered.length === 0 && (
          <p className="text-[11px] text-gray-400 text-center py-6">
            {convsLoading ? "Loading conversations…" : "No conversations yet — ask your first question"}
          </p>
        )}
      </div>
    </div>
  );
}

function ConvItem({ conv, active, onClick }: { conv: ConvSummary; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={cn("w-full text-left px-3 py-2.5 rounded-lg mb-0.5 transition-all duration-150 group",
        active ? "bg-brand-50 border border-brand-200" : "hover:bg-gray-50 border border-transparent")}>
      <div className={cn("text-[12.5px] font-medium truncate leading-snug", active ? "text-brand-500" : "text-gray-500 group-hover:text-gray-800")}>
        {conv.title}
      </div>
      <div className="text-[10px] text-gray-400 mt-0.5">{formatRelativeTime(conv.updatedAt)}</div>
    </button>
  );
}

// ── Reasoning panel ───────────────────────────────────────────────────────────

function ReasoningPanel({ query, open, onClose, recentInsights }: {
  query: string | null; open: boolean; onClose: () => void; recentInsights?: string[];
}) {
  return (
    <div className={cn(
      "shrink-0 border-l border-border-default flex flex-col transition-all duration-300 overflow-hidden bg-surface-page",
      open ? "w-[320px]" : "w-0",
    )}>
      {open && (
        <>
          <div className="flex items-center justify-between px-4 py-3 border-b border-border-default">
            <span className="text-[12px] font-bold text-gray-800 uppercase tracking-wider">
              {query ? "Reasoning Chain" : "Recent Insights"}
            </span>
            <button onClick={onClose} className="w-6 h-6 rounded-md flex items-center justify-center text-gray-400 hover:text-gray-900 hover:bg-gray-50 transition-colors">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            {query ? (
              <ReasoningChain query={query} onComplete={() => {}} onError={() => {}} />
            ) : (
              <div className="space-y-2">
                {["IHS Ikeja Cluster SLA breach — ₦2.66M exposure", "NCC QoS return Q1 2026 due in 12 days", "ATC Lagos Zone 2 contract expires in 28 days"].map((insight, i) => (
                  <div key={i} className="p-3 rounded-xl border border-border-default bg-surface-card">
                    <div className="w-2 h-2 rounded-full mb-2" style={{ background: i === 0 ? "#EF4444" : i === 1 ? "#F59E0B" : "#38BDF8" }} />
                    <p className="text-[11px] text-gray-500 leading-relaxed">{insight}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

// Canonical starter question per agent for "/chat?agent=…" deep links.
const AGENT_PROMPTS: Record<string, string> = {
  compliance: "Are we ready to submit the CBN prudential return for Q1 2026?",
  watchdog: "Give me a summary of all active alerts generated today",
  noc: "What network incidents or outages have been reported today?",
  contracts: "Which vendor contracts expire in the next 90 days?",
  care: "Summarise the MoMo deduction complaints trend in Lagos this quarter",
  field: "Which site visits are outstanding for the Ikeja cluster?",
};

export default function ChatPage() {
  const { messages, isLoading, error, sendMessage, clearChat, loadConversation, conversationId } = useChat();
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [convs, setConvs] = useState<ConvSummary[]>([]);
  const [convsLoading, setConvsLoading] = useState(true);

  // Load the conversation list from the backend (same-origin proxy, cookie auth).
  const refreshConvs = useCallback(async () => {
    try {
      const res = await fetch("/api/atlas/conversations");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const items: ConvSummary[] = (data.conversations ?? []).map(
        (c: { id: string; title: string; updated_at?: string; created_at?: string }) => ({
          id: String(c.id),
          title: c.title || "Untitled conversation",
          updatedAt: c.updated_at ?? c.created_at ?? new Date().toISOString(),
        }),
      );
      setConvs(items);
    } catch {
      // Sidebar list is non-critical — leave whatever we have.
    } finally {
      setConvsLoading(false);
    }
  }, []);

  useEffect(() => { refreshConvs(); }, [refreshConvs]);

  // Deep link: /chat?conv=<id> (via /chat/[id]) loads that conversation.
  useEffect(() => {
    const conv = new URLSearchParams(window.location.search).get("conv");
    if (conv) {
      window.history.replaceState({}, document.title, window.location.pathname);
      loadConversation(conv);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // After a send completes (a new conversation may have been created), refresh the list.
  const prevLoadingRef = useRef(false);
  useEffect(() => {
    if (prevLoadingRef.current && !isLoading) refreshConvs();
    prevLoadingRef.current = isLoading;
  }, [isLoading, refreshConvs]);

  const handleSend = useCallback(async (content: string) => {
    setLastQuery(content);
    setReasoningOpen(true);
    await sendMessage(content);
  }, [sendMessage]);

  const handleSelectConv = useCallback((id: string) => {
    setLastQuery(null);
    setReasoningOpen(false);
    loadConversation(id);
  }, [loadConversation]);

  const handleNew = useCallback(() => {
    clearChat();
    setLastQuery(null);
    setReasoningOpen(false);
  }, [clearChat]);

  // Map hook messages to ChatMessage type for ChatWindow
  const chatMessages = messages.map(m => ({
    id: m.id,
    role: m.role,
    content: m.content,
    reasoning_steps: m.trace?.map(t => ({ agent: t.agent, status: "done" as const, message: t.description, timestamp: t.timestamp })),
    // The backend emits either {document_id, document_title} or {source, excerpt} — accept both.
    citations: m.citations?.map(c => {
      const cc = c as { document_id?: string; document_title?: string; source?: string; excerpt?: string };
      return {
        document_id: cc.document_id ?? cc.source ?? "unknown",
        document_title: cc.document_title ?? cc.source ?? cc.document_id ?? "Source document",
        excerpt: cc.excerpt,
      };
    }),
    timestamp: m.timestamp,
  }));

  return (
    <AppShell title="Iroko Chat" subtitle="Multi-agent enterprise intelligence">
      <div className="flex h-full -m-4 md:-m-6 lg:-m-7 overflow-hidden" style={{ height: "calc(100vh - 64px)" }}>
        {/* Conversation sidebar */}
        <ConvSidebar convs={convs} convsLoading={convsLoading} activeId={conversationId} onSelect={handleSelectConv} onNew={handleNew} />

        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <AgentStatusBar />
          <ChatWindow conversationId={conversationId ?? "new"} messages={chatMessages} isStreaming={isLoading} />

          {/* Error banner — a failed request must never look like a silent freeze */}
          {error && !isLoading && (
            <div className="mx-4 mb-2 flex items-center justify-between gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3">
              <div className="min-w-0">
                <p className="text-[12.5px] font-semibold text-red-300">Iroko couldn&apos;t complete that request</p>
                <p className="text-[11px] text-red-400/80 truncate">{error}</p>
              </div>
              {lastQuery && (
                <button onClick={() => handleSend(lastQuery)}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-[11.5px] font-bold text-white bg-red-500/80 hover:bg-red-500 transition-colors">
                  Retry
                </button>
              )}
            </div>
          )}

          {/* Suggested prompts when empty */}
          {messages.length === 0 && !isLoading && (
            <div className="px-4 pb-2 flex flex-wrap gap-2 justify-center">
              {DEFAULT_SUGGESTED_PROMPTS.map(p => (
                <button key={p.query} onClick={() => handleSend(p.query)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-[12px] font-medium text-gray-500 hover:text-gray-800 border border-border-default hover:border-border-strong bg-surface-card hover:bg-gray-50 transition-all duration-150">
                  {p.label}
                </button>
              ))}
            </div>
          )}

          <InputBar onSend={handleSend} isStreaming={isLoading} autoSendQuery agentPrompts={AGENT_PROMPTS} />
        </div>

        {/* Reasoning panel */}
        <ReasoningPanel
          query={lastQuery}
          open={reasoningOpen}
          onClose={() => setReasoningOpen(false)}
        />

        {/* Toggle reasoning panel button */}
        {!reasoningOpen && lastQuery && (
          <button onClick={() => setReasoningOpen(true)}
            className="fixed right-0 top-1/2 -translate-y-1/2 z-10 flex items-center gap-1.5 px-2.5 py-3 rounded-l-xl text-[10px] font-bold text-brand-500 border border-r-0 border-brand-200 bg-surface-card hover:bg-brand-50 transition-all"
            style={{ writingMode: "vertical-rl" }}>
            Reasoning
          </button>
        )}
      </div>
    </AppShell>
  );
}
