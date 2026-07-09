"use client";
/**
 * components/dashboard/webintel/SignalsTab.tsx
 *
 * Tab 1 — Live Signals: 5-category signal feed (signal card,
 * category column, and the tab layout itself).
 */

import React, { type FC } from "react";
import Link from "next/link";
import type { Signal, SignalCategory, SignalsResponse } from "./types";
import { CATEGORY_META, riskBadgeClasses, formatTime, truncate } from "./meta";
import { PulsingDot, SkeletonCard, ErrorBanner, LiveBadge } from "./primitives";

// ─────────────────────────────────────────────────────────────────────────────
// Signal Card
// ─────────────────────────────────────────────────────────────────────────────

const SignalCard: FC<{ signal: Signal; category: SignalCategory }> = ({
  signal, category,
}) => {
  const meta    = CATEGORY_META[category];
  const snippet = signal.snippet ?? signal.description ?? "";
  const isHigh  = signal.risk_level?.toUpperCase() === "HIGH";

  return (
    <div
      className={`group relative rounded-xl p-4 transition-all duration-200 hover:translate-y-[-1px] bg-surface-card border border-border-default shadow-xs border-l-[3px] ${meta.leftBorder}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <PulsingDot dotClass={meta.dot} />
          <p className="text-[13px] font-semibold leading-snug line-clamp-2 text-gray-900">
            {signal.title}
          </p>
        </div>
        {signal.risk_level && (
          <span
            className={`shrink-0 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${riskBadgeClasses(signal.risk_level)}`}
          >
            {signal.risk_level}
          </span>
        )}
      </div>

      {/* Snippet */}
      {snippet && (
        <p className="text-[12px] leading-relaxed mb-3 text-gray-500">
          {truncate(snippet, 120)}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {signal.source && (
            <span className="text-[10px] px-2 py-0.5 rounded-md font-medium bg-gray-50 border border-border-default text-gray-500">
              {truncate(signal.source, 24)}
            </span>
          )}
          {signal.signal_type && (
            <span className={`text-[10px] px-2 py-0.5 rounded-md font-medium ${meta.chip}`}>
              {signal.signal_type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Link
            href={`/chat?q=${encodeURIComponent(`Tell me about this web signal: ${signal.title}`)}`}
            className="text-[10px] flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity text-success-700 hover:text-success-500"
          >
            Chat
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
              <path d="M2 2h6M2 5h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
          </Link>
          {signal.url && (
            <a
              href={signal.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity text-brand-600 hover:text-brand-700"
            >
              Source
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                <path d="M2 8L8 2M8 2H4M8 2v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
            </a>
          )}
        </div>
      </div>

      {/* Detected at */}
      {signal.detected_at && (
        <p className="text-[10px] mt-2 pt-2 border-t border-border-default text-gray-400">
          {formatTime(signal.detected_at)}
        </p>
      )}

      {/* High-risk accent ring */}
      {isHigh && (
        <div
          className="absolute inset-0 rounded-xl pointer-events-none ring-1 ring-inset ring-danger-200"
          aria-hidden="true"
        />
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Category Column
// ─────────────────────────────────────────────────────────────────────────────

const CategoryColumn: FC<{
  category: SignalCategory;
  signals: Signal[];
  loading: boolean;
}> = ({ category, signals, loading }) => {
  const meta = CATEGORY_META[category];

  return (
    <div className="flex flex-col min-w-0">
      {/* Column header */}
      <div className="flex items-center gap-2 px-1 mb-3 pb-3 border-b border-border-default">
        <span className={meta.text} aria-hidden="true">{meta.icon}</span>
        <span className={`text-[12px] font-bold uppercase tracking-wider ${meta.text}`}>
          {meta.label}
        </span>
        <span className={`ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full ${meta.chip}`}>
          {loading ? "…" : signals.length}
        </span>
      </div>

      {/* Cards */}
      <div className="flex flex-col gap-3">
        {loading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : signals.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 rounded-xl gap-2 bg-gray-50 border border-dashed border-border-default">
            <span className={`${meta.text} opacity-40`} aria-hidden="true">{meta.icon}</span>
            <p className="text-[11px] text-gray-400">No signals</p>
          </div>
        ) : (
          signals.map((s, i) => (
            <SignalCard key={s.id ?? `${category}-${i}`} signal={s} category={category} />
          ))
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Live Signals tab
// ─────────────────────────────────────────────────────────────────────────────

const LiveSignalsTab: FC<{
  signals:   SignalsResponse | null;
  loading:   boolean;
  error:     string | null;
  onRefresh: () => void;
}> = ({ signals, loading, error, onRefresh }) => {
  const totalSignals = signals
    ? Object.values(signals).reduce(
        (acc, arr) => acc + (Array.isArray(arr) ? arr.length : 0),
        0
      )
    : 0;
  const isMock = signals?.mock === true;

  return (
    <div className="flex flex-col gap-5">
      {/* Sub-header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {isMock ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10.5px] font-bold uppercase tracking-wide bg-warning-50 border border-warning-100 text-warning-700">
              <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor" aria-hidden="true">
                <circle cx="4" cy="4" r="4"/>
              </svg>
              Demo data
            </span>
          ) : (
            <LiveBadge />
          )}
          <p className="text-[13px] text-gray-500">
            {loading
              ? "Fetching signals across 5 intelligence domains…"
              : isMock
              ? `${totalSignals} signals — live feed unavailable, showing representative data`
              : `${totalSignals} signals across 5 domains`}
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-[12px] font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.02] active:scale-[0.98] bg-brand-50 border border-brand-100 text-brand-700 shadow-xs hover:bg-brand-100"
        >
          <svg
            width="13" height="13" viewBox="0 0 16 16" fill="none"
            className={loading ? "animate-spin" : ""}
            aria-hidden="true"
          >
            <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M8 1.5L10.5 4 8 6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Refresh Signals
        </button>
      </div>

      {/* Error */}
      {error && <ErrorBanner message={error} />}

      {/* 5-column grid */}
      <div className="grid gap-5 grid-cols-5">
        {(["regulatory", "competitor", "vendor_risk", "fraud", "market"] as SignalCategory[]).map(
          (cat) => (
            <CategoryColumn
              key={cat}
              category={cat}
              signals={signals?.[cat] ?? []}
              loading={loading}
            />
          )
        )}
      </div>
    </div>
  );
};

export default LiveSignalsTab;
