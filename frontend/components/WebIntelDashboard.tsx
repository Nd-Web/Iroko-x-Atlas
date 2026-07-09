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
 * Data: fetches from /api/v1/intel/* on mount + manual refresh.
 */

import React, { useState, useEffect, useCallback, type FC } from "react";
import type {
  SignalsResponse,
  AuditTrailResponse,
  TabId,
} from "@/components/dashboard/webintel/types";
import { apiFetch } from "@/components/dashboard/webintel/api";
import { TabButton, StatPill } from "@/components/dashboard/webintel/primitives";
import LiveSignalsTab from "@/components/dashboard/webintel/SignalsTab";
import ComplianceTab from "@/components/dashboard/webintel/ComplianceTab";
import AuditTrailTab from "@/components/dashboard/webintel/AuditTab";

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

  // Signals state
  const [signals,        setSignals]        = useState<SignalsResponse | null>(null);
  const [signalsLoading, setSignalsLoading] = useState(true);
  const [signalsError,   setSignalsError]   = useState<string | null>(null);

  // Audit state
  const [auditData,    setAuditData]    = useState<AuditTrailResponse | null>(null);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditError,   setAuditError]   = useState<string | null>(null);

  // Operation-level stats — "what does Iroko know about my operation right now"
  const [opsStats, setOpsStats] = useState<{ alerts: number | null; docs: number | null }>({ alerts: null, docs: null });

  // Fetch signals
  const fetchSignals = useCallback(async () => {
    setSignalsLoading(true);
    setSignalsError(null);
    try {
      const data = await apiFetch<SignalsResponse>("/signals");
      setSignals(data);
    } catch (e) {
      setSignalsError((e as Error).message ?? "Failed to load signals.");
    } finally {
      setSignalsLoading(false);
    }
  }, []);

  // Fetch audit trail
  const fetchAudit = useCallback(async () => {
    setAuditLoading(true);
    setAuditError(null);
    try {
      const data = await apiFetch<AuditTrailResponse>(
        "/audit-trail?limit=200&verify_chain=true"
      );
      setAuditData(data);
    } catch (e) {
      setAuditError((e as Error).message ?? "Failed to load audit trail.");
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSignals();
    fetchAudit();
  }, [fetchSignals, fetchAudit]);

  // Fetch live operation counts (same-origin proxies, cookie auth) — non-critical.
  useEffect(() => {
    fetch("/api/alerts?status=new&limit=1")
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((d: { total?: number }) => setOpsStats(s => ({ ...s, alerts: d.total ?? null })))
      .catch(() => {});
    fetch("/api/documents?page_size=1")
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((d: { total?: number; documents?: unknown[] }) =>
        setOpsStats(s => ({ ...s, docs: d.total ?? d.documents?.length ?? null })))
      .catch(() => {});
  }, []);

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
            <div className="w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 bg-brand-600 text-white shadow-xs">
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
              <p className="text-[13px] mt-0.5 text-gray-500">
                Boardroom-ready document &amp; operations intelligence for enterprise telecoms — powered by Bright Data
              </p>
            </div>
          </div>

          {/* Stats pills */}
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {opsStats.docs !== null && (
              <StatPill label="Documents Indexed" value={opsStats.docs} valueClass="text-success-700" loading={false} />
            )}
            {opsStats.alerts !== null && (
              <StatPill label="Open Alerts" value={opsStats.alerts} valueClass="text-warning-700" loading={false} />
            )}
            <StatPill label="Total Signals"  value={totalSignals} valueClass="text-brand-600"  loading={signalsLoading} />
            <StatPill label="Fraud Alerts"   value={fraudCount}   valueClass="text-danger-600" loading={signalsLoading} />
            <StatPill label="Audit Entries"  value={auditCount}   valueClass="text-brand-600"  loading={auditLoading}  />
            {auditData?.chain_integrity?.valid !== undefined && (
              <div
                className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-[12px] font-bold border ${
                  auditData.chain_integrity.valid
                    ? "bg-success-50 border-success-100 text-success-700"
                    : "bg-danger-50 border-danger-100 text-danger-700"
                }`}
              >
                {auditData.chain_integrity.valid ? "✅" : "⚠️"} Chain{" "}
                {auditData.chain_integrity.valid ? "OK" : "Broken"}
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
            count={auditLoading ? undefined : auditCount}
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
