"use client";
/**
 * app/network-intelligence/page.tsx — Full NOC dashboard.
 * Circular health gauge, Nigeria network map, incident feed, chat.
 */
import { useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useChat } from "@/hooks/useChat";
import InputBar from "@/components/chat/InputBar";
import ChatWindow from "@/components/chat/ChatWindow";
import { cn } from "@/lib/utils";

// ── Data ──────────────────────────────────────────────────────────────────────

const REGIONS = [
  { name: "Lagos",    lat: 6.45,  lng: 3.4,   score: 97.2, status: "operational", incidents: 1, sites: 42 },
  { name: "Abuja",    lat: 9.07,  lng: 7.4,   score: 91.4, status: "degraded",    incidents: 3, sites: 28 },
  { name: "Kano",     lat: 12.0,  lng: 8.52,  score: 88.9, status: "degraded",    incidents: 2, sites: 19 },
  { name: "PH",       lat: 4.84,  lng: 7.04,  score: 95.1, status: "operational", incidents: 0, sites: 24 },
  { name: "Enugu",    lat: 6.46,  lng: 7.55,  score: 78.3, status: "degraded",    incidents: 4, sites: 16 },
  { name: "Ibadan",   lat: 7.38,  lng: 3.9,   score: 93.6, status: "operational", incidents: 1, sites: 21 },
  { name: "Benin",    lat: 6.34,  lng: 5.63,  score: 99.1, status: "operational", incidents: 0, sites: 14 },
  { name: "Kaduna",   lat: 10.52, lng: 7.43,  score: 84.7, status: "degraded",    incidents: 2, sites: 18 },
];

const INCIDENTS = [
  { id: "i1", title: "Abuja zone 3 — BTS overload", region: "Abuja",  sev: "critical", age: "8m",  sla: true  },
  { id: "i2", title: "Enugu cluster — 4 sites offline", region: "Enugu", sev: "critical", age: "22m", sla: true  },
  { id: "i3", title: "Kano — RAN latency spike",      region: "Kano",   sev: "warning",  age: "45m", sla: false },
  { id: "i4", title: "Kaduna — fibre cut PH-KD link", region: "Kaduna", sev: "warning",  age: "1h",  sla: true  },
  { id: "i5", title: "Lagos — MTR congestion on A1",  region: "Lagos",  sev: "info",     age: "2h",  sla: false },
];

const SEV_COL: Record<string, string> = { critical: "#EF4444", warning: "#F59E0B", info: "#3B7BF6" };
const STATUS_COL = (s: string) => s === "operational" ? "#10B981" : s === "degraded" ? "#F59E0B" : "#EF4444";

// Nigeria outline paths
const _x = (lng: number) => ((lng - 2.5) / 12) * 440;
const _y = (lat: number) => ((14.5 - lat) / 11) * 340;
const OUTLINE = "M32,262 L88,290 L106,307 L141,327 L158,332 L194,327 L221,321 L244,300 L280,280 L297,267 L332,257 L368,223 L385,190 L402,140 L420,73 L425,33 L385,23 L332,10 L262,10 L209,13 L157,13 L104,10 L59,30 L35,23 L18,23 L7,43 L7,73 L12,157 L7,207 L7,240 Z";

// ── Components ────────────────────────────────────────────────────────────────

function HealthGauge({ score }: { score: number }) {
  const r = 56, circ = 2 * Math.PI * r;
  const pct = score / 100;
  const col = score >= 90 ? "#10B981" : score >= 75 ? "#F59E0B" : "#EF4444";
  return (
    <div className="flex flex-col items-center justify-center p-6 rounded-2xl border border-white/[0.06]" style={{ background: "#0F1320" }}>
      <svg width="140" height="140" viewBox="0 0 140 140" className="-rotate-90">
        <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
        <circle cx="70" cy="70" r={r} fill="none" stroke={col} strokeWidth="10"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - pct)}
          strokeLinecap="round" style={{ transition: "stroke-dashoffset 1s ease", filter: `drop-shadow(0 0 6px ${col}80)` }} />
      </svg>
      <div className="-mt-20 text-center">
        <div className="text-4xl font-black" style={{ color: col }}>{score.toFixed(1)}</div>
        <div className="text-[11px] text-[#6B7280] mt-0.5">Network Health</div>
      </div>
      <div className="grid grid-cols-3 gap-3 mt-6 w-full">
        {[["RAN", "98.7%", "#10B981"], ["Core", "91.4%", "#F59E0B"], ["TX", "95.2%", "#10B981"]].map(([k, v, c]) => (
          <div key={k as string} className="text-center">
            <div className="text-[16px] font-black" style={{ color: c as string }}>{v}</div>
            <div className="text-[10px] text-[#6B7280]">{k}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NetworkMap() {
  const [tooltip, setTooltip] = useState<typeof REGIONS[0] | null>(null);
  return (
    <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.06]">
        <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Nigeria Network Map</h2>
        <div className="flex items-center gap-3 text-[10px]">
          {[["#10B981","Operational"],["#F59E0B","Degraded"],["#EF4444","Down"]].map(([c,l]) => (
            <span key={l as string} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: c as string }} /><span className="text-[#6B7280]">{l}</span>
            </span>
          ))}
        </div>
      </div>
      <div className="p-4 relative">
        <svg viewBox="0 0 440 340" className="w-full" style={{ maxHeight: 280 }}>
          <path d={OUTLINE} fill="#131625" stroke="#2D3250" strokeWidth="1.5" />
          {REGIONS.map(r => {
            const cx = _x(r.lng), cy = _y(r.lat);
            const col = STATUS_COL(r.status);
            const rad = Math.max(7, Math.min(18, 6 + r.sites * 0.25));
            return (
              <g key={r.name} onMouseEnter={() => setTooltip(r)} onMouseLeave={() => setTooltip(null)} style={{ cursor: "pointer" }}>
                {r.incidents > 0 && <circle cx={cx} cy={cy} r={rad + 8} fill={col} opacity={0.12} style={{ animation: "ping-svg 2s ease infinite" }} />}
                <circle cx={cx} cy={cy} r={rad} fill={col} opacity={0.9} stroke="white" strokeWidth="0.6" />
                <text x={cx} y={cy - rad - 4} textAnchor="middle" fontSize="6" fill="#E5E7EB" fontWeight="700">{r.name}</text>
                <text x={cx} y={cy + 4} textAnchor="middle" fontSize="5" fill="white" fontWeight="bold">{r.score}%</text>
              </g>
            );
          })}
        </svg>
        {tooltip && (
          <div className="absolute bottom-6 left-6 px-4 py-3 rounded-xl text-xs pointer-events-none z-10"
            style={{ background: "#1a1d27", border: "1px solid rgba(255,255,255,0.1)" }}>
            <div className="font-bold text-[#E5E7EB] mb-1">{tooltip.name}</div>
            <div className="text-[#6B7280] space-y-0.5">
              <div>Health: <span style={{ color: STATUS_COL(tooltip.status) }}>{tooltip.score}%</span></div>
              <div>Sites: {tooltip.sites}</div>
              <div>Incidents: <span className={tooltip.incidents > 0 ? "text-red-400" : "text-emerald-400"}>{tooltip.incidents}</span></div>
            </div>
          </div>
        )}
      </div>
      <style>{`@keyframes ping-svg{0%,100%{opacity:.1}50%{opacity:.3}}`}</style>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NetworkIntelligencePage() {
  const { messages, isLoading, sendMessage } = useChat();
  const chatMessages = messages.map(m => ({
    id: m.id, role: m.role, content: m.content,
    reasoning_steps: m.trace?.map(t => ({ agent: t.agent, status: "done" as const, message: t.description, timestamp: t.timestamp })),
    timestamp: m.timestamp,
  }));
  const overallScore = REGIONS.reduce((s, r) => s + r.score, 0) / REGIONS.length;

  return (
    <AppShell title="Network Intelligence" subtitle="Real-time RAN, Core and Transmission health"
      actions={
        <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-3 py-1.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-live 2s ease infinite" }} />Live
        </span>
      }>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Left column: gauge + incidents */}
        <div className="space-y-4">
          <HealthGauge score={overallScore} />
          {/* Incident feed */}
          <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
            <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-[#E5E7EB]">Active Incidents</h3>
              <span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">
                {INCIDENTS.filter(i => i.sev === "critical").length} critical
              </span>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {INCIDENTS.map(inc => {
                const c = SEV_COL[inc.sev];
                return (
                  <div key={inc.id} className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors" style={{ borderLeft: `3px solid ${c}` }}>
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] text-[#D1D5DB] font-medium truncate">{inc.title}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[9.5px] font-bold uppercase px-1.5 py-0.5 rounded-full" style={{ color: c, background: `${c}15` }}>{inc.sev}</span>
                        {inc.sla && <span className="text-[9px] font-bold text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded-full">SLA</span>}
                        <span className="text-[10px] text-[#4B5563]">{inc.age} ago</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Map */}
        <div className="xl:col-span-2 space-y-4">
          <NetworkMap />
          {/* NOC Chat */}
          <div className="rounded-2xl border border-white/[0.06] flex flex-col overflow-hidden" style={{ background: "#0F1320", minHeight: 280 }}>
            <div className="px-4 py-3 border-b border-white/[0.06]">
              <h3 className="text-[13px] font-bold text-[#E5E7EB]">🛡️ Network Intelligence Query</h3>
            </div>
            <div className="flex-1 min-h-0">
              <ChatWindow conversationId="net" messages={chatMessages} isStreaming={isLoading} />
            </div>
            <InputBar onSend={sendMessage} isStreaming={isLoading} placeholder="Ask about network incidents, coverage, SLA…" />
          </div>
        </div>
      </div>
      <style>{`@keyframes pulse-live{0%,100%{opacity:.4}50%{opacity:1}}`}</style>
    </AppShell>
  );
}
