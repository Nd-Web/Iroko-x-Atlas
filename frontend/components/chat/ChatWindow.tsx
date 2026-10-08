"use client";

import { useRef, useEffect, useState } from "react";
import MessageBubble from "./MessageBubble";
import { DEFAULT_SUGGESTED_PROMPTS, type ChatMessage } from "@/types/chat";
import { isNearChatBottom, splitLatestExchange } from "@/lib/chat-ux";
import { cn } from "@/lib/utils";

interface Props {
  conversationId: string;
  messages: ChatMessage[];
  isStreaming: boolean;
  isLoadingHistory?: boolean;
  progress?: string;
  onPrompt?: (text: string) => void;
  compact?: boolean;
}

function ResponseProgress({ progress, writing }: { progress?: string; writing: boolean }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="rounded-xl border border-border-default bg-surface-card/60 p-3">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500 motion-reduce:animate-none" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p role="status" className="text-sm leading-relaxed text-gray-700">{writing ? "Writing your answer…" : progress || "Checking the available evidence…"}</p>
          {seconds >= 45 && <p className="mt-2 text-xs leading-relaxed text-gray-500">This check is taking longer. You can stop it and refine your question.</p>}
        </div>
        <span aria-hidden="true" className="shrink-0 text-[11px] tabular-nums text-gray-400">{seconds}s</span>
      </div>
    </div>
  );
}

function EmptyState({ onPrompt }: { onPrompt?: (text: string) => void }) {
  const labels = ["Regulations", "My documents", "Recent changes", "Compliance risks"];
  return (
    <div className="mx-auto w-full max-w-[960px] py-3 sm:py-5">
      <div className="mb-3 flex items-center gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-brand-200 bg-brand-50 text-brand-500 shadow-[0_0_24px_rgba(110,231,183,0.06)]">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" strokeLinecap="round" strokeLinejoin="round"/></svg>
      </div>
      <div><p className="mb-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-brand-500">Compliance workspace</p><h1 className="text-[26px] font-semibold leading-none tracking-tight text-gray-900 sm:text-[30px]">Ask Iroko</h1></div>
      </div>
      <p className="text-[13px] leading-6 text-gray-500">Your documents. Official sources. Clearer answers.</p>
      {onPrompt && <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
        {DEFAULT_SUGGESTED_PROMPTS.map((prompt, index) => (
          <button key={prompt.label} onClick={() => onPrompt(prompt.query)} aria-label={prompt.label} title={prompt.query} className="group flex min-h-[52px] items-center gap-2 rounded-xl border border-border-default bg-surface-card/80 px-3 py-2.5 text-left transition-colors hover:border-brand-200 hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-brand-500">
            <svg className="hidden shrink-0 text-brand-500 sm:block" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d={index === 0 ? "M6 4h12v16H6zM9 8h6m-6 4h6m-6 4h4" : index === 1 ? "M3 6h7l2 2h9v12H3z" : index === 2 ? "M3 12a9 9 0 1 0 3-7M3 3v6h6m3-3v6l3 2" : "m12 3 8 4v5c0 5-8 9-8 9s-8-4-8-9V7l8-4Zm-3 9 2 2 4-4"} strokeLinecap="round" strokeLinejoin="round"/></svg>
            <span className="flex-1 text-[12px] font-medium leading-snug text-gray-700 group-hover:text-gray-900">{labels[index]}</span>
            <span aria-hidden="true" className="text-gray-400 group-hover:text-brand-500">↗</span>
          </button>
        ))}
      </div>}
    </div>
  );
}

export default function ChatWindow({ conversationId, messages, isStreaming, isLoadingHistory = false, progress, onPrompt, compact = false }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const previousConversationRef = useRef(conversationId);
  const previousUserRef = useRef<string | undefined>(undefined);
  const [showJump, setShowJump] = useState(false);
  const [expandedHistoryFor, setExpandedHistoryFor] = useState<string | null>(null);

  useEffect(() => {
    const lastUser = [...messages].reverse().find(message => message.role === "user");
    if (previousConversationRef.current !== conversationId || previousUserRef.current !== lastUser?.id) {
      pinnedRef.current = true;
      previousConversationRef.current = conversationId;
      previousUserRef.current = lastUser?.id;
    }
    if (!messages.length && scrollerRef.current) {
      scrollerRef.current.scrollTop = 0;
      return;
    }
    if (pinnedRef.current && scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [conversationId, messages, progress, isStreaming]);

  useEffect(() => {
    const content = contentRef.current;
    if (!content || !isStreaming) return;
    const observer = new ResizeObserver(() => {
      if (pinnedRef.current && scrollerRef.current) scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, [isStreaming]);

  const latest = messages[messages.length - 1];
  const exchange = splitLatestExchange(messages);
  const exchangeKey = exchange.current[0]?.id ?? "new";
  const historyOpen = expandedHistoryFor === exchangeKey;
  const visible = (compact && !historyOpen ? exchange.current : messages).filter(message => message.content.trim());
  const empty = !messages.length && !isStreaming && !isLoadingHistory;
  const followups = !isStreaming && !isLoadingHistory && latest?.role === "assistant" && !latest.interrupted
    ? latest.suggested_followups?.filter(text => !!text.trim()).slice(0, 3) : [];

  return (
    <div className={cn("relative flex min-h-0 flex-col", empty ? "shrink-0" : "flex-1")}>
      <div ref={scrollerRef} data-chat-scroll tabIndex={0} aria-label="Conversation messages"
        onScroll={() => {
          if (!scrollerRef.current) return;
          pinnedRef.current = isNearChatBottom(scrollerRef.current);
          setShowJump(!pinnedRef.current);
        }}
        className={cn("min-h-0 overscroll-contain px-4 sm:px-6", empty ? "overflow-visible" : "flex-1 overflow-y-auto")}>
        <div ref={contentRef} className={cn("mx-auto w-full max-w-[960px]", !empty && "min-h-full py-4")}>
          {isLoadingHistory ? (
            <div role="status" className="flex min-h-[260px] items-center justify-center gap-3 text-sm text-gray-500"><span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500 motion-reduce:animate-none" aria-hidden="true" />Loading conversation…</div>
          ) : !messages.length && !isStreaming ? (
            <EmptyState onPrompt={onPrompt} />
          ) : (
            <div className="space-y-4">
              {compact && exchange.previous.length > 0 && <button aria-expanded={historyOpen} onClick={() => {
                pinnedRef.current = false;
                setExpandedHistoryFor(historyOpen ? null : exchangeKey);
              }} className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-border-default py-2 text-[11px] text-gray-500 hover:border-brand-200 hover:text-gray-700">
                {historyOpen ? "Hide earlier messages" : "Show earlier messages"}<span className="rounded-full bg-gray-50 px-2 py-0.5 tabular-nums text-gray-400">{exchange.previous.length}</span><span aria-hidden="true">{historyOpen ? "↑" : "↓"}</span>
              </button>}
              {visible.map(message => {
                const originalIndex = messages.findIndex(item => item.id === message.id);
                const previousQuestion = messages.slice(0, originalIndex).reverse().find(item => item.role === "user");
                return <MessageBubble key={message.id} message={message} contextQuery={previousQuestion?.content}
                  isStreaming={isStreaming && message.id === latest?.id} compact={compact && message.id !== latest?.id} />;
              })}
              {isStreaming && <ResponseProgress progress={progress} writing={!!latest?.content} />}
              {!!followups?.length && onPrompt && <div className="flex flex-wrap gap-2">
                {followups.map(text => <button key={text} title={text} onClick={() => onPrompt(text)} className="max-w-full truncate rounded-lg border border-border-default px-3 py-2 text-left text-[11px] text-gray-500 hover:border-brand-200 hover:text-gray-800 sm:max-w-[300px]">{text} <span aria-hidden="true" className="ml-1 text-brand-500">↗</span></button>)}
              </div>}
            </div>
          )}
        </div>
      </div>
      {showJump && !!messages.length && <button onClick={() => {
        pinnedRef.current = true;
        setShowJump(false);
        if (scrollerRef.current) scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
      }} className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full border border-border-strong bg-surface-card px-4 py-2.5 text-xs font-medium text-gray-700 shadow-md hover:text-gray-900">↓ Latest message</button>}
    </div>
  );
}
