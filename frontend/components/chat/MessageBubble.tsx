"use client";
/**
 * components/chat/MessageBubble.tsx
 * Single message bubble — user right-aligned, assistant left-aligned.
 */
import React, { useState } from "react";
import { cn, formatRelativeTime, getRiskHex, getRiskLabel } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";

interface Props {
  message: ChatMessage;
}

function RiskBadge({ score }: { score: number }) {
  const hex = getRiskHex(score);
  const label = getRiskLabel(score);
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold"
      style={{ background: `${hex}20`, color: hex, border: `1px solid ${hex}40` }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: hex }} />
      {label} · {score}/10
    </span>
  );
}

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // Code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      nodes.push(
        <pre key={i} className="my-2 rounded-lg bg-[#0a0d17] border border-white/10 p-3 overflow-x-auto">
          <code className="text-xs font-mono text-[#a5b4fc]">{codeLines.join("\n")}</code>
        </pre>
      );
    } else {
      // Inline formatting: **bold**, `code`
      const parts = line.split(/(\*\*.*?\*\*|`[^`]+`)/g).map((p, idx) => {
        if (p.startsWith("**") && p.endsWith("**"))
          return <strong key={idx} className="font-semibold text-white">{p.slice(2, -2)}</strong>;
        if (p.startsWith("`") && p.endsWith("`"))
          return <code key={idx} className="px-1 py-0.5 rounded text-[11px] bg-white/10 text-[#a5b4fc] font-mono">{p.slice(1, -1)}</code>;
        return p;
      });
      if (parts.some(p => p !== "")) {
        nodes.push(<p key={i} className="mb-1 last:mb-0 leading-relaxed">{parts}</p>);
      } else {
        nodes.push(<br key={i} />);
      }
    }
    i++;
  }
  return nodes;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const hasSteps = message.reasoning_steps && message.reasoning_steps.length > 0;

  return (
    <div className={cn("flex gap-3 max-w-full", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#3B7BF6] to-[#8B5CF6] flex items-center justify-center shrink-0 mt-1 shadow-[0_0_12px_rgba(59,123,246,0.4)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      )}

      <div className={cn("flex flex-col gap-1 max-w-[75%]", isUser ? "items-end" : "items-start")}>
        {/* Risk badge for assistant */}
        {!isUser && message.risk_score !== undefined && message.risk_score !== null && (
          <RiskBadge score={message.risk_score} />
        )}

        {/* Bubble */}
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-gradient-to-br from-[#3B7BF6] to-[#2563EB] text-white rounded-tr-sm shadow-[0_0_20px_rgba(59,123,246,0.2)]"
              : "bg-[#1a1d27] text-[#D1D5DB] border border-white/[0.06] rounded-tl-sm",
          )}
        >
          {isUser ? (
            <span>{message.content}</span>
          ) : (
            <div className="space-y-0.5">{renderMarkdown(message.content)}</div>
          )}
        </div>

        {/* Reasoning steps toggle */}
        {hasSteps && (
          <button
            onClick={() => setReasoningOpen(!reasoningOpen)}
            className="text-[11px] text-[#6B7280] hover:text-[#9CA3AF] transition-colors flex items-center gap-1"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={cn("transition-transform", reasoningOpen ? "rotate-180" : "")}>
              <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            {reasoningOpen ? "Hide" : "View"} reasoning ({message.reasoning_steps!.length} steps)
          </button>
        )}

        {/* Reasoning steps inline */}
        {hasSteps && reasoningOpen && (
          <div className="w-full space-y-1.5 mt-1">
            {message.reasoning_steps!.map((step, i) => (
              <div
                key={i}
                className="flex items-start gap-2 px-3 py-2 rounded-lg bg-[#0F1320] border border-white/[0.05] text-xs"
              >
                <span className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold bg-[#8B5CF6]/20 text-[#8B5CF6]">{i + 1}</span>
                <div>
                  <span className="font-semibold text-[#8B5CF6]">{step.agent.replace("Agent","")}: </span>
                  <span className="text-[#9CA3AF]">{step.message}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-[#4B5563]">{formatRelativeTime(message.timestamp)}</span>
      </div>
    </div>
  );
}
