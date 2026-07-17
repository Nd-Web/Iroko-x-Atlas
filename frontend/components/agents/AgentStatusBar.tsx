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

const AGENT_META: Record<string, { color: string }> = {
  WatchdogAgent:   { color: "#F87171" },
  ResearcherAgent: { color: "#38BDF8" },
  AnalystAgent:    { color: "#818CF8" },
  StrategistAgent: { color: "#FB923C" },
  ScribeAgent:     { color: "#34D399" },
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
        className="w-2 h-2 rounded-full bg-[#F59E0B] shrink-0"
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
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border-default bg-surface-page/80 backdrop-blur-sm overflow-x-auto scrollbar-none">
        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest shrink-0 mr-1">
          Agents
        </span>
        {agents.map((agent) => {
          const meta = AGENT_META[agent.name] ?? { color: "#9C9CA6" };
          return (
            <div
              key={agent.name}
              title={`${agent.display_name} · ${agent.total_runs} runs · ${agent.avg_response_time}ms avg`}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-medium shrink-0 transition-all duration-200",
                agent.status === "running"
                  ? "border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#F59E0B]"
                  : agent.status === "error"
                  ? "border-red-400/30 bg-red-400/10 text-red-300"
                  : "border-border-default bg-gray-50 text-gray-500 hover:border-border-strong hover:text-gray-800",
              )}
            >
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: meta.color }} />
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
