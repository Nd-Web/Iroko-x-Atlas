"use client";
/**
 * app/insights/page.tsx — Insights page with filter bar and card grid.
 * Data comes exclusively from /api/insights; loading, error, empty and
 * populated states are all rendered honestly (no mock fallbacks).
 */
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { formatRelativeTime, cn } from "@/lib/utils";
import { getSeverityColor, getSeverityLabel } from "@/types/insight";
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
    <div className="relative rounded-2xl border overflow-hidden transition-all duration-200 hover:border-white/20 group"
      style={{ background: "#131316", borderColor: "rgba(255,255,255,0.08)", borderLeft: `3px solid ${color}` }}>
      {isNew && (
        <div className="absolute top-3 right-3 w-2 h-2 rounded-full bg-brand-500" style={{ animation: "ping 2s ease infinite" }} aria-hidden="true" />
      )}
      <div className="p-5">
        {/* Category + agent */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full text-info-500 bg-info-50 border border-[#38BDF8]/20">{insight.category}</span>
          <span className="text-[10px] text-gray-400">by {insight.agent_source.replace("Agent","")}</span>
          <span className="ml-auto"><SeverityBadge severity={insight.severity} /></span>
        </div>

        <h3 className="text-[14px] font-semibold text-gray-800 mb-2 leading-snug">{insight.title}</h3>
        <p className="text-[12.5px] text-gray-400 leading-relaxed line-clamp-3">{insight.summary}</p>

        {/* Footer */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/[0.05]">
          <span className="text-[10px] text-gray-300">{formatRelativeTime(insight.created_at)}</span>
          <div className="flex items-center gap-2">
            {insight.status === "new" && (
              <>
                <button onClick={() => onReview(insight.id)}
                  className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-[#10B981] hover:bg-[#10B981]/10 border border-[#10B981]/20 transition-all">
                  Review
                </button>
                <button onClick={() => onDismiss(insight.id)}
                  className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-gray-400 hover:bg-white/5 border border-white/10 transition-all">
                  Dismiss
                </button>
              </>
            )}
            {insight.status === "reviewed" && (
              <span className="text-[10px] font-bold text-[#10B981] px-2 py-1 rounded-full bg-[#10B981]/10">Reviewed</span>
            )}
            {insight.status === "dismissed" && (
              <span className="text-[10px] text-gray-300 italic">Dismissed</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-border-default p-5 space-y-3 animate-pulse" style={{ background: "#131316" }}>
      <div className="flex gap-2"><div className="h-5 w-20 rounded-full bg-white/[0.08]" /><div className="h-5 w-16 rounded-full bg-white/[0.06]" /></div>
      <div className="h-4 w-3/4 rounded bg-white/[0.08]" />
      <div className="space-y-1.5">
        <div className="h-3 rounded bg-white/[0.05]" /><div className="h-3 w-5/6 rounded bg-white/[0.05]" /><div className="h-3 w-4/6 rounded bg-white/[0.05]" />
      </div>
    </div>
  );
}

// The backend reuses Alert rows, whose statuses are new/acknowledged/
// resolved/dismissed — normalise onto the insight vocabulary so the
// status filter and card actions always match.
function normaliseInsightStatus(s: string): Insight["status"] {
  if (s === "acknowledged" || s === "resolved" || s === "reviewed") return "reviewed";
  if (s === "dismissed") return "dismissed";
  return "new";
}

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [category, setCategory] = useState("All");
  const [statusFilter, setStatusFilter] = useState<"all" | "new" | "reviewed" | "dismissed">("all");
  const [severityMin, setSeverityMin] = useState(1);

  const load = useCallback(() => {
    setLoading(true);
    setLoadError(null);
    apiFetch<{ insights: Insight[] }>("/api/insights")
      .then(d => {
        setInsights((d.insights ?? []).map(i => ({ ...i, status: normaliseInsightStatus(String(i.status)) })));
      })
      .catch((e: unknown) => {
        setLoadError(e instanceof Error ? e.message : "Failed to load insights.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  // Optimistic status change; rolled back with a toast if the API rejects it.
  const updateStatus = async (id: string, next: "reviewed" | "dismissed", endpoint: string) => {
    const previous = insights;
    setInsights(prev => prev.map(i => i.id === id ? { ...i, status: next } : i));
    try {
      await apiFetch(endpoint, { method: "PATCH" });
    } catch {
      setInsights(previous);
      toast.error(`Could not mark the insight as ${next}. Please try again.`);
    }
  };
  const handleReview = (id: string) => updateStatus(id, "reviewed", `/api/insights/${id}/review`);
  const handleDismiss = (id: string) => updateStatus(id, "dismissed", `/api/insights/${id}/dismiss`);

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
        {/* Category chips — derived from the loaded data so live categories always match */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {["All", ...Array.from(new Set(insights.map(i => i.category)))].map(cat => (
            <button key={cat} onClick={() => setCategory(cat)}
              aria-pressed={category === cat}
              className={cn("px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all border",
                category === cat
                  ? "bg-brand-500 text-[#0A0A0B] border-brand-500"
                  : "text-gray-500 border-white/[0.08] bg-white/[0.03] hover:border-white/20 hover:text-gray-900")}>
              {cat}
            </button>
          ))}
        </div>

        <div className="h-6 w-px bg-white/[0.08] mx-1 hidden sm:block" aria-hidden="true" />

        {/* Status filter */}
        <div className="flex items-center gap-1">
          {(["all","new","reviewed","dismissed"] as const).map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              aria-pressed={statusFilter === s}
              className={cn("px-2.5 py-1 rounded-lg text-[11px] font-medium capitalize transition-all",
                statusFilter === s ? "bg-white/10 text-gray-800" : "text-gray-400 hover:text-gray-800")}>
              {s}
            </button>
          ))}
        </div>

        <label className="ml-auto flex items-center gap-2 text-[12px] text-gray-400">
          <span>Min severity</span>
          <input type="range" min={1} max={10} value={severityMin} onChange={e => setSeverityMin(+e.target.value)}
            aria-label="Minimum severity"
            className="w-24 accent-[#FFCB05]" />
          <span className="font-bold text-gray-800">{severityMin}+</span>
        </label>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : loadError ? (
        <div role="alert" className="flex flex-col items-center justify-center gap-3 py-16 px-6 rounded-2xl text-center"
          style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}>
          <p className="text-[14px] font-semibold text-[#F87171]">Insights could not be loaded</p>
          <p className="text-[12px] text-[#FCA5A5] max-w-md">{loadError}</p>
          <button onClick={load}
            className="mt-1 px-4 py-2 rounded-lg text-[12px] font-semibold text-[#F87171] transition-all"
            style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)" }}>
            Retry
          </button>
        </div>
      ) : insights.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-16 h-16 rounded-2xl border border-border-default flex items-center justify-center" style={{ background: "#131316" }}>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#4A4A54" strokeWidth="1.5" aria-hidden="true"><path d="M14 2a5 5 0 0 1 4 9c0 1 1 1.5 1 2.5v.5H9v-.5c0-1 1-1.5 1-2.5A5 5 0 0 1 14 2Z"/><path d="M11 17v1a3 3 0 0 0 6 0v-1" strokeLinecap="round"/></svg>
          </div>
          <div className="text-center">
            <p className="text-[14px] font-semibold text-gray-400">No insights yet</p>
            <p className="text-[12px] text-gray-300 mt-1">Your agents will surface insights here as they analyse incoming documents and events.</p>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-16 h-16 rounded-2xl border border-border-default flex items-center justify-center" style={{ background: "#131316" }}>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#4A4A54" strokeWidth="1.5" aria-hidden="true"><path d="M14 2a5 5 0 0 1 4 9c0 1 1 1.5 1 2.5v.5H9v-.5c0-1 1-1.5 1-2.5A5 5 0 0 1 14 2Z"/><path d="M11 17v1a3 3 0 0 0 6 0v-1" strokeLinecap="round"/></svg>
          </div>
          <div className="text-center">
            <p className="text-[14px] font-semibold text-gray-400">No insights match your filters</p>
            <p className="text-[12px] text-gray-300 mt-1">Try adjusting the category, status or severity range</p>
          </div>
          <button onClick={() => { setCategory("All"); setStatusFilter("all"); setSeverityMin(1); }}
            className="px-4 py-2 rounded-xl text-[12px] font-semibold text-brand-500 border border-brand-200 hover:bg-brand-50 transition-all">
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
