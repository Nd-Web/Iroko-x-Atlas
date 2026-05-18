const fs = require('fs');

// 1. compliance/reports
const complianceReports = `"use client";

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
      <div className="grid grid-cols-3 gap-[14px]">
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
                <span className={\`text-xs font-semibold \${r.progress === 100 ? "text-success-700" : r.progress === 0 ? "text-gray-400" : "text-brand-700"}\`}>
                  {r.status}
                </span>
                <span className="text-xs text-gray-400">{r.progress}%</span>
              </div>
              <div className="h-[5px] bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-[width] duration-[400ms] ease-in-out" style={{ width: \`\${r.progress}%\`, background: r.progressColor }} />
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
      <div className="card flex items-center justify-between gap-6 px-9 py-8 mt-6">
        <div className="flex items-start gap-4">
          <div className="size-11 rounded-[10px] bg-brand-50 border border-brand-100 flex items-center justify-center shrink-0">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="text-brand-600">
              <rect x="3" y="3" width="16" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M7 11h8M11 7v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em] mb-[5px]">
              DPIA Wizard
            </h2>
            <p className="text-[13px] text-gray-400 leading-relaxed max-w-[500px] m-0">
              Start a new Data Protection Impact Assessment. Iroko AI will pre-fill fields from your existing processing records and policies, and guide you through NDPA requirements.
            </p>
          </div>
        </div>
        <button 
          className="btn-primary shrink-0" 
          style={{ padding: "10px 20px" }}
          onClick={() => setModal({ type: "dpia" })}
        >
          Start new DPIA
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="ml-1.5">
            <path d="M3 7h8M8 4l3 3-3 3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      {/* DSR queue summary */}
      <div className="card overflow-hidden mt-6">
        <div className="px-5 py-4 border-b border-border-default flex justify-between items-center">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">DSR queue</h2>
            <p className="text-xs text-gray-400 mt-[2px]">Data subject requests — must respond within 30 days</p>
          </div>
          <button className="btn-secondary" style={{ padding: "6px 12px", fontSize: "12.5px" }}>View all</button>
        </div>
        {[
          { id: "DSR-0041", type: "Right to access",        daysLeft: 1, status: "urgent"  },
          { id: "DSR-0040", type: "Right to erasure",       daysLeft: 3, status: "pending" },
          { id: "DSR-0039", type: "Right to rectification", daysLeft: 4, status: "pending" },
        ].map((dsr, i, arr) => (
          <div
            key={dsr.id}
            className={\`flex items-center justify-between px-5 py-[13px] gap-4\${i < arr.length - 1 ? " border-b border-border-default" : ""}\`}
          >
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-brand-700 font-semibold">{dsr.id}</span>
              <span className="text-[13px] text-gray-700 font-medium">{dsr.type}</span>
            </div>
            <div className="flex items-center gap-[10px]">
              <span className={\`text-xs \${dsr.daysLeft <= 1 ? "text-danger-700" : "text-gray-500"}\`}>
                {dsr.daysLeft} day{dsr.daysLeft !== 1 ? "s" : ""} left
              </span>
              <span className={\`text-[11px] font-semibold px-2 py-[2px] rounded-full \${dsr.status === "urgent" ? "text-danger-700 bg-danger-50" : "text-warning-700 bg-warning-50"}\`}>
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

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setModal(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "480px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">
                {modal.type === "report" ? modal.title : modal.type === "dpia" ? "Start DPIA Wizard" : \`Respond to \${modal.title}\`}
              </h2>
              <button onClick={() => setModal(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-6">
              <p className="text-[13px] text-gray-600 leading-[1.6]">
                This is a placeholder for the {modal.type === "report" ? "Report viewer" : modal.type === "dpia" ? "DPIA initiation process" : "DSR response editor"}. Forms and fields will be generated dynamically based on the regulatory configuration.
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
`;
fs.writeFileSync("app/compliance/reports/page.tsx", complianceReports);

// 2. settings/integrations/page.tsx
const integrationsCode = `"use client";

import AppShell from "@/components/layout/AppShell";
import { useState, useEffect } from "react";

const INTEGRATIONS = [
  {
    name: "Microsoft Teams",
    desc: "Bot integration via Microsoft 365 plugin. Accessible from any Teams channel or meeting.",
    status: "connected",
    category: "Messaging",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="2" y="5" width="10" height="10" rx="2" fill="#5558AF"/>
        <rect x="10" y="8" width="8" height="7" rx="2" fill="#7B83EB"/>
        <circle cx="14" cy="5" r="3" fill="#5558AF"/>
      </svg>
    ),
  },
  {
    name: "WhatsApp Business",
    desc: "Voice notes and text queries for field staff and trade partners. Fully agent-aware.",
    status: "connected",
    category: "Messaging",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="9" fill="#25D366"/>
        <path d="M10 5.5C7.5 5.5 5.5 7.5 5.5 10c0 .88.24 1.71.66 2.42L5.5 14.5l2.18-.63A4.5 4.5 0 0 0 10 14.5c2.5 0 4.5-2 4.5-4.5S12.5 5.5 10 5.5Z" fill="white" fillOpacity=".9"/>
        <path d="M8 9.5C8 9 8.5 8 9.25 8.5c.38.25.5 1.25 1.25 1.75s1.5-.25 2 .25-.25 1.5-1 1.5c-1 0-3-1-3.5-2Z" fill="#25D366"/>
      </svg>
    ),
  },
  {
    name: "Microsoft Entra ID",
    desc: "SSO authentication and ABAC attribute claims from your directory. MFA enforced.",
    status: "connected",
    category: "Identity",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 2L2 6v8l8 4 8-4V6L10 2Z" fill="#0078D4"/>
        <path d="M10 2v18M2 6l8 4M18 6l-8 4" stroke="white" strokeWidth="1" strokeOpacity=".4"/>
      </svg>
    ),
  },
  {
    name: "Slack",
    desc: "Bot fallback for non-Microsoft teams. Full agent access via slash commands.",
    status: "not-connected",
    category: "Messaging",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="2" y="11" width="5" height="5" rx="2.5" fill="#E01E5A"/>
        <rect x="2" y="4" width="5" height="5" rx="2.5" fill="#ECB22E"/>
        <rect x="9" y="11" width="5" height="5" rx="2.5" fill="#2EB67D"/>
        <rect x="9" y="4" width="5" height="5" rx="2.5" fill="#36C5F0"/>
        <rect x="14" y="8" width="5" height="5" rx="2.5" fill="#2EB67D" transform="rotate(90 14 8)"/>
      </svg>
    ),
  },
  {
    name: "Outlook Plugin",
    desc: "Embed Iroko AI answers inline in Outlook mail. Context-aware, cite-first.",
    status: "not-connected",
    category: "Productivity",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <rect x="1" y="4" width="18" height="13" rx="2" fill="#0078D4"/>
        <path d="M1 7l9 5 9-5" stroke="white" strokeWidth="1.5" strokeOpacity=".8"/>
      </svg>
    ),
  },
  {
    name: "MCP (Copilot)",
    desc: "Expose Iroko as a Model Context Protocol server to Microsoft 365 Copilot.",
    status: "not-connected",
    category: "AI",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="#6366F1" strokeWidth="1.5"/>
        <path d="M7 10l2 2 4-4" stroke="#6366F1" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
];

export default function IntegrationsPage() {
  const [activeIntegration, setActiveIntegration] = useState<typeof INTEGRATIONS[0] | null>(null);

  useEffect(() => {
    if (!activeIntegration) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setActiveIntegration(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [activeIntegration]);

  return (
    <AppShell title="Integrations" subtitle="Teams · Slack · WhatsApp · Outlook · Microsoft 365 MCP · SSO">
      <div className="grid grid-cols-2 gap-[14px] max-w-[840px]">
        {INTEGRATIONS.map((it) => (
          <div key={it.name} className="card flex flex-col gap-3 py-5 px-[22px]">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-[10px]">
                <div className="size-9 rounded-lg bg-gray-50 border border-border-default flex items-center justify-center shrink-0">
                  {it.icon}
                </div>
                <div>
                  <div className="text-sm font-semibold text-gray-800 leading-[1.2]">{it.name}</div>
                  <div className="text-[11px] text-gray-400">{it.category}</div>
                </div>
              </div>
              <span
                className={\`text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0 \${
                  it.status === "connected"
                    ? "text-success-700 bg-success-50"
                    : "text-gray-400 bg-gray-100"
                }\`}
              >
                {it.status === "connected" ? "Connected" : "Not connected"}
              </span>
            </div>

            <p className="text-[13px] text-gray-400 leading-[1.55] m-0">
              {it.desc}
            </p>

            <button
              className={\`\${it.status === "connected" ? "btn-secondary" : "btn-primary"} py-[7px] px-[14px] text-[13px] mt-auto self-start\`}
              onClick={() => setActiveIntegration(it)}
            >
              {it.status === "connected" ? "Configure" : "Connect"}
            </button>
          </div>
        ))}
      </div>

      {activeIntegration && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setActiveIntegration(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "480px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <div className="size-6 *:w-4 *:h-4 flex items-center justify-center opacity-80">{activeIntegration.icon}</div>
                {activeIntegration.status === "connected" ? \`Configure \${activeIntegration.name}\` : \`Connect \${activeIntegration.name}\`}
              </h2>
              <button onClick={() => setActiveIntegration(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-6">
              <p className="text-[13px] text-gray-600 leading-[1.6]">
                {activeIntegration.status === "connected" 
                  ? \`Configuration settings for \${activeIntegration.name}. You can manage channels, endpoints, or revoke API keys.\`
                  : \`Setting up \${activeIntegration.name} requires administrator consent. You will be redirected to authenticate.\`
                }
              </p>
              
              {activeIntegration.status === "connected" && (
                <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-border-default">
                  <label className="flex items-center justify-between text-sm text-gray-700">
                    <span>Enable Global Agent Access</span>
                    <input type="checkbox" defaultChecked className="rounded border-gray-300 text-brand-600 focus:ring-brand-500" />
                  </label>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setActiveIntegration(null)}>Cancel</button>
              <button 
                className="btn-primary"
                onClick={() => setActiveIntegration(null)}
              >
                {activeIntegration.status === "connected" ? "Save Settings" : "Continue to Auth"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
`;
fs.writeFileSync("app/settings/integrations/page.tsx", integrationsCode);

// 3. settings/offline/page.tsx
const offlineCode = `"use client";

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
      <div className="max-w-[680px] flex flex-col gap-4">
        {/* Info banner */}
        <div className="flex gap-3 px-[18px] py-[14px] bg-brand-50 border border-brand-100 rounded-lg">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="shrink-0 mt-[1px]">
            <circle cx="9" cy="9" r="7.5" stroke="var(--color-brand-600)" strokeWidth="1.4"/>
            <path d="M9 8.25V12M9 6h.008" stroke="var(--color-brand-600)" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
          <p className="text-[13px] text-brand-800 leading-[1.6] m-0">
            Offline mode uses a quantised 7B on-device model. Bundles sync automatically when you return to coverage.
            Download only the sites and docs relevant to your current deployment to conserve storage.
          </p>
        </div>

        {/* Bundle list */}
        <div className="card overflow-hidden">
          <div className="flex justify-between items-center px-5 py-[14px] border-b border-border-default">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Your bundles</h2>
              <p className="text-xs text-gray-400 mt-[2px]">{BUNDLES.length} bundles · {BUNDLES.reduce((a, b) => a + parseInt(b.size), 0)} MB total</p>
            </div>
            <button 
              className="btn-primary py-[7px] px-[14px] text-[13px] flex items-center gap-1.5"
              onClick={() => setModalOpen("build")}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 2v6M4 6l3-3 3 3M2 10h10" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Build new bundle
            </button>
          </div>

          {BUNDLES.map((b, i) => (
            <div
              key={b.name}
              className={\`flex justify-between items-center px-5 py-[15px] gap-4 hover:bg-gray-50 transition-colors\${i < BUNDLES.length - 1 ? " border-b border-border-default" : ""}\`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={\`size-9 rounded-lg flex items-center justify-center shrink-0 \${
                    b.status === "outdated"
                      ? "bg-warning-50 border border-warning-100"
                      : "bg-success-50 border border-success-100"
                  }\`}
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={b.status === "outdated" ? "text-warning-700" : "text-success-700"}>
                    {b.status === "outdated" ? (
                      <path d="M8 2v8M5 7l3 3 3-3M2 13h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    ) : (
                      <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                    )}
                  </svg>
                </div>
                <div>
                  <div className="text-[13.5px] font-medium text-gray-800 mb-[3px]">{b.name}</div>
                  <div className="text-xs text-gray-400">
                    {b.docs} documents · {b.size} · Synced {b.synced}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className={\`text-[11px] font-semibold px-2 py-[2px] rounded-full \${
                    b.status === "ready"
                      ? "text-success-700 bg-success-50"
                      : "text-warning-700 bg-warning-50"
                  }\`}
                >
                  {b.status === "ready" ? "Ready" : "Update available"}
                </span>
                <button 
                  className="btn-secondary py-[5px] px-[10px] text-xs"
                  onClick={() => setModalOpen(b.name)}
                >
                  {b.status === "outdated" ? "Sync now" : "Re-download"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setModalOpen(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "480px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">
                {modalOpen === "build" ? "Build new offline bundle" : \`Sync \${modalOpen}\`}
              </h2>
              <button onClick={() => setModalOpen(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-6">
              {modalOpen === "build" ? (
                <>
                  <label className="label-base block mb-1.5">Bundle Name</label>
                  <input type="text" className="input-base w-full mb-4" placeholder="e.g. Lagos Fibre Phase 4" />
                  <label className="label-base block mb-1.5">Sites / Location tags</label>
                  <input type="text" className="input-base w-full" placeholder="e.g. site:LGS-01, site:LGS-02" />
                  <p className="text-[11px] text-gray-400 mt-1.5">Select tags to proactively cache related documents and manuals.</p>
                </>
              ) : (
                <p className="text-[13px] text-gray-600 leading-[1.6]">
                  Starting synchronization to pull the latest differential documents for {modalOpen}. Please stay connected to Wi-Fi.
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setModalOpen(null)}>Cancel</button>
              <button 
                className="btn-primary"
                onClick={() => setModalOpen(null)}
              >
                {modalOpen === "build" ? "Build & Bundle" : "Start Sync"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
`;
fs.writeFileSync("app/settings/offline/page.tsx", offlineCode);

// 4. knowledge-graph/page.tsx
const kgCode = `"use client";

import AppShell from "@/components/layout/AppShell";
import { useState, useEffect } from "react";

const STATS = [
  { label: "Unanswered queries",     value: "218",   sub: "last 30 days",          accent: "#F04438" },
  { label: "Low-confidence answers", value: "1,042", sub: "confidence < 60%",      accent: "#F79009" },
  { label: "Missing doc types",      value: "7",     sub: "critical coverage gaps", accent: "#9E77ED" },
  { label: "Avg. confidence score",  value: "71%",   sub: "across all responses",  accent: "#2E90FA" },
];

const GAPS = [
  { topic: "Lagos fibre outage RCAs", queries: 84, confidence: 38, coverage: "critical", action: "Upload post-incident RCA reports" },
  { topic: "Vendor SLA breach history", queries: 61, confidence: 44, coverage: "critical", action: "Add vendor SLA performance documents" },
  { topic: "5G FWA site commissioning", queries: 47, confidence: 52, coverage: "low", action: "Upload Abuja 5G FWA site bundles" },
  { topic: "NCC compliance filings 2024", queries: 39, confidence: 58, coverage: "low", action: "Ingest NCC regulatory submissions" },
  { topic: "Enterprise contract termination clauses", queries: 33, confidence: 63, coverage: "partial", action: "Review contract clause extraction pipeline" },
  { topic: "Field engineer dispatch procedures", queries: 28, confidence: 67, coverage: "partial", action: "Upload NOC dispatch runbooks" },
  { topic: "Customer churn risk signals", queries: 22, confidence: 71, coverage: "partial", action: "Connect CRM data feed or upload exports" },
];

const SUGGESTED = [
  { priority: "Critical", priorityClass: "text-danger-700 bg-danger-50", title: "Upload RCA reports for Lagos fibre outages", detail: "84 queries in the past 30 days returned low-confidence answers. Engineers are querying post-incident summaries that don't exist in the knowledge base.", icon: "#F04438" },
  { priority: "Critical", priorityClass: "text-danger-700 bg-danger-50", title: "Add vendor SLA performance documents", detail: "Huawei and IHS SLA breach histories are missing. The Contracts agent is unable to ground penalty calculations against historical data.", icon: "#F04438" },
  { priority: "High", priorityClass: "text-warning-700 bg-warning-50", title: "Ingest NCC regulatory submissions for 2024", detail: "Compliance queries referencing Q3/Q4 2024 filings are returning stale context from 2023 documents.", icon: "#F79009" },
  { priority: "High", priorityClass: "text-warning-700 bg-warning-50", title: "Upload Abuja 5G FWA site commissioning reports", detail: "31 MB bundle is marked outdated. Field queries about site specs are being answered from generic templates.", icon: "#F79009" },
  { priority: "Medium", priorityClass: "text-brand-700 bg-brand-50", title: "Connect CRM data feed for churn signals", detail: "Care agent queries about enterprise account health lack grounded data. A live CRM export or webhook would close this gap.", icon: "#4A55D4" },
];

const COL = "2fr 80px 110px 120px 2fr";

function ConfidenceBadge({ score }: { score: number }) {
  const color = score < 50 ? "text-danger-700 bg-danger-50" : score < 65 ? "text-warning-700 bg-warning-50" : "text-success-700 bg-success-50";
  return <span className={\`text-xs font-bold px-2 py-[2px] rounded-full \${color}\`}>{score}%</span>;
}

function CoverageBadge({ coverage }: { coverage: string }) {
  const map: Record<string, string> = { critical: "text-danger-700 bg-danger-50", low: "text-warning-700 bg-warning-50", partial: "text-brand-700 bg-brand-50" };
  return <span className={\`text-xs font-semibold px-2 py-[2px] rounded-full \${map[coverage] ?? ""}\`}>{coverage.charAt(0).toUpperCase() + coverage.slice(1)}</span>;
}

export default function KnowledgeGapPage() {
  const [takeAction, setTakeAction] = useState<string | null>(null);

  useEffect(() => {
    if (!takeAction) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setTakeAction(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [takeAction]);

  return (
    <AppShell title="Knowledge gap" subtitle="What does the AI not know well enough yet? Fix these gaps to improve answer quality.">
      <div className="grid grid-cols-4 gap-[14px]">
        {STATS.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-[18px] px-5">
            <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            <div className="text-[28px] font-bold text-gray-900 tracking-[-0.04em] leading-none mb-[5px]">{s.value}</div>
            <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{s.label}</div>
            <div className="text-[11.5px] text-gray-300">{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden mt-6">
        <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Gap analysis</h2>
            <p className="text-xs text-gray-400 mt-[2px]">Topics with weak coverage, sorted by query volume</p>
          </div>
          <button className="btn-secondary py-[5px] px-3 text-xs">Export</button>
        </div>
        <div className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3" style={{ gridTemplateColumns: COL }}>
          {["Topic", "Queries", "Confidence", "Coverage", "Suggested action"].map((h) => (
            <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
          ))}
        </div>
        {GAPS.map((g, i) => (
          <div key={g.topic} className={\`grid items-center py-[13px] px-5 gap-3 hover:bg-gray-50 transition-colors\${i < GAPS.length - 1 ? " border-b border-border-default" : ""}\`} style={{ gridTemplateColumns: COL }}>
            <span className="text-[13px] font-medium text-gray-700">{g.topic}</span>
            <span className="text-xs font-semibold text-gray-500 font-mono">{g.queries}</span>
            <ConfidenceBadge score={g.confidence} />
            <CoverageBadge coverage={g.coverage} />
            <span className="text-[12px] text-gray-400">{g.action}</span>
          </div>
        ))}
      </div>

      <div className="mt-8">
        <div className="mb-[14px]">
          <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em]">Suggested actions</h2>
          <p className="text-xs text-gray-400 mt-0.5">Highest-impact steps to close knowledge gaps</p>
        </div>
        <div className="flex flex-col gap-3">
          {SUGGESTED.map((s) => (
            <div key={s.title} className="card flex gap-4 px-5 py-[18px] items-start">
              <div className="size-9 rounded-[9px] flex items-center justify-center shrink-0 mt-[1px]" style={{ background: \`\${s.icon}15\`, border: \`1px solid \${s.icon}25\` }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ color: s.icon }}>
                  <path d="M8 2v8M5 7l3 3 3-3M2 13h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-[5px]">
                  <span className={\`text-[11px] font-bold px-2 py-[2px] rounded-full \${s.priorityClass}\`}>{s.priority}</span>
                  <span className="text-[13.5px] font-semibold text-gray-800 tracking-[-0.01em]">{s.title}</span>
                </div>
                <p className="text-[12.5px] text-gray-400 leading-[1.6] m-0">{s.detail}</p>
              </div>
              <button 
                className="btn-primary py-[7px] px-[14px] text-[12.5px] shrink-0 mt-[1px]"
                onClick={() => setTakeAction(s.title)}
              >
                Take action
              </button>
            </div>
          ))}
        </div>
      </div>

      {takeAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setTakeAction(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "480px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">Take action: Upload documents</h2>
              <button onClick={() => setTakeAction(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-6">
              <p className="text-[13px] text-gray-600 leading-[1.6]">
                You selected: <strong>{takeAction}</strong>. 
                <br /><br />
                Please drag and drop the required PDF, Word, or text files below to ingest them into the knowledge graph and close this context gap.
              </p>
              
              <div className="mt-4 p-8 border-2 border-dashed border-gray-200 rounded-lg flex flex-col items-center justify-center bg-gray-50 text-center cursor-pointer hover:bg-gray-100 transition-colors">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-gray-400 mb-2">
                  <path d="M12 4v12m0-12l-4 4m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <div className="text-sm font-medium text-gray-700">Click to upload or drag and drop</div>
                <div className="text-xs text-gray-400 mt-1">PDF, DOCX, CSV up to 50MB</div>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setTakeAction(null)}>Cancel</button>
              <button 
                className="btn-primary"
                onClick={() => setTakeAction(null)}
              >
                Start Ingestion
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
`;
fs.writeFileSync("app/knowledge-graph/page.tsx", kgCode);
