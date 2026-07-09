"use client";
/**
 * app/search/page.tsx — Semantic document search.
 * Results come exclusively from /api/search; a failed request shows a
 * visible error state with retry (no mock fallbacks).
 */
import { useState, useCallback } from "react";
import Link from "next/link";
import AppShell from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { truncate } from "@/lib/utils";

interface SearchResult { content: string; source: string; score: number; document_id: string; }

function ResultCard({ result, query }: { result: SearchResult; query: string }) {
  const pct = Math.round(result.score * 100);
  const scoreClass =
    pct >= 80 ? "text-success-700 bg-success-50" :
    pct >= 60 ? "text-warning-700 bg-warning-50" :
    "text-gray-500 bg-gray-100";
  const parts = truncate(result.content, 400).split(
    new RegExp(`(${query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"),
  );
  return (
    <div className="rounded-xl bg-surface-card border border-border-default shadow-xs p-5 hover:border-border-strong hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-3 mb-3">
        <span className="text-[12px] font-semibold text-brand-600 truncate">{result.source}</span>
        <span className={`shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-black ${scoreClass}`}>{pct}%</span>
      </div>
      <p className="text-[12.5px] text-gray-500 leading-relaxed line-clamp-4">
        {parts.map((p, i) =>
          p.toLowerCase() === query.trim().toLowerCase()
            ? <mark key={i} className="bg-brand-100 text-brand-800 rounded px-0.5 not-italic font-semibold">{p}</mark>
            : p,
        )}
      </p>
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border-default">
        <span className="text-[10px] text-gray-400 font-mono">id:{result.document_id.slice(0, 10)}…</span>
        <Link href="/documents" className="text-[11px] font-semibold text-brand-600 hover:text-brand-700 transition-colors">Open →</Link>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-xl bg-surface-card border border-border-default p-5 animate-pulse space-y-3">
      <div className="flex justify-between"><div className="h-3.5 w-40 rounded bg-gray-100" /><div className="h-6 w-12 rounded-lg bg-gray-100" /></div>
      <div className="h-3 rounded bg-gray-100" /><div className="h-3 w-5/6 rounded bg-gray-100" /><div className="h-3 w-4/6 rounded bg-gray-100" />
    </div>
  );
}

const STARTERS = ["Ikeja cluster outage root cause", "IHS diesel backup SLA penalties", "NCC QoS return requirements", "MoMo deduction complaints Q1"];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [took, setTook] = useState(0);

  const run = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true); setSearched(true); setSearchError(null);
    const t0 = Date.now();
    try {
      const d = await apiFetch<{ results: SearchResult[] }>("/api/search", {
        method: "POST",
        body: JSON.stringify({ query: trimmed, top_k: 10 }),
      });
      setResults(d.results ?? []); setTook(Date.now() - t0);
    } catch (e: unknown) {
      setResults([]);
      setSearchError(e instanceof Error ? e.message : "Search failed. Please try again.");
    } finally { setLoading(false); }
  }, []);

  return (
    <AppShell title="Search" subtitle="Semantic search across your document corpus">
      {/* Search bar */}
      <form onSubmit={e => { e.preventDefault(); run(q); }} role="search">
        <div className="relative flex items-center rounded-xl bg-surface-card border border-border-strong shadow-xs transition-all duration-200 focus-within:border-brand-500 focus-within:shadow-[0_0_0_4px_rgba(97,114,243,0.12)]">
          <svg className="absolute left-5 text-gray-400" width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M16 16l-3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input type="text" value={q} onChange={e => setQ(e.target.value)} autoFocus
            aria-label="Search documents"
            placeholder="Search documents, SLA agreements, contracts…"
            className="flex-1 bg-transparent pl-12 pr-4 py-4 text-[15px] text-gray-800 placeholder-gray-300 outline-none" />
          <button type="submit" disabled={loading || !q.trim()}
            className="mr-2 px-5 py-2.5 rounded-lg text-sm font-bold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xs">
            {loading ? "Searching…" : "Search"}
          </button>
        </div>
      </form>

      {/* Result stats */}
      {searched && !loading && !searchError && (
        <div className="flex items-center justify-end">
          <span className="text-[11px] text-gray-400">{results.length} result{results.length !== 1 ? "s" : ""} · {took}ms</span>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : searchError ? (
        <div role="alert" className="flex flex-col items-center gap-3 py-16 px-6 rounded-xl bg-danger-50 border border-danger-200 text-center">
          <p className="text-[14px] font-semibold text-danger-700">Search is currently unavailable</p>
          <p className="text-[12px] text-danger-600 max-w-md">{searchError}</p>
          <button onClick={() => run(q)}
            className="mt-1 px-4 py-2 rounded-lg text-[12px] font-semibold text-white bg-danger-600 hover:bg-danger-700 transition-colors">
            Retry
          </button>
        </div>
      ) : searched && results.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <p className="text-[14px] font-semibold text-gray-600">No results for &ldquo;{q}&rdquo;</p>
          <p className="text-[12px] text-gray-400">Try different keywords or broaden the category.</p>
        </div>
      ) : searched ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {results.map((r, i) => <ResultCard key={i} result={r} query={q} />)}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-6 py-16 text-center">
          <div className="w-20 h-20 rounded-3xl bg-brand-50 border border-brand-100 flex items-center justify-center">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true"><circle cx="14" cy="14" r="10" stroke="var(--color-brand-600)" strokeWidth="1.5"/><path d="M28 28l-6-6" stroke="var(--color-brand-400)" strokeWidth="1.5" strokeLinecap="round"/></svg>
          </div>
          <div>
            <p className="text-[16px] font-bold text-gray-900">Semantic Document Search</p>
            <p className="text-[13px] text-gray-500 mt-2 max-w-md">Search across your indexed documents using natural language — contracts, SLAs, compliance reports.</p>
          </div>
          <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
            {STARTERS.map(s => (
              <button key={s} onClick={() => { setQ(s); run(s); }}
                className="text-left px-4 py-3 rounded-xl text-[12px] text-gray-500 hover:text-gray-800 border border-border-default hover:border-border-strong bg-surface-card hover:bg-gray-50 transition-all shadow-xs">
                🔍 {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </AppShell>
  );
}
