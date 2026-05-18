"use client";

import AppShell from "@/components/layout/AppShell";
import { useState, useEffect } from "react";

const INTEGRATIONS = [
  {
    name: "Microsoft Teams",
    desc: "Bot integration via Microsoft 365 plugin.",
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
    desc: "Voice notes and text queries for field staff.",
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
    desc: "SSO authentication and ABAC attribute claims.",
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
    desc: "Bot fallback for non-Microsoft teams.",
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
    desc: "Embed Iroko AI answers inline in Outlook mail.",
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
    desc: "Expose Iroko as a MCP server to M365 Copilot.",
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
    <AppShell title="Integrations" subtitle="Teams · Slack · WhatsApp · Outlook · M365 · SSO">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px] max-w-[840px]">
        {INTEGRATIONS.map((it) => (
          <div key={it.name} className="card flex flex-col gap-3 py-5 px-5 md:px-[22px]">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-[10px] min-w-0">
                <div className="size-9 rounded-lg bg-gray-50 border border-border-default flex items-center justify-center shrink-0">
                  {it.icon}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-gray-800 leading-[1.2] truncate">{it.name}</div>
                  <div className="text-[11px] text-gray-400">{it.category}</div>
                </div>
              </div>
              <span
                className={`text-[10px] md:text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0 ${
                  it.status === "connected"
                    ? "text-success-700 bg-success-50"
                    : "text-gray-400 bg-gray-100"
                }`}
              >
                {it.status === "connected" ? "Connected" : "Disconnected"}
              </span>
            </div>

            <p className="text-[13px] text-gray-400 leading-[1.55] m-0">
              {it.desc}
            </p>

            <button
              className={`${it.status === "connected" ? "btn-secondary" : "btn-primary"} py-[7px] px-[14px] text-[13px] mt-auto self-start md:self-auto w-full md:w-auto font-semibold`}
              onClick={() => setActiveIntegration(it)}
            >
              {it.status === "connected" ? "Configure" : "Connect"}
            </button>
          </div>
        ))}
      </div>

      {activeIntegration && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6" onClick={() => setActiveIntegration(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "480px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2 truncate">
                <div className="size-6 *:w-4 *:h-4 flex items-center justify-center opacity-80 shrink-0">{activeIntegration.icon}</div>
                <span className="truncate">{activeIntegration.name}</span>
              </h2>
              <button onClick={() => setActiveIntegration(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-6">
              <p className="text-[13px] text-gray-600 leading-[1.6]">
                {activeIntegration.status === "connected" 
                  ? `Configuration settings for ${activeIntegration.name}.`
                  : `Setting up ${activeIntegration.name} requires administrator consent.`
                }
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setActiveIntegration(null)}>Cancel</button>
              <button className="btn-primary" onClick={() => setActiveIntegration(null)}>
                {activeIntegration.status === "connected" ? "Save Settings" : "Connect"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
