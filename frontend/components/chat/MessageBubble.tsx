"use client";
/**
 * components/chat/MessageBubble.tsx
 * Single message bubble — user right-aligned, assistant left-aligned.
 * Uses react-markdown + remark-gfm for proper rendering.
 */
import React, { useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn, formatRelativeTime, getRiskHex, getRiskLabel } from "@/lib/utils";
import { toast } from "sonner";
import type { ChatMessage } from "@/types/chat";

interface Props {
  message: ChatMessage;
  /** The user question this assistant message answered — included in PDF exports. */
  contextQuery?: string;
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

const markdownComponents: React.ComponentProps<typeof ReactMarkdown>["components"] = {
  // Headings
  h1: ({ children }) => (
    <h1 className="text-base font-bold text-white mt-3 mb-1.5 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-sm font-bold text-white mt-3 mb-1 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-[#a5b4fc] mt-2.5 mb-1 first:mt-0">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-xs font-semibold text-[#a5b4fc] mt-2 mb-0.5 first:mt-0">{children}</h4>
  ),

  // Paragraph
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 leading-relaxed text-[#D1D5DB]">{children}</p>
  ),

  // Strong / bold
  strong: ({ children }) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),

  // Emphasis / italic
  em: ({ children }) => (
    <em className="italic text-[#c4b5fd]">{children}</em>
  ),

  // Unordered list
  ul: ({ children }) => (
    <ul className="mb-2 space-y-1 pl-4">{children}</ul>
  ),

  // Ordered list
  ol: ({ children }) => (
    <ol className="mb-2 space-y-1 pl-5 list-decimal">{children}</ol>
  ),

  // List item
  li: ({ children }) => (
    <li className="text-[#D1D5DB] leading-relaxed relative before:content-[''] pl-1">
      <span className="flex gap-2 items-start">
        <span className="mt-[6px] w-1.5 h-1.5 rounded-full bg-[#3B7BF6] shrink-0" />
        <span>{children}</span>
      </span>
    </li>
  ),

  // Override li for ordered lists
  // (react-markdown passes ordered flag via context, handled naturally by ol wrapper)

  // Horizontal rule
  hr: () => (
    <hr className="my-3 border-0 border-t border-white/10" />
  ),

  // Inline code
  code: ({ children, className }) => {
    const isBlock = className?.startsWith("language-");
    if (isBlock) {
      return (
        <pre className="my-2 rounded-lg bg-[#0a0d17] border border-white/10 p-3 overflow-x-auto">
          <code className="text-xs font-mono text-[#a5b4fc]">{children}</code>
        </pre>
      );
    }
    return (
      <code className="px-1 py-0.5 rounded text-[11px] bg-white/10 text-[#a5b4fc] font-mono">
        {children}
      </code>
    );
  },

  // Blockquote
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-[#3B7BF6] pl-3 my-2 text-[#9CA3AF] italic">
      {children}
    </blockquote>
  ),

  // Table
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto rounded-lg border border-white/10">
      <table className="w-full text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-white/5 text-white font-semibold">{children}</thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-white/5">{children}</tbody>
  ),
  tr: ({ children }) => <tr>{children}</tr>,
  th: ({ children }) => (
    <th className="px-3 py-2 text-left text-[11px] font-semibold text-[#a5b4fc]">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-[#D1D5DB]">{children}</td>
  ),

  // Links
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[#3B7BF6] underline hover:text-[#60a5fa] transition-colors"
    >
      {children}
    </a>
  ),
};

export default function MessageBubble({ message, contextQuery }: Props) {
  const isUser = message.role === "user";
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const hasSteps = message.reasoning_steps && message.reasoning_steps.length > 0;
  const contentRef = React.useRef<HTMLDivElement>(null);

  const [exporting, setExporting] = useState(false);

  const handleDownloadPdf = async () => {
    if (exporting) return;
    setExporting(true);

    const toastId = toast.loading("Generating detailed PDF report…");

    try {
      // Use the relative Next.js proxy path instead of hardcoded localhost
      const response = await fetch("/api/v1/pdf/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: contextQuery ?? "Context derived from chat",
          original_response: message.content,
          trace_id: message.id,
          citations: message.citations ?? [],
        })
      });

      if (!response.ok) {
        throw new Error("Failed to generate PDF on backend");
      }

      // Download the binary blob
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `iroko-ai-detailed-report-${Date.now()}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success("PDF report downloaded!", { id: toastId });
    } catch (err) {
      console.error("PDF export failed:", err);
      toast.error("Failed to generate PDF. Please try again.", { id: toastId });
    } finally {
      setExporting(false);
    }
  };


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

      <div className={cn("flex flex-col gap-1 max-w-[78%]", isUser ? "items-end" : "items-start")}>
        {/* Risk badge for assistant */}
        {!isUser && message.risk_score !== undefined && message.risk_score !== null && (
          <RiskBadge score={message.risk_score} />
        )}

        {/* Bubble */}
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm",
            isUser
              ? "bg-gradient-to-br from-[#3B7BF6] to-[#2563EB] text-white rounded-tr-sm shadow-[0_0_20px_rgba(59,123,246,0.2)]"
              : "bg-[#1a1d27] text-[#D1D5DB] border border-white/[0.06] rounded-tl-sm",
          )}
        >
          {isUser ? (
            <span>{message.content}</span>
          ) : (
            <div className="prose-sm max-w-none" ref={contentRef}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Cited sources — chips linking into the document library */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mt-1 max-w-full">
            <span className="text-[10px] font-bold text-[#4B5563] uppercase tracking-wider mr-0.5">Sources</span>
            {message.citations.map((c) => (
              <Link
                key={c.document_id + c.document_title}
                href="/documents"
                title={c.excerpt ?? c.document_title}
                className="inline-flex items-center gap-1 max-w-[220px] px-2 py-1 rounded-lg text-[10.5px] font-semibold text-[#93C5FD] bg-[#3B7BF6]/10 border border-[#3B7BF6]/20 hover:bg-[#3B7BF6]/20 transition-colors"
              >
                <svg width="10" height="10" viewBox="0 0 12 12" fill="none" className="shrink-0">
                  <path d="M7.5 1H3A1.5 1.5 0 0 0 1.5 2.5v7A1.5 1.5 0 0 0 3 11h6A1.5 1.5 0 0 0 10.5 9.5V4l-3-3Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                </svg>
                <span className="truncate">{c.document_title}</span>
              </Link>
            ))}
          </div>
        )}

        {/* Actions row: Reasoning + PDF Export */}
        <div className="flex items-center gap-4 mt-1">
          {hasSteps && (
            <button
              onClick={() => setReasoningOpen(!reasoningOpen)}
              className="text-[11px] text-[#6B7280] hover:text-[#9CA3AF] transition-colors flex items-center gap-1.5"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={cn("transition-transform", reasoningOpen ? "rotate-180" : "")}>
                <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              {reasoningOpen ? "Hide" : "View"} reasoning ({message.reasoning_steps!.length} steps)
            </button>
          )}

          {!isUser && (
            <button
              onClick={handleDownloadPdf}
              disabled={exporting}
              className={cn(
                "text-[11px] flex items-center gap-1.5 transition-all duration-200",
                exporting
                  ? "text-[#3B7BF6] opacity-70 cursor-wait"
                  : "text-[#6B7280] hover:text-[#3B7BF6] cursor-pointer"
              )}
              title="Download as PDF"
            >
              {exporting ? (
                <>
                  <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                  </svg>
                  Generating…
                </>
              ) : (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  Export PDF
                </>
              )}
            </button>
          )}
        </div>

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
