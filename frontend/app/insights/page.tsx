"use client";
/**
 * app/insights/page.tsx — Insights page with filter bar and card grid.
 */
import { useState, useEffect } from "react";
import AppShell from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { formatRelativeTime, cn } from "@/lib/utils";
import { getSeverityColor, getSeverityLabel, INSIGHT_CATEGORIES } from "@/types/insight";
import type { Insight } from "@/types/insight";

function SeverityBadge({ severity }: { severity: number }) {
  const color = getSeverityColor(severity);
  const label = getSeverityLabel(severity);
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold"
      style={{ background: `${color}15`, color, border: `1px solid ${color}30` }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      {label} · {severity}/10
    </span>
  );
}

function InsightCard({ insight, onReview, onDismiss }: {
  insight: Insight; onReview: (id: string) => void; onDismiss: (id: string) => void;
}) {
  const color = getSeverityColor(insight.severity);
  const isNew = insight.status === "new";

  return (
    <div className="relative rounded-2xl border overflow-hidden transition-all duration-200 hover:border-white/20 hover:shadow-[0_0_24px_rgba(59,123,246,0.06)] group"
      style={{ background: "#0F1320", borderColor: "rgba(255,255,255,0.06)", borderLeft: `3px solid ${color}` }}>
      {isNew && (
        <div className="absolute top-3 right-3 w-2 h-2 rounded-full bg-[#3B7BF6]" style={{ animation: "ping 2s ease infinite" }} />
      )}
      <div className="p-5">
        {/* Category + agent */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full text-[#3B7BF6] bg-[#3B7BF6]/10 border border-[#3B7BF6]/20">{insight.category}</span>
          <span className="text-[10px] text-[#6B7280]">by {insight.agent_source.replace("Agent","")}</span>
          <span className="ml-auto"><SeverityBadge severity={insight.severity} /></span>
        </div>

        <h3 className="text-[14px] font-semibold text-[#E5E7EB] mb-2 leading-snug">{insight.title}</h3>
        <p className="text-[12.5px] text-[#6B7280] leading-relaxed line-clamp-3">{insight.summary}</p>

        {/* Footer */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/[0.05]">
          <span className="text-[10px] text-[#4B5563]">{formatRelativeTime(insight.created_at)}</span>
          <div className="flex items-center gap-2">
            {insight.status === "new" && (
              <>
                <button onClick={() => onReview(insight.id)}
                  className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-[#10B981] hover:bg-[#10B981]/10 border border-[#10B981]/20 transition-all">
                  Review
                </button>
                <button onClick={() => onDismiss(insight.id)}
                  className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-[#6B7280] hover:bg-white/5 border border-white/10 transition-all">
                  Dismiss
                </button>
              </>
            )}
            {insight.status === "reviewed" && (
              <span className="text-[10px] font-bold text-[#10B981] px-2 py-1 rounded-full bg-[#10B981]/10">✓ Reviewed</span>
            )}
            {insight.status === "dismissed" && (
              <span className="text-[10px] text-[#4B5563] italic">Dismissed</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-white/[0.06] p-5 space-y-3 animate-pulse" style={{ background: "#0F1320" }}>
      <div className="flex gap-2"><div className="h-5 w-20 rounded-full bg-white/[0.08]" /><div className="h-5 w-16 rounded-full bg-white/[0.06]" /></div>
      <div className="h-4 w-3/4 rounded bg-white/[0.08]" />
      <div className="space-y-1.5">
        <div className="h-3 rounded bg-white/[0.05]" /><div className="h-3 w-5/6 rounded bg-white/[0.05]" /><div className="h-3 w-4/6 rounded bg-white/[0.05]" />
      </div>
    </div>
  );
}

const MOCK_INSIGHTS: Insight[] = [
  { id: "i1", org_id: null, document_id: null, title: "Carbon MFB CAR breach — capital adequacy ratio below 10% CBN minimum", summary: "Carbon MFB's CAR has dropped to 8.4%, breaching the CBN 10% minimum under BOFIA 2020. Immediate capital injection or loan book reduction required to avoid sanctions.", category: "compliance", severity: 9, agent_source: "WatchdogAgent", status: "new", created_at: new Date(Date.now()-120000).toISOString() },
  { id: "i2", org_id: null, document_id: null, title: "CBN AML/CFT return submission deadline in 14 days", summary: "Q2 2026 AML/CFT quarterly return is due July 15, 2026. 14-day window for final data reconciliation and FinA submission. Risk of ₦500K/day late penalty under CBN ENF-001.", category: "regulatory", severity: 6, agent_source: "WatchdogAgent", status: "new", created_at: new Date(Date.now()-3600000).toISOString() },
  { id: "i3", org_id: null, document_id: null, title: "CBN lending limit data discrepancy detected in Q2 2026 submission", summary: "Internal lending data shows single-borrower exposure at ₦52M while submitted return shows ₦48M. This discrepancy could trigger a regulatory inquiry under CBN BOFIA 2020 Section 35.", category: "compliance", severity: 9, agent_source: "AnalystAgent", status: "new", created_at: new Date(Date.now()-7200000).toISOString() },
  { id: "i4", org_id: null, document_id: null, title: "Loan disbursement anomaly — Duplicate batch #7 entries detected", summary: "Three disbursement entries for the same borrower in batch #7 total ₦47.3M. Pattern may indicate duplicate-processing error or internal fraud. Recommend immediate payment suspension.", category: "fraud", severity: 9, agent_source: "WatchdogAgent", status: "reviewed", created_at: new Date(Date.now()-86400000).toISOString() },
  { id: "i5", org_id: null, document_id: null, title: "Transaction velocity anomaly — 3 Kuda agent wallets flagged", summary: "3 Kuda agent wallets show 340% above-average transaction velocity in the last 48 hours. Total flagged exposure: ₦31.4M. STR filing recommended per CBN AML/CFT guidelines.", category: "fraud", severity: 7, agent_source: "AnalystAgent", status: "new", created_at: new Date(Date.now()-172800000).toISOString() },
  { id: "i6", org_id: null, document_id: null, title: "CRC Credit Bureau data agreement — renewal due in 30 days", summary: "The CRC Credit Bureau data processing agreement expires 2025-12-31. Non-renewal would prevent credit bureau checks on new loan applicants, breaching CBN MFB lending guidelines. Renewal negotiation should commence immediately.", category: "contract", severity: 5, agent_source: "ResearcherAgent", status: "dismissed", created_at: new Date(Date.now()-259200000).toISOString() },
];

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>(MOCK_INSIGHTS);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState("All");
  const [statusFilter, setStatusFilter] = useState<"all" | "new" | "reviewed" | "dismissed">("all");
  const [severityMin, setSeverityMin] = useState(1);

  useEffect(() => {
    setLoading(true);
    apiFetch<{ insights: Insight[] }>("/api/insights")
      .then(d => { if (d.insights?.length) setInsights(d.insights); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleReview = async (id: string) => {
    await apiFetch(`/api/insights/${id}/review`, { method: "PATCH" }).catch(() => {});
    setInsights(prev => prev.map(i => i.id === id ? { ...i, status: "reviewed" } : i));
  };
  const handleDismiss = async (id: string) => {
    await apiFetch(`/api/insights/${id}/dismiss`, { method: "PATCH" }).catch(() => {});
    setInsights(prev => prev.map(i => i.id === id ? { ...i, status: "dismissed" } : i));
  };

  const filtered = insights.filter(i => {
    if (category !== "All" && i.category !== category) return false;
    if (statusFilter !== "all" && i.status !== statusFilter) return false;
    if (i.severity < severityMin) return false;
    return true;
  });

  const newCount = insights.filter(i => i.status === "new").length;

  return (
    <AppShell title="Insights" subtitle={`${newCount} new insight${newCount !== 1 ? "s" : ""} from your agents`}>
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Category chips */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {["All", "SLA", "compliance", "contract", "network", "fraud"].map(cat => (
            <button key={cat} onClick={() => setCategory(cat)}
              className={cn("px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all border",
                category === cat
                  ? "bg-[#3B7BF6] text-white border-[#3B7BF6] shadow-[0_0_12px_rgba(59,123,246,0.3)]"
                  : "text-[#9CA3AF] border-white/[0.08] bg-white/[0.03] hover:border-white/20 hover:text-white")}>
              {cat}
            </button>
          ))}
        </div>

        <div className="h-6 w-px bg-white/[0.08] mx-1 hidden sm:block" />

        {/* Status filter */}
        <div className="flex items-center gap-1">
          {(["all","new","reviewed","dismissed"] as const).map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={cn("px-2.5 py-1 rounded-lg text-[11px] font-medium capitalize transition-all",
                statusFilter === s ? "bg-white/10 text-[#E5E7EB]" : "text-[#6B7280] hover:text-[#E5E7EB]")}>
              {s}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2 text-[12px] text-[#6B7280]">
          <span>Min severity</span>
          <input type="range" min={1} max={10} value={severityMin} onChange={e => setSeverityMin(+e.target.value)}
            className="w-24 accent-[#3B7BF6]" />
          <span className="font-bold text-[#E5E7EB]">{severityMin}+</span>
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-16 h-16 rounded-2xl border border-white/[0.06] flex items-center justify-center" style={{ background: "#0F1320" }}>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#4B5563" strokeWidth="1.5"><path d="M14 2a5 5 0 0 1 4 9c0 1 1 1.5 1 2.5v.5H9v-.5c0-1 1-1.5 1-2.5A5 5 0 0 1 14 2Z"/><path d="M11 17v1a3 3 0 0 0 6 0v-1" strokeLinecap="round"/></svg>
          </div>
          <div className="text-center">
            <p className="text-[14px] font-semibold text-[#6B7280]">No insights match your filters</p>
            <p className="text-[12px] text-[#4B5563] mt-1">Try adjusting the category, status or severity range</p>
          </div>
          <button onClick={() => { setCategory("All"); setStatusFilter("all"); setSeverityMin(1); }}
            className="px-4 py-2 rounded-xl text-[12px] font-semibold text-[#3B7BF6] border border-[#3B7BF6]/20 hover:bg-[#3B7BF6]/10 transition-all">
            Reset filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(insight => (
            <InsightCard key={insight.id} insight={insight} onReview={handleReview} onDismiss={handleDismiss} />
          ))}
        </div>
      )}
      <style>{`@keyframes ping{75%,100%{transform:scale(2);opacity:0}}`}</style>
    </AppShell>
  );
}
