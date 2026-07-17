"use client";

interface VoiceMicButtonProps {
  isListening:  boolean;
  isProcessing: boolean;
  onStart:      () => void;
  onStop:       () => void;
  className?:   string;
}

export default function VoiceMicButton({
  isListening,
  isProcessing,
  onStart,
  onStop,
  className = "",
}: VoiceMicButtonProps) {
  if (isProcessing) {
    return (
      <button
        disabled
        className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-[12.5px] font-semibold opacity-60 cursor-not-allowed ${className}`}
        style={{
          background: "rgba(255,255,255,0.04)",
          border:     "1px solid rgba(255,255,255,0.08)",
          color:      "#9C9CA6",
        }}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin">
          <circle cx="7" cy="7" r="5.5" stroke="rgba(255,255,255,0.2)" strokeWidth="2"/>
          <path d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5" stroke="#9C9CA6" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        Checking…
      </button>
    );
  }

  if (isListening) {
    return (
      <button
        onClick={onStop}
        className={`relative flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-[12.5px] font-semibold transition-all duration-200 ${className}`}
        style={{
          background: "rgba(239,68,68,0.12)",
          border:     "1px solid rgba(239,68,68,0.35)",
          color:      "#EF4444",
        }}
      >
        {/* Pulse ring */}
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
        Listening… tap to stop
      </button>
    );
  }

  return (
    <button
      onClick={onStart}
      className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-[12.5px] font-semibold transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] ${className}`}
      style={{
        background: "rgba(16,185,129,0.1)",
        border:     "1px solid rgba(16,185,129,0.3)",
        color:      "#10B981",
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
        <line x1="8"  y1="23" x2="16" y2="23"/>
      </svg>
      Speak to check
    </button>
  );
}
