"use client";
/**
 * components/agents/AgentStatusBar.tsx
 * Horizontal pill bar showing all 5 agents with live status dots.
 */
import React from "react";
import { cn } from "@/lib/utils";
import type { AgentStatus } from "@/types/api";

interface Props {
  agents?: AgentStatus[];
}

const AGENT_META: Record<string, { icon: string; color: string }> = {
  WatchdogAgent:   { icon: "🛡️", color: "#EF4444" },
  ResearcherAgent: { icon: "🔍", color: "#3B7BF6" },
  AnalystAgent:    { icon: "📊", color: "#8B5CF6" },
  StrategistAgent: { icon: "🧠", color: "#F59E0B" },
  ScribeAgent:     { icon: "✍️", color: "#10B981" },
};

const DEFAULT_AGENTS: AgentStatus[] = [
  { name: "WatchdogAgent",   display_name: "Watchdog",   last_run: null, total_runs: 0, avg_response_time: 0, status: "idle" },
  { name: "ResearcherAgent", display_name: "Researcher", last_run: null, total_runs: 0, avg_response_time: 0, status: "idle" },
  { name: "AnalystAgent",    display_name: "Analyst",    last_run: null, total_runs: 0, avg_response_time: 0, status: "idle" },
  { name: "StrategistAgent", display_name: "Strategist", last_run: null, total_runs: 0, avg_response_time: 0, status: "idle" },
  { name: "ScribeAgent",     display_name: "Scribe",     last_run: null, total_runs: 0, avg_response_time: 0, status: "idle" },
];

function StatusDot({ status }: { status: string }) {
  if (status === "running") {
    return (
      <span
        className="w-2 h-2 rounded-full bg-amber-400 shrink-0"
        style={{ animation: "pulse-dot 1.2s ease-in-out infinite" }}
      />
    );
  }
  if (status === "error") return <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" />;
  return <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />;
}

export default function AgentStatusBar({ agents = DEFAULT_AGENTS }: Props) {
  return (
    <>
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06] bg-[#080B14]/80 backdrop-blur-sm overflow-x-auto scrollbar-none">
        <span className="text-[10px] font-semibold text-[#6B7280] uppercase tracking-widest shrink-0 mr-1">
          Agents
        </span>
        {agents.map((agent) => {
          const meta = AGENT_META[agent.name] ?? { icon: "⚙️", color: "#9CA3AF" };
          return (
            <div
              key={agent.name}
              title={`${agent.display_name} · ${agent.total_runs} runs · ${agent.avg_response_time}ms avg`}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-medium shrink-0 transition-all duration-200",
                agent.status === "running"
                  ? "border-amber-400/30 bg-amber-400/10 text-amber-300"
                  : agent.status === "error"
                  ? "border-red-400/30 bg-red-400/10 text-red-300"
                  : "border-white/[0.06] bg-white/[0.03] text-[#9CA3AF] hover:border-white/10 hover:text-[#E5E7EB]",
              )}
            >
              <span className="text-[11px]">{meta.icon}</span>
              <StatusDot status={agent.status} />
              <span>{agent.display_name}</span>
            </div>
          );
        })}
      </div>
      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 0.4; transform: scale(0.85); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </>
  );
}
