"use client";
/**
 * app/agents/contracts/page.tsx — Contract intelligence agent.
 * Clause matching with risk scores + ReasoningChain integration.
 *
 * NOTE: This page is a demo showcase for the contract agent. The registry and
 * clause data below (SAMPLE_*) are static sample fixtures — there is no
 * backend endpoint behind them, and they are labeled as such in the UI.
 */
import { useState, useCallback } from "react";
import AppShell from "@/components/layout/AppShell";
import ReasoningChain from "@/components/ReasoningChain";
import InputBar from "@/components/chat/InputBar";
import { cn, getRiskHex } from "@/lib/utils";

interface ClauseMatch {
  id: string;
  title: string;
  document: string;
  clause: string;
  excerpt: string;
  riskScore: number;
  category: string;
}

// ATC renewal is ~28 days out; compute at module load so it never goes stale.
const ATC_RENEWAL_DATE = new Date(Date.now() + 28 * 86400000).toISOString().slice(0, 10);

const SAMPLE_CONTRACTS = [
  { id: "cx1", vendor: "ATC Lagos Zone 2", type: "Tower Lease — 12 Sites", value: "₦19.5M/mo", expiry: ATC_RENEWAL_DATE, risk: 8, clauses: 94, status: "expiring" },
  { id: "cx2", vendor: "IHS Nigeria Limited", type: "Tower Lease & Power Mgmt", value: "—", expiry: "2027-03-31", risk: 7, clauses: 211, status: "active" },
  { id: "cx3", vendor: "Ericsson Nigeria Limited", type: "RAN Maintenance SLA 2026", value: "—", expiry: "2026-12-31", risk: 4, clauses: 67, status: "active" },
  { id: "cx4", vendor: "Julius Berger Nigeria Plc", type: "Kano-Kaduna Fibre BoQ", value: "—", expiry: "2026-06-30", risk: 6, clauses: 38, status: "active" },
  { id: "cx5", vendor: "Zenith Bank Plc (EBU)", type: "Enterprise Connectivity SLA", value: "—", expiry: "2027-01-31", risk: 5, clauses: 52, status: "active" },
];

const SAMPLE_CLAUSES: ClauseMatch[] = [
  { id: "cl1", title: "Diesel backup SLA — fee reduction penalty trigger", document: "TowerCo IHS Nigeria Tower Lease Agreement", clause: "Section 6.3", excerpt: "Where site availability falls below the guaranteed diesel backup SLA, the monthly service fee shall be reduced by 2% for every 0.1% below the SLA threshold. Repeat breaches in consecutive quarters trigger escalation to executive review.", riskScore: 8, category: "SLA" },
  { id: "cl2", title: "Auto-renewal — 28-day written notice window", document: "ATC Lagos Zone 2 Lease (ATC/MTN/LAG/2023-007)", clause: "Section 15.2", excerpt: "This agreement covering 12 sites at ₦19.5M per month shall renew automatically unless written notice is served prior to expiry. Failure to serve notice within the renewal window locks in prevailing rates for a further 24 months.", riskScore: 6, category: "Termination" },
  { id: "cl3", title: "Fault response times — maintenance window caps", document: "Ericsson RAN Maintenance SLA 2026", clause: "Article 4.1", excerpt: "Priority 1 faults shall be acknowledged within 15 minutes and restored within 4 hours. Scheduled preventive maintenance shall not exceed two windows per site per quarter, each capped at 120 minutes outside busy hours.", riskScore: 5, category: "Operational" },
];

/** Small badge marking a card as demo/sample content rather than live data. */
function SampleDataBadge() {
  return (
    <span className="inline-flex items-center gap-1 text-[9.5px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-warning-50 text-warning-700 border border-warning-100 shrink-0">
      Sample data — for demonstration
    </span>
  );
}

function ClauseCard({ clause }: { clause: ClauseMatch }) {
  const [expanded, setExpanded] = useState(false);
  const hex = getRiskHex(clause.riskScore);
  return (
    <div
      className="rounded-xl bg-surface-card border border-border-default shadow-xs overflow-hidden transition-all duration-200 hover:border-border-strong"
      style={{ borderLeft: `3px solid ${hex}` }}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[9.5px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full" style={{ color: hex, background: `${hex}15` }}>{clause.category}</span>
              <span className="text-[9.5px] text-gray-400">{clause.clause}</span>
            </div>
            <h4 className="text-[13px] font-semibold text-gray-900 leading-snug">{clause.title}</h4>
            <p className="text-[11px] text-gray-400 mt-0.5">{clause.document}</p>
          </div>
          <div className="flex items-center gap-1 shrink-0 px-2.5 py-1.5 rounded-lg text-[12px] font-black" style={{ background: `${hex}15`, color: hex }}>
            {clause.riskScore}/10
          </div>
        </div>
        {expanded && (
          <div id={`clause-excerpt-${clause.id}`} className="mt-3 p-3 rounded-lg text-[12px] text-gray-500 leading-relaxed italic bg-gray-50 border border-border-default">
            &ldquo;{clause.excerpt}&rdquo;
          </div>
        )}
        <button
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          aria-controls={`clause-excerpt-${clause.id}`}
          className="mt-2 text-[10px] text-gray-500 hover:text-brand-600 transition-colors flex items-center gap-1"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true" className={cn("transition-transform", expanded ? "rotate-180" : "")}>
            <path d="M2 3.5l3 3 3-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
          {expanded ? "Hide excerpt" : "Show excerpt"}
        </button>
      </div>
    </div>
  );
}

export default function ContractsPage() {
  const [query, setQuery] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [selectedContract, setSelectedContract] = useState<string | null>(null);

  const handleSearch = useCallback((q: string) => {
    setQuery(q);
    setStreaming(true);
  }, []);

  return (
    <AppShell title="Contract Intelligence" subtitle="AI-powered clause analysis and risk scoring">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Left: contracts + search */}
        <div className="xl:col-span-2 space-y-4">
          {/* Contract list */}
          <div className="rounded-2xl bg-surface-card border border-border-default shadow-xs overflow-hidden">
            <div className="px-5 py-4 border-b border-border-default">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-[14px] font-semibold text-gray-900">Contract Registry</h2>
                <SampleDataBadge />
              </div>
              <p className="text-[11px] text-gray-500">{SAMPLE_CONTRACTS.length} agreements · 1 expiring soon</p>
            </div>
            <div className="divide-y divide-gray-100">
              {SAMPLE_CONTRACTS.map(c => {
                const rHex = getRiskHex(c.risk);
                const isSelected = selectedContract === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => setSelectedContract(isSelected ? null : c.id)}
                    aria-pressed={isSelected}
                    className={cn("w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-gray-50 transition-colors", isSelected && "bg-brand-50")}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[13px] font-semibold text-gray-900">{c.vendor}</span>
                        {c.status === "expiring" && (
                          <span className="text-[9px] font-bold text-warning-700 bg-warning-50 border border-warning-100 px-1.5 py-0.5 rounded-full animate-pulse">⚠ EXPIRING</span>
                        )}
                      </div>
                      <div className="text-[11px] text-gray-500">{c.type} · {c.clauses} clauses · Expires {c.expiry}</div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[11px] font-mono text-gray-500">{c.value}</span>
                      <span className="text-[12px] font-black px-2 py-1 rounded-lg" style={{ color: rHex, background: `${rHex}15` }}>{c.risk}/10</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Clause matches */}
          <div className="rounded-2xl bg-surface-card border border-border-default shadow-xs overflow-hidden">
            <div className="px-5 py-4 border-b border-border-default">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-[14px] font-semibold text-gray-900">Clause Intelligence</h2>
                <SampleDataBadge />
              </div>
              <p className="text-[11px] text-gray-500">AI-extracted high-risk clauses · sorted by risk score</p>
            </div>
            <div className="p-4 space-y-3 bg-surface-page">
              {SAMPLE_CLAUSES.map(c => <ClauseCard key={c.id} clause={c} />)}
            </div>
          </div>

          {/* Search bar */}
          <div className="rounded-2xl bg-surface-card border border-border-default shadow-xs overflow-hidden">
            <div className="px-4 pt-3">
              <p className="text-[12px] text-gray-500 mb-2">Ask the Contract Agent a question…</p>
            </div>
            <InputBar onSend={handleSearch} isStreaming={streaming}
              placeholder="What are the SLA penalties in the Interswitch agreement?" />
          </div>
        </div>

        {/* Right: reasoning chain */}
        <div className="xl:col-span-1">
          {query ? (
            <ReasoningChain
              query={query}
              onComplete={() => setStreaming(false)}
              onError={() => setStreaming(false)}
            />
          ) : (
            <div className="rounded-2xl bg-surface-card border border-border-default shadow-xs p-8 flex flex-col items-center gap-4 text-center">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-brand-50 border border-brand-100">
                <span className="text-2xl" aria-hidden="true">📄</span>
              </div>
              <div>
                <p className="text-[13px] font-semibold text-gray-900">Contract Agent ready</p>
                <p className="text-[11px] text-gray-500 mt-1">Type a question to see the 5-agent reasoning pipeline in action.</p>
              </div>
              <div className="space-y-2 w-full">
                {["What SLA penalties exist?", "Show expiring contracts", "Risk-score all agreements"].map(q => (
                  <button key={q} onClick={() => handleSearch(q)}
                    className="w-full text-left px-3 py-2.5 rounded-xl text-[11px] text-gray-500 hover:text-gray-800 bg-gray-50 border border-border-default hover:border-border-strong hover:bg-gray-100 transition-all">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
