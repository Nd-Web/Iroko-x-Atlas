"use client";
/**
 * app/agents/contracts/page.tsx — Contract intelligence agent.
 * Clause matching with risk scores + ReasoningChain integration.
 */
import { useState, useCallback } from "react";
import AppShell from "@/components/layout/AppShell";
import ReasoningChain from "@/components/ReasoningChain";
import InputBar from "@/components/chat/InputBar";
import { cn, getRiskHex, getRiskLabel } from "@/lib/utils";

interface ClauseMatch {
  id: string;
  title: string;
  document: string;
  clause: string;
  excerpt: string;
  riskScore: number;
  category: string;
}

const MOCK_CONTRACTS = [
  { id: "cx1", vendor: "IHS Nigeria", type: "Tower Lease", value: "₦2.4B/yr", expiry: "2027-06-30", risk: 6, clauses: 148, status: "active" },
  { id: "cx2", vendor: "Ericsson Nigeria", type: "RAN Maintenance", value: "₦890M/yr", expiry: "2025-12-31", risk: 8, clauses: 94, status: "expiring" },
  { id: "cx3", vendor: "Huawei Nigeria", type: "Core Network SLA", value: "₦1.2B/yr", expiry: "2026-03-31", risk: 4, clauses: 211, status: "active" },
  { id: "cx4", vendor: "MTN MoMo PSB", type: "Financial Services", value: "—", expiry: "Ongoing", risk: 5, clauses: 67, status: "active" },
];

const MOCK_CLAUSES: ClauseMatch[] = [
  { id: "cl1", title: "SLA Credit Mechanism — Uptime breach penalty", document: "IHS Nigeria Tower Lease", clause: "Article 9.3", excerpt: "In the event that Network Uptime falls below 99.5% in any calendar month, IHS Nigeria shall provide a service credit equal to 10% of the monthly fee for each 0.1% below the threshold.", riskScore: 8, category: "SLA" },
  { id: "cl2", title: "Termination for cause — 72-hour cure period", document: "Ericsson RAN Maintenance", clause: "Section 15.2", excerpt: "Either party may terminate this agreement if the other party fails to cure a material breach within 72 hours of written notice. Force majeure events shall extend this period by 30 days.", riskScore: 6, category: "Termination" },
  { id: "cl3", title: "Price escalation — CPI adjustment clause", document: "IHS Nigeria Tower Lease", clause: "Article 4.1", excerpt: "Annual lease fees shall be adjusted on the anniversary date in line with the Official Consumer Price Index as published by the NBS, subject to a maximum of 12% per annum.", riskScore: 5, category: "Financial" },
];

function ClauseCard({ clause }: { clause: ClauseMatch }) {
  const [expanded, setExpanded] = useState(false);
  const hex = getRiskHex(clause.riskScore);
  return (
    <div className="rounded-xl border overflow-hidden transition-all duration-200 hover:border-white/15"
      style={{ background: "#0F1320", borderColor: "rgba(255,255,255,0.06)", borderLeft: `3px solid ${hex}` }}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[9.5px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full" style={{ color: hex, background: `${hex}15` }}>{clause.category}</span>
              <span className="text-[9.5px] text-[#6B7280]">{clause.clause}</span>
            </div>
            <h4 className="text-[13px] font-semibold text-[#E5E7EB] leading-snug">{clause.title}</h4>
            <p className="text-[11px] text-[#6B7280] mt-0.5">{clause.document}</p>
          </div>
          <div className="flex items-center gap-1 shrink-0 px-2.5 py-1.5 rounded-lg text-[12px] font-black" style={{ background: `${hex}15`, color: hex }}>
            {clause.riskScore}/10
          </div>
        </div>
        {expanded && (
          <div className="mt-3 p-3 rounded-lg text-[12px] text-[#9CA3AF] leading-relaxed italic border border-white/[0.05]" style={{ background: "rgba(255,255,255,0.02)" }}>
            &ldquo;{clause.excerpt}&rdquo;
          </div>
        )}
        <button onClick={() => setExpanded(!expanded)}
          className="mt-2 text-[10px] text-[#6B7280] hover:text-[#3B7BF6] transition-colors flex items-center gap-1">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className={cn("transition-transform", expanded ? "rotate-180" : "")}>
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
          <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
            <div className="px-5 py-4 border-b border-white/[0.06]">
              <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Contract Registry</h2>
              <p className="text-[11px] text-[#6B7280]">{MOCK_CONTRACTS.length} agreements · 1 expiring soon</p>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {MOCK_CONTRACTS.map(c => {
                const rHex = getRiskHex(c.risk);
                const isSelected = selectedContract === c.id;
                return (
                  <button key={c.id} onClick={() => setSelectedContract(isSelected ? null : c.id)}
                    className={cn("w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-white/[0.02] transition-colors", isSelected && "bg-[#3B7BF6]/05")}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[13px] font-semibold text-[#E5E7EB]">{c.vendor}</span>
                        {c.status === "expiring" && (
                          <span className="text-[9px] font-bold text-amber-400 bg-amber-400/10 border border-amber-400/20 px-1.5 py-0.5 rounded-full animate-pulse">⚠ EXPIRING</span>
                        )}
                      </div>
                      <div className="text-[11px] text-[#6B7280]">{c.type} · {c.clauses} clauses · Expires {c.expiry}</div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[11px] font-mono text-[#9CA3AF]">{c.value}</span>
                      <span className="text-[12px] font-black px-2 py-1 rounded-lg" style={{ color: rHex, background: `${rHex}15` }}>{c.risk}/10</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Clause matches */}
          <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
            <div className="px-5 py-4 border-b border-white/[0.06]">
              <h2 className="text-[14px] font-semibold text-[#E5E7EB]">Clause Intelligence</h2>
              <p className="text-[11px] text-[#6B7280]">AI-extracted high-risk clauses · sorted by risk score</p>
            </div>
            <div className="p-4 space-y-3">
              {MOCK_CLAUSES.map(c => <ClauseCard key={c.id} clause={c} />)}
            </div>
          </div>

          {/* Search bar */}
          <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#0F1320" }}>
            <div className="px-4 pt-3">
              <p className="text-[12px] text-[#6B7280] mb-2">Ask the Contract Agent a question…</p>
            </div>
            <InputBar onSend={handleSearch} isStreaming={streaming}
              placeholder="What are the SLA penalties in the IHS agreement?" />
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
            <div className="rounded-2xl border border-white/[0.06] p-8 flex flex-col items-center gap-4 text-center" style={{ background: "#0F1320" }}>
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{ background: "rgba(59,123,246,0.1)", border: "1px solid rgba(59,123,246,0.2)" }}>
                <span className="text-2xl">📄</span>
              </div>
              <div>
                <p className="text-[13px] font-semibold text-[#E5E7EB]">Contract Agent ready</p>
                <p className="text-[11px] text-[#6B7280] mt-1">Type a question to see the 5-agent reasoning pipeline in action.</p>
              </div>
              <div className="space-y-2 w-full">
                {["What SLA penalties exist?", "Show expiring contracts", "Risk-score all agreements"].map(q => (
                  <button key={q} onClick={() => handleSearch(q)}
                    className="w-full text-left px-3 py-2.5 rounded-xl text-[11px] text-[#9CA3AF] hover:text-[#E5E7EB] border border-white/[0.06] hover:border-white/15 bg-white/[0.02] hover:bg-white/[0.04] transition-all">
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
