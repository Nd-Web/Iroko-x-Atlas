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

function daysUntil(isoDate: string): number {
  const due = new Date(isoDate);
  const now = new Date();
  due.setHours(0, 0, 0, 0);
  now.setHours(0, 0, 0, 0);
  return Math.max(0, Math.round((due.getTime() - now.getTime()) / 86400000));
}

const amlDaysNoc = daysUntil("2026-07-15");

const KUDA_ALERTS = [
  { id: "a1", title: "Kuda MFB — lending exposure limit approaching CBN threshold",                       region: "Lagos",    severity: "critical", age: "4m ago", slaImpact: true,  status: "active" },
  { id: "a2", title: `Kuda MFB — AML/CFT quarterly return due in ${amlDaysNoc} day${amlDaysNoc !== 1 ? "s" : ""}`, region: "National", severity: "warning",  age: "1h ago", slaImpact: false, status: "active" },
  { id: "a3", title: "Kuda MFB — 3 incomplete SAR filings flagged by CBN",                                region: "Abuja",    severity: "warning",  age: "2h ago", slaImpact: false, status: "active" },
  { id: "a4", title: "Kuda MFB — KYC gap in Q2 onboarding batch (187 accounts)",                         region: "Lagos",    severity: "info",     age: "3h ago", slaImpact: false, status: "acknowledged" },
];

const COMPETITOR_ALERTS = [
  { id: "c1", title: "Carbon MFB — CAR below 10% minimum — immediate action required", region: "Lagos",    severity: "critical", age: "12m ago", status: "active" },
  { id: "c2", title: "Moniepoint — AML/CFT quarterly return overdue by 3 days",        region: "National", severity: "warning",  age: "28m ago", status: "active" },
  { id: "c3", title: "Fairmoney — CBN credit bureau check gap detected in loan batch",  region: "Abuja",    severity: "warning",  age: "1h ago",  status: "acknowledged" },
  { id: "c4", title: "Opay PSB — consumer complaint resolution SLA exceeded",          region: "National", severity: "info",     age: "2h ago",  status: "acknowledged" },
  { id: "c5", title: "Risevest — SEC registration renewal due in 15 days",             region: "Lagos",    severity: "warning",  age: "3h ago",  status: "active" },
];

// threshold: breach only when value falls BELOW this CBN minimum
const SLA_INDICATORS = [
  { name: "Lending Compliance",  value: 94.2, threshold: 90.0, unit: "%", label: "≥ 90% CBN min" },
  { name: "KYC Coverage Rate",   value: 98.7, threshold: 95.0, unit: "%", label: "≥ 95% CBN min" },
  { name: "CAR (Avg Portfolio)", value: 12.4, threshold: 10.0, unit: "%", label: "≥ 10% CBN min" },
  { name: "AML Filing Rate",     value: 96.1, threshold: 95.0, unit: "%", label: "≥ 95% CBN min" },
];

const SEV_COLOR: Record<string, string> = { critical: "#EF4444", warning: "#F59E0B", info: "#3B7BF6" };

function SLAGauge({ sla }: { sla: typeof SLA_INDICATORS[0] }) {
  const passing = sla.value >= sla.threshold;
  const pct = Math.min(100, (sla.value / (sla.threshold * 1.5)) * 100);
  const color = passing ? "#10B981" : "#EF4444";
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
        <span className="text-[11px] text-[#4B5563]">{sla.label}</span>
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

  const filteredKuda = KUDA_ALERTS.filter(a =>
    activeFilter === "all" || a.severity === activeFilter || a.status === activeFilter
  );

  const chatMessages = messages.map(m => ({
    id: m.id, role: m.role, content: m.content,
    reasoning_steps: m.trace?.map(t => ({ agent: t.agent, status: "done" as const, message: t.description, timestamp: t.timestamp })),
    timestamp: m.timestamp,
  }));

  return (
    <AppShell title="Fintech Risk Operations Centre"
      subtitle="Kuda MFB — Real-time CBN/SEC Compliance Monitor"
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

      {/* SLA indicators — Kuda MFB metrics only */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {SLA_INDICATORS.map(sla => <SLAGauge key={sla.name} sla={sla} />)}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Alert feed */}
        <div className="xl:col-span-3 space-y-4">

          {/* Kuda internal alerts */}
          <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
              <div>
                <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Kuda MFB — Active Incidents</h2>
                <p className="text-[11px] text-[#6B7280]">
                  {KUDA_ALERTS.filter(a => a.status === "active").length} active · {KUDA_ALERTS.filter(a => a.severity === "critical").length} critical
                </p>
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
              {filteredKuda.map(alert => {
                const col = SEV_COLOR[alert.severity] ?? "#6B7280";
                return (
                  <div key={alert.id} className="flex items-start gap-3 px-5 py-4 hover:bg-white/[0.02] transition-colors" style={{ borderLeft: `3px solid ${col}` }}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full" style={{ color: col, background: `${col}15` }}>{alert.severity}</span>
                        <span className="text-[9.5px] font-bold text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-full border border-blue-400/20">Internal</span>
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

          {/* Competitor intelligence section */}
          <div className="rounded-2xl border border-orange-400/20 overflow-hidden" style={{ background: "#0F1320" }}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-orange-400/20">
              <div>
                <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Competitor Intelligence</h2>
                <p className="text-[11px] text-[#6B7280]">Market watch — regulatory signals from peers</p>
              </div>
              <span className="text-[9.5px] font-bold text-orange-400 bg-orange-400/10 px-2.5 py-1 rounded-full border border-orange-400/20">
                {COMPETITOR_ALERTS.filter(a => a.severity === "critical").length} critical signals
              </span>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {COMPETITOR_ALERTS.map(alert => {
                const col = SEV_COLOR[alert.severity] ?? "#6B7280";
                return (
                  <div key={alert.id} className="flex items-start gap-3 px-5 py-4 hover:bg-white/[0.02] transition-colors" style={{ borderLeft: "3px solid #F97316" }}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full" style={{ color: col, background: `${col}15` }}>{alert.severity}</span>
                        <span className="text-[9.5px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded-full border border-orange-400/20">Competitor Intel</span>
                        <span className="text-[10px] text-[#4B5563] ml-auto">{alert.age}</span>
                      </div>
                      <p className="text-[13px] text-[#D1D5DB] font-medium leading-snug">{alert.title}</p>
                      <p className="text-[11px] text-[#6B7280] mt-0.5">{alert.region}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Watchdog chat panel */}
        <div className="xl:col-span-2 rounded-2xl border border-white/[0.06] flex flex-col overflow-hidden" style={{ background: "#0F1320", minHeight: 400 }}>
          <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
            <span className="text-lg">🛡️</span>
            <span className="text-[13px] font-bold text-[#E5E7EB]">Fintech Watchdog Intelligence</span>
            <span className="ml-auto text-[9px] font-bold px-2 py-0.5 rounded-full text-red-400 bg-red-400/10 border border-red-400/20 animate-pulse">
              {KUDA_ALERTS.filter(a => a.severity === "critical").length} CRITICAL
            </span>
          </div>
          <div className="flex-1 min-h-0">
            <ChatWindow conversationId="noc" messages={chatMessages} isStreaming={isLoading} />
          </div>
          <InputBar onSend={sendMessage} isStreaming={isLoading}
            placeholder="Ask Watchdog about CBN violations, regulatory alerts…" />
        </div>
      </div>
      <style>{`@keyframes pulse-noc{0%,100%{opacity:.4}50%{opacity:1}}`}</style>
    </AppShell>
  );
}
