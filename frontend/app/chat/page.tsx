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
import Link from "next/link";

// ── Conversation list sidebar ─────────────────────────────────────────────────

interface ConvSummary { id: string; title: string; updatedAt: string; pinned?: boolean; }

const MOCK_CONVS: ConvSummary[] = [
  { id: "c1", title: "IHS tower lease fee breakdown",             updatedAt: new Date(Date.now() - 120000).toISOString() },
  { id: "c2", title: "NCC QoS quarterly compliance",              updatedAt: new Date(Date.now() - 3600000).toISOString(), pinned: true },
  { id: "c3", title: "Ericsson RAN maintenance SLA analysis",     updatedAt: new Date(Date.now() - 7200000).toISOString() },
  { id: "c4", title: "Ikeja cluster network degradation",         updatedAt: new Date(Date.now() - 86400000).toISOString() },
  { id: "c5", title: "MoMo fraud risk assessment",                updatedAt: new Date(Date.now() - 172800000).toISOString() },
];

function ConvSidebar({ activeId, onSelect, onNew }: {
  activeId: string | null; onSelect: (id: string) => void; onNew: () => void;
}) {
  const [search, setSearch] = useState("");
  const filtered = MOCK_CONVS.filter(c => c.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="w-[280px] shrink-0 flex flex-col border-r border-white/[0.06] h-full" style={{ background: "#08090F" }}>
      {/* Header */}
      <div className="px-4 pt-4 pb-3 space-y-3">
        <button id="new-chat-btn" onClick={onNew}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-bold text-white transition-all hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(59,123,246,0.3)]"
          style={{ background: "linear-gradient(135deg, #3B7BF6, #2563EB)" }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1v12M1 7h12" stroke="white" strokeWidth="2" strokeLinecap="round"/></svg>
          New Chat
        </button>
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]" width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.3"/><path d="M11 11l-2.5-2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search conversations…"
            className="w-full pl-8 pr-3 py-2 text-[12px] bg-white/[0.04] border border-white/[0.08] rounded-lg text-[#D1D5DB] placeholder-[#4B5563] outline-none focus:border-[#3B7BF6]/40 transition-colors" />
        </div>
      </div>
      {/* Conversations */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {filtered.filter(c => c.pinned).length > 0 && (
          <div className="text-[9.5px] font-bold text-[#374151] uppercase tracking-widest px-2 mb-1 mt-2">Pinned</div>
        )}
        {filtered.filter(c => c.pinned).map(c => (
          <ConvItem key={c.id} conv={c} active={activeId === c.id} onClick={() => onSelect(c.id)} />
        ))}
        <div className="text-[9.5px] font-bold text-[#374151] uppercase tracking-widest px-2 mb-1 mt-3">Recent</div>
        {filtered.filter(c => !c.pinned).map(c => (
          <ConvItem key={c.id} conv={c} active={activeId === c.id} onClick={() => onSelect(c.id)} />
        ))}
        {filtered.length === 0 && (
          <p className="text-[11px] text-[#4B5563] text-center py-6">No conversations found</p>
        )}
      </div>
    </div>
  );
}

function ConvItem({ conv, active, onClick }: { conv: ConvSummary; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={cn("w-full text-left px-3 py-2.5 rounded-lg mb-0.5 transition-all duration-150 group",
        active ? "bg-[#3B7BF6]/15 border border-[#3B7BF6]/20" : "hover:bg-white/[0.04] border border-transparent")}>
      <div className={cn("text-[12.5px] font-medium truncate leading-snug", active ? "text-[#E5E7EB]" : "text-[#9CA3AF] group-hover:text-[#D1D5DB]")}>
        {conv.pinned && <span className="mr-1">📌</span>}
        {conv.title}
      </div>
      <div className="text-[10px] text-[#4B5563] mt-0.5">{formatRelativeTime(conv.updatedAt)}</div>
    </button>
  );
}

// ── Reasoning panel ───────────────────────────────────────────────────────────

function ReasoningPanel({ query, open, onClose, recentInsights }: {
  query: string | null; open: boolean; onClose: () => void; recentInsights?: string[];
}) {
  return (
    <div className={cn(
      "shrink-0 border-l border-white/[0.06] flex flex-col transition-all duration-300 overflow-hidden",
      open ? "w-[320px]" : "w-0",
    )} style={{ background: "#08090F" }}>
      {open && (
        <>
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
            <span className="text-[12px] font-bold text-[#E5E7EB] uppercase tracking-wider">
              {query ? "Reasoning Chain" : "Recent Insights"}
            </span>
            <button onClick={onClose} className="w-6 h-6 rounded-md flex items-center justify-center text-[#6B7280] hover:text-white hover:bg-white/5 transition-colors">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            {query ? (
              <ReasoningChain query={query} onComplete={() => {}} onError={() => {}} />
            ) : (
              <div className="space-y-2">
                {["IHS SLA breach detected — severity 8/10", "Contract renewal window opens in 14 days", "NCC QoS threshold exceeded in Abuja zone"].map((insight, i) => (
                  <div key={i} className="p-3 rounded-xl border border-white/[0.06]" style={{ background: "#0F1320" }}>
                    <div className="w-2 h-2 rounded-full mb-2" style={{ background: i === 0 ? "#EF4444" : i === 1 ? "#F59E0B" : "#3B7BF6" }} />
                    <p className="text-[11px] text-[#9CA3AF] leading-relaxed">{insight}</p>
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

export default function ChatPage() {
  const { messages, isLoading, sendMessage, clearChat } = useChat();
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const [lastQuery, setLastQuery] = useState<string | null>(null);

  const handleSend = useCallback(async (content: string) => {
    setLastQuery(content);
    setReasoningOpen(true);
    await sendMessage(content);
  }, [sendMessage]);

  const handleNew = useCallback(() => {
    clearChat();
    setActiveConvId(null);
    setLastQuery(null);
    setReasoningOpen(false);
  }, [clearChat]);

  // Map hook messages to ChatMessage type for ChatWindow
  const chatMessages = messages.map(m => ({
    id: m.id,
    role: m.role,
    content: m.content,
    reasoning_steps: m.trace?.map(t => ({ agent: t.agent, status: "done" as const, message: t.description, timestamp: t.timestamp })),
    timestamp: m.timestamp,
  }));

  return (
    <AppShell title="Atlas Chat" subtitle="Multi-agent enterprise intelligence">
      <div className="flex h-full -m-4 md:-m-6 lg:-m-7 overflow-hidden" style={{ height: "calc(100vh - 64px)" }}>
        {/* Conversation sidebar */}
        <ConvSidebar activeId={activeConvId} onSelect={setActiveConvId} onNew={handleNew} />

        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <AgentStatusBar />
          <ChatWindow conversationId={activeConvId ?? "new"} messages={chatMessages} isStreaming={isLoading} />

          {/* Suggested prompts when empty */}
          {messages.length === 0 && !isLoading && (
            <div className="px-4 pb-2 flex flex-wrap gap-2 justify-center">
              {DEFAULT_SUGGESTED_PROMPTS.map(p => (
                <button key={p.query} onClick={() => handleSend(p.query)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-[12px] font-medium text-[#9CA3AF] hover:text-[#E5E7EB] border border-white/[0.08] hover:border-white/20 bg-white/[0.02] hover:bg-white/[0.05] transition-all duration-150">
                  <span>{p.icon}</span>
                  {p.label}
                </button>
              ))}
            </div>
          )}

          <InputBar onSend={handleSend} isStreaming={isLoading} />
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
            className="fixed right-0 top-1/2 -translate-y-1/2 z-10 flex items-center gap-1.5 px-2.5 py-3 rounded-l-xl text-[10px] font-bold text-[#3B7BF6] border border-r-0 border-[#3B7BF6]/20 hover:bg-[#3B7BF6]/10 transition-all"
            style={{ background: "#0F1320", writingMode: "vertical-rl" }}>
            Reasoning ▶
          </button>
        )}
      </div>
    </AppShell>
  );
}
