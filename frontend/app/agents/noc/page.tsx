"use client";
/**
 * app/agents/noc/page.tsx — Network Operations Centre view.
 * Live alerts (via /api/alerts), SLA indicators, and an embedded query interface.
 */
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import AppShell from "@/components/layout/AppShell";
import { cn, formatRelativeTime } from "@/lib/utils";
import { useChat } from "@/hooks/useChat";
import InputBar from "@/components/chat/InputBar";
import ChatWindow from "@/components/chat/ChatWindow";
import { toast } from "sonner";

interface NocAlert {
  id: string;
  title: string;
  detail: string;
  severity: string;
  age: string;
  slaImpact: boolean;
  status: string;
}

// Fallback alerts mirroring the seeded backend data — shown only if the live
// fetch fails, so the story stays identical either way.
const FALLBACK_ALERTS: NocAlert[] = [
  { id: "a1", title: "IHS Ikeja Cluster SLA Breach — February 2026 Outage",     detail: "vendor_sla · ₦2.66M exposure",     severity: "critical", age: "4m ago", slaImpact: true,  status: "new" },
  { id: "a2", title: "ATC Lagos Zone 2 Contract Expiring in 28 Days",           detail: "contract · ₦19.5M/month",          severity: "critical", age: "1h ago", slaImpact: false, status: "new" },
  { id: "a3", title: "NCC QoS Return Q1 2026 — Submission Due in 12 Days",      detail: "regulatory · ₦5M/day if late",     severity: "warning",  age: "2h ago", slaImpact: false, status: "new" },
  { id: "a4", title: "MoMo Deduction Complaints Spike — Lagos +312% vs Q4 2025", detail: "complaints · ₦28.4M disputed",     severity: "warning",  age: "3h ago", slaImpact: false, status: "new" },
  { id: "a5", title: "NDPA Article 24 Processing Record — Annual Review Overdue", detail: "regulatory · DPO action required", severity: "warning",  age: "5h ago", slaImpact: false, status: "acknowledged" },
  { id: "a6", title: "Kano-Kaduna Fibre Cut — SLA Milestone at Risk",           detail: "network · Km 142 ROW excavation",  severity: "info",     age: "6h ago", slaImpact: true,  status: "new" },
];

// Regulator-sourced signals — market watch, not operator incidents.
const REGULATORY_WATCH = [
  { id: "r1", title: "NCC directive — operators to actively detect and disable SIM-box lines",       source: "NCC",   severity: "warning", age: "1h ago" },
  { id: "r2", title: "NDPC enforcement precedent — ₦766.2M fine for illegal cross-border transfer",  source: "NDPC",  severity: "critical", age: "2h ago" },
  { id: "r3", title: "GAID 2025 — cross-border data transfer restrictions now in force",             source: "NDPC",  severity: "warning", age: "4h ago" },
  { id: "r4", title: "FCCPC notice — quarterly consumer complaint reporting reminder",               source: "FCCPC", severity: "info",    age: "6h ago" },
  { id: "r5", title: "NCC consultation — proposed QoS framework revision for 5G services",           source: "NCC",   severity: "info",    age: "8h ago" },
];

// threshold: breach when value falls BELOW the regulatory/target minimum
const SLA_INDICATORS = [
  { name: "National Availability",     value: 99.2, threshold: 95.0, unit: "%", label: "≥ 95% NCC min" },
  { name: "Ikeja Cluster Availability", value: 82.7, threshold: 95.0, unit: "%", label: "≥ 95% NCC min" },
  { name: "Call Setup Success",        value: 96.8, threshold: 95.0, unit: "%", label: "≥ 95% NCC min" },
  { name: "CX Resolution Rate",        value: 76.0, threshold: 70.0, unit: "%", label: "≥ 70% target" },
];

const SEV_COLOR: Record<string, string> = { critical: "#EF4444", warning: "#F59E0B", info: "#38BDF8" };

function SLAGauge({ sla }: { sla: typeof SLA_INDICATORS[0] }) {
  const passing = sla.value >= sla.threshold;
  const pct = Math.min(100, (sla.value / (sla.threshold * 1.5)) * 100);
  const color = passing ? "#10B981" : "#EF4444";
  return (
    <div className="rounded-xl p-4 border border-border-default bg-surface-card">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] text-gray-500 font-medium">{sla.name}</span>
        <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full", passing ? "text-emerald-400 bg-emerald-400/10" : "text-red-400 bg-red-400/10")}>
          {passing ? "✓ PASS" : "✗ BREACH"}
        </span>
      </div>
      <div className="flex items-baseline gap-1.5 mb-2">
        <span className="text-2xl font-black" style={{ color }}>{sla.value}{sla.unit}</span>
        <span className="text-[11px] text-gray-300">{sla.label}</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
      </div>
    </div>
  );
}

export default function NOCPage() {
  const router = useRouter();
  const [activeFilter, setActiveFilter] = useState("all");
  const [alerts, setAlerts] = useState<NocAlert[]>(FALLBACK_ALERTS);
  const [isLive, setIsLive] = useState(false);
  const { messages, isLoading, error, sendMessage } = useChat();
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);

  // Load live alerts through the Next.js proxy (cookie auth).
  useEffect(() => {
    fetch("/api/alerts?status=all&limit=20")
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: { alerts?: Array<{ id: string; title: string; summary?: string; severity: string; status: string; alert_type?: string; created_at?: string }> }) => {
        const rows: NocAlert[] = (data.alerts ?? []).map(a => ({
          id: String(a.id),
          title: a.title,
          detail: a.alert_type ?? "general",
          severity: a.severity ?? "info",
          age: a.created_at ? formatRelativeTime(a.created_at) : "—",
          slaImpact: (a.alert_type ?? "").toLowerCase().includes("sla") || (a.title ?? "").toLowerCase().includes("sla"),
          status: a.status ?? "new",
        }));
        if (rows.length > 0) {
          setAlerts(rows);
          setIsLive(true);
        }
      })
      .catch(() => { /* fall back to canonical demo alerts */ });
  }, []);

  const handleSend = useCallback((content: string) => {
    setLastQuery(content);
    sendMessage(content);
  }, [sendMessage]);

  /** Acknowledge or resolve an alert via the existing proxies. */
  const advanceAlert = async (alert: NocAlert) => {
    const action = alert.status === "acknowledged" ? "resolve" : "acknowledge";
    const nextStatus = action === "acknowledge" ? "acknowledged" : "resolved";
    try {
      if (isLive) {
        const res = await fetch(`/api/alerts/${alert.id}/${action}`, { method: "PATCH" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
      }
      setAlerts(prev => prev.map(a => a.id === alert.id ? { ...a, status: nextStatus } : a));
      toast.success(`Alert ${nextStatus}`);
    } catch {
      toast.error(`Could not ${action} the alert — backend unreachable`);
    }
  };

  const filteredAlerts = alerts.filter(a =>
    activeFilter === "all" || a.severity === activeFilter || a.status === activeFilter
  );

  const activeCount = alerts.filter(a => a.status === "new").length;
  const criticalCount = alerts.filter(a => a.severity === "critical" && a.status !== "resolved").length;

  const chatMessages = messages.map(m => ({
    id: m.id, role: m.role, content: m.content,
    reasoning_steps: m.trace?.map(t => ({ agent: t.agent, status: "done" as const, message: t.description, timestamp: t.timestamp })),
    // The backend emits either {document_id, document_title} or {source, excerpt} — accept both.
    citations: m.citations?.map(c => {
      const cc = c as { document_id?: string; document_title?: string; source?: string; excerpt?: string };
      return {
        document_id: cc.document_id ?? cc.source ?? "unknown",
        document_title: cc.document_title ?? cc.source ?? cc.document_id ?? "Source document",
        excerpt: cc.excerpt,
      };
    }),
    timestamp: m.timestamp,
  }));

  return (
    <AppShell title="Network Operations Centre"
      subtitle="Real-time network, SLA & regulatory monitor"
      actions={
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-3 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-noc 2s ease infinite" }} />
            {isLive ? "LIVE MONITORING" : "DEMO DATA"}
          </span>
          <button onClick={() => setChatOpen(!chatOpen)}
            className={cn("flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-bold transition-all",
              chatOpen
                ? "bg-gray-100 text-gray-800 border border-border-default"
                : "bg-brand-500 text-[#0A0A0B] border border-transparent hover:bg-brand-400")}>
            Ask Watchdog
          </button>
        </div>
      }>

      {/* SLA indicators */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {SLA_INDICATORS.map(sla => <SLAGauge key={sla.name} sla={sla} />)}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Alert feed */}
        <div className="xl:col-span-3 space-y-4">

          {/* Operator alerts */}
          <div className="rounded-2xl border border-border-default overflow-hidden bg-surface-card">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
              <div>
                <h2 className="text-[14px] font-semibold text-gray-800">Active Alerts</h2>
                <p className="text-[11px] text-gray-400">
                  {activeCount} active · {criticalCount} critical
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                {["all","critical","warning","acknowledged"].map(f => (
                  <button key={f} onClick={() => setActiveFilter(f)}
                    className={cn("px-2.5 py-1 rounded-lg text-[10px] font-semibold capitalize transition-all",
                      activeFilter === f ? "bg-brand-50 text-brand-500" : "text-gray-400 hover:text-gray-800")}>
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <div className="divide-y divide-border-default">
              {filteredAlerts.length === 0 && (
                <p className="text-[12px] text-gray-400 text-center py-8">No alerts match this filter</p>
              )}
              {filteredAlerts.map(alert => {
                const col = SEV_COLOR[alert.severity] ?? "#9C9CA6";
                return (
                  <div key={alert.id} className="flex items-start gap-3 px-5 py-4 hover:bg-gray-50 transition-colors" style={{ borderLeft: `3px solid ${col}` }}>
                    {/* Clicking the alert asks Iroko about it — see insight → ask why → cited answer */}
                    <div
                      className="flex-1 min-w-0 cursor-pointer"
                      title="Ask Iroko about this alert"
                      onClick={() => router.push(`/chat?q=${encodeURIComponent(`Tell me more about this alert and what we should do: ${alert.title}`)}`)}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full" style={{ color: col, background: `${col}15` }}>{alert.severity}</span>
                        <span className="text-[9.5px] font-bold text-info-500 bg-info-50 px-2 py-0.5 rounded-full border border-info-100">Internal</span>
                        {alert.slaImpact && <span className="text-[9.5px] font-bold text-warning-500 bg-warning-50 px-2 py-0.5 rounded-full border border-warning-100">SLA Impact</span>}
                        <span className="text-[10px] text-gray-400 ml-auto">{alert.age}</span>
                      </div>
                      <p className="text-[13px] text-gray-800 font-medium leading-snug">{alert.title}</p>
                      <p className="text-[11px] text-gray-400 mt-0.5">{alert.detail}</p>
                    </div>
                    <div className="flex flex-col gap-1.5 shrink-0">
                      {alert.status === "resolved" ? (
                        <span className="text-[10px] font-bold px-2.5 py-1.5 rounded-lg text-emerald-400 bg-emerald-400/10 border border-emerald-400/20">✓ Resolved</span>
                      ) : (
                        <button onClick={() => advanceAlert(alert)}
                          className="text-[10px] font-bold px-2.5 py-1.5 rounded-lg text-brand-500 border border-brand-200 hover:bg-brand-50 transition-all">
                          {alert.status === "acknowledged" ? "Resolve" : "Acknowledge"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Regulatory watch section */}
          <div className="rounded-2xl border border-orange-400/20 overflow-hidden bg-surface-card">
            <div className="flex items-center justify-between px-5 py-4 border-b border-orange-400/20">
              <div>
                <h2 className="text-[14px] font-semibold text-gray-800">Regulatory Watch</h2>
                <p className="text-[11px] text-gray-400">Market watch — signals from NCC · NDPC · FCCPC</p>
              </div>
              <span className="text-[9.5px] font-bold text-orange-400 bg-orange-400/10 px-2.5 py-1 rounded-full border border-orange-400/20">
                {REGULATORY_WATCH.filter(a => a.severity === "critical").length} critical signals
              </span>
            </div>
            <div className="divide-y divide-border-default">
              {REGULATORY_WATCH.map(alert => {
                const col = SEV_COLOR[alert.severity] ?? "#9C9CA6";
                return (
                  <div key={alert.id} className="flex items-start gap-3 px-5 py-4 hover:bg-gray-50 transition-colors" style={{ borderLeft: "3px solid #F97316" }}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full" style={{ color: col, background: `${col}15` }}>{alert.severity}</span>
                        <span className="text-[9.5px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded-full border border-orange-400/20">{alert.source}</span>
                        <span className="text-[10px] text-gray-400 ml-auto">{alert.age}</span>
                      </div>
                      <p className="text-[13px] text-gray-800 font-medium leading-snug">{alert.title}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Watchdog chat panel */}
        <div className="xl:col-span-2 rounded-2xl border border-border-default bg-surface-card flex flex-col overflow-hidden" style={{ minHeight: 400 }}>
          <div className="px-4 py-3 border-b border-border-default flex items-center gap-2">
            <span className="text-[13px] font-bold text-gray-800">Watchdog Intelligence</span>
            <span className="ml-auto text-[9px] font-bold px-2 py-0.5 rounded-full text-red-400 bg-red-400/10 border border-red-400/20 animate-pulse">
              {criticalCount} CRITICAL
            </span>
          </div>
          <div className="flex-1 min-h-0">
            <ChatWindow conversationId="noc" messages={chatMessages} isStreaming={isLoading} />
          </div>
          {error && !isLoading && (
            <div className="mx-3 mb-1 flex items-center justify-between gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
              <span className="text-[11px] text-red-300 truncate">Request failed — {error}</span>
              {lastQuery && (
                <button onClick={() => handleSend(lastQuery)}
                  className="shrink-0 text-[10.5px] font-bold text-red-300 hover:text-gray-900 transition-colors">
                  Retry
                </button>
              )}
            </div>
          )}
          <InputBar onSend={handleSend} isStreaming={isLoading}
            placeholder="Ask Watchdog about incidents, SLAs, regulatory deadlines…" />
        </div>
      </div>
      <style>{`@keyframes pulse-noc{0%,100%{opacity:.4}50%{opacity:1}}`}</style>
    </AppShell>
  );
}
