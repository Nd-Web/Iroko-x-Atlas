"use client";
/**
 * app/agents/noc/page.tsx — Network Operations Centre view.
 * Active alerts, SLA indicators, and an embedded query interface.
 */
import { useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { cn } from "@/lib/utils";
import { useChat } from "@/hooks/useChat";
import InputBar from "@/components/chat/InputBar";
import ChatWindow from "@/components/chat/ChatWindow";

const ALERTS = [
  { id: "a1", title: "Ikeja cluster uptime below SLA threshold", region: "Lagos", severity: "critical", age: "4m ago", slaImpact: true, status: "active" },
  { id: "a2", title: "Huawei BTS overload — Abuja zone 3", region: "Abuja", severity: "critical", age: "12m ago", slaImpact: true, status: "active" },
  { id: "a3", title: "Transmission link degradation — Port Harcourt", region: "PH", severity: "warning", age: "28m ago", slaImpact: false, status: "active" },
  { id: "a4", title: "NCC QoS threshold exceeded — Kano", region: "Kano", severity: "warning", age: "1h ago", slaImpact: true, status: "acknowledged" },
  { id: "a5", title: "Ericsson scheduled maintenance window missed", region: "National", severity: "info", age: "2h ago", slaImpact: false, status: "acknowledged" },
  { id: "a6", title: "Abnormal drop-call rate — Enugu cluster", region: "Enugu", severity: "warning", age: "3h ago", slaImpact: false, status: "active" },
];

const SLA_INDICATORS = [
  { name: "RAN Availability", value: 98.7, target: 99.5, unit: "%" },
  { name: "Core Network Latency", value: 14.2, target: 12.0, unit: "ms" },
  { name: "Drop Call Rate", value: 1.8, target: 1.5, unit: "%" },
  { name: "MTTR", value: 3.4, target: 4.0, unit: "hr", good: true },
];

const SEV_COLOR: Record<string, string> = { critical: "#EF4444", warning: "#F59E0B", info: "#3B7BF6" };

function SLAGauge({ sla }: { sla: typeof SLA_INDICATORS[0] }) {
  const passing = sla.good ? sla.value <= sla.target : sla.value >= sla.target;
  const pct = Math.min(100, (sla.value / sla.target) * 100);
  const color = passing ? "#10B981" : sla.value / sla.target < 0.97 ? "#EF4444" : "#F59E0B";
  return (
    <div className="rounded-xl p-4 border border-white/[0.06]" style={{ background: "#0F1320" }}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] text-[#9CA3AF] font-medium">{sla.name}</span>
        <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full", passing ? "text-emerald-400 bg-emerald-400/10" : "text-red-400 bg-red-400/10")}>
          {passing ? "✓ PASS" : "✗ BREACH"}
        </span>
      </div>
      <div className="flex items-baseline gap-1.5 mb-2">
        <span className="text-2xl font-black" style={{ color }}>{sla.value}{sla.unit}</span>
        <span className="text-[11px] text-[#4B5563]">/ {sla.target}{sla.unit} target</span>
      </div>
      <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
      </div>
    </div>
  );
}

export default function NOCPage() {
  const [activeFilter, setActiveFilter] = useState("all");
  const { messages, isLoading, sendMessage } = useChat();
  const [chatOpen, setChatOpen] = useState(false);

  const filtered = ALERTS.filter(a => activeFilter === "all" || a.severity === activeFilter || a.status === activeFilter);

  const chatMessages = messages.map(m => ({
    id: m.id, role: m.role, content: m.content,
    reasoning_steps: m.trace?.map(t => ({ agent: t.agent, status: "done" as const, message: t.description, timestamp: t.timestamp })),
    timestamp: m.timestamp,
  }));

  return (
    <AppShell title="Network Operations Centre"
      subtitle="Real-time network intelligence · 5 agents monitoring"
      actions={
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-3 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-noc 2s ease infinite" }} />
            LIVE MONITORING
          </span>
          <button onClick={() => setChatOpen(!chatOpen)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-bold text-white transition-all"
            style={{ background: chatOpen ? "#1a1d27" : "linear-gradient(135deg,#3B7BF6,#8B5CF6)", border: "1px solid rgba(59,123,246,0.2)" }}>
            🛡️ Ask Watchdog
          </button>
        </div>
      }>

      {/* SLA indicators */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {SLA_INDICATORS.map(sla => <SLAGauge key={sla.name} sla={sla} />)}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Alert feed */}
        <div className="xl:col-span-3 rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
            <div>
              <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Active Incidents</h2>
              <p className="text-[11px] text-[#6B7280]">{ALERTS.filter(a => a.status === "active").length} active · {ALERTS.filter(a => a.severity === "critical").length} critical</p>
            </div>
            <div className="flex items-center gap-1.5">
              {["all","critical","warning","acknowledged"].map(f => (
                <button key={f} onClick={() => setActiveFilter(f)}
                  className={cn("px-2.5 py-1 rounded-lg text-[10px] font-semibold capitalize transition-all",
                    activeFilter === f ? "bg-white/10 text-[#E5E7EB]" : "text-[#6B7280] hover:text-[#E5E7EB]")}>
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {filtered.map(alert => {
              const col = SEV_COLOR[alert.severity] ?? "#6B7280";
              return (
                <div key={alert.id} className="flex items-start gap-3 px-5 py-4 hover:bg-white/[0.02] transition-colors" style={{ borderLeft: `3px solid ${col}` }}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full" style={{ color: col, background: `${col}15` }}>{alert.severity}</span>
                      {alert.slaImpact && <span className="text-[9.5px] font-bold text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded-full border border-amber-400/20">SLA Impact</span>}
                      <span className="text-[10px] text-[#4B5563] ml-auto">{alert.age}</span>
                    </div>
                    <p className="text-[13px] text-[#D1D5DB] font-medium leading-snug">{alert.title}</p>
                    <p className="text-[11px] text-[#6B7280] mt-0.5">{alert.region}</p>
                  </div>
                  <div className="flex flex-col gap-1.5 shrink-0">
                    <button className="text-[10px] font-bold px-2.5 py-1.5 rounded-lg text-[#3B7BF6] border border-[#3B7BF6]/20 hover:bg-[#3B7BF6]/10 transition-all">
                      {alert.status === "active" ? "Acknowledge" : "Resolve"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Watchdog chat panel */}
        <div className="xl:col-span-2 rounded-2xl border border-white/[0.06] flex flex-col overflow-hidden" style={{ background: "#0F1320", minHeight: 400 }}>
          <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
            <span className="text-lg">🛡️</span>
            <span className="text-[13px] font-bold text-[#E5E7EB]">Watchdog Intelligence</span>
            <span className="ml-auto text-[9px] font-bold px-2 py-0.5 rounded-full text-red-400 bg-red-400/10 border border-red-400/20 animate-pulse">
              {ALERTS.filter(a => a.severity === "critical").length} CRITICAL
            </span>
          </div>
          <div className="flex-1 min-h-0">
            <ChatWindow conversationId="noc" messages={chatMessages} isStreaming={isLoading} />
          </div>
          <InputBar onSend={sendMessage} isStreaming={isLoading}
            placeholder="Ask Watchdog about incidents, SLA, alerts…" />
        </div>
      </div>
      <style>{`@keyframes pulse-noc{0%,100%{opacity:.4}50%{opacity:1}}`}</style>
    </AppShell>
  );
}
