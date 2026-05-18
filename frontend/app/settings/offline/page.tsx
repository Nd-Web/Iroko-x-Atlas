"use client";

import AppShell from "@/components/layout/AppShell";
import { useState, useEffect } from "react";

const BUNDLES = [
  { name: "Kano-Kaduna Rollout Q2", size: "48 MB", docs: 34, synced: "Today 06:11",  status: "ready"    },
  { name: "Lagos Fibre Phase 3",    size: "62 MB", docs: 51, synced: "Yesterday",    status: "ready"    },
  { name: "Abuja 5G FWA Sites",     size: "31 MB", docs: 22, synced: "Apr 29",       status: "outdated" },
];

export default function OfflinePage() {
  const [modalOpen, setModalOpen] = useState<string | null>(null);

  useEffect(() => {
    if (!modalOpen) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setModalOpen(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [modalOpen]);

  return (
    <AppShell title="Offline bundle manager" subtitle="Pre-download document bundles for field edge-cache mode">
      <div className="max-w-[680px] flex flex-col gap-4 mx-auto lg:mx-0">
        {/* Info banner */}
        <div className="flex gap-3 px-[18px] py-[14px] bg-brand-50 border border-brand-100 rounded-lg">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="shrink-0 mt-[1px]">
            <circle cx="9" cy="9" r="7.5" stroke="var(--color-brand-600)" strokeWidth="1.4"/>
            <path d="M9 8.25V12M9 6h.008" stroke="var(--color-brand-600)" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
          <p className="text-[13px] text-brand-800 leading-[1.6] m-0">
            Bundles sync automatically when you return to coverage.
          </p>
        </div>

        {/* Bundle list */}
        <div className="card overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center px-5 py-[14px] border-b border-border-default gap-3">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Your bundles</h2>
              <p className="text-xs text-gray-400 mt-[2px]">{BUNDLES.length} bundles · {BUNDLES.reduce((a, b) => a + parseInt(b.size), 0)} MB</p>
            </div>
            <button 
              className="btn-primary py-2 px-[14px] text-[13px] flex items-center justify-center gap-1.5 w-full sm:w-auto font-semibold"
              onClick={() => setModalOpen("build")}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 2v6M4 6l3-3 3 3M2 10h10" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Build new
            </button>
          </div>

          <div className="divide-y divide-border-default">
            {BUNDLES.map((b) => (
              <div
                key={b.name}
                className="flex flex-col sm:flex-row sm:justify-between sm:items-center px-5 py-4 gap-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`size-9 rounded-lg flex items-center justify-center shrink-0 ${
                      b.status === "outdated"
                        ? "bg-warning-50 border border-warning-100"
                        : "bg-success-50 border border-success-100"
                    }`}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={b.status === "outdated" ? "text-warning-700" : "text-success-700"}>
                      {b.status === "outdated" ? (
                        <path d="M8 2v8M5 7l3 3 3-3M2 13h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      ) : (
                        <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      )}
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <div className="text-[13.5px] font-medium text-gray-800 mb-[3px] truncate">{b.name}</div>
                    <div className="text-xs text-gray-400 truncate">
                      {b.docs} docs · {b.size} · {b.synced}
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between sm:justify-end gap-2 shrink-0">
                  <span
                    className={`text-[10px] md:text-[11px] font-semibold px-2 py-[2px] rounded-full ${
                      b.status === "ready"
                        ? "text-success-700 bg-success-50"
                        : "text-warning-700 bg-warning-50"
                    }`}
                  >
                    {b.status === "ready" ? "Ready" : "Update"}
                  </span>
                  <button 
                    className="btn-secondary py-[5px] px-[10px] text-xs font-medium"
                    onClick={() => setModalOpen(b.name)}
                  >
                    {b.status === "outdated" ? "Sync" : "Download"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6" onClick={() => setModalOpen(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "440px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900 truncate">
                {modalOpen === "build" ? "Build bundle" : "Sync bundle"}
              </h2>
              <button onClick={() => setModalOpen(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-6 overflow-y-auto">
              {modalOpen === "build" ? (
                <div className="flex flex-col gap-4">
                  <div>
                    <label className="label-base block mb-1.5">Bundle Name</label>
                    <input type="text" className="input-base w-full" placeholder="e.g. Lagos Phase 4" />
                  </div>
                  <div>
                    <label className="label-base block mb-1.5">Sites / Location</label>
                    <input type="text" className="input-base w-full" placeholder="e.g. LGS-01, LGS-02" />
                  </div>
                </div>
              ) : (
                <p className="text-[13px] text-gray-600 leading-[1.6]">
                  Starting sync for <strong>{modalOpen}</strong>.
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setModalOpen(null)}>Cancel</button>
              <button className="btn-primary" onClick={() => setModalOpen(null)}>
                {modalOpen === "build" ? "Build" : "Start"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
