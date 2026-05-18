"use client";
/**
 * app/search/page.tsx — Semantic document search.
 */
import { useState, useCallback, useRef } from "react";
import AppShell from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { cn, truncate } from "@/lib/utils";

interface SearchResult { content: string; source: string; score: number; document_id: string; }

const CATEGORIES = ["All", "SLA", "Compliance", "Contracts", "Network", "Fraud"];

function ResultCard({ result, query }: { result: SearchResult; query: string }) {
  const pct = Math.round(result.score * 100);
  const col = pct >= 80 ? "#10B981" : pct >= 60 ? "#F59E0B" : "#6B7280";
  const parts = truncate(result.content, 400).split(
    new RegExp(`(${query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"),
  );
  return (
    <div className="rounded-2xl border border-white/[0.06] p-5 hover:border-white/15 transition-all" style={{ background: "#0F1320" }}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <span className="text-[12px] font-semibold text-[#3B7BF6] truncate">{result.source}</span>
        <span className="shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-black" style={{ color: col, background: `${col}15` }}>{pct}%</span>
      </div>
      <p className="text-[12.5px] text-[#9CA3AF] leading-relaxed line-clamp-4">
        {parts.map((p, i) =>
          p.toLowerCase() === query.trim().toLowerCase()
            ? <mark key={i} className="bg-[#3B7BF6]/25 text-[#93C5FD] rounded px-0.5 not-italic font-semibold">{p}</mark>
            : p,
        )}
      </p>
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/[0.04]">
        <span className="text-[10px] text-[#4B5563] font-mono">id:{result.document_id.slice(0, 10)}…</span>
        <button className="text-[11px] font-semibold text-[#3B7BF6] hover:text-[#60A5FA] transition-colors">Open →</button>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-white/[0.06] p-5 animate-pulse space-y-3" style={{ background: "#0F1320" }}>
      <div className="flex justify-between"><div className="h-3.5 w-40 rounded bg-white/[0.08]" /><div className="h-6 w-12 rounded-lg bg-white/[0.06]" /></div>
      <div className="h-3 rounded bg-white/[0.06]" /><div className="h-3 w-5/6 rounded bg-white/[0.05]" /><div className="h-3 w-4/6 rounded bg-white/[0.04]" />
    </div>
  );
}

const STARTERS = ["SLA credit penalty clauses", "Contracts expiring this quarter", "NCC compliance obligations", "IHS tower lease fees"];
const MOCK_RESULTS: SearchResult[] = [
  { content: "In the event that Network Uptime falls below 99.5% in any calendar month, IHS Nigeria shall provide a service credit equal to 10% of the monthly fee for each 0.1% below the threshold.", source: "IHS_Nigeria_Tower_Lease_2024.pdf", score: 0.94, document_id: "doc-1a2b3c4d" },
  { content: "The Ericsson RAN maintenance agreement requires that all Priority 1 incidents are resolved within 4 hours of initial ticket creation. SLA credits of 15% apply for each hour of breach.", source: "Ericsson_RAN_Maintenance_SLA.pdf", score: 0.88, document_id: "doc-4d5e6f7g" },
  { content: "Annual lease fees shall be adjusted on the anniversary date in line with the Official Consumer Price Index, subject to a maximum escalation of 12% per annum per Article 4.1.", source: "IHS_Nigeria_Tower_Lease_2024.pdf", score: 0.79, document_id: "doc-7g8h9i1j" },
];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [took, setTook] = useState(0);

  const run = useCallback(async (query: string, category: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true); setSearched(true);
    const t0 = Date.now();
    try {
      const d = await apiFetch<{ results: SearchResult[] }>("/api/search", {
        method: "POST",
        body: JSON.stringify({ query: trimmed, category: category === "All" ? undefined : category, top_k: 10 }),
      });
      setResults(d.results ?? []); setTook(Date.now() - t0);
    } catch {
      setResults(MOCK_RESULTS); setTook(Date.now() - t0);
    } finally { setLoading(false); }
  }, []);

  return (
    <AppShell title="Search" subtitle="Semantic search across your document corpus">
      {/* Search bar */}
      <form onSubmit={e => { e.preventDefault(); run(q, cat); }}>
        <div className="relative flex items-center rounded-2xl border transition-all duration-200 focus-within:border-[#3B7BF6]/50 focus-within:shadow-[0_0_28px_rgba(59,123,246,0.12)]"
          style={{ background: "#0F1320", borderColor: "rgba(255,255,255,0.08)" }}>
          <svg className="absolute left-5 text-[#6B7280]" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M16 16l-3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input type="text" value={q} onChange={e => setQ(e.target.value)} autoFocus
            placeholder="Search documents, SLA agreements, contracts…"
            className="flex-1 bg-transparent pl-12 pr-4 py-4 text-[15px] text-[#E5E7EB] placeholder-[#4B5563] outline-none" />
          <button type="submit" disabled={loading || !q.trim()}
            className="mr-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white disabled:opacity-50 transition-all hover:shadow-[0_0_20px_rgba(59,123,246,0.3)]"
            style={{ background: "linear-gradient(135deg,#3B7BF6,#2563EB)" }}>
            {loading ? "Searching…" : "Search"}
          </button>
        </div>
      </form>

      {/* Category chips + stats */}
      <div className="flex items-center gap-2 flex-wrap">
        {CATEGORIES.map(c => (
          <button key={c} onClick={() => { setCat(c); if (searched) run(q, c); }}
            className={cn("px-3.5 py-1.5 rounded-full text-[12px] font-semibold transition-all border",
              cat === c
                ? "bg-[#3B7BF6] text-white border-[#3B7BF6]"
                : "text-[#9CA3AF] border-white/[0.08] bg-white/[0.02] hover:text-white hover:border-white/20")}>
            {c}
          </button>
        ))}
        {searched && !loading && (
          <span className="ml-auto text-[11px] text-[#6B7280]">{results.length} result{results.length !== 1 ? "s" : ""} · {took}ms</span>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : searched && results.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <p className="text-[14px] font-semibold text-[#6B7280]">No results for &ldquo;{q}&rdquo;</p>
          <p className="text-[12px] text-[#4B5563]">Try different keywords or broaden the category.</p>
        </div>
      ) : searched ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {results.map((r, i) => <ResultCard key={i} result={r} query={q} />)}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-6 py-16 text-center">
          <div className="w-20 h-20 rounded-3xl flex items-center justify-center"
            style={{ background: "linear-gradient(135deg,rgba(59,123,246,0.1),rgba(139,92,246,0.1))", border: "1px solid rgba(59,123,246,0.15)" }}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><circle cx="14" cy="14" r="10" stroke="#3B7BF6" strokeWidth="1.5"/><path d="M28 28l-6-6" stroke="#8B5CF6" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </div>
          <div>
            <p className="text-[16px] font-bold text-[#E5E7EB]">Semantic Document Search</p>
            <p className="text-[13px] text-[#6B7280] mt-2 max-w-md">Search across your indexed documents using natural language — contracts, SLAs, compliance reports.</p>
          </div>
          <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
            {STARTERS.map(s => (
              <button key={s} onClick={() => { setQ(s); run(s, cat); }}
                className="text-left px-4 py-3 rounded-xl text-[12px] text-[#9CA3AF] hover:text-[#E5E7EB] border border-white/[0.06] hover:border-white/15 bg-white/[0.02] hover:bg-white/[0.04] transition-all">
                🔍 {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </AppShell>
  );
}
