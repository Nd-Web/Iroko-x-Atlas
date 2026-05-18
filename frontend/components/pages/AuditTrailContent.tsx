"use client";

import { useState, useEffect } from "react";

const ENTRIES = [
  { id: "AUD-29041", user: "Adaeze Okonkwo",  query: "Wetin dey happen for Ikeja cluster?",          agent: "Strategist", chunks: 5, latency: "1.84s", time: "09:41:22" },
  { id: "AUD-29040", user: "Adaeze Okonkwo",  query: "SLA exposure if not resolved in 2 hours?",      agent: "Analyst",    chunks: 3, latency: "2.31s", time: "09:43:07" },
  { id: "AUD-29039", user: "Tunde Adeyemi",   query: "List DPIAs without DPO approval",               agent: "Researcher", chunks: 4, latency: "1.62s", time: "09:10:55" },
  { id: "AUD-29038", user: "Ifeoma Chukwu",   query: "Generate draft NDPA audit return Q1 2026",      agent: "Scribe",     chunks: 9, latency: "4.12s", time: "08:54:31" },
  { id: "AUD-29037", user: "Bukola Adesanya", query: "Current data tariff for Yello Pulse 5GB",       agent: "Researcher", chunks: 2, latency: "0.94s", time: "08:32:14" },
  { id: "AUD-29036", user: "Musa Garba",      query: "Site card for KAN-0341",                        agent: "Researcher", chunks: 1, latency: "0.71s", time: "07:18:40" },
];

const AGENT_COLORS: Record<string, string> = {
  Strategist: "#4A55D4",
  Researcher: "#2E90FA",
  Analyst:    "#17B26A",
  Scribe:     "#F79009",
  Watchdog:   "#F04438",
};

const SOURCES: Record<string, string[]> = {
  "AUD-29041": ["INC-4821 ServiceNow record", "Ikeja Cluster HLD v3.2", "NOC ops runbook Q1-2026", "INC-4311 RCA report", "CHG-8819 change log"],
  "AUD-29040": ["HW-MTN-2024-0341 SLA Schedule", "INC-4821 impact assessment", "Contracts penalty calculator"],
  "AUD-29039": ["DPIA register 2026", "MoMo Analytics DPIA v2", "NDPA Art. 34 checklist", "DPO approval log"],
  "AUD-29038": ["NDPA audit template Q1-2026", "Processing activities register", "Breach notification log", "Data transfer agreements", "Q4-2025 audit return", "DPIAs (×3)", "NCC QoS Return Q4-2025", "NDPC correspondence log", "Legal opinions archive"],
  "AUD-29037": ["Yello Pulse tariff sheet Apr-2026", "Care agent escalation log"],
  "AUD-29036": ["KAN-0341 site card", "Kano cluster network diagram"],
};

const STATS = [
  { label: "Queries today",       value: "1,284", sub: "100% cited",                  accent: "#4A55D4" },
  { label: "Unique users",        value: "6",     sub: "across all roles",             accent: "#17B26A" },
  { label: "High-stakes queries", value: "14",    sub: "priority processing",          accent: "#F79009" },
  { label: "Refused queries",     value: "2",     sub: "policy guardrail triggered",   accent: "#F04438" },
];

const COL = "110px 130px 1fr 90px 60px 80px 70px";

type Entry = typeof ENTRIES[0];

export default function AuditTrailContent() {
  const [selected, setSelected] = useState<Entry | null>(null);
  const [exported, setExported] = useState(false);

  useEffect(() => {
    if (!selected) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setSelected(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [selected]);

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[14px]">
        {STATS.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-[18px] px-5">
            <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            <div className="text-[28px] font-bold text-gray-900 tracking-[-0.04em] leading-none mb-[5px]">{s.value}</div>
            <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{s.label}</div>
            <div className="text-[11.5px] text-gray-400">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Integrity banner */}
      <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-[10px] px-4 py-3 bg-success-50 border border-success-100 rounded-lg">
        <div className="flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0">
            <circle cx="8" cy="8" r="6.5" stroke="var(--color-success-700)" strokeWidth="1.3" />
            <path d="M5 8l2 2 4-4" stroke="var(--color-success-700)" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-[13px] font-semibold text-success-700 whitespace-nowrap">Audit log integrity verified</span>
        </div>
        <span className="text-[12px] md:text-[13px] text-success-700 opacity-75">All 1,284 entries cryptographically chained. Last hash verified 30s ago.</span>
      </div>

      {/* Query log */}
      <div className="card overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between px-4 md:px-5 py-[14px] border-b border-border-default gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Query log</h2>
            <p className="text-xs text-gray-400 mt-[2px]">NDPA-grade · cryptographically chained</p>
          </div>
          <div className="flex gap-2">
            <input type="text" placeholder="Search log…" className="input-base flex-1 md:w-[190px] py-[7px] px-3" />
            <button
              className={`btn-secondary py-[7px] px-3 text-[12.5px] shrink-0 ${exported ? "text-success-700" : ""}`}
              onClick={() => { setExported(true); setTimeout(() => setExported(false), 2500); }}
            >
              {exported ? "Exported ✓" : "Export CSV"}
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <div className="min-w-[1000px]">
            <div className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3" style={{ gridTemplateColumns: COL }}>
              {["Entry ID", "User", "Query", "Agent", "Sources", "Latency", "Time"].map((h) => (
                <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
              ))}
            </div>

            {ENTRIES.map((e) => (
              <div
                key={e.id}
                onClick={() => setSelected(e)}
                className="grid items-center py-3 px-5 gap-3 border-b border-border-default cursor-pointer hover:bg-gray-50 transition-colors"
                style={{ gridTemplateColumns: COL }}
              >
                <span className="font-mono text-[11px] text-brand-700 font-semibold">{e.id}</span>
                <span className="text-xs text-gray-600">{e.user.split(" ")[0]} {e.user.split(" ")[1][0]}.</span>
                <span className="text-[13px] text-gray-700 overflow-hidden text-ellipsis whitespace-nowrap">{e.query}</span>
                <span className="text-[11px] font-semibold px-2 py-[2px] rounded-full w-fit" style={{ color: AGENT_COLORS[e.agent], background: `${AGENT_COLORS[e.agent]}14` }}>{e.agent}</span>
                <span className="text-[13px] text-gray-500 text-center">{e.chunks}</span>
                <span className="font-mono text-xs text-gray-400">{e.latency}</span>
                <span className="text-[11.5px] text-gray-300 font-mono">{e.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Audit entry detail modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden" style={{ maxWidth: "560px" }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-gray-900">Query trace</h2>
                <p className="text-[11.5px] text-gray-400 mt-0.5 font-mono truncate">{selected.id}</p>
              </div>
              <button onClick={() => setSelected(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400 transition-colors">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-5">
              {/* User + agent row */}
              <div className="flex items-center gap-3">
                <div className="size-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[11px] font-bold shrink-0">
                  {selected.user.split(" ").map(n => n[0]).join("").slice(0, 2)}
                </div>
                <div className="min-w-0">
                  <span className="text-[13px] font-semibold text-gray-800 block truncate">{selected.user}</span>
                  <span className="text-[11.5px] text-gray-400 font-mono">{selected.time}</span>
                </div>
                <span className="ml-auto text-[11px] font-semibold px-2 py-[2px] rounded-full" style={{ color: AGENT_COLORS[selected.agent], background: `${AGENT_COLORS[selected.agent]}14` }}>{selected.agent}</span>
              </div>

              {/* Query */}
              <div className="bg-gray-50 rounded-lg border border-border-default px-4 py-3.5 text-[13.5px] text-gray-800 font-medium italic leading-relaxed">
                "{selected.query}"
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-1 xs:grid-cols-2 gap-2">
                {[
                  { label: "Sources",      value: `${selected.chunks} docs` },
                  { label: "Latency",      value: selected.latency },
                ].map((m) => (
                  <div key={m.label} className="bg-gray-50 rounded-lg px-3 py-2.5 text-center">
                    <div className="text-[10px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-1">{m.label}</div>
                    <div className="text-[12px] font-semibold text-gray-700 font-mono truncate">{m.value}</div>
                  </div>
                ))}
              </div>

              {/* Response summary */}
              <div>
                <div className="text-[12px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-2">Response summary</div>
                <p className="text-[13px] text-gray-600 leading-[1.6] m-0">
                  The AI synthesised an answer grounded across {selected.chunks} source document{selected.chunks !== 1 ? "s" : ""}.
                </p>
              </div>

              {/* Cited sources */}
              <div>
                <div className="text-[12px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-2">Cited sources</div>
                <div className="flex flex-col gap-1.5">
                  {(SOURCES[selected.id] ?? []).map((src) => (
                    <div key={src} className="flex items-center gap-2 text-[12.5px] text-gray-600">
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-gray-300 shrink-0">
                        <path d="M7.5 1H3A1.5 1.5 0 0 0 1.5 2.5v7A1.5 1.5 0 0 0 3 11h6A1.5 1.5 0 0 0 10.5 9.5V4l-3-3Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                        <path d="M7.5 1V4H10.5" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                      </svg>
                      <span className="truncate">{src}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Compliance note */}
              <div className="flex gap-2.5 bg-success-50 border border-success-100 rounded-lg px-3.5 py-3">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="shrink-0 mt-[1px] text-success-600">
                  <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3"/>
                  <path d="M4.5 7l2 2 3.5-3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <p className="text-[12px] text-success-700 leading-[1.5] m-0">This entry is cryptographically signed and robust.</p>
              </div>
            </div>
            <div className="flex justify-end px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
