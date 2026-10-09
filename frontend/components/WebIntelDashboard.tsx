"use client";
/**
 * components/WebIntelDashboard.tsx
 *
 * Boardroom-ready Web Intelligence panel for Iroko AI.
 * Thin composition root — owns shared state (tab, signals, audit, ops stats)
 * and delegates each section to components/dashboard/webintel/*:
 *   1. Live Signals     — 5-category signal feed from Bright Data
 *   2. Verdict & Compliance — NCC/NDPA compliance checker + PDF brief download
 *   3. Audit Trail      — Hash-chained audit log with integrity verification
 *
 * Auth: reads Bearer token from localStorage["iroko_token"].
 * Data: /api/v1/intel/* via React Query (cached across navigation) + manual refresh.
 */

import React, { useState, useCallback, type FC } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import type {
  SignalsResponse,
  AuditTrailResponse,
  TabId,
} from "@/components/dashboard/webintel/types";
import { apiFetch } from "@/components/dashboard/webintel/api";
import { TabButton, StatPill } from "@/components/dashboard/webintel/primitives";
import LiveSignalsTab from "@/components/dashboard/webintel/SignalsTab";

const tabLoading = () => <div role="status" className="min-h-48 animate-pulse text-sm text-gray-400">Loading workspace…</div>;
const ComplianceTab = dynamic(() => import("@/components/dashboard/webintel/ComplianceTab"), { loading: tabLoading });
const AuditTrailTab = dynamic(() => import("@/components/dashboard/webintel/AuditTab"), { loading: tabLoading });

// Re-export shared types so existing imports keep working.
export type {
  SignalCategory,
  Signal,
  SignalsResponse,
  VerdictViolation,
  VerdictOutput,
  AuditEntry,
  AuditTrailResponse,
} from "@/components/dashboard/webintel/types";

const WebIntelDashboard: FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("signals");

  // Cached via React Query so returning to the dashboard renders instantly
  // from the last result instead of refetching everything behind spinners.
  const signalsQuery = useQuery({
    queryKey: ["webintel", "signals"],
    queryFn: () => apiFetch<SignalsResponse>("/signals"),
  });
  const auditQuery = useQuery({
    queryKey: ["webintel", "audit-trail"],
    queryFn: () => apiFetch<AuditTrailResponse>("/audit-trail?limit=200&verify_chain=true"),
    // Hash-chain verification is only needed when the audit tab is opened.
    enabled: activeTab === "audit",
  });

  // Operation-level stats — "what does Iroko know about my operation right now"
  // (same-origin proxies, cookie auth) — non-critical, failures show "—".
  const alertsCountQuery = useQuery({
    queryKey: ["webintel", "ops", "alerts"],
    queryFn: async () => {
      const r = await fetch("/api/alerts?status=new&limit=1");
      if (!r.ok) throw new Error(String(r.status));
      const d: { total?: number } = await r.json();
      return d.total ?? null;
    },
    retry: false,
  });
  const docsCountQuery = useQuery({
    queryKey: ["webintel", "ops", "docs"],
    queryFn: async () => {
      const r = await fetch("/api/documents?page_size=1");
      if (!r.ok) throw new Error(String(r.status));
      const d: { total?: number; documents?: unknown[] } = await r.json();
      return d.total ?? d.documents?.length ?? null;
    },
    retry: false,
  });

  const signals        = signalsQuery.data ?? null;
  const [refreshing, setRefreshing] = useState(false);
  const signalsLoading = signalsQuery.isLoading || refreshing;
  const signalsError   = signalsQuery.error
    ? (signalsQuery.error.message || "Failed to load signals.")
    : null;
  const fetchSignals = useCallback(async () => {
    setRefreshing(true);
    try { await signalsQuery.refetch(); } finally { setRefreshing(false); }
  }, [signalsQuery]);

  const auditData    = auditQuery.data ?? null;
  const auditLoading = auditQuery.isLoading;
  const auditError   = auditQuery.error
    ? (auditQuery.error.message || "Failed to load audit trail.")
    : null;

  const opsStats = {
    alerts: alertsCountQuery.data ?? null,
    docs: docsCountQuery.data ?? null,
  };

  // Derived counts for tab badges
  const totalSignals = signals
    ? Object.values(signals).reduce(
        (a, b) => a + (Array.isArray(b) ? b.length : 0),
        0
      )
    : 0;
  const fraudCount   = signals?.fraud?.length ?? 0;
  const auditCount   = auditData?.entries?.length ?? 0;

  return (
    <div className="flex flex-col min-h-screen bg-surface-page text-gray-800">
      {/* ── Page header ───────────────────────────────────────────────────── */}
      <div className="px-8 pt-8 pb-0 border-b border-border-default">
        <div className="flex items-start justify-between gap-6 pb-5">
          {/* Title block */}
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 bg-brand-50 border border-brand-200 text-brand-500">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 2L22 7V12C22 17 17.5 21 12 22C6.5 21 2 17 2 12V7L12 2Z"
                  stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/>
              </svg>
            </div>
            <div>
              <h1 className="text-[22px] font-black tracking-tight leading-tight text-gray-900">
                Web Intelligence
              </h1>
              <p className="text-[13px] mt-0.5 text-gray-400">
                Boardroom-ready document &amp; operations intelligence for enterprise telecoms — powered by Bright Data
              </p>
            </div>
          </div>

          {/* Stats pills */}
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {opsStats.docs !== null && (
              <StatPill label="Documents Indexed" value={opsStats.docs} valueClass="text-[#10B981]" loading={false} />
            )}
            {opsStats.alerts !== null && (
              <StatPill label="Open Alerts" value={opsStats.alerts} valueClass="text-[#F59E0B]" loading={false} />
            )}
            <StatPill label="Total Signals"  value={totalSignals} valueClass="text-[#38BDF8]" loading={signalsLoading} />
            <StatPill label="Fraud Alerts"   value={fraudCount}   valueClass="text-[#EF4444]" loading={signalsLoading} />
            <StatPill label="Audit Entries"  value={auditCount}   valueClass="text-[#38BDF8]" loading={auditLoading}  />
            {auditData?.chain_integrity?.valid !== undefined && (
              <div
                className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-[12px] font-bold border ${
                  auditData.chain_integrity.valid
                    ? "bg-[rgba(16,185,129,0.08)] border-[rgba(16,185,129,0.2)] text-[#10B981]"
                    : "bg-[rgba(239,68,68,0.08)] border-[rgba(239,68,68,0.2)] text-[#EF4444]"
                }`}
              >
                Chain {auditData.chain_integrity.valid ? "OK" : "Broken"}
              </div>
            )}
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex gap-0 -mb-px" role="tablist" aria-label="Web Intelligence tabs">
          <TabButton
            active={activeTab === "signals"}
            onClick={() => setActiveTab("signals")}
            icon={
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M2 12L6 8l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="14" cy="5" r="1.5" fill="currentColor"/>
              </svg>
            }
            label="Live Signals"
            count={signalsLoading ? undefined : totalSignals}
          />
          <TabButton
            active={activeTab === "compliance"}
            onClick={() => setActiveTab("compliance")}
            icon={
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
                  stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            }
            label="Verdict & Compliance"
          />
          <TabButton
            active={activeTab === "audit"}
            onClick={() => setActiveTab("audit")}
            icon={
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <rect x="2.5" y="1.5" width="11" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M5 6h6M5 8.5h6M5 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            }
            label="Audit Trail"
            count={auditLoading || !auditData ? undefined : auditCount}
          />
        </div>
      </div>

      {/* ── Tab content ───────────────────────────────────────────────────── */}
      <div className="flex-1 px-8 py-7">
        {activeTab === "signals" && (
          <LiveSignalsTab
            signals={signals}
            loading={signalsLoading}
            error={signalsError}
            onRefresh={fetchSignals}
          />
        )}
        {activeTab === "compliance" && <ComplianceTab />}
        {activeTab === "audit" && (
          <AuditTrailTab
            data={auditData}
            loading={auditLoading}
            error={auditError}
          />
        )}
      </div>
    </div>
  );
};

export default WebIntelDashboard;
