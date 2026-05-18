"use client";
/**
 * components/chat/ChatWindow.tsx
 * Full chat window with auto-scroll, typing indicator, and message list.
 */
import React, { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import type { ChatMessage } from "@/types/chat";

interface Props {
  conversationId: string;
  messages: ChatMessage[];
  isStreaming: boolean;
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 items-start">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#3B7BF6] to-[#8B5CF6] flex items-center justify-center shrink-0 shadow-[0_0_12px_rgba(59,123,246,0.4)]">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div className="bg-[#1a1d27] border border-white/[0.06] rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-2 h-2 rounded-full bg-[#3B7BF6]"
            style={{ animation: `bounce 1.4s ease-in-out ${i * 0.2}s infinite` }}
          />
        ))}
      </div>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 py-12">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#3B7BF6]/20 to-[#8B5CF6]/20 border border-white/10 flex items-center justify-center">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#3B7BF6" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div className="text-center">
        <p className="text-[15px] font-semibold text-[#E5E7EB]">Ask Atlas anything</p>
        <p className="text-[13px] text-[#6B7280] mt-1 max-w-xs">
          Your enterprise AI is ready. Query documents, analyse contracts, or investigate network alerts.
        </p>
      </div>
    </div>
  );
}

export default function ChatWindow({ conversationId, messages, isStreaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isStreaming]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
      {messages.length === 0 && !isStreaming ? (
        <EmptyState />
      ) : (
        <>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isStreaming && <TypingIndicator />}
        </>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
