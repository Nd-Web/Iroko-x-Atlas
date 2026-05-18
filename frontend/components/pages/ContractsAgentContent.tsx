"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

const STATS = [
  { label: "Active contracts",   value: "214",    sub: "vendor + customer",        accent: "#4A55D4", color: "#4A55D4" },
  { label: "Total SLA exposure", value: "₦58.8M", sub: "at current incidents",     accent: "#F04438", color: "#F04438" },
  { label: "Auto-renewing 30d",  value: "7",      sub: "review required",          accent: "#F79009", color: "#F79009" },
  { label: "Expiring 90d",       value: "12",     sub: "renegotiation pipeline",   accent: "#0BA5EC", color: "#0BA5EC" },
];

const CONTRACTS = [
  { id: "HW-MTN-2024-0341",   party: "Huawei Technologies Nigeria",  type: "Vendor MSA",         value: "₦4.2B", exposure: "₦27.3M", renewal: "Jan 2027" },
  { id: "ENT-ACC-2023-0088",  party: "AccessBank HQ",                type: "Enterprise Customer", value: "₦1.8B", exposure: "₦8.4M",  renewal: "Aug 2026" },
  { id: "ENT-MTN-LZ2-0112",   party: "MTN Enterprise Lagos Zone 2",  type: "Enterprise Customer", value: "₦2.1B", exposure: "₦12.1M", renewal: "Dec 2026" },
  { id: "ENT-DAN-2024-0071",  party: "Dangote Group",                type: "Enterprise Customer", value: "₦3.4B", exposure: "₦6.8M",  renewal: "Mar 2027" },
  { id: "IHS-LEA-2023-0044",  party: "IHS Towers Nigeria",           type: "Tower Lease",         value: "₦8.9B", exposure: "₦4.2M",  renewal: "Jun 2026" },
];

const COL = "160px 1.5fr 1fr 100px 110px 110px";

export default function ContractsAgentContent() {
  const [selected, setSelected] = useState<typeof CONTRACTS[0] | null>(null);
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
      <div className="grid grid-cols-4 gap-[14px]">
        {STATS.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-[18px] px-5">
            <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            <div className="text-[28px] font-bold tracking-[-0.04em] leading-none mb-[5px]" style={{ color: s.color }}>{s.value}</div>
            <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{s.label}</div>
            <div className="text-[11.5px] text-gray-300">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* High-exposure contracts table */}
      <div className="card overflow-hidden">
        <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">High-exposure contracts</h2>
            <p className="text-xs text-gray-400 mt-[2px]">Sorted by current SLA credit exposure</p>
          </div>
          <button 
            className={`btn-secondary py-[5px] px-3 text-xs ${exported ? "text-success-700" : ""}`}
            onClick={() => { setExported(true); setTimeout(() => setExported(false), 2500); }}
          >
            {exported ? "Exported ✓" : "Export"}
          </button>
        </div>
        <div className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3" style={{ gridTemplateColumns: COL }}>
          {["Contract ID", "Counterparty", "Type", "Value", "SLA Exposure", "Renewal"].map((h) => (
            <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
          ))}
        </div>
        {CONTRACTS.map((c, i) => (
          <div
            key={c.id}
            onClick={() => setSelected(c)}
            className={`grid items-center py-[13px] px-5 gap-3 cursor-pointer hover:bg-gray-50 transition-colors${i < CONTRACTS.length - 1 ? " border-b border-border-default" : ""}`}
            style={{ gridTemplateColumns: COL }}
          >
            <span className="font-mono text-[11px] text-brand-700 font-semibold">{c.id}</span>
            <span className="text-[13px] font-medium text-gray-700">{c.party}</span>
            <span className="text-xs text-gray-400">{c.type}</span>
            <span className="text-[13px] font-semibold text-gray-700 font-mono">{c.value}</span>
            <span className="text-xs font-bold text-danger-700">{c.exposure}</span>
            <span className="text-xs text-gray-400">{c.renewal}</span>
          </div>
        ))}
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "560px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">{selected.id}</h2>
              <button onClick={() => setSelected(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto px-5 py-5 gap-5 flex flex-col">
              <div>
                <h1 className="text-[16px] font-bold text-gray-900 leading-tight">{selected.party}</h1>
                <span className="text-[11px] font-semibold px-2 py-[2px] mt-2 inline-block rounded-full text-brand-700 bg-brand-50">{selected.type}</span>
              </div>
              
              <div className="grid grid-cols-2 gap-3 bg-gray-50 rounded-lg p-4">
                {[
                  { label: "Value", value: selected.value },
                  { label: "SLA Exposure", value: selected.exposure },
                  { label: "Type", value: selected.type },
                  { label: "Renewal", value: selected.renewal }
                ].map((item, idx) => (
                  <div key={idx}>
                    <div className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-0.5">{item.label}</div>
                    <div className="text-[13px] font-semibold text-gray-700 font-mono">{item.value}</div>
                  </div>
                ))}
              </div>

              <div>
                <div className="text-[12px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-2">Key provisions</div>
                <ul className="text-[13px] text-gray-600 pl-4 list-disc space-y-1.5 marker:text-gray-300">
                  <li>Payment terms: Net 45 days from invoice date.</li>
                  <li>Penalty cap: Total SLA penalties capped at 15% of annual contract value.</li>
                  <li>Termination: 90 days written notice required for termination without cause.</li>
                </ul>
              </div>

              {Number(selected.exposure.replace(/[^0-9.]/g, '')) > 10 && (
                <div className="flex gap-2.5 bg-danger-50 border border-danger-100 rounded-lg px-3.5 py-3">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="shrink-0 mt-[1px] text-danger-600">
                    <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3"/>
                    <path d="M7 4v3m0 3h.01" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <p className="text-[12.5px] text-danger-700 leading-[1.4] m-0 font-medium">High SLA exposure. Recommend immediate review of penalty clauses.</p>
                </div>
              )}

              <div>
                <div className="text-[12px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-2">Actions</div>
                <div className="flex gap-2">
                  <Link href="/chat?agent=Contracts" className="btn-primary no-underline text-[12.5px] py-1.5 px-3">Ask Contracts Agent</Link>
                  <button className="btn-secondary text-[12.5px] py-1.5 px-3">Download PDF</button>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
