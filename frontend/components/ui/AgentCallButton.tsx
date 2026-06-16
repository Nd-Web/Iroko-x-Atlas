"use client";

import { type AgentCallStatus } from "@/hooks/useAethexAgent";

interface AgentCallButtonProps {
  status:    AgentCallStatus;
  onStart:   () => void;
  onEnd:     () => void;
  className?: string;
}

export default function AgentCallButton({
  status,
  onStart,
  onEnd,
  className = "",
}: AgentCallButtonProps) {
  if (status === "connecting") {
    return (
      <button
        disabled
        className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-[12.5px] font-semibold opacity-70 cursor-not-allowed ${className}`}
        style={{
          background: "rgba(139,92,246,0.1)",
          border:     "1px solid rgba(139,92,246,0.25)",
          color:      "#8B5CF6",
        }}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin">
          <circle cx="7" cy="7" r="5.5" stroke="rgba(139,92,246,0.25)" strokeWidth="2"/>
          <path d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5" stroke="#8B5CF6" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        Connecting…
      </button>
    );
  }

  if (status === "active") {
    return (
      <button
        onClick={onEnd}
        className={`relative flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-[12.5px] font-semibold transition-all duration-200 ${className}`}
        style={{
          background: "rgba(239,68,68,0.12)",
          border:     "1px solid rgba(239,68,68,0.35)",
          color:      "#EF4444",
        }}
      >
        {/* Live pulse */}
        <span className="relative flex h-3 w-3 shrink-0">
          <span
            className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60"
            style={{ backgroundColor: "#EF4444" }}
          />
          <span
            className="relative inline-flex rounded-full h-3 w-3"
            style={{ backgroundColor: "#EF4444" }}
          />
        </span>
        Live — tap to end
      </button>
    );
  }

  if (status === "ending") {
    return (
      <button
        disabled
        className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-[12.5px] font-semibold opacity-50 cursor-not-allowed ${className}`}
        style={{
          background: "rgba(255,255,255,0.04)",
          border:     "1px solid rgba(255,255,255,0.08)",
          color:      "#9CA3AF",
        }}
      >
        Ending…
      </button>
    );
  }

  // idle
  return (
    <button
      onClick={onStart}
      className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-[12.5px] font-semibold transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] ${className}`}
      style={{
        background: "rgba(139,92,246,0.1)",
        border:     "1px solid rgba(139,92,246,0.3)",
        color:      "#8B5CF6",
      }}
    >
      {/* Phone icon */}
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.6 3.39 2 2 0 0 1 3.57 1h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L7.91 8.96a16 16 0 0 0 6.13 6.13l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
      </svg>
      Talk to Compliance Agent
    </button>
  );
}
