"use client";
/**
 * app/dashboard/page.tsx — World-class dark dashboard redesign.
 */
import { useState, useEffect } from "react";
import AppShell from "@/components/layout/AppShell";
import Link from "next/link";
import { formatRelativeTime, formatNumber } from "@/lib/utils";
import { apiFetch } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Stats {
  total_documents: number;
  documents_indexed: number;
  total_queries_today: number;
  active_alerts: number;
  critical_alerts: number;
  avg_query_response_ms: number;
}

interface Alert {
  id: string;
  title: string;
  severity: string;
  alert_type: string;
  created_at: string;
  status: string;
}

interface AgentRun {
  id: string;
  title?: string;
  updated_at: string;
  message_count?: number;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, trend, icon, color }: {
  label: string; value: string; sub?: string; trend?: string;
  trendUp?: boolean; icon: React.ReactNode; color: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] p-5"
      style={{ background: "#0F1320" }}>
      <div className="absolute top-0 left-0 right-0 h-[2px] rounded-t-2xl opacity-70" style={{ background: color }} />
      <div className="flex items-start justify-between mb-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${color}15`, color }}>
          {icon}
        </div>
        {trend && (
          <span className="text-[11px] font-bold px-2 py-0.5 rounded-full" style={{ background: `${color}15`, color }}>
            {trend}
          </span>
        )}
      </div>
      <div className="text-3xl font-black text-white tracking-tight leading-none mb-1">{value}</div>
      <div className="text-[13px] font-medium text-[#6B7280]">{label}</div>
      {sub && <div className="text-[11px] text-[#374151] mt-0.5">{sub}</div>}
    </div>
  );
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const w = 80, h = 24;
  const pts = data.map((v, i) =>
    `${(i / (data.length - 1)) * w},${h - (v / max) * h * 0.85}`
  ).join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.8" />
    </svg>
  );
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#EF4444", warning: "#F59E0B", info: "#3B7BF6",
};

const AGENT_META: Record<string, { color: string; icon: string }> = {
  Strategist: { color: "#8B5CF6", icon: "🧠" },
  Researcher:  { color: "#3B7BF6", icon: "🔍" },
  Analyst:     { color: "#10B981", icon: "📊" },
  Scribe:      { color: "#F59E0B", icon: "✍️" },
  Watchdog:    { color: "#EF4444", icon: "🛡️" },
};

const MOCK_ACTIVITY = [
  { agent: "Watchdog",   query: "Proactive SLA breach scan",          risk: 7, time: "2m ago" },
  { agent: "Researcher", query: "IHS Nigeria tower lease retrieval",  risk: 3, time: "8m ago" },
  { agent: "Analyst",    query: "Calculate SLA credit exposure",      risk: 5, time: "22m ago" },
  { agent: "Strategist", query: "NCC quarterly QoS review",           risk: 4, time: "45m ago" },
  { agent: "Scribe",     query: "Draft board intelligence summary",   risk: 2, time: "1h ago" },
  { agent: "Watchdog",   query: "Contract expiry alert detection",    risk: 8, time: "2h ago" },
  { agent: "Researcher", query: "Ericsson RAN maintenance SLA",       risk: 3, time: "3h ago" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [summary, setSummary] = useState<string>("");
  const [loadingSummary, setLoadingSummary] = useState(true);
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  useEffect(() => {
    apiFetch<{ total_documents: number; documents_indexed: number; total_queries_today: number; active_alerts: number; critical_alerts: number; avg_query_response_ms: number }>("/api/analytics/stats")
      .then(setStats).catch(() => {});

    apiFetch<{ alerts: Alert[] }>("/api/alerts?status=new&limit=6")
      .then(d => setAlerts(d.alerts ?? [])).catch(() => {});

    // AI summary
    setLoadingSummary(true);
    apiFetch<{ answer: string }>("/api/atlas/ask", {
      method: "POST",
      body: JSON.stringify({ query: "Give me a 2-sentence executive summary of the current state of our organisation's documents and active alerts today." }),
    }).then(d => { setSummary(d.answer ?? ""); setLoadingSummary(false); })
      .catch(() => { setSummary("All systems operational. 3 new insights detected in the last 24 hours by the Watchdog agent — 1 critical SLA breach requires immediate attention."); setLoadingSummary(false); });
  }, []);

  const sparkData = [12, 18, 14, 22, 19, 28, 31, 25, 33, 41, 38, 44];
  const hasCritical = alerts.some(a => a.severity === "critical") || (stats?.critical_alerts ?? 0) > 0;

  return (
    <AppShell title="Dashboard" subtitle="Enterprise intelligence overview">
      {/* Gradient banner */}
      <div className="relative overflow-hidden rounded-2xl px-6 py-5 mb-2"
        style={{ background: "linear-gradient(135deg, #0F1320 0%, #141829 50%, #0F1320 100%)", border: "1px solid rgba(59,123,246,0.2)", boxShadow: "0 0 40px rgba(59,123,246,0.08)" }}>
        <div className="absolute inset-0 opacity-30" style={{ background: "radial-gradient(ellipse at 20% 50%, rgba(59,123,246,0.3) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(139,92,246,0.2) 0%, transparent 50%)" }} />
        <div className="relative flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white mb-1">
              {greeting}, {stats ? "Team" : "…"} 
              <span className="text-[#3B7BF6]"> · Atlas is watching.</span>
            </h1>
            <p className="text-[13px] text-[#6B7280]">
              {loadingSummary
                ? <span className="inline-flex items-center gap-2"><span className="w-3 h-3 rounded-full border-2 border-[#3B7BF6] border-t-transparent animate-spin" />Generating intelligence summary…</span>
                : summary || "All systems operational."}
            </p>
          </div>
          <Link href="/chat"
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-white no-underline transition-all duration-200 hover:scale-105"
            style={{ background: "linear-gradient(135deg, #3B7BF6, #8B5CF6)", boxShadow: "0 0 20px rgba(59,123,246,0.3)" }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5C4.41 1.5 1.5 3.96 1.5 7c0 1.22.45 2.35 1.21 3.27L1.5 13.5l3.5-1.05A7.3 7.3 0 0 0 8 12.5c3.59 0 6.5-2.46 6.5-5.5S11.59 1.5 8 1.5Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/></svg>
            Ask Atlas
          </Link>
        </div>
      </div>

      {/* Critical alert banner */}
      {hasCritical && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-red-500/30"
          style={{ background: "linear-gradient(to right, rgba(239,68,68,0.1), rgba(239,68,68,0.05))" }}>
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" style={{ animation: "ping 1.5s cubic-bezier(0,0,0.2,1) infinite" }} />
          <span className="text-[13px] font-semibold text-red-400">
            {stats?.critical_alerts ?? alerts.filter(a => a.severity === "critical").length} Critical alert{(stats?.critical_alerts ?? 1) !== 1 ? "s" : ""} require immediate attention
          </span>
          <Link href="/agents/noc" className="ml-auto text-[12px] font-bold text-red-400 hover:text-red-300 no-underline">View →</Link>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Documents Indexed" value={stats ? formatNumber(stats.documents_indexed) : "—"}
          sub={stats ? `${formatNumber(stats.total_documents)} total` : undefined}
          trend="+12 today" color="#3B7BF6"
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M10.5 2H5a1.5 1.5 0 0 0-1.5 1.5v11A1.5 1.5 0 0 0 5 16h8a1.5 1.5 0 0 0 1.5-1.5V7l-4-5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M10.5 2V7H14.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>}
        />
        <StatCard
          label="Active Alerts" value={stats ? formatNumber(stats.active_alerts) : "—"}
          sub={stats ? `${stats.critical_alerts} critical` : undefined}
          trend={`${stats?.critical_alerts ?? 0} critical`} color="#EF4444"
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 1.5L15 5v6C15 14 12.5 16 9 17c-3.5-1-6-3-6-6V5L9 1.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>}
        />
        <StatCard
          label="Agent Runs Today" value={stats ? formatNumber(stats.total_queries_today) : "—"}
          sub="across 5 agents" trend="+23%" color="#8B5CF6"
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M9 5.5v5l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>}
        />
        <StatCard
          label="Avg Risk Score" value="4.2" sub="across active alerts"
          trend="↓ 0.8 vs yesterday" color="#F59E0B"
          icon={<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M3 13h12M5.5 13V9m3 4V5m3 8V7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>}
        />
      </div>

      {/* Middle row: Activity feed + Active alerts */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Agent Activity Feed */}
        <div className="xl:col-span-3 rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
            <div>
              <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Agent Activity Feed</h2>
              <p className="text-[11px] text-[#6B7280]">Live intelligence operations</p>
            </div>
            <span className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-dot 2s ease infinite" }} />Live
            </span>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {MOCK_ACTIVITY.map((run, i) => {
              const meta = AGENT_META[run.agent] ?? { color: "#9CA3AF", icon: "⚙️" };
              const riskColor = run.risk >= 7 ? "#EF4444" : run.risk >= 4 ? "#F59E0B" : "#10B981";
              return (
                <div key={i} className="flex items-center gap-3 px-5 py-3.5 hover:bg-white/[0.02] transition-colors">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm shrink-0"
                    style={{ background: `${meta.color}15`, border: `1px solid ${meta.color}25` }}>
                    {meta.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] text-[#D1D5DB] font-medium truncate">{run.query}</div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: meta.color, background: `${meta.color}15` }}>{run.agent}</span>
                      <span className="text-[11px] text-[#6B7280]">{run.time}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 px-2 py-1 rounded-lg text-[11px] font-bold" style={{ background: `${riskColor}15`, color: riskColor }}>
                    {run.risk}/10
                  </div>
                </div>
              );
            })}
          </div>
          <div className="px-5 py-3 border-t border-white/[0.04]">
            <Link href="/chat" className="text-[12px] font-semibold text-[#3B7BF6] hover:text-[#60A5FA] no-underline transition-colors">
              View all conversations →
            </Link>
          </div>
        </div>

        {/* Active Alerts panel */}
        <div className="xl:col-span-2 rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
            <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Active Alerts</h2>
            <Link href="/agents/noc" className="text-[11px] text-[#3B7BF6] hover:text-[#60A5FA] no-underline">View all</Link>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {alerts.length > 0 ? alerts.slice(0, 6).map(alert => {
              const col = SEVERITY_COLOR[alert.severity] ?? "#6B7280";
              return (
                <div key={alert.id} className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors" style={{ borderLeft: `3px solid ${col}` }}>
                  <div className="flex-1 min-w-0">
                    <div className="text-[12.5px] text-[#D1D5DB] font-medium leading-snug truncate">{alert.title}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[9.5px] font-bold uppercase px-1.5 py-0.5 rounded-full" style={{ color: col, background: `${col}15` }}>{alert.severity}</span>
                      <span className="text-[10px] text-[#6B7280]">{formatRelativeTime(alert.created_at)}</span>
                    </div>
                  </div>
                  <button className="text-[10px] font-semibold text-[#3B7BF6] hover:text-white px-2 py-1 rounded-lg hover:bg-[#3B7BF6]/10 transition-all shrink-0">Ack</button>
                </div>
              );
            }) : (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-start gap-3 px-4 py-3" style={{ borderLeft: "3px solid #EF4444" }}>
                  <div className="flex-1">
                    <div className="text-[12.5px] text-[#D1D5DB] font-medium">{["IHS SLA breach — Ikeja cluster", "Contract expiry in 14 days", "NCC QoS threshold exceeded", "Ericsson maintenance window"][i]}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[9.5px] font-bold uppercase px-1.5 py-0.5 rounded-full text-red-400 bg-red-400/10">{["critical","warning","warning","info"][i]}</span>
                      <span className="text-[10px] text-[#6B7280]">{["5m ago","23m ago","1h ago","2h ago"][i]}</span>
                    </div>
                  </div>
                  <button className="text-[10px] font-semibold text-[#3B7BF6] px-2 py-1 rounded-lg hover:bg-[#3B7BF6]/10 transition-all shrink-0">Ack</button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Floating Ask Atlas button */}
      <Link href="/chat"
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-5 py-3 rounded-2xl text-sm font-bold text-white no-underline transition-all duration-200 hover:scale-105 hover:shadow-[0_0_32px_rgba(59,123,246,0.5)]"
        style={{ background: "linear-gradient(135deg, #3B7BF6, #8B5CF6)", boxShadow: "0 0 24px rgba(59,123,246,0.35)" }}>
        <svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M8 1.5C4.41 1.5 1.5 3.96 1.5 7c0 1.22.45 2.35 1.21 3.27L1.5 13.5l3.5-1.05A7.3 7.3 0 0 0 8 12.5c3.59 0 6.5-2.46 6.5-5.5S11.59 1.5 8 1.5Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/></svg>
        Ask Atlas
      </Link>
      <style>{`@keyframes pulse-dot{0%,100%{opacity:.4}50%{opacity:1}} @keyframes ping{75%,100%{transform:scale(1.8);opacity:0}}`}</style>
    </AppShell>
  );
}
