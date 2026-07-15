"use client";
/**
 * components/dashboard/webintel/AuditTab.tsx
 *
 * Tab 3 — Audit Trail: hash-chained audit log table with
 * chain-integrity badge and client-side pagination.
 */

import React, { useState, useEffect, type FC } from "react";
import type { AuditEntry, AuditTrailResponse } from "./types";
import { verdictMeta, formatTime, truncate } from "./meta";
import { SkeletonLine, ErrorBanner } from "./primitives";

// ─────────────────────────────────────────────────────────────────────────────
// Table row
// ─────────────────────────────────────────────────────────────────────────────

const verdictPill = (v?: string) => {
  if (!v) return null;
  const meta = verdictMeta(v);
  return (
    <span className={`inline-flex items-center text-[10px] font-bold px-2 py-0.5 rounded-full ${meta.pill}`}>
      {v}
    </span>
  );
};

const AuditRow: FC<{ entry: AuditEntry; index: number }> = ({ entry, index }) => {
  const hashTail = entry.chain_hash?.slice(-8) ?? "—";

  return (
    <tr
      className={`transition-colors duration-150 hover:bg-[rgba(59,123,246,0.04)] ${
        index % 2 === 0 ? "bg-transparent" : "bg-white/[0.015]"
      }`}
    >
      {/* Agent */}
      <td className="px-4 py-3 text-[12px] font-semibold text-[#E5E7EB]">
        {entry.agent_name}
      </td>
      {/* Action */}
      <td className="px-4 py-3">
        <span className="text-[11px] px-2 py-0.5 rounded-md font-medium bg-white/[0.05] border border-white/[0.08] text-[#9CA3AF]">
          {entry.action_type}
        </span>
      </td>
      {/* Summary */}
      <td
        className="px-4 py-3 text-[12px] max-w-xs text-[#6B7280]"
        title={entry.decision_summary}
      >
        {truncate(entry.decision_summary, 64)}
      </td>
      {/* Verdict */}
      <td className="px-4 py-3">{verdictPill(entry.verdict)}</td>
      {/* Timestamp */}
      <td className="px-4 py-3 text-[11px] whitespace-nowrap text-[#4B5563]">
        {formatTime(entry.created_at)}
      </td>
      {/* Chain hash */}
      <td className="px-4 py-3">
        <code className="text-[10px] font-mono px-2 py-1 rounded-lg tracking-[0.04em] bg-[rgba(139,92,246,0.1)] border border-[rgba(139,92,246,0.2)] text-[#8B5CF6]">
          …{hashTail}
        </code>
      </td>
    </tr>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Audit Trail tab
// ─────────────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

const AuditTrailTab: FC<{
  data:    AuditTrailResponse | null;
  loading: boolean;
  error:   string | null;
}> = ({ data, loading, error }) => {
  const [page, setPage] = useState(0);

  const entries    = data?.entries ?? [];
  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const pageSlice  = entries.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const chainValid = data?.chain_integrity?.valid ?? data?.chain_valid;

  // Reset to page 0 when data changes
  useEffect(() => { setPage(0); }, [data]);

  return (
    <div className="flex flex-col gap-5">
      {/* Header row */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {loading ? (
            <span className="text-[12px] px-3 py-1 rounded-full bg-[#141824] text-[#6B7280]">
              Loading audit trail…
            </span>
          ) : (
            <>
              <span className="text-[13px] font-semibold text-[#E5E7EB]">
                {entries.length} entries
              </span>
              {/* Chain integrity badge */}
              {data && chainValid !== undefined && (
                <span
                  className={`flex items-center gap-1.5 text-[11px] font-bold px-3 py-1 rounded-full border ${
                    chainValid
                      ? "bg-[rgba(16,185,129,0.1)] border-[rgba(16,185,129,0.25)] text-[#10B981]"
                      : "bg-[rgba(239,68,68,0.1)] border-[rgba(239,68,68,0.25)] text-[#EF4444]"
                  }`}
                >
                  {chainValid ? (
                    <>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                        <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
                          stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                        <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      Chain Verified
                    </>
                  ) : (
                    <>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                        <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                        <path d="M8 6.5v3M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      Chain Broken
                    </>
                  )}
                </span>
              )}
            </>
          )}
        </div>

        {/* Pagination controls */}
        {!loading && totalPages > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-[#4B5563]">
              Page {page + 1} / {totalPages}
            </span>
            <div className="flex gap-1">
              {[
                { label: "←", aria: "Previous page", disabled: page === 0,             action: () => setPage((p) => Math.max(0, p - 1)) },
                { label: "→", aria: "Next page",     disabled: page >= totalPages - 1, action: () => setPage((p) => Math.min(totalPages - 1, p + 1)) },
              ].map(({ label, aria, disabled, action }) => (
                <button
                  key={label}
                  onClick={action}
                  disabled={disabled}
                  aria-label={aria}
                  className="w-8 h-8 rounded-lg text-[13px] font-bold transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed bg-[#141824] border border-white/[0.06] text-[#9CA3AF]"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Table */}
      <div className="rounded-2xl overflow-hidden border border-white/[0.06]">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="bg-[#141824]">
                {["Agent", "Action", "Summary", "Verdict", "Timestamp", "Chain Hash"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-[10px] font-black uppercase tracking-widest whitespace-nowrap text-[#4B5563] border-b border-white/[0.06]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <SkeletonLine w={j === 2 ? "w-40" : j === 4 ? "w-28" : "w-20"} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : pageSlice.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-16 text-center text-[13px] text-[#4B5563]">
                    No audit entries found.
                  </td>
                </tr>
              ) : (
                pageSlice.map((entry, i) => (
                  <AuditRow key={entry.id} entry={entry} index={i} />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Table footer */}
        {!loading && entries.length > 0 && (
          <div className="px-4 py-3 flex items-center justify-between border-t border-white/[0.06] bg-[#141824]">
            <p className="text-[11px] text-[#4B5563]">
              Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, entries.length)} of {entries.length}
            </p>
            {data?.chain_integrity?.broken_at && (
              <p className="text-[11px] text-[#EF4444]">
                Chain broken at entry: {data.chain_integrity.broken_at}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditTrailTab;
