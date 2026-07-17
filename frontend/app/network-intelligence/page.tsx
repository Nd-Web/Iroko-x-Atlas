"use client";
/**
 * app/network-intelligence/page.tsx — Network Intelligence dashboard.
 * Network health gauge, Nigeria network map, incident feed, vendor SLA watch, chat.
 *
 * Live data: fetches /api/network/heatmap and /api/network/incidents on mount
 * (via the Next.js proxy, which forwards the httpOnly iroko_token cookie).
 * Falls back to the seeded canonical constants below on error/empty response.
 */
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useChat } from "@/hooks/useChat";
import InputBar from "@/components/chat/InputBar";
import ChatWindow from "@/components/chat/ChatWindow";
import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import { useRouter } from "next/navigation";

// ── Types ─────────────────────────────────────────────────────────────────────

interface RegionInfo {
  name: string;
  lat: number;
  lng: number;
  score: number;
  status: string;
  incidents: number;
  sites: number;
  label: string;
}

interface IncidentInfo {
  id: string;
  title: string;
  region: string;
  sev: string;
  age: string;
  sla: boolean;
  priority?: string;
  status?: string;
}

// ── Fallback data (mirrors backend seeds — /api/network) ─────────────────────

const FALLBACK_REGIONS: RegionInfo[] = [
  { name: "Lagos",         lat: 6.45,  lng: 3.4,  score: 98.9, status: "degraded",    incidents: 1, sites: 12, label: "Ikeja cluster — 6 IHS macro sites" },
  { name: "Abuja",         lat: 9.07,  lng: 7.4,  score: 99.2, status: "operational", incidents: 0, sites: 6,  label: "Maitama / CBD cluster" },
  { name: "Kano",          lat: 12.0,  lng: 8.52, score: 98.6, status: "degraded",    incidents: 1, sites: 4,  label: "Kano Metro cluster" },
  { name: "Port Harcourt", lat: 4.84,  lng: 7.04, score: 99.1, status: "operational", incidents: 0, sites: 5,  label: "GRA cluster" },
];

const FALLBACK_INCIDENTS: IncidentInfo[] = [
  { id: "i1", title: "Ikeja Cluster Power Outage — AES Feeder Failure",            region: "Lagos",         sev: "critical", age: "3d", sla: true,  priority: "P1", status: "resolved" },
  { id: "i2", title: "IKJ-004 Sector B Antenna Tilt Fault — Degraded Coverage",    region: "Lagos",         sev: "major",    age: "8h", sla: false, priority: "P2", status: "investigating" },
  { id: "i3", title: "Kano-Kaduna Fibre Cut — ROW Excavation at Km 142",           region: "Kano",          sev: "major",    age: "2h", sla: false, priority: "P2", status: "open" },
  { id: "i4", title: "Port Harcourt GRA — Vandalism at PHC-001",                   region: "Port Harcourt", sev: "critical", age: "5d", sla: true,  priority: "P1", status: "resolved" },
  { id: "i5", title: "Abuja CBD — Maitama Site Software Fault Post-Upgrade",       region: "Abuja",         sev: "major",    age: "6d", sla: false, priority: "P2", status: "resolved" },
];

const VENDOR_WATCH = [
  { id: "v1", title: "IHS Nigeria — Ikeja cluster SLA breach, ₦2.66M exposure (Feb outage)",       sev: "critical", age: "3d" },
  { id: "v2", title: "ATC — Lagos Zone 2 contract expiring in 28 days (12 sites, ₦19.5M/month)",   sev: "warning",  age: "1d" },
  { id: "v3", title: "Julius Berger — Kano-Kaduna fibre Phase 1 SLA milestone at risk",            sev: "info",     age: "2h" },
];

const SEV_COL: Record<string, string> = { critical: "#EF4444", major: "#F97316", warning: "#F59E0B", minor: "#38BDF8", info: "#38BDF8" };
const STATUS_COL = (s: string) => s === "operational" ? "#10B981" : s === "degraded" ? "#F59E0B" : "#EF4444";

const geoUrl = "/nigeria-states.json";

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Relative age from an ISO timestamp: "8m", "3h", "12d". */
function relAge(iso?: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (!isFinite(ms) || ms < 0) return "now";
  const m = Math.floor(ms / 60000);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

/** Loose region match — backend may report "Kano Metro" while the marker says "Kano". */
function inRegion(incidentRegion: string, selected: string): boolean {
  return (
    incidentRegion === selected ||
    incidentRegion.includes(selected) ||
    selected.includes(incidentRegion)
  );
}

// ── Components ────────────────────────────────────────────────────────────────

function HealthGauge({ score }: { score: number }) {
  const r = 56, circ = 2 * Math.PI * r;
  const pct = score / 100;
  const col = score >= 90 ? "#10B981" : score >= 75 ? "#F59E0B" : "#EF4444";
  return (
    <div className="flex flex-col items-center justify-center p-6 rounded-2xl border border-border-default bg-surface-card">
      <svg width="140" height="140" viewBox="0 0 140 140" className="-rotate-90">
        <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
        <circle cx="70" cy="70" r={r} fill="none" stroke={col} strokeWidth="10"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - pct)}
          strokeLinecap="round" style={{ transition: "stroke-dashoffset 1s ease", filter: `drop-shadow(0 0 6px ${col}80)` }} />
      </svg>
      <div className="-mt-20 text-center">
        <div className="text-4xl font-black" style={{ color: col }}>{score.toFixed(1)}</div>
        <div className="text-[11px] text-gray-400 mt-0.5">Network Health</div>
      </div>
      <div className="grid grid-cols-3 gap-3 mt-6 w-full">
        {[["Ikeja Avail", "82.7%", "#EF4444"], ["NCC Min", "95%", "#F59E0B"], ["Drop-call", "12.4%", "#EF4444"]].map(([k, v, c]) => (
          <div key={k as string} className="text-center">
            <div className="text-[16px] font-black" style={{ color: c as string }}>{v}</div>
            <div className="text-[10px] text-gray-400">{k}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NetworkMap({
  regions,
  selectedRegion,
  onSelectRegion
}: {
  regions: RegionInfo[];
  selectedRegion: string | null;
  onSelectRegion: (region: string | null) => void;
}) {
  const [tooltip, setTooltip] = useState<RegionInfo | null>(null);
  return (
    <div className="rounded-2xl border border-border-default bg-surface-card overflow-hidden flex flex-col">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border-default shrink-0">
        <h2 className="text-[14px] font-semibold text-gray-800">Nigeria Network Health Map</h2>
        <div className="flex items-center gap-3 text-[10px]">
          {[["#10B981","Operational"],["#F59E0B","Degraded"],["#EF4444","Down"]].map(([c,l]) => (
            <span key={l as string} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: c as string }} /><span className="text-gray-400">{l}</span>
            </span>
          ))}
        </div>
      </div>
      <div className="flex-1 relative flex items-center justify-center p-4 min-h-[340px]">
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{
            center: [8, 9],
            scale: 2400
          }}
          className="w-full h-full"
        >
          <Geographies geography={geoUrl}>
            {({ geographies }) =>
              geographies.map((geo) => (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill="#17171A"
                  stroke="#2A2A31"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: "none" },
                    hover: { outline: "none", fill: "#1E1E23" },
                    pressed: { outline: "none" }
                  }}
                />
              ))
            }
          </Geographies>

          {regions.map((r) => {
            const col = STATUS_COL(r.status);
            const rad = Math.max(5, Math.min(12, 4 + r.sites * 0.2));
            return (
              <Marker
                key={r.name}
                coordinates={[r.lng, r.lat]}
                onMouseEnter={() => setTooltip(r)}
                onMouseLeave={() => setTooltip(null)}
                onClick={() => onSelectRegion(selectedRegion === r.name ? null : r.name)}
                style={{
                  default: { outline: "none" },
                  hover: { outline: "none" },
                  pressed: { outline: "none" }
                }}
              >
                {r.incidents > 0 && (
                  <circle
                    r={rad + 6}
                    fill={col}
                    opacity={0.12}
                    style={{ animation: "ping-svg 2s ease infinite", cursor: "pointer" }}
                  />
                )}
                <circle
                  r={rad}
                  fill={col}
                  opacity={selectedRegion && selectedRegion !== r.name ? 0.3 : 0.9}
                  stroke={selectedRegion === r.name ? "white" : "white"}
                  strokeWidth={selectedRegion === r.name ? "2" : "0.6"}
                  style={{ cursor: "pointer" }}
                />
                <text
                  textAnchor="middle"
                  y={-rad - 4}
                  style={{ fontSize: "8px", fill: "#EBEBEF", fontWeight: 700 }}
                >
                  {r.name}
                </text>
                <text
                  textAnchor="middle"
                  y={3}
                  style={{ fontSize: "7px", fill: "white", fontWeight: "bold" }}
                >
                  {r.score}%
                </text>
              </Marker>
            );
          })}
        </ComposableMap>

        {tooltip && (
          <div className="absolute bottom-6 left-6 px-4 py-3 rounded-xl text-xs pointer-events-none z-10 shadow-lg"
            style={{ background: "#1A1A1F", border: "1px solid rgba(255,255,255,0.1)" }}>
            <div className="font-bold text-gray-800 mb-0.5">{tooltip.name}</div>
            <div className="text-[9px] text-info-500 mb-1">{tooltip.label}</div>
            <div className="text-gray-400 space-y-0.5">
              <div>Availability: <span style={{ color: STATUS_COL(tooltip.status) }}>{tooltip.score}%</span></div>
              <div>Sites: {tooltip.sites}</div>
              <div>Active incidents: <span className={tooltip.incidents > 0 ? "text-red-400" : "text-emerald-400"}>{tooltip.incidents}</span></div>
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
  const router = useRouter();
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [regions, setRegions] = useState<RegionInfo[]>(FALLBACK_REGIONS);
  const [incidents, setIncidents] = useState<IncidentInfo[]>(FALLBACK_INCIDENTS);
  const { messages, isLoading, error, sendMessage } = useChat();
  const lastQuestionRef = useRef<string>("");
  const handleSend = (content: string) => {
    lastQuestionRef.current = content;
    void sendMessage(content);
  };
  const chatMessages = messages.map(m => ({
    id: m.id, role: m.role, content: m.content,
    reasoning_steps: m.trace?.map(t => ({ agent: t.agent, status: "done" as const, message: t.description, timestamp: t.timestamp })),
    timestamp: m.timestamp,
  }));
  const overallScore = regions.length
    ? regions.reduce((sum, r) => sum + r.score, 0) / regions.length
    : 0;

  // Live data: heatmap + incidents from the seeded backend (same-origin proxy).
  // Falls back silently to the canonical constants above on error/empty.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch("/api/network/heatmap", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          const live = Array.isArray(data?.regions) ? data.regions : [];
          if (!cancelled && live.length > 0) {
            setRegions(live.map((r: Record<string, unknown>): RegionInfo => ({
              name: String(r.region ?? ""),
              lat: Number(r.latitude ?? 0),
              lng: Number(r.longitude ?? 0),
              score: Math.round(Number(r.availability_pct ?? 0) * 10) / 10,
              status: String(r.status ?? "operational"),
              incidents: Number(r.active_incidents ?? 0),
              sites: Number(r.site_count ?? 0),
              label: `${Number(r.operational ?? 0)}/${Number(r.site_count ?? 0)} sites operational`,
            })));
          }
        }
      } catch {
        // keep fallback regions
      }

      try {
        const res = await fetch("/api/network/incidents?days=180", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          const live = Array.isArray(data?.incidents) ? data.incidents : [];
          if (!cancelled && live.length > 0) {
            setIncidents(live.map((i: Record<string, unknown>): IncidentInfo => ({
              id: String(i.id ?? i.incident_ref ?? ""),
              title: String(i.title ?? ""),
              region: String(i.region ?? ""),
              sev: String(i.severity ?? "info"),
              age: relAge(i.started_at as string | null),
              sla: Boolean(i.sla_breached),
              priority: i.priority ? String(i.priority) : undefined,
              status: i.status ? String(i.status) : undefined,
            })));
          }
        }
      } catch {
        // keep fallback incidents
      }
    })();

    return () => { cancelled = true; };
  }, []);

  return (
    <AppShell title="Network Intelligence" subtitle="Real-time network & regulatory monitor"
      actions={
        <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-3 py-1.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-live 2s ease infinite" }} />Live
        </span>
      }>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Left column: gauge + incidents */}
        <div className="space-y-4">
          <HealthGauge score={overallScore} />

          {/* Network incident feed */}
          <div className="rounded-2xl border border-border-default bg-surface-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border-default flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-gray-800">
                {selectedRegion ? `Incidents — ${selectedRegion}` : "Network Incidents"}
                {selectedRegion && (
                  <button onClick={() => setSelectedRegion(null)} className="ml-3 text-[10px] text-gray-400 hover:text-gray-900 underline">
                    Clear
                  </button>
                )}
              </h3>
              <span className="text-[10px] font-bold text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full">
                {incidents.filter(i => i.sev === "critical" && (!selectedRegion || inRegion(i.region, selectedRegion))).length} critical
              </span>
            </div>
            <div className="divide-y divide-border-default">
              {incidents.filter(i => !selectedRegion || inRegion(i.region, selectedRegion)).map(inc => {
                const c = SEV_COL[inc.sev] ?? SEV_COL.info;
                return (
                  <div
                    key={inc.id}
                    onClick={() => router.push(`/chat?q=${encodeURIComponent('Tell me about this network incident: ' + inc.title)}`)}
                    className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 transition-colors cursor-pointer"
                    style={{ borderLeft: `3px solid ${c}` }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-[9px] font-bold text-info-500 bg-info-50 px-1.5 py-0.5 rounded-full border border-info-100">NOC</span>
                        {inc.priority && (
                          <span className="text-[9px] font-bold text-info-500 bg-info-50 px-1.5 py-0.5 rounded-full border border-info-100">{inc.priority}</span>
                        )}
                      </div>
                      <p className="text-[12px] text-gray-800 font-medium truncate hover:text-gray-900">{inc.title}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[9.5px] font-bold uppercase px-1.5 py-0.5 rounded-full" style={{ color: c, background: `${c}15` }}>{inc.sev}</span>
                        {inc.status && <span className="text-[9.5px] font-bold uppercase text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-full">{inc.status}</span>}
                        {inc.sla && <span className="text-[9px] font-bold text-warning-700 bg-warning-50 px-1.5 py-0.5 rounded-full">SLA breach</span>}
                        <span className="text-[10px] text-gray-300">{inc.age} ago</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Vendor SLA watch section */}
          <div className="rounded-2xl border border-orange-400/20 bg-surface-card overflow-hidden">
            <div className="px-4 py-3 border-b border-orange-400/20 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-gray-800">Vendor SLA Watch</h3>
              <span className="text-[9.5px] font-bold text-orange-400 bg-orange-400/10 px-2 py-0.5 rounded-full border border-orange-400/20">Contract Watch</span>
            </div>
            <div className="divide-y divide-border-default">
              {VENDOR_WATCH.map(inc => {
                const c = SEV_COL[inc.sev] ?? SEV_COL.info;
                return (
                  <div
                    key={inc.id}
                    onClick={() => router.push(`/chat?q=${encodeURIComponent('Tell me about this vendor SLA item: ' + inc.title)}`)}
                    className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 transition-colors cursor-pointer"
                    style={{ borderLeft: `3px solid #F97316` }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-[9px] font-bold text-orange-400 bg-orange-400/10 px-1.5 py-0.5 rounded-full border border-orange-400/20">Vendor SLA</span>
                      </div>
                      <p className="text-[12px] text-gray-800 font-medium truncate hover:text-gray-900">{inc.title}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[9.5px] font-bold uppercase px-1.5 py-0.5 rounded-full" style={{ color: c, background: `${c}15` }}>{inc.sev}</span>
                        <span className="text-[10px] text-gray-300">{inc.age} ago</span>
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
          <NetworkMap regions={regions} selectedRegion={selectedRegion} onSelectRegion={setSelectedRegion} />
          {/* NOC Chat */}
          <div className="rounded-2xl border border-border-default bg-surface-card flex flex-col overflow-hidden" style={{ minHeight: 280 }}>
            <div className="px-4 py-3 border-b border-border-default">
              <h3 className="text-[13px] font-bold text-gray-800">Ask Iroko — Network Intelligence</h3>
            </div>
            <div className="flex-1 min-h-0">
              <ChatWindow conversationId="net" messages={chatMessages} isStreaming={isLoading} />
            </div>
            {error && (
              <div className="flex items-center justify-between gap-3 mx-4 mb-2 px-3 py-2 rounded-lg border border-red-400/20 bg-red-400/10">
                <p className="text-[11px] text-red-400 truncate">Message failed: {error}</p>
                {lastQuestionRef.current && (
                  <button
                    onClick={() => void sendMessage(lastQuestionRef.current)}
                    className="text-[11px] font-bold text-red-300 hover:text-white underline shrink-0"
                  >
                    Retry
                  </button>
                )}
              </div>
            )}
            <InputBar onSend={handleSend} isStreaming={isLoading} placeholder="Ask about outages, vendor SLAs, NCC QoS returns…" />
          </div>
        </div>
      </div>
      <style>{`@keyframes pulse-live{0%,100%{opacity:.4}50%{opacity:1}}`}</style>
    </AppShell>
  );
}
