"use client";
/**
 * components/chat/InputBar.tsx
 * Chat input bar with auto-grow textarea, Ctrl+Enter send, character count.
 */
import React, { useRef, useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import Spinner from "@/components/ui/Spinner";

interface Props {
  onSend: (content: string) => void;
  isStreaming: boolean;
  placeholder?: string;
  /** When true, a `?q=` query param is sent immediately instead of prefilled. */
  autoSendQuery?: boolean;
  /** Maps `?agent=<name>` deep links to a canonical starter question (prefilled). */
  agentPrompts?: Record<string, string>;
}

const MAX_CHARS = 4000;
const CHAR_WARN_THRESHOLD = 500;

export default function InputBar({
  onSend,
  isStreaming,
  placeholder = "Ask Iroko a question…",
  autoSendQuery = false,
  agentPrompts,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const onSendRef = useRef(onSend);
  onSendRef.current = onSend;

  // Auto-grow textarea (max 5 lines ≈ 120px)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [value]);

  // Handle deep-link params: `?q=` (prefill, or auto-send when enabled) and
  // `?agent=` (prefill that agent's canonical starter question).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q");
    const agent = params.get("agent");
    const agentPrompt =
      !q && agent && agentPrompts
        ? agentPrompts[agent.toLowerCase()] ?? null
        : null;
    if (q || agentPrompt) {
      window.history.replaceState({}, document.title, window.location.pathname);
      if (q && autoSendQuery) {
        onSendRef.current(q.trim());
      } else {
        setValue((prev) => prev || (q ?? agentPrompt ?? ""));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || trimmed.length > MAX_CHARS) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [value, isStreaming, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = value.trim().length > 0 && !isStreaming && value.length <= MAX_CHARS;
  const overLimit = value.length > MAX_CHARS;
  const showCount = value.length >= CHAR_WARN_THRESHOLD;

  return (
    <div className="px-4 pb-4 pt-2 shrink-0">
      <div
        className={cn(
          "relative flex items-end gap-3 rounded-2xl border bg-white px-4 py-3 transition-all duration-200",
          focused
            ? "border-brand-500 shadow-sm"
            : "border-border-strong shadow-xs",
          overLimit && "border-danger-500",
        )}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          disabled={isStreaming}
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-300",
            "outline-none leading-relaxed min-h-[24px] max-h-[120px]",
            "disabled:opacity-60 disabled:cursor-not-allowed",
          )}
        />

        {/* Right side: count + send */}
        <div className="flex items-center gap-2 shrink-0 pb-0.5">
          {showCount && (
            <span className={cn("text-[11px] font-medium", overLimit ? "text-danger-600" : "text-gray-400")}>
              {value.length}/{MAX_CHARS}
            </span>
          )}
          <button
            id="chat-send-btn"
            onClick={handleSend}
            disabled={!canSend}
            className={cn(
              "w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-200",
              canSend
                ? "bg-brand-600 text-white shadow-xs hover:bg-brand-700 hover:shadow-sm hover:scale-105 active:scale-95"
                : "bg-gray-100 text-gray-300 cursor-not-allowed",
            )}
            title="Send (Ctrl+Enter)"
            aria-label="Send message"
          >
            {isStreaming ? (
              <Spinner size="sm" className="text-white" />
            ) : (
              <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M14 8L2 2l2.5 6L2 14l12-6z" fill="currentColor"/>
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Hint */}
      <p className="text-[10px] text-gray-400 text-center mt-1.5">
        Press <kbd className="px-1 py-0.5 rounded bg-gray-100 border border-border-default text-[9px] text-gray-500">Ctrl+Enter</kbd> to send
      </p>
    </div>
  );
}
