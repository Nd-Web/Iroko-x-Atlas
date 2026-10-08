"use client";

import { useState, useRef, useEffect, useId, type ComponentProps } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn, formatRelativeTime, getRiskHex, getRiskLabel } from "@/lib/utils";
import { toast } from "sonner";
import type { AnswerFeedbackState, ChatMessage } from "@/types/chat";
import { citationUrl } from "@/lib/citation-url";

// Reviewed "not right" answers become evaluation cases, so the reason matters more than a score.
const FEEDBACK_REASONS = [
  { id: "wrong_fact", label: "Wrong or unsupported fact" },
  { id: "missed_part", label: "Missed part of my question" },
  { id: "wrong_document", label: "Used the wrong document" },
  { id: "unclear", label: "Hard to understand" },
  { id: "other", label: "Something else" },
] as const;

function AnswerFeedback({ messageId, initial }: { messageId: string; initial?: AnswerFeedbackState | null }) {
  const [vote, setVote] = useState<AnswerFeedbackState | null>(initial ?? null);
  const [choosingReason, setChoosingReason] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);

  const send = async (helpful: boolean) => {
    if (sending) return;
    setSending(true);
    try {
      const response = await fetch(`/api/atlas/messages/${encodeURIComponent(messageId)}/feedback`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ helpful, reason: helpful ? null : reason, comment: helpful ? null : note.trim() || null }),
      });
      if (!response.ok) throw new Error("Feedback failed");
      setVote({ helpful, reason: helpful ? null : reason });
      setChoosingReason(false);
      toast.success(helpful ? "Thanks for confirming this answer." : "Thanks. This answer will be reviewed to improve Iroko.");
    } catch {
      toast.error("Couldn’t save your feedback. Please try again.");
    } finally {
      setSending(false);
    }
  };

  if (vote && !choosingReason) {
    const label = FEEDBACK_REASONS.find(item => item.id === vote.reason)?.label;
    return <span className="flex min-h-9 items-center gap-2">
      <span>{vote.helpful ? "You marked this answer right" : `You marked this answer not right${label ? `: ${label.toLowerCase()}` : ""}`}</span>
      <button onClick={() => { setVote(null); setReason(null); setNote(""); }} className="underline-offset-2 hover:text-gray-800 hover:underline">Change</button>
    </span>;
  }

  return <div className="flex min-w-0 flex-col gap-2">
    <div className="flex min-h-9 items-center gap-1" role="group" aria-label="Was this answer right?">
      <span className="mr-1">Was this answer right?</span>
      <button onClick={() => void send(true)} disabled={sending} aria-label="Yes, this answer was right"
        className="rounded-md px-2 py-1 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-50">👍 Yes</button>
      <button onClick={() => setChoosingReason(true)} disabled={sending} aria-label="No, this answer was not right" aria-expanded={choosingReason}
        className="rounded-md px-2 py-1 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-50">👎 No</button>
    </div>
    {choosingReason && <div className="rounded-xl border border-border-default bg-surface-card p-3 text-xs text-gray-600">
      <p className="mb-2 font-medium text-gray-700">What was wrong?</p>
      <div className="mb-2 flex flex-wrap gap-2">
        {FEEDBACK_REASONS.map(item => <button key={item.id} onClick={() => setReason(item.id)} aria-pressed={reason === item.id}
          className={cn("rounded-lg border px-2.5 py-1.5", reason === item.id ? "border-brand-300 bg-brand-50 text-brand-600" : "border-border-default hover:border-brand-200")}>{item.label}</button>)}
      </div>
      <label className="sr-only" htmlFor={`feedback-note-${messageId}`}>What should the answer have said? (optional)</label>
      <textarea id={`feedback-note-${messageId}`} value={note} onChange={event => setNote(event.target.value)} maxLength={1000} rows={2}
        placeholder="What should the answer have said? (optional)"
        className="w-full resize-none rounded-lg border border-border-default bg-surface-page/40 p-2 text-xs text-gray-700 outline-none focus:border-brand-300" />
      <div className="mt-2 flex gap-2">
        <button onClick={() => void send(false)} disabled={sending || !reason}
          className="rounded-lg bg-brand-500 px-3 py-1.5 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">{sending ? "Sending…" : "Send feedback"}</button>
        <button onClick={() => setChoosingReason(false)} className="rounded-lg px-3 py-1.5 hover:text-gray-800">Cancel</button>
      </div>
    </div>}
  </div>;
}

interface Props {
  message: ChatMessage;
  contextQuery?: string;
  isStreaming?: boolean;
  compact?: boolean;
}

const markdownComponents: ComponentProps<typeof ReactMarkdown>["components"] = {
  h1: ({ children }) => <h2 className="mb-3 mt-6 text-lg font-semibold leading-snug text-gray-900 first:mt-0">{children}</h2>,
  h2: ({ children }) => <h2 className="mb-3 mt-6 text-base font-semibold leading-snug text-gray-900 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-2 mt-5 text-sm font-semibold text-gray-900 first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-2 mt-4 font-semibold text-gray-900">{children}</h4>,
  p: ({ children }) => <p className="mb-3 leading-6 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 marker:text-brand-500">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 marker:text-gray-500">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-6 [&>p]:mb-1">{children}</li>,
  hr: () => <hr className="my-6 border-border-default" />,
  pre: ({ children }) => <pre className="my-4 max-w-full overflow-x-auto rounded-xl border border-border-default bg-surface-card p-4 text-xs leading-relaxed">{children}</pre>,
  code: ({ children, className }) => <code className={cn("break-words font-mono text-info-700", className || "rounded bg-gray-50 px-1 py-0.5 text-[12px]")}>{children}</code>,
  blockquote: ({ children }) => <blockquote className="my-4 border-l-2 border-brand-300 pl-4 text-gray-500">{children}</blockquote>,
  table: ({ children }) => <div className="my-4 max-w-full overflow-x-auto rounded-xl border border-border-default"><table className="w-full min-w-[440px] text-xs">{children}</table></div>,
  thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
  tbody: ({ children }) => <tbody className="divide-y divide-border-default">{children}</tbody>,
  th: ({ children }) => <th className="px-4 py-3 text-left font-semibold text-gray-800">{children}</th>,
  td: ({ children }) => <td className="px-4 py-3 align-top leading-relaxed">{children}</td>,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="break-words text-info-700 underline decoration-info-500/40 underline-offset-4 hover:decoration-info-500">{children}</a>,
};

export default function MessageBubble({ message, contextQuery, isStreaming = false, compact = false }: Props) {
  const isUser = message.role === "user";
  const isConversational = message.answer_status === "conversational";
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [hasOverflow, setHasOverflow] = useState(false);
  const answerRef = useRef<HTMLDivElement>(null);
  const answerId = useId();

  useEffect(() => {
    const content = answerRef.current;
    if (!content || !compact) return;
    const measure = () => {
      const previewHeight = Math.min(240, Math.max(120, window.innerHeight * 0.26));
      setHasOverflow(content.scrollHeight > previewHeight + 4);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(content);
    window.addEventListener("resize", measure);
    return () => { observer.disconnect(); window.removeEventListener("resize", measure); };
  }, [compact, message.content]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
    } catch {
      toast.error("Couldn’t copy. Select the answer text to copy it.");
    }
  };

  const handleDownloadPdf = async () => {
    if (exporting || isStreaming) return;
    setExporting(true);
    const toastId = toast.loading("Generating PDF report…");
    try {
      const response = await fetch("/api/v1/pdf/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: contextQuery ?? "Context derived from chat", original_response: message.content, trace_id: message.id, citations: message.citations ?? [] }),
      });
      if (!response.ok) throw new Error("Failed to generate PDF");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "iroko-ai-report-" + Date.now() + ".pdf";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      toast.success("PDF report downloaded", { id: toastId });
    } catch {
      toast.error("Couldn’t generate the PDF. Please try again.", { id: toastId });
    } finally {
      setExporting(false);
    }
  };

  if (isUser) return (
    <article className="flex justify-end" aria-label="Your question">
      <div className="max-w-[95%] rounded-2xl rounded-tr-md border border-brand-200 bg-brand-50 px-4 py-2.5 text-[13px] leading-6 text-gray-800 sm:max-w-[85%]">
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
      </div>
    </article>
  );

  return (
    <article aria-label="Iroko answer" className={cn("min-w-0", compact && "rounded-2xl border border-border-default bg-surface-card/70 p-4 sm:p-5 shadow-[0_4px_24px_rgba(0,0,0,0.08)]")}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-brand-200 bg-brand-50 text-brand-500" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </span>
        <span className="text-xs font-semibold text-gray-700">Iroko</span>
        <span className="text-[10px] text-gray-400">{formatRelativeTime(message.timestamp)}</span>
        {message.risk_score != null && <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ color: getRiskHex(message.risk_score), background: getRiskHex(message.risk_score) + "20" }}>{getRiskLabel(message.risk_score)} · {message.risk_score}/10</span>}
        {message.interrupted && <span className="text-[11px] text-warning-700">Stopped · incomplete answer</span>}
        {compact && hasOverflow && !isStreaming && <button onClick={() => setExpanded(value => !value)} aria-expanded={expanded} aria-controls={answerId} className="ml-auto min-h-8 rounded-lg border border-border-default px-2.5 text-[11px] font-medium text-gray-600 hover:border-brand-200 hover:text-brand-500">{expanded ? "Collapse answer ↑" : "Read full answer ↗"}</button>}
      </div>
      {compact && hasOverflow && !expanded && <p className="sr-only">Earlier answer collapsed. Select Read full answer to read it.</p>}
      <div id={answerId} className={cn("relative min-w-0 overflow-hidden", compact && !expanded && "max-h-[clamp(120px,26dvh,240px)]")}
        inert={compact && hasOverflow && !expanded ? true : undefined}>
      <div ref={answerRef} className="min-w-0 break-words text-[13px] leading-6 text-gray-700 sm:text-[14px]">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.content}</ReactMarkdown>
      </div>
      {compact && hasOverflow && !expanded && <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-8 bg-linear-to-t from-surface-card to-transparent" />}
      </div>
      {compact && hasOverflow && !expanded && <p className="mt-3 flex flex-wrap items-center gap-x-2 rounded-lg border border-border-default bg-surface-page/40 px-3 py-2 text-[11px] leading-relaxed text-gray-500"><span className="font-medium text-brand-500">Preview</span>{isStreaming ? "The answer is still arriving." : "Open the full answer for all details and limitations."}</p>}

      {!!message.citations?.length && !isStreaming && <details className="group mt-3 rounded-xl border border-border-default bg-surface-page/50">
        <summary className="cursor-pointer px-3 py-2.5 text-[11px] font-medium text-gray-600 marker:text-brand-500">Sources checked <span className="ml-1 text-gray-400">({message.citations.length})</span></summary>
        <div className="space-y-3 border-t border-border-default p-4">
          <p className="text-[11px] leading-relaxed text-gray-400">Inspect the source context and applicability before relying on an answer.</p>
          {message.citations.map((source, index) => {
            const href = citationUrl(source.source_url);
            return <div key={source.document_id + index} className="rounded-lg border border-border-default p-3">
              <Link href={href ?? "/documents"} target={href ? "_blank" : undefined} rel={href ? "noopener noreferrer" : undefined}
                className="flex items-start gap-2 text-xs font-medium leading-relaxed text-info-700 hover:underline">
                <span className="shrink-0 text-gray-400">[{index + 1}]</span><span className="min-w-0 break-words">{source.document_title}</span><span aria-hidden="true" className="ml-auto shrink-0">↗</span>
              </Link>
              {source.excerpt && <blockquote className="mt-2 whitespace-pre-wrap break-words border-l border-border-strong pl-3 text-xs leading-relaxed text-gray-500">{source.excerpt}</blockquote>}
              <p className="mt-2 text-[10px] text-gray-400">{href ? new URL(href).hostname : "Open document library"}</p>
            </div>;
          })}
        </div>
      </details>}

      {!isStreaming && <div className="mt-2 flex flex-wrap items-start gap-x-4 gap-y-1 text-[11px] text-gray-400">
        <button onClick={handleCopy} title="Copy the complete answer, including content beyond the preview" onBlur={() => setCopied(false)} className="min-h-9 hover:text-gray-800">{copied ? "Copied ✓" : "Copy answer"}</button>
        {!isConversational && !message.interrupted && <button onClick={handleDownloadPdf} disabled={exporting} className="min-h-9 hover:text-gray-800 disabled:cursor-wait disabled:opacity-50">{exporting ? "Preparing PDF…" : "Export PDF"}</button>}
        {!isConversational && !message.interrupted && message.message_id && <AnswerFeedback key={message.message_id} messageId={message.message_id} initial={message.feedback} />}
        {!isConversational && !!message.reasoning_steps?.length && <details className="min-w-0 flex-1">
          <summary className="min-h-9 cursor-pointer py-2.5 hover:text-gray-800">View activity ({message.reasoning_steps.length})</summary>
          <div className="mt-2 space-y-3 rounded-xl border border-border-default bg-surface-card p-4">
            {message.reasoning_steps.map((step, index) => <div key={index} className="flex gap-3 text-xs">
              <span className="mt-0.5 text-gray-400">{index + 1}</span>
              <div className="min-w-0"><p className="font-medium text-brand-500">{step.agent.replace("Agent", "")}</p><p className="mt-1 break-words leading-relaxed text-gray-500">{step.message}</p></div>
            </div>)}
          </div>
        </details>}
      </div>}
    </article>
  );
}
