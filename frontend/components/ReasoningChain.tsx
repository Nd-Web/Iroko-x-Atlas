"use client";
/**
 * components/ReasoningChain.tsx
 *
 * Vertical pipeline diagram — live circuit board aesthetic.
 * Each agent step is a node connected by an animated glowing line.
 *
 * FIXES (May 2026):
 *  1. Calls /api/atlas/ask/stream (Next.js proxy) — not the backend directly.
 *     The proxy reads the httpOnly cookie server-side, so no auth header needed.
 *  2. Removed getStoredToken() / Authorization header — the JWT is httpOnly and
 *     cannot be read by JS. The Next.js proxy at /api/atlas/ask/stream handles auth.
 *  3. Event parsing now matches the backend's actual SSE format:
 *       {type:"start"}  → show initialising state
 *       {type:"agent_action", agent, tool, description} → pipeline step
 *       {type:"token", content} → streaming token (collected into answer)
 *       {type:"complete", answer, agent_trace, citations, suggested_followups} → done
 *       {type:"error", message} → show error
 */
import { useState, useEffect, useRef, useCallback } from "react";

interface AgentStep {
  agent: string;
  status: "thinking" | "done" | "handoff";
  message: string;
  timestamp: string;
}
interface FinalResult {
  type: "final";
  response: string;
  risk_score: number;
  citations?: unknown[];
  reasoning_steps?: AgentStep[];
}
interface Props {
  query: string;
  onComplete: (response: string, riskScore: number) => void;
  onError: () => void;
}

const AGENT_META: Record<string, { color: string; bg: string; icon: JSX.Element; label: string }> = {
  Watchdog: {
    color: "#EF4444", bg: "rgba(239,68,68,0.08)", label: "Watchdog",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  },
  WatchdogAgent: {
    color: "#EF4444", bg: "rgba(239,68,68,0.08)", label: "Watchdog",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  },
  Researcher: {
    color: "#3B7BF6", bg: "rgba(59,123,246,0.08)", label: "Researcher",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>,
  },
  ResearcherAgent: {
    color: "#3B7BF6", bg: "rgba(59,123,246,0.08)", label: "Researcher",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>,
  },
  Analyst: {
    color: "#8B5CF6", bg: "rgba(139,92,246,0.08)", label: "Analyst",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>,
  },
  AnalystAgent: {
    color: "#8B5CF6", bg: "rgba(139,92,246,0.08)", label: "Analyst",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>,
  },
  Strategist: {
    color: "#F59E0B", bg: "rgba(245,158,11,0.08)", label: "Strategist",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3zM14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3z"/></svg>,
  },
  StrategistAgent: {
    color: "#F59E0B", bg: "rgba(245,158,11,0.08)", label: "Strategist",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3zM14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3z"/></svg>,
  },
  Scribe: {
    color: "#10B981", bg: "rgba(16,185,129,0.08)", label: "Scribe",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>,
  },
  ScribeAgent: {
    color: "#10B981", bg: "rgba(16,185,129,0.08)", label: "Scribe",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>,
  },
};
const DEFAULT_META = {
  color: "#9CA3AF", bg: "rgba(156,163,175,0.08)", label: "Agent",
  icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/></svg>,
};

function PipelineNode({ step, index, isLast, active }: { step: AgentStep; index: number; isLast: boolean; active: boolean }) {
  const meta = AGENT_META[step.agent] ?? DEFAULT_META;
  const isDone = step.status === "done";
  const isThinking = step.status === "thinking";

  return (
    <div className="flex gap-3">
      {/* Connector column */}
      <div className="flex flex-col items-center" style={{ width: 32 }}>
        {/* Node circle */}
        <div
          className="relative w-8 h-8 rounded-full flex items-center justify-center shrink-0 z-10 transition-all duration-500"
          style={{
            background: isDone ? `${meta.color}25` : isThinking ? `${meta.color}15` : "rgba(255,255,255,0.04)",
            border: `2px solid ${isDone ? meta.color : isThinking ? meta.color : "rgba(255,255,255,0.1)"}`,
            boxShadow: isThinking ? `0 0 16px ${meta.color}60` : isDone ? `0 0 8px ${meta.color}30` : "none",
          }}
        >
          <span style={{ color: isDone || isThinking ? meta.color : "#6B7280" }}>
            {isDone ? (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke={meta.color} strokeWidth="1.5"/>
                <path d="M4 7l2 2 4-4" stroke={meta.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            ) : isThinking ? (
              <span className="animate-spin block w-3.5 h-3.5 rounded-full"
                style={{ border: `2px solid transparent`, borderTopColor: meta.color, borderRightColor: meta.color }} />
            ) : meta.icon}
          </span>
        </div>
        {/* Connector line */}
        {!isLast && (
          <div className="flex-1 w-px my-1 transition-all duration-700"
            style={{ background: isDone ? `linear-gradient(to bottom, ${meta.color}60, rgba(255,255,255,0.06))` : "rgba(255,255,255,0.06)" }} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-4">
        <div
          className="rounded-xl px-4 py-3 transition-all duration-500"
          style={{
            background: isThinking ? meta.bg : "rgba(255,255,255,0.02)",
            border: `1px solid ${isThinking ? `${meta.color}30` : isDone ? `${meta.color}15` : "rgba(255,255,255,0.05)"}`,
            boxShadow: isThinking ? `0 0 24px ${meta.color}15` : "none",
          }}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: meta.color }}>{meta.label}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
              style={{
                background: isThinking ? `${meta.color}20` : isDone ? "rgba(16,185,129,0.1)" : "rgba(255,255,255,0.05)",
                color: isThinking ? meta.color : isDone ? "#10B981" : "#6B7280",
              }}>
              {isThinking ? "thinking" : isDone ? "done" : step.status}
            </span>
          </div>
          <p className="text-[12.5px] text-[#9CA3AF] leading-relaxed">{step.message}</p>
        </div>
        {step.status === "handoff" && !isLast && (
          <div className="flex items-center gap-2 mt-1.5 ml-2">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent to-transparent"
              style={{ backgroundImage: `linear-gradient(to right, transparent, ${meta.color}40, transparent)` }} />
            <span className="text-[10px] text-[#6B7280] italic">handoff</span>
            <div className="h-px flex-1" style={{ backgroundImage: `linear-gradient(to right, ${meta.color}40, transparent)` }} />
          </div>
        )}
      </div>
    </div>
  );
}

function RiskBadgeLarge({ score }: { score: number }) {
  const color = score <= 3 ? "#10B981" : score <= 6 ? "#F59E0B" : "#EF4444";
  const label = score <= 3 ? "Low Risk" : score <= 6 ? "Medium Risk" : "High Risk";
  return (
    <div className="flex items-center gap-3">
      <div className="text-3xl font-black" style={{ color }}>{score}</div>
      <div>
        <div className="text-xs font-bold uppercase tracking-wider" style={{ color }}>{label}</div>
        <div className="text-[10px] text-[#6B7280]">out of 10</div>
      </div>
    </div>
  );
}

/**
 * Derive a rough risk score from the agent trace when the backend doesn't
 * send one explicitly. Watchdog "breach" / "critical" keywords → high risk.
 */
function deriveRiskScore(agentTrace: Array<{ agent?: string; description?: string }>): number {
  let score = 2;
  for (const t of agentTrace) {
    const desc = (t.description ?? "").toLowerCase();
    if (desc.includes("critical") || desc.includes("breach") || desc.includes("sla violation")) score = Math.max(score, 8);
    else if (desc.includes("warning") || desc.includes("risk") || desc.includes("expire")) score = Math.max(score, 5);
    else if (desc.includes("compliance") || desc.includes("alert")) score = Math.max(score, 4);
  }
  return Math.min(score, 10);
}

export default function ReasoningChain({ query, onComplete, onError }: Props) {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [finalResult, setFinalResult] = useState<FinalResult | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [hasError, setHasError] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [steps.length]);

  const startStream = useCallback(async () => {
    setSteps([]); setFinalResult(null); setHasError(false); setIsStreaming(true);
    abortRef.current = new AbortController();

    try {
      /**
       * CRITICAL FIX: Call the Next.js proxy route at /api/atlas/ask/stream
       * NOT the backend directly. The proxy reads the httpOnly JWT cookie
       * server-side and forwards it to the backend as a Bearer token.
       * Calling the backend directly bypasses cookie auth → always 401.
       */
      const res = await fetch(`/api/atlas/ask/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // No Authorization header — the Next.js proxy handles this via httpOnly cookie
        body: JSON.stringify({ query }),
        signal: abortRef.current.signal,
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const raw of lines) {
          const line = raw.trim();
          if (!line) continue;
          if (line === "data: [DONE]" || line === "[DONE]") break;

          // SSE format: "data: {...}"
          const payload = line.startsWith("data: ") ? line.slice(6).trim() : line;
          if (!payload || payload === "[DONE]") continue;

          let event: Record<string, unknown>;
          try { event = JSON.parse(payload); }
          catch { continue; }

          const eventType = event.type as string;

          if (eventType === "start") {
            // Pipeline initialised — nothing to render yet
            continue;

          } else if (eventType === "agent_action") {
            /**
             * Backend sends: {type:"agent_action", agent:"Researcher", tool:"search",
             *                  description:"...", timestamp:"..."}
             * Mark previous step as done, add this as "thinking"
             */
            setSteps(prev => {
              const updated = prev.map((s, i) =>
                i === prev.length - 1 ? { ...s, status: "done" as const } : s
              );
              return [
                ...updated,
                {
                  agent: (event.agent as string) ?? "Agent",
                  status: "thinking" as const,
                  message: (event.description as string) ?? (event.tool as string) ?? "Processing…",
                  timestamp: (event.timestamp as string) ?? new Date().toISOString(),
                },
              ];
            });

          } else if (eventType === "token") {
            // Token streaming — no step update needed (answer builds separately)
            continue;

          } else if (eventType === "complete") {
            /**
             * Backend sends: {type:"complete", answer, citations, suggested_followups,
             *                  agent_trace, duration_ms, map_data, fraud_data}
             */
            const agentTrace = (event.agent_trace as Array<Record<string, unknown>>) ?? [];
            const riskScore = deriveRiskScore(
              agentTrace.map(t => ({ agent: t.agent as string, description: t.description as string }))
            );
            const answer = (event.answer as string) ?? "";

            // Mark last step as done
            setSteps(prev => prev.map((s, i) =>
              i === prev.length - 1 ? { ...s, status: "done" as const } : s
            ));

            setFinalResult({
              type: "final",
              response: answer,
              risk_score: riskScore,
              citations: (event.citations as unknown[]) ?? [],
            });
            setIsStreaming(false);
            onComplete(answer, riskScore);

          } else if (eventType === "error") {
            throw new Error((event.message as string) ?? "Stream error");
          }
        }
      }

      setIsStreaming(false);

    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") return;
      console.error("ReasoningChain stream error:", err);
      setIsStreaming(false);
      setHasError(true);
      onError();
    }
  }, [query, onComplete, onError]);

  useEffect(() => {
    startStream();
    return () => { abortRef.current?.abort(); };
  }, []); // eslint-disable-line

  return (
    <div className="w-full rounded-2xl overflow-hidden" style={{ background: "#0A0D16" }}>
      {/* Header */}
      <div className="px-5 py-3.5 flex items-center gap-3 border-b border-white/[0.06]"
        style={{ background: "linear-gradient(to right, rgba(59,123,246,0.08), rgba(139,92,246,0.08))" }}>
        <div className="flex gap-1.5">
          {["#EF4444","#3B7BF6","#8B5CF6","#F59E0B","#10B981"].map((c,i) => (
            <div key={i} className="w-2 h-2 rounded-full" style={{ background: c, opacity: isStreaming ? 1 : 0.35,
              animation: isStreaming ? `pulse-agent 1.4s ease ${i * 0.15}s infinite` : "none" }} />
          ))}
        </div>
        <span className="text-sm font-bold text-[#E5E7EB] tracking-tight">Agent Reasoning Pipeline</span>
        {isStreaming && (
          <span className="ml-auto text-[10px] font-bold px-2.5 py-0.5 rounded-full animate-pulse"
            style={{ background: "rgba(59,123,246,0.2)", color: "#3B7BF6", border: "1px solid rgba(59,123,246,0.3)" }}>
            LIVE
          </span>
        )}
      </div>

      {/* Query badge */}
      <div className="px-5 pt-4 pb-2">
        <div className="rounded-lg px-3 py-2 text-xs" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <span style={{ color: "#6B7280" }}>Query: </span>
          <span style={{ color: "#E5E7EB" }}>{query}</span>
        </div>
      </div>

      {/* Pipeline */}
      <div className="px-5 py-3 max-h-[520px] overflow-y-auto">
        {steps.map((step, i) => (
          <PipelineNode key={`${step.agent}-${i}`} step={step} index={i} isLast={i === steps.length - 1 && !isStreaming && !finalResult} active={i === steps.length - 1} />
        ))}

        {isStreaming && steps.length === 0 && (
          <div className="flex items-center gap-3 py-4 text-sm text-[#6B7280]">
            <div className="w-4 h-4 rounded-full border-2 border-[#3B7BF6] border-t-transparent animate-spin" />
            Initialising agent pipeline…
          </div>
        )}

        {/* Output node */}
        {finalResult && (
          <div className="rounded-xl px-5 py-4 mt-2 transition-all duration-700"
            style={{ background: "linear-gradient(135deg, rgba(139,92,246,0.08) 0%, rgba(59,123,246,0.06) 100%)", border: "1px solid rgba(139,92,246,0.25)", boxShadow: "0 0 32px rgba(139,92,246,0.1)" }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-[#8B5CF6] animate-pulse" />
                <span className="text-xs font-bold uppercase tracking-wider text-[#8B5CF6]">Output</span>
              </div>
              <RiskBadgeLarge score={finalResult.risk_score} />
            </div>
            <p className="text-[13.5px] leading-[1.8] text-[#D1D5DB] whitespace-pre-wrap">{finalResult.response}</p>
          </div>
        )}

        {hasError && (
          <div className="rounded-xl px-5 py-4 text-center" style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}>
            <p className="text-sm font-medium mb-3 text-[#F87171]">Pipeline connection lost. Please retry.</p>
            <button onClick={() => { setHasError(false); startStream(); }}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-[#F87171] transition-all"
              style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)" }}>
              ↻ Retry
            </button>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <style>{`
        @keyframes pulse-agent { 0%,100%{opacity:.3;transform:scale(.8)} 50%{opacity:1;transform:scale(1.2)} }
      `}</style>
    </div>
  );
}
