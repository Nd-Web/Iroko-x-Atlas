"use client";

import { useRef, useEffect, useState, useCallback, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import { CHAT_MAX_CHARS, shouldSubmitChat } from "@/lib/chat-ux";

interface Props {
  onSend: (content: string) => void;
  isStreaming: boolean;
  onStop?: () => void;
  disabled?: boolean;
  placeholder?: string;
  autoSendQuery?: boolean;
  agentPrompts?: Record<string, string>;
  /** A user-selected suggestion, never an automatic model request. */
  draft?: { text: string; version: number };
}

export default function InputBar({
  onSend, isStreaming, onStop, disabled = false,
  placeholder = "Ask Iroko about your compliance…",
  autoSendQuery = false, agentPrompts, draft,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState("");
  const onSendRef = useRef(onSend);
  useEffect(() => { onSendRef.current = onSend; }, [onSend]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [value]);

  useEffect(() => {
    if (!draft) return;
    // External suggestion selection updates the controlled composer.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setValue(draft.text);
    if (draft.text) textareaRef.current?.focus();
  }, [draft]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q")?.trim();
    const agent = params.get("agent");
    const text = q || (agent ? agentPrompts?.[agent.toLowerCase()] : "");
    if (!text) return;
    params.delete("q");
    params.delete("agent");
    const remaining = params.toString();
    window.history.replaceState({}, document.title,
      `${window.location.pathname}${remaining ? `?${remaining}` : ""}${window.location.hash}`);
    if (q && autoSendQuery && q.length <= CHAT_MAX_CHARS) {
      onSendRef.current(q);
    } else {
      // Browser deep links are only available after mount.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setValue(prev => prev || text);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || disabled || value.length > CHAT_MAX_CHARS) return;
    onSend(trimmed);
    setValue("");
    textareaRef.current?.focus();
  }, [value, isStreaming, disabled, onSend]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (shouldSubmitChat(event)) {
      event.preventDefault();
      handleSend();
    }
  };

  const overLimit = value.length > CHAT_MAX_CHARS;
  const canSend = !!value.trim() && !isStreaming && !disabled && !overLimit;

  return (
    <div className="shrink-0 px-3 pt-2 pb-[max(12px,env(safe-area-inset-bottom))] sm:px-6 sm:pb-4">
      <div className="mx-auto max-w-[960px]">
        <form onSubmit={event => { event.preventDefault(); handleSend(); }}
          className={cn("flex items-end gap-3 rounded-2xl border bg-surface-card p-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.15)] transition-colors focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-50 sm:p-3",
            overLimit ? "border-danger-500" : "border-border-strong")}>
          <textarea ref={textareaRef} value={value} onChange={event => setValue(event.target.value)}
            onKeyDown={handleKeyDown} placeholder={placeholder} rows={1} disabled={disabled}
            aria-label="Your question" aria-describedby="chat-composer-help" aria-invalid={overLimit}
            className="min-h-[24px] max-h-[160px] flex-1 min-w-0 resize-none self-center bg-transparent pl-1 text-[16px] leading-6 text-gray-800 placeholder:text-gray-400 outline-none disabled:opacity-50 sm:text-sm" />
          {isStreaming && onStop ? (
            <button key="stop" type="button" onClick={event => { event.preventDefault(); onStop(); }} aria-label="Stop response" title="Stop response"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border-strong bg-gray-50 text-gray-800 hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-brand-500">
              <span className="h-3.5 w-3.5 rounded-sm bg-current" />
            </button>
          ) : (
            <button key="send" type="submit" id="chat-send-btn" disabled={!canSend} aria-label="Send question" title="Send question (Enter)"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-500 text-[#0A0A0B] transition-colors hover:bg-brand-400 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 19V5m-6 6 6-6 6 6" />
              </svg>
            </button>
          )}
        </form>
        <div id="chat-composer-help" className="mt-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[11px] leading-relaxed text-gray-400">
          <span>{disabled ? "Loading conversation…" : isStreaming ? "Draft your next question while Iroko responds." : "Verify the sources before acting."}</span>
          {value.length >= 1500 ? (
            <span className={cn("shrink-0 tabular-nums", overLimit && "text-danger-400")} role={overLimit ? "alert" : undefined}>
              {value.length.toLocaleString()}/{CHAT_MAX_CHARS.toLocaleString()}{overLimit ? " — shorten your question" : ""}
            </span>
          ) : <span className="hidden shrink-0 sm:inline">Enter to send · Shift + Enter for a new line</span>}
        </div>
      </div>
    </div>
  );
}
