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
}

const MAX_CHARS = 4000;
const CHAR_WARN_THRESHOLD = 500;

export default function InputBar({ onSend, isStreaming, placeholder = "Ask Atlas a question…" }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);

  // Auto-grow textarea (max 5 lines ≈ 120px)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [value]);

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
          "relative flex items-end gap-3 rounded-2xl border bg-[#0F1320] px-4 py-3 transition-all duration-200",
          focused
            ? "border-[#3B7BF6]/60 shadow-[0_0_20px_rgba(59,123,246,0.15)]"
            : "border-white/[0.08]",
          overLimit && "border-red-500/60",
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
            "flex-1 resize-none bg-transparent text-sm text-[#E5E7EB] placeholder-[#4B5563]",
            "outline-none leading-relaxed min-h-[24px] max-h-[120px]",
            "disabled:opacity-60 disabled:cursor-not-allowed",
          )}
        />

        {/* Right side: count + send */}
        <div className="flex items-center gap-2 shrink-0 pb-0.5">
          {showCount && (
            <span className={cn("text-[11px] font-medium", overLimit ? "text-red-400" : "text-[#6B7280]")}>
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
                ? "bg-gradient-to-br from-[#3B7BF6] to-[#2563EB] text-white shadow-[0_0_16px_rgba(59,123,246,0.3)] hover:shadow-[0_0_24px_rgba(59,123,246,0.5)] hover:scale-105 active:scale-95"
                : "bg-white/5 text-[#374151] cursor-not-allowed",
            )}
            title="Send (Ctrl+Enter)"
          >
            {isStreaming ? (
              <Spinner size="sm" color="white" />
            ) : (
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M14 8L2 2l2.5 6L2 14l12-6z" fill="currentColor"/>
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Hint */}
      <p className="text-[10px] text-[#374151] text-center mt-1.5">
        Press <kbd className="px-1 py-0.5 rounded bg-white/5 border border-white/10 text-[9px]">Ctrl+Enter</kbd> to send
      </p>
    </div>
  );
}
