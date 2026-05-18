"use client";

import AppShell from "@/components/layout/AppShell";
import { useState, useEffect } from "react";

const REPORTS = [
  { title: "NCC Q1 2026 QoS Return",       due: "May 15, 2026", status: "In progress", regulator: "NCC",  progress: 60,  progressColor: "#4A55D4" },
  { title: "NDPA Annual Audit Return 2026", due: "Jun 30, 2026", status: "Not started", regulator: "NDPC", progress: 0,   progressColor: "#4A55D4" },
  { title: "NDPA Breach Notification Log",  due: "Ongoing",      status: "Clear",       regulator: "NDPC", progress: 100, progressColor: "#17B26A" },
];

export default function ComplianceReportsPage() {
  const [modal, setModal] = useState<{type: "report" | "dpia" | "dsr", title?: string} | null>(null);

  useEffect(() => {
    if (!modal) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setModal(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [modal]);

  return (
    <AppShell title="Compliance reports" subtitle="NCC returns · NDPA audit · DPIA tracker · DSR queue">
      {/* Report cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-[14px]">
        {REPORTS.map((r) => (
          <div key={r.title} className="card flex flex-col gap-3 px-[22px] py-5">
            <div className="flex justify-between items-start">
              <span className="text-[11px] font-bold text-brand-700 bg-brand-50 px-2 py-[2px] rounded-full">
                {r.regulator}
              </span>
              <span className="text-[11.5px] text-gray-400">Due {r.due}</span>
            </div>

            <h3 className="text-sm font-semibold text-gray-800 leading-[1.4] m-0">{r.title}</h3>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <span className={`text-xs font-semibold ${r.progress === 100 ? "text-success-700" : r.progress === 0 ? "text-gray-400" : "text-brand-700"}`}>
                  {r.status}
                </span>
                <span className="text-xs text-gray-400">{r.progress}%</span>
              </div>
              <div className="h-[5px] bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-[width] duration-[400ms] ease-in-out" style={{ width: `${r.progress}%`, background: r.progressColor }} />
              </div>
            </div>

            <button 
              className="btn-secondary mt-auto" 
              style={{ padding: "6px 14px", fontSize: "12.5px" }}
              onClick={() => setModal({ type: "report", title: r.title })}
            >
              Open report
            </button>
          </div>
        ))}
      </div>

      {/* DPIA wizard */}
      <div className="card flex flex-col md:flex-row md:items-center justify-between gap-6 px-6 md:px-9 py-6 md:py-8 mt-6">
        <div className="flex items-start gap-4">
          <div className="size-11 rounded-[10px] bg-brand-50 border border-brand-100 flex items-center justify-center shrink-0">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="text-brand-600">
              <rect x="3" y="3" width="16" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M7 11h8M11 7v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em] mb-[5px]">
              DPIA Wizard
            </h2>
            <p className="text-[13px] text-gray-400 leading-relaxed max-w-[500px] m-0">
              Start a new Data Protection Impact Assessment. Field mapping is automated via the Atlas Scribe agent.
            </p>
          </div>
        </div>
        <button 
          className="btn-primary shrink-0 w-full md:w-auto" 
          style={{ padding: "10px 20px" }}
          onClick={() => setModal({ type: "dpia" })}
        >
          Start new DPIA
        </button>
      </div>

      {/* DSR queue summary */}
      <div className="card overflow-hidden mt-6">
        <div className="px-5 py-4 border-b border-border-default flex justify-between items-center">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">DSR queue</h2>
            <p className="text-xs text-gray-400 mt-[2px]">Data subject requests</p>
          </div>
          <button className="btn-secondary" style={{ padding: "6px 12px", fontSize: "12.5px" }}>View all</button>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[600px] md:min-w-0">
            {[
              { id: "DSR-0041", type: "Right to access",        daysLeft: 1, status: "urgent"  },
              { id: "DSR-0040", type: "Right to erasure",       daysLeft: 3, status: "pending" },
              { id: "DSR-0039", type: "Right to rectification", daysLeft: 4, status: "pending" },
            ].map((dsr, i, arr) => (
              <div
                key={dsr.id}
                className={`flex items-center justify-between px-5 py-[13px] gap-4${i < arr.length - 1 ? " border-b border-border-default" : ""}`}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-brand-700 font-semibold">{dsr.id}</span>
                  <span className="text-[13px] text-gray-700 font-medium">{dsr.type}</span>
                </div>
                <div className="flex items-center gap-[10px]">
                  <span className={`text-xs ${dsr.daysLeft <= 1 ? "text-danger-700" : "text-gray-500"}`}>
                    {dsr.daysLeft} day{dsr.daysLeft !== 1 ? "s" : ""} left
                  </span>
                  <span className={`text-[11px] font-semibold px-2 py-[2px] rounded-full ${dsr.status === "urgent" ? "text-danger-700 bg-danger-50" : "text-warning-700 bg-warning-50"}`}>
                    {dsr.status === "urgent" ? "Urgent" : "Pending"}
                  </span>
                  <button 
                    className="btn-secondary" 
                    style={{ padding: "4px 10px", fontSize: "12px" }}
                    onClick={() => setModal({ type: "dsr", title: dsr.id })}
                  >
                    Respond
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6" onClick={() => setModal(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "480px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900 truncate">
                {modal.type === "report" ? modal.title : modal.type === "dpia" ? "Start DPIA Wizard" : `Respond to ${modal.title}`}
              </h2>
              <button onClick={() => setModal(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-6">
              <p className="text-[13px] text-gray-600 leading-[1.6]">
                This is a placeholder for the {modal.type === "report" ? "Report viewer" : modal.type === "dpia" ? "DPIA initiation process" : "DSR response editor"}.
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setModal(null)}>Close</button>
              <button 
                className="btn-primary"
                onClick={() => setModal(null)}
              >
                {modal.type === "dsr" ? "Submit Response" : "Continue"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
