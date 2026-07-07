"use client";
/**
 * components/WebIntelDashboard.tsx
 *
 * Boardroom-ready Web Intelligence panel for Iroko AI.
 * Three tabs:
 *   1. Live Signals     — 5-category signal feed from Bright Data
 *   2. Verdict & Compliance — NCC/NDPA compliance checker + PDF brief download
 *   3. Audit Trail      — Hash-chained audit log with integrity verification
 *
 * Auth: reads Bearer token from localStorage["iroko_token"].
 * Data: fetches from /api/v1/intel/* on mount + manual refresh.
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  type FC,
  type ReactNode,
} from "react";
import Link from "next/link";
import { useVoiceCompliance } from "@/hooks/useVoiceCompliance";
import VoiceMicButton from "@/components/ui/VoiceMicButton";
import { useAgent } from "@/hooks/useAgent";
import AgentCallButton from "@/components/ui/AgentCallButton";

// ─────────────────────────────────────────────────────────────────────────────
// API Base
// ─────────────────────────────────────────────────────────────────────────────

const API = "/api/v1/intel";

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("iroko_token") ?? "";
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─────────────────────────────────────────────────────────────────────────────
// TypeScript Interfaces
// ─────────────────────────────────────────────────────────────────────────────

export type SignalCategory =
  | "regulatory"
  | "competitor"
  | "vendor_risk"
  | "fraud"
  | "market";

export interface Signal {
  id?: string;
  title: string;
  snippet?: string;
  description?: string;
  url?: string;
  source?: string;
  risk_level?: "HIGH" | "MEDIUM" | "LOW" | string;
  detected_at?: string;
  signal_type?: string;
}

export interface SignalsResponse {
  regulatory: Signal[];
  competitor: Signal[];
  vendor_risk: Signal[];
  fraud: Signal[];
  market: Signal[];
  mock?: boolean;
}

export interface VerdictViolation {
  regulation_id: string;
  section: string;
  reason: string;
}

export interface VerdictOutput {
  verdict: "GO" | "NO-GO" | "MONITOR" | string;
  compliant: boolean;
  confidence_score?: number;
  violations: VerdictViolation[];
  recommended_actions?: string[];
  ncc_refs?: string[];
  finding?: {
    summary?: string;
    action_type?: string;
    ncc_regulation_ref?: string;
  };
  color?: string;
  label?: string;
  generated_at?: string;
}

export interface AuditEntry {
  id: string;
  agent_name: string;
  action_type: string;
  decision_summary: string;
  verdict?: string;
  ncc_ref?: string;
  confidence?: number;
  workspace_id?: string;
  chain_hash?: string;
  previous_hash?: string;
  created_at: string;
}

export interface AuditTrailResponse {
  entries: AuditEntry[];
  total?: number;
  chain_valid?: boolean;
  chain_integrity?: {
    valid: boolean;
    checked_entries: number;
    broken_at?: string;
  };
}

type TabId = "signals" | "compliance" | "audit";

// ─────────────────────────────────────────────────────────────────────────────
// Design tokens (mirrors existing Iroko palette)
// ─────────────────────────────────────────────────────────────────────────────

const SURFACE = {
  page:     "#080B14",
  card:     "#0F1320",
  elevated: "#141824",
  border:   "rgba(255,255,255,0.06)",
  hover:    "rgba(255,255,255,0.04)",
} as const;

const BRAND = {
  blue:   "#3B7BF6",
  purple: "#8B5CF6",
  glow:   "rgba(59,123,246,0.25)",
} as const;

const CATEGORY_META: Record<
  SignalCategory,
  { label: string; color: string; dot: string; border: string; icon: ReactNode }
> = {
  regulatory: {
    label:  "Regulatory",
    color:  "#3B7BF6",
    dot:    "#3B7BF6",
    border: "#3B7BF6",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
          stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  competitor: {
    label:  "Competitor",
    color:  "#F59E0B",
    dot:    "#F59E0B",
    border: "#F59E0B",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  vendor_risk: {
    label:  "Vendor Risk",
    color:  "#8B5CF6",
    dot:    "#8B5CF6",
    border: "#8B5CF6",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L2 5v4c0 3.3 2.7 5.3 6 6 3.3-.7 6-2.7 6-6V5L8 2Z"
          stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M8 6v3M8 10.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  fraud: {
    label:  "Fraud",
    color:  "#EF4444",
    dot:    "#EF4444",
    border: "#EF4444",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M8 6.5v3M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  market: {
    label:  "Market Intel",
    color:  "#10B981",
    dot:    "#10B981",
    border: "#10B981",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M2 12L6 8l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="14" cy="5" r="1.5" fill="currentColor"/>
      </svg>
    ),
  },
};

const VERDICT_META: Record<
  string,
  { bg: string; border: string; text: string; glow: string; label: string; icon: ReactNode }
> = {
  GO: {
    bg:     "rgba(16,185,129,0.08)",
    border: "rgba(16,185,129,0.3)",
    text:   "#10B981",
    glow:   "rgba(16,185,129,0.2)",
    label:  "✅ GO — Proceed with confidence",
    icon:   <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="#10B981" strokeWidth="1.8"/><path d="M8 12l3 3 5-5" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  },
  "NO-GO": {
    bg:     "rgba(239,68,68,0.08)",
    border: "rgba(239,68,68,0.3)",
    text:   "#EF4444",
    glow:   "rgba(239,68,68,0.2)",
    label:  "🚫 NO-GO — Action required immediately",
    icon:   <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="#EF4444" strokeWidth="1.8"/><path d="M15 9l-6 6M9 9l6 6" stroke="#EF4444" strokeWidth="2" strokeLinecap="round"/></svg>,
  },
  MONITOR: {
    bg:     "rgba(245,158,11,0.08)",
    border: "rgba(245,158,11,0.3)",
    text:   "#F59E0B",
    glow:   "rgba(245,158,11,0.2)",
    label:  "⚠️ MONITOR — Flag for human review",
    icon:   <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="#F59E0B" strokeWidth="1.8"/><path d="M12 8v5M12 15.5h.01" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round"/></svg>,
  },
};

function verdictMeta(v: string) {
  return VERDICT_META[v] ?? VERDICT_META["MONITOR"];
}

function riskLevelColor(level?: string): string {
  if (!level) return "#6B7280";
  const l = level.toUpperCase();
  if (l === "HIGH")   return "#EF4444";
  if (l === "MEDIUM") return "#F59E0B";
  return "#10B981";
}

function formatTime(iso?: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function truncate(str: string, n: number): string {
  return str.length > n ? str.slice(0, n) + "…" : str;
}

// ─────────────────────────────────────────────────────────────────────────────
// Micro components
// ─────────────────────────────────────────────────────────────────────────────

const PulsingDot: FC<{ color: string }> = ({ color }) => (
  <span
    className="relative flex h-2 w-2 shrink-0"
    aria-hidden="true"
  >
    <span
      className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60"
      style={{ backgroundColor: color }}
    />
    <span
      className="relative inline-flex rounded-full h-2 w-2"
      style={{ backgroundColor: color }}
    />
  </span>
);

const SkeletonLine: FC<{ w?: string }> = ({ w = "w-full" }) => (
  <div
    className={`h-3 rounded-md animate-pulse ${w}`}
    style={{ background: "rgba(255,255,255,0.06)" }}
  />
);

const SkeletonCard: FC = () => (
  <div
    className="rounded-xl p-4 space-y-3"
    style={{ background: SURFACE.elevated, border: `1px solid ${SURFACE.border}` }}
  >
    <SkeletonLine w="w-3/4" />
    <SkeletonLine w="w-full" />
    <SkeletonLine w="w-1/2" />
  </div>
);

const ErrorBanner: FC<{ message: string; onDismiss?: () => void }> = ({
  message, onDismiss,
}) => (
  <div
    className="flex items-start gap-3 px-4 py-3 rounded-xl text-sm"
    style={{
      background:   "rgba(239,68,68,0.08)",
      border:       "1px solid rgba(239,68,68,0.25)",
      color:        "#FCA5A5",
    }}
  >
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
      <path d="M8 2L14 13H2L8 2Z" stroke="#EF4444" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M8 6.5v3M8 11h.01" stroke="#EF4444" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
    <span className="flex-1 leading-snug">{message}</span>
    {onDismiss && (
      <button
        onClick={onDismiss}
        className="text-[#EF4444] hover:text-white transition-colors shrink-0 mt-0.5"
        aria-label="Dismiss error"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M10.5 3.5l-7 7M3.5 3.5l7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </button>
    )}
  </div>
);

// Shimmer badge for live status
const LiveBadge: FC = () => (
  <span
    className="flex items-center gap-1.5 text-[10px] font-bold tracking-wide uppercase px-2 py-0.5 rounded-full"
    style={{
      color:      "#10B981",
      background: "rgba(16,185,129,0.1)",
      border:     "1px solid rgba(16,185,129,0.2)",
    }}
  >
    <PulsingDot color="#10B981" />
    Live
  </span>
);

// Tab button
const TabButton: FC<{
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
  count?: number;
}> = ({ active, onClick, icon, label, count }) => (
  <button
    onClick={onClick}
    className="relative flex items-center gap-2 px-5 py-3 text-sm font-semibold transition-all duration-200 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3B7BF6]"
    style={{
      color:      active ? "#E5E7EB" : "#6B7280",
      background: "transparent",
      borderBottom: active
        ? "2px solid #3B7BF6"
        : "2px solid transparent",
    }}
    aria-selected={active}
    role="tab"
  >
    <span style={{ color: active ? BRAND.blue : "#6B7280" }}>{icon}</span>
    {label}
    {count !== undefined && count > 0 && (
      <span
        className="text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center"
        style={{
          background: active ? "rgba(59,123,246,0.2)" : "rgba(255,255,255,0.06)",
          color:      active ? BRAND.blue : "#9CA3AF",
        }}
      >
        {count}
      </span>
    )}
  </button>
);

// ─────────────────────────────────────────────────────────────────────────────
// Tab 1 — Signal Card
// ─────────────────────────────────────────────────────────────────────────────

const SignalCard: FC<{ signal: Signal; category: SignalCategory }> = ({
  signal, category,
}) => {
  const meta    = CATEGORY_META[category];
  const snippet = signal.snippet ?? signal.description ?? "";
  const isHigh  = signal.risk_level?.toUpperCase() === "HIGH";

  return (
    <div
      className="group relative rounded-xl p-4 transition-all duration-200 hover:translate-y-[-1px]"
      style={{
        background:   SURFACE.elevated,
        border:       `1px solid ${SURFACE.border}`,
        borderLeft:   `3px solid ${meta.border}`,
        boxShadow:    "0 2px 8px rgba(0,0,0,0.3)",
      }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <PulsingDot color={meta.dot} />
          <p
            className="text-[13px] font-semibold leading-snug line-clamp-2"
            style={{ color: "#E5E7EB" }}
          >
            {signal.title}
          </p>
        </div>
        {signal.risk_level && (
          <span
            className="shrink-0 text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
            style={{
              color:      riskLevelColor(signal.risk_level),
              background: `${riskLevelColor(signal.risk_level)}18`,
              border:     `1px solid ${riskLevelColor(signal.risk_level)}35`,
            }}
          >
            {signal.risk_level}
          </span>
        )}
      </div>

      {/* Snippet */}
      {snippet && (
        <p
          className="text-[12px] leading-relaxed mb-3"
          style={{ color: "#6B7280" }}
        >
          {truncate(snippet, 120)}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {signal.source && (
            <span
              className="text-[10px] px-2 py-0.5 rounded-md font-medium"
              style={{
                background: "rgba(255,255,255,0.05)",
                border:     "1px solid rgba(255,255,255,0.08)",
                color:      "#9CA3AF",
              }}
            >
              {truncate(signal.source, 24)}
            </span>
          )}
          {signal.signal_type && (
            <span
              className="text-[10px] px-2 py-0.5 rounded-md font-medium"
              style={{
                background: `${meta.color}12`,
                border:     `1px solid ${meta.color}25`,
                color:      meta.color,
              }}
            >
              {signal.signal_type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Link
            href={`/chat?q=${encodeURIComponent(`Tell me about this web signal: ${signal.title}`)}`}
            className="text-[10px] flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity text-emerald-400 hover:text-emerald-300"
          >
            Chat
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 2h6M2 5h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
          </Link>
          {signal.url && (
            <a
              href={signal.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ color: BRAND.blue }}
            >
              Source
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 8L8 2M8 2H4M8 2v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
            </a>
          )}
        </div>
      </div>

      {/* Detected at */}
      {signal.detected_at && (
        <p
          className="text-[10px] mt-2 pt-2"
          style={{ borderTop: "1px solid rgba(255,255,255,0.04)", color: "#4B5563" }}
        >
          {formatTime(signal.detected_at)}
        </p>
      )}

      {/* High-risk glow */}
      {isHigh && (
        <div
          className="absolute inset-0 rounded-xl pointer-events-none"
          style={{ boxShadow: "inset 0 0 0 1px rgba(239,68,68,0.15)" }}
        />
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Tab 1 — Category Column
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
      <div
        className="flex items-center gap-2 px-1 mb-3 pb-3"
        style={{ borderBottom: `1px solid ${SURFACE.border}` }}
      >
        <span style={{ color: meta.color }}>{meta.icon}</span>
        <span
          className="text-[12px] font-bold uppercase tracking-wider"
          style={{ color: meta.color }}
        >
          {meta.label}
        </span>
        <span
          className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full"
          style={{
            background: `${meta.color}15`,
            border:     `1px solid ${meta.color}30`,
            color:      meta.color,
          }}
        >
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
          <div
            className="flex flex-col items-center justify-center py-10 rounded-xl gap-2"
            style={{ background: SURFACE.elevated, border: `1px dashed ${SURFACE.border}` }}
          >
            <span style={{ color: meta.color, opacity: 0.4 }}>{meta.icon}</span>
            <p className="text-[11px]" style={{ color: "#4B5563" }}>
              No signals
            </p>
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
// Tab 1 — Live Signals
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
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10.5px] font-bold uppercase tracking-wide"
              style={{
                background: "rgba(245,158,11,0.12)",
                border:     "1px solid rgba(245,158,11,0.35)",
                color:      "#F59E0B",
              }}
            >
              <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor">
                <circle cx="4" cy="4" r="4"/>
              </svg>
              Demo data
            </span>
          ) : (
            <LiveBadge />
          )}
          <p className="text-[13px]" style={{ color: "#6B7280" }}>
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
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-[12px] font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.02] active:scale-[0.98]"
          style={{
            background: "rgba(59,123,246,0.1)",
            border:     "1px solid rgba(59,123,246,0.25)",
            color:      BRAND.blue,
            boxShadow:  loading ? "none" : `0 0 16px ${BRAND.glow}`,
          }}
        >
          <svg
            width="13" height="13" viewBox="0 0 16 16" fill="none"
            className={loading ? "animate-spin" : ""}
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
      <div
        className="grid gap-5"
        style={{ gridTemplateColumns: "repeat(5, minmax(0, 1fr))" }}
      >
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

// ─────────────────────────────────────────────────────────────────────────────
// Tab 2 — Verdict Output Card
// ─────────────────────────────────────────────────────────────────────────────

const VerdictCard: FC<{ output: VerdictOutput }> = ({ output }) => {
  const meta       = verdictMeta(output.verdict);
  const violations = output.violations ?? [];
  const actions    = output.recommended_actions ?? [];
  const nccRefs    = output.ncc_refs ?? violations.map((v) => v.regulation_id).filter(Boolean);

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        border:    `1px solid ${meta.border}`,
        boxShadow: `0 0 32px ${meta.glow}`,
      }}
    >
      {/* Verdict banner */}
      <div
        className="flex items-center gap-4 px-6 py-5"
        style={{ background: meta.bg }}
      >
        {meta.icon}
        <div className="flex-1 min-w-0">
          <div
            className="text-[22px] font-black tracking-tight leading-tight"
            style={{ color: meta.text }}
          >
            {output.verdict}
          </div>
          <p className="text-[13px] mt-0.5" style={{ color: meta.text, opacity: 0.8 }}>
            {meta.label}
          </p>
        </div>
        {output.confidence_score !== undefined && (
          <div
            className="flex flex-col items-end shrink-0"
            style={{ color: meta.text }}
          >
            <span className="text-[28px] font-black leading-none">
              {Math.round((output.confidence_score ?? 0) * 100)}%
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
              Confidence
            </span>
          </div>
        )}
      </div>

      {/* Details section */}
      <div
        className="px-6 py-5 space-y-5"
        style={{ background: SURFACE.card }}
      >
        {/* Summary */}
        {output.finding?.summary && (
          <div>
            <p
              className="text-[11px] font-bold uppercase tracking-wider mb-2"
              style={{ color: "#4B5563" }}
            >
              Finding Summary
            </p>
            <p className="text-[13px] leading-relaxed" style={{ color: "#9CA3AF" }}>
              {output.finding.summary}
            </p>
          </div>
        )}

        {/* NCC/NDPA References */}
        {nccRefs.length > 0 && (
          <div>
            <p
              className="text-[11px] font-bold uppercase tracking-wider mb-2"
              style={{ color: "#4B5563" }}
            >
              NCC/NDPA Regulation References
            </p>
            <div className="flex flex-wrap gap-2">
              {nccRefs.map((ref, i) => (
                <span
                  key={i}
                  className="text-[11px] font-mono font-semibold px-2.5 py-1 rounded-lg"
                  style={{
                    background: "rgba(59,123,246,0.1)",
                    border:     "1px solid rgba(59,123,246,0.25)",
                    color:      BRAND.blue,
                  }}
                >
                  {ref}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Violations */}
        {violations.length > 0 && (
          <div>
            <p
              className="text-[11px] font-bold uppercase tracking-wider mb-2"
              style={{ color: "#4B5563" }}
            >
              Violations Detected
            </p>
            <div className="space-y-2">
              {violations.map((v, i) => (
                <div
                  key={i}
                  className="flex gap-3 px-3 py-2.5 rounded-xl"
                  style={{
                    background: "rgba(239,68,68,0.06)",
                    border:     "1px solid rgba(239,68,68,0.15)",
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
                    <path d="M8 2L14 13H2L8 2Z" stroke="#EF4444" strokeWidth="1.4" strokeLinejoin="round"/>
                    <path d="M8 6.5v2.5M8 11h.01" stroke="#EF4444" strokeWidth="1.4" strokeLinecap="round"/>
                  </svg>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {v.regulation_id && (
                        <span className="text-[10px] font-mono font-bold" style={{ color: "#EF4444" }}>
                          {v.regulation_id}
                        </span>
                      )}
                      {v.section && (
                        <span className="text-[10px]" style={{ color: "#6B7280" }}>
                          § {v.section}
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] mt-0.5 leading-snug" style={{ color: "#9CA3AF" }}>
                      {v.reason}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommended actions */}
        {actions.length > 0 && (
          <div>
            <p
              className="text-[11px] font-bold uppercase tracking-wider mb-2"
              style={{ color: "#4B5563" }}
            >
              Recommended Actions
            </p>
            <ol className="space-y-2">
              {actions.map((action, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black mt-0.5"
                    style={{
                      background: "rgba(59,123,246,0.15)",
                      color:      BRAND.blue,
                      border:     "1px solid rgba(59,123,246,0.25)",
                    }}
                  >
                    {i + 1}
                  </span>
                  <p className="text-[13px] leading-snug" style={{ color: "#D1D5DB" }}>
                    {action}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Tab 2 — Verdict & Compliance
// ─────────────────────────────────────────────────────────────────────────────

const LAST_VERDICT_KEY   = "iroko_last_verdict";
const LAST_DECISION_KEY  = "iroko_last_decision";

const ComplianceTab: FC = () => {
  // Restore last compliance check from localStorage so Download always reflects the last result
  const [decisionText, setDecisionText] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(LAST_DECISION_KEY) ?? "";
  });
  const [checking,    setChecking]    = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [verdict,     setVerdict]     = useState<VerdictOutput | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const stored = localStorage.getItem(LAST_VERDICT_KEY);
      return stored ? (JSON.parse(stored) as VerdictOutput) : null;
    } catch {
      return null;
    }
  });
  const [error,       setError]       = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ── Voice compliance ───────────────────────────────────────────────────────
  const voiceEnabled = process.env.NEXT_PUBLIC_VOICE_ENABLED !== "false";
  // apiKeyRef lets the hook always read the latest key without re-mounting
  const apiKeyRef = useRef<string>("");

  const handleVoiceVerdict = useCallback((v: import("@/hooks/useVoiceCompliance").VerdictResponse) => {
    const asVerdictOutput = {
      verdict:             v.verdict,
      compliant:           v.verdict === "GO",
      confidence_score:    v.confidence,
      violations:          v.flags.map((f) => ({ regulation_id: "", section: "", reason: f })),
      recommended_actions: [],
      ncc_refs:            v.regulation ? [v.regulation] : [],
      finding:             { summary: v.reasoning },
    };
    setVerdict(asVerdictOutput);
    localStorage.setItem(LAST_VERDICT_KEY, JSON.stringify(asVerdictOutput));
  }, []);

  const {
    isListening,
    isProcessing: voiceProcessing,
    transcript,
    error: voiceError,
    startListening,
    stopListening,
  } = useVoiceCompliance({
    userApiKey: apiKeyRef.current,
    onVerdict:  handleVoiceVerdict,
  });

  // Populate textarea when transcript arrives
  useEffect(() => {
    if (transcript) {
      setDecisionText(transcript);
      localStorage.setItem(LAST_DECISION_KEY, transcript);
    }
  }, [transcript]);

  // ── AethexAI live voice agent ──────────────────────────────────────────────
  const [agentError, setAgentError] = useState<string | null>(null);
  const { status: agentStatus, startCall, endCall } = useAgent({
    agentId: process.env.NEXT_PUBLIC_IROKO_AGENT_ID ?? "9aad19b0-5d6e-4306-ac66-cbc8e2486cae",
    onError: (msg) => setAgentError(msg),
  });

  // ── API key state ──────────────────────────────────────────────────────────
  const [apiKey,     setApiKey]     = useState<string | null>(null);
  const [keyVisible, setKeyVisible] = useState(false);
  const [keyCopied,  setKeyCopied]  = useState(false);
  const [keyLoading, setKeyLoading] = useState(false);
  const [keyError,   setKeyError]   = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("atlas_user");
      if (raw) {
        const user = JSON.parse(raw) as Record<string, unknown>;
        const k = user?.api_key;
        if (typeof k === "string" && k) { setApiKey(k); apiKeyRef.current = k; }
      }
    } catch { /* ignore */ }
  }, []);

  const handleGenerateKey = async () => {
    setKeyLoading(true);
    setKeyError(null);
    try {
      const res = await fetch("/api/auth/generate-key", {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status}: ${text}`);
      }
      const data = await res.json() as { key?: unknown; api_key?: string };
      // Proxy wraps backend response as { key: { api_key, message, ... } }
      const newKey: string =
        typeof data.key === "string"
          ? data.key
          : (data.key as Record<string, string> | null)?.api_key
            ?? data.api_key
            ?? "";
      setApiKey(newKey);
      apiKeyRef.current = newKey;
      setKeyVisible(true);
      try {
        const raw  = localStorage.getItem("atlas_user");
        const user = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
        localStorage.setItem("atlas_user", JSON.stringify({ ...user, api_key: newKey }));
      } catch { /* ignore */ }
    } catch (e) {
      setKeyError((e as Error).message ?? "Failed to generate key");
    } finally {
      setKeyLoading(false);
    }
  };

  const handleCopyKey = async () => {
    if (!apiKey) return;
    await navigator.clipboard.writeText(apiKey);
    setKeyCopied(true);
    setTimeout(() => setKeyCopied(false), 2000);
  };

  const maskedKey = apiKey
    ? `${apiKey.slice(0, 12)}${"•".repeat(Math.max(0, apiKey.length - 16))}${apiKey.slice(-4)}`
    : null;

  const handleCheck = async () => {
    if (!decisionText.trim()) return;
    setChecking(true);
    setError(null);
    setVerdict(null);
    try {
      const result = await apiFetch<VerdictOutput>("/check-compliance", {
        method: "POST",
        body:   JSON.stringify({ decision_text: decisionText }),
      });
      setVerdict(result);
      // Persist so Download works even after a page refresh
      localStorage.setItem(LAST_VERDICT_KEY,  JSON.stringify(result));
      localStorage.setItem(LAST_DECISION_KEY, decisionText);
    } catch (e) {
      setError((e as Error).message ?? "Compliance check failed.");
    } finally {
      setChecking(false);
    }
  };

  const handleDownloadBrief = async () => {
    setDownloading(true);
    setError(null);
    try {
      let blob: Blob;

      // ── Resolve verdict: prefer React state, fall back to localStorage ──
      // This guards against React closure edge-cases where `verdict` state
      // is transiently null (e.g. during a check) but localStorage still
      // holds the last successful result.
      let activeVerdict: VerdictOutput | null = verdict;
      let activeDecision: string = decisionText;
      if (!activeVerdict) {
        try {
          const stored = localStorage.getItem(LAST_VERDICT_KEY);
          if (stored) activeVerdict = JSON.parse(stored) as VerdictOutput;
          const storedDecision = localStorage.getItem(LAST_DECISION_KEY);
          if (storedDecision) activeDecision = storedDecision;
        } catch { /* ignore parse errors */ }
      }

      if (activeVerdict) {
        // ── A compliance check exists — use the dedicated PDF endpoint ──
        const res = await fetch(`${API}/compliance-pdf`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken()}`,
          },
          body: JSON.stringify({
            verdict:             activeVerdict.verdict,
            compliant:           activeVerdict.compliant ?? true,
            confidence_score:    activeVerdict.confidence_score ?? null,
            violations:          activeVerdict.violations ?? [],
            recommended_actions: activeVerdict.recommended_actions ?? [],
            ncc_refs:            activeVerdict.ncc_refs ?? [],
            decision_text:       activeDecision,
            summary:             activeVerdict.finding?.summary ?? "",
            workspace_name:      "Enterprise Telecom Operations",
          }),
        });
        if (!res.ok) {
          const detail = await res.text().catch(() => res.statusText);
          throw new Error(`PDF generation failed (${res.status}): ${detail}`);
        }
        blob = await res.blob();
      } else {
        // ── No compliance check ever run — fall back to generic audit brief ──
        const res = await fetch(`${API}/brief?include_audit_trail=true`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
        blob = await res.blob();
      }

      const downloadVerdict = activeVerdict?.verdict;
      const url = URL.createObjectURL(blob);
      const a   = document.createElement("a");
      a.href     = url;
      a.download = downloadVerdict
        ? `iroko-compliance-${downloadVerdict.toLowerCase()}-${new Date().toISOString().slice(0, 10)}.pdf`
        : `iroko-document-intelligence-brief-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Brief download failed: ${(e as Error).message}`);
    } finally {
      setDownloading(false);
    }
  };

  // Auto-grow textarea
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setDecisionText(e.target.value);
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 220)}px`;
  };

  return (
    <div className="flex flex-col gap-6">
    <div className="grid gap-6" style={{ gridTemplateColumns: "1fr 1fr" }}>
      {/* Left: input panel */}
      <div className="flex flex-col gap-5">
        {/* Compliance checker */}
        <div
          className="rounded-2xl p-6"
          style={{ background: SURFACE.card, border: `1px solid ${SURFACE.border}` }}
        >
          <div className="flex items-center gap-3 mb-5">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{
                background: "rgba(59,123,246,0.12)",
                border:     "1px solid rgba(59,123,246,0.2)",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
                  stroke={BRAND.blue} strokeWidth="1.4" strokeLinejoin="round"/>
                <path d="M5.5 8l2 2 3-3" stroke={BRAND.blue} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <h3 className="text-[14px] font-bold" style={{ color: "#E5E7EB" }}>
                NCC/NDPA Compliance Check
              </h3>
              <p className="text-[11px] mt-0.5" style={{ color: "#6B7280" }}>
                Evaluate a decision against the live NCC/NDPA regulatory corpus
              </p>
            </div>
          </div>

          {voiceEnabled && (
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <VoiceMicButton
                isListening={isListening}
                isProcessing={voiceProcessing}
                onStart={startListening}
                onStop={stopListening}
              />
              <AgentCallButton
                status={agentStatus}
                onStart={startCall}
                onEnd={endCall}
              />
              {(voiceError ?? agentError) && (
                <span className="text-[11.5px]" style={{ color: "#EF4444" }}>
                  {voiceError ?? agentError}
                </span>
              )}
            </div>
          )}

          <div className="relative">
            <textarea
              ref={textareaRef}
              value={decisionText}
              onChange={handleInput}
              placeholder="Describe a decision or planned action for compliance review…&#10;&#10;e.g. &quot;We plan to launch a new analytics pipeline on MoMo transaction data next quarter — what NDPA obligations apply?&quot;"
              className="w-full resize-none rounded-xl text-[13px] leading-relaxed transition-all duration-200 placeholder:text-[#374151] focus:outline-none"
              style={{
                minHeight:    "140px",
                background:   SURFACE.elevated,
                border:       "1px solid rgba(255,255,255,0.08)",
                color:        "#E5E7EB",
                padding:      "14px 16px",
                caretColor:   BRAND.blue,
              }}
              onFocus={(e) => {
                e.currentTarget.style.border = `1px solid rgba(59,123,246,0.5)`;
                e.currentTarget.style.boxShadow = `0 0 0 3px rgba(59,123,246,0.1)`;
              }}
              onBlur={(e) => {
                e.currentTarget.style.border = "1px solid rgba(255,255,255,0.08)";
                e.currentTarget.style.boxShadow = "none";
              }}
            />
            {decisionText.length > 0 && (
              <span
                className="absolute bottom-3 right-3 text-[10px]"
                style={{ color: "#374151" }}
              >
                {decisionText.length} chars
              </span>
            )}
          </div>

          {error && (
            <div className="mt-3">
              <ErrorBanner message={error} onDismiss={() => setError(null)} />
            </div>
          )}

          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={handleCheck}
              disabled={checking || !decisionText.trim()}
              className="flex-1 flex items-center justify-center gap-2 h-11 rounded-xl text-[13px] font-bold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.01] active:scale-[0.99]"
              style={{
                background: checking
                  ? "rgba(59,123,246,0.15)"
                  : "linear-gradient(135deg, #3B7BF6, #2563EB)",
                color:      "#fff",
                border:     "1px solid rgba(59,123,246,0.4)",
                boxShadow:  checking ? "none" : `0 0 20px ${BRAND.glow}`,
              }}
            >
              {checking ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin">
                    <circle cx="7" cy="7" r="5.5" stroke="rgba(255,255,255,0.3)" strokeWidth="2"/>
                    <path d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  Analysing against NCC/NDPA corpus…
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
                      stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
                    <path d="M5.5 8l2 2 3-3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Check Compliance
                </>
              )}
            </button>
          </div>
        </div>

        {/* Brief download */}
        <div
          className="rounded-2xl p-6"
          style={{ background: SURFACE.card, border: `1px solid ${SURFACE.border}` }}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-[14px] font-bold" style={{ color: "#E5E7EB" }}>
                Compliance Brief
              </h3>
              <p className="text-[12px] mt-1 leading-relaxed" style={{ color: "#6B7280" }}>
                Export a boardroom-ready PDF containing the compliance summary,
                audit trail, and recommended actions for regulatory review.
              </p>
            </div>
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z"
                  stroke="#EF4444" strokeWidth="1.6" strokeLinejoin="round"/>
                <path d="M14 2v6h6M8 13h8M8 17h5" stroke="#EF4444" strokeWidth="1.6" strokeLinecap="round"/>
              </svg>
            </div>
          </div>

          <button
            onClick={handleDownloadBrief}
            disabled={downloading || checking}
            className="mt-5 w-full flex items-center justify-center gap-2.5 h-11 rounded-xl text-[13px] font-bold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.01] active:scale-[0.99]"
            style={{
              background: downloading
                ? "rgba(239,68,68,0.08)"
                : "rgba(239,68,68,0.1)",
              border:     "1px solid rgba(239,68,68,0.25)",
              color:      "#EF4444",
              boxShadow:  downloading ? "none" : "0 0 16px rgba(239,68,68,0.12)",
            }}
          >
            {downloading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="animate-spin">
                  <circle cx="7" cy="7" r="5.5" stroke="rgba(239,68,68,0.3)" strokeWidth="2"/>
                  <path d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5" stroke="#EF4444" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Generating PDF…
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <path d="M8 2v8M5 7l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M2.5 11.5v1A1.5 1.5 0 0 0 4 14h8a1.5 1.5 0 0 0 1.5-1.5v-1"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                Download Compliance Brief (PDF)
              </>
            )}
          </button>
        </div>
      </div>

      {/* Right: verdict output */}
      <div className="flex flex-col gap-4">
        {verdict ? (
          <VerdictCard output={verdict} />
        ) : (
          <div
            className="flex-1 flex flex-col items-center justify-center rounded-2xl py-20 gap-4"
            style={{
              background:   SURFACE.elevated,
              border:       `1px dashed ${SURFACE.border}`,
              minHeight:    "380px",
            }}
          >
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center"
              style={{
                background: "rgba(59,123,246,0.08)",
                border:     "1px solid rgba(59,123,246,0.15)",
              }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M12 3L21 7.5V12C21 16.5 17.5 20.5 12 22C6.5 20.5 3 16.5 3 12V7.5L12 3Z"
                  stroke={BRAND.blue} strokeWidth="1.5" strokeLinejoin="round"/>
                <path d="M9 12l2 2 4-4" stroke={BRAND.blue} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="text-center">
              <p className="text-[14px] font-semibold" style={{ color: "#E5E7EB" }}>
                Verdict will appear here
              </p>
              <p className="text-[12px] mt-1" style={{ color: "#4B5563" }}>
                Enter a decision and click Check Compliance
              </p>
            </div>
          </div>
        )}
      </div>
    </div>

    {/* API key panel — full width below the 2-column grid */}
    <div
      className="rounded-2xl p-6"
      style={{ background: SURFACE.card, border: `1px solid ${SURFACE.border}` }}
    >
      <div className="flex items-center justify-between gap-4 mb-4">
        <div>
          <h3 className="text-[14px] font-bold" style={{ color: "#E5E7EB" }}>
            Compliance API Key
          </h3>
          <p className="text-[11px] mt-0.5" style={{ color: "#6B7280" }}>
            Use with{" "}
            <code
              className="px-1.5 py-0.5 rounded-md text-[10.5px] font-mono"
              style={{ background: SURFACE.elevated, color: BRAND.blue }}
            >
              POST /api/v1/compliance/check
            </code>
          </p>
        </div>
        <button
          onClick={handleGenerateKey}
          disabled={keyLoading}
          className="shrink-0 px-4 py-2 rounded-xl text-[12px] font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{
            background: "rgba(59,123,246,0.1)",
            border:     "1px solid rgba(59,123,246,0.25)",
            color:      BRAND.blue,
          }}
        >
          {keyLoading ? "Generating…" : apiKey ? "Regenerate" : "Generate key"}
        </button>
      </div>

      {keyError && (
        <div className="mb-3">
          <ErrorBanner message={keyError} onDismiss={() => setKeyError(null)} />
        </div>
      )}

      {apiKey ? (
        <>
          <div className="flex items-center gap-2">
            <code
              className="flex-1 px-3 py-2.5 rounded-xl text-[12.5px] font-mono truncate select-all"
              style={{
                background: SURFACE.elevated,
                border:     `1px solid ${SURFACE.border}`,
                color:      "#D1D5DB",
              }}
            >
              {keyVisible ? apiKey : maskedKey}
            </code>
            <button
              onClick={() => setKeyVisible((v) => !v)}
              title={keyVisible ? "Hide" : "Show"}
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-colors"
              style={{ background: SURFACE.elevated, border: `1px solid ${SURFACE.border}`, color: "#6B7280" }}
            >
              {keyVisible ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
            <button
              onClick={handleCopyKey}
              title="Copy"
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-colors"
              style={{
                background: keyCopied ? "rgba(16,185,129,0.1)" : SURFACE.elevated,
                border:     `1px solid ${keyCopied ? "rgba(16,185,129,0.3)" : SURFACE.border}`,
                color:      keyCopied ? "#10B981" : "#6B7280",
              }}
            >
              {keyCopied ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              )}
            </button>
          </div>
          <p className="text-[11px] mt-3" style={{ color: "#4B5563" }}>
            Pass as{" "}
            <code
              className="px-1 py-0.5 rounded text-[10.5px] font-mono"
              style={{ background: SURFACE.elevated, color: BRAND.blue }}
            >
              Authorization: Bearer &lt;key&gt;
            </code>
            . Regenerating immediately invalidates the old key.
          </p>
        </>
      ) : (
        <p className="text-[12px]" style={{ color: "#9CA3AF" }}>
          No API key yet.{" "}
          <button
            onClick={handleGenerateKey}
            className="underline"
            style={{ color: BRAND.blue, background: "none", border: "none", cursor: "pointer" }}
          >
            Generate one
          </button>{" "}
          to call the compliance API directly.
        </p>
      )}
    </div>
    </div>
  );
};



// ─────────────────────────────────────────────────────────────────────────────
// Tab 3 — Audit Trail Table Row
// ─────────────────────────────────────────────────────────────────────────────

const verdictPill = (v?: string) => {
  if (!v) return null;
  const meta = VERDICT_META[v] ?? VERDICT_META["MONITOR"];
  return (
    <span
      className="inline-flex items-center text-[10px] font-bold px-2 py-0.5 rounded-full"
      style={{
        background: meta.bg,
        border:     `1px solid ${meta.border}`,
        color:      meta.text,
      }}
    >
      {v}
    </span>
  );
};

const AuditRow: FC<{ entry: AuditEntry; index: number }> = ({ entry, index }) => {
  const hashTail = entry.chain_hash?.slice(-8) ?? "—";

  return (
    <tr
      className="transition-colors duration-150"
      style={{
        background: index % 2 === 0 ? "transparent" : "rgba(255,255,255,0.015)",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLTableRowElement).style.background = "rgba(59,123,246,0.04)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLTableRowElement).style.background =
          index % 2 === 0 ? "transparent" : "rgba(255,255,255,0.015)";
      }}
    >
      {/* Agent */}
      <td className="px-4 py-3 text-[12px] font-semibold" style={{ color: "#E5E7EB" }}>
        {entry.agent_name}
      </td>
      {/* Action */}
      <td className="px-4 py-3">
        <span
          className="text-[11px] px-2 py-0.5 rounded-md font-medium"
          style={{
            background: "rgba(255,255,255,0.05)",
            border:     "1px solid rgba(255,255,255,0.08)",
            color:      "#9CA3AF",
          }}
        >
          {entry.action_type}
        </span>
      </td>
      {/* Summary */}
      <td
        className="px-4 py-3 text-[12px] max-w-xs"
        style={{ color: "#6B7280" }}
        title={entry.decision_summary}
      >
        {truncate(entry.decision_summary, 64)}
      </td>
      {/* Verdict */}
      <td className="px-4 py-3">{verdictPill(entry.verdict)}</td>
      {/* Timestamp */}
      <td className="px-4 py-3 text-[11px] whitespace-nowrap" style={{ color: "#4B5563" }}>
        {formatTime(entry.created_at)}
      </td>
      {/* Chain hash */}
      <td className="px-4 py-3">
        <code
          className="text-[10px] font-mono px-2 py-1 rounded-lg"
          style={{
            background: "rgba(139,92,246,0.1)",
            border:     "1px solid rgba(139,92,246,0.2)",
            color:      "#8B5CF6",
            letterSpacing: "0.04em",
          }}
        >
          …{hashTail}
        </code>
      </td>
    </tr>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Tab 3 — Audit Trail
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
            <span
              className="text-[12px] px-3 py-1 rounded-full"
              style={{ background: SURFACE.elevated, color: "#6B7280" }}
            >
              Loading audit trail…
            </span>
          ) : (
            <>
              <span
                className="text-[13px] font-semibold"
                style={{ color: "#E5E7EB" }}
              >
                {entries.length} entries
              </span>
              {/* Chain integrity badge */}
              {data && chainValid !== undefined && (
                <span
                  className="flex items-center gap-1.5 text-[11px] font-bold px-3 py-1 rounded-full"
                  style={{
                    background: chainValid
                      ? "rgba(16,185,129,0.1)"
                      : "rgba(239,68,68,0.1)",
                    border: `1px solid ${chainValid
                      ? "rgba(16,185,129,0.25)"
                      : "rgba(239,68,68,0.25)"}`,
                    color: chainValid ? "#10B981" : "#EF4444",
                  }}
                >
                  {chainValid ? (
                    <>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                        <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
                          stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                        <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      Chain Verified
                    </>
                  ) : (
                    <>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
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
            <span className="text-[11px]" style={{ color: "#4B5563" }}>
              Page {page + 1} / {totalPages}
            </span>
            <div className="flex gap-1">
              {[
                { label: "←", disabled: page === 0,               action: () => setPage((p) => Math.max(0, p - 1)) },
                { label: "→", disabled: page >= totalPages - 1,   action: () => setPage((p) => Math.min(totalPages - 1, p + 1)) },
              ].map(({ label, disabled, action }) => (
                <button
                  key={label}
                  onClick={action}
                  disabled={disabled}
                  className="w-8 h-8 rounded-lg text-[13px] font-bold transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed"
                  style={{
                    background: SURFACE.elevated,
                    border:     `1px solid ${SURFACE.border}`,
                    color:      "#9CA3AF",
                  }}
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
      <div
        className="rounded-2xl overflow-hidden"
        style={{ border: `1px solid ${SURFACE.border}` }}
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr style={{ background: SURFACE.elevated }}>
                {["Agent", "Action", "Summary", "Verdict", "Timestamp", "Chain Hash"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-[10px] font-black uppercase tracking-widest whitespace-nowrap"
                    style={{ color: "#4B5563", borderBottom: `1px solid ${SURFACE.border}` }}
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
                  <td colSpan={6} className="px-4 py-16 text-center text-[13px]" style={{ color: "#4B5563" }}>
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
          <div
            className="px-4 py-3 flex items-center justify-between"
            style={{ borderTop: `1px solid ${SURFACE.border}`, background: SURFACE.elevated }}
          >
            <p className="text-[11px]" style={{ color: "#4B5563" }}>
              Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, entries.length)} of {entries.length}
            </p>
            {data?.chain_integrity?.broken_at && (
              <p className="text-[11px]" style={{ color: "#EF4444" }}>
                Chain broken at entry: {data.chain_integrity.broken_at}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Header stats bar
// ─────────────────────────────────────────────────────────────────────────────

const StatPill: FC<{
  label:   string;
  value:   string | number;
  color?:  string;
  loading: boolean;
}> = ({ label, value, color = "#6B7280", loading }) => (
  <div
    className="flex items-center gap-2 px-4 py-2 rounded-xl"
    style={{ background: SURFACE.elevated, border: `1px solid ${SURFACE.border}` }}
  >
    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#4B5563" }}>
      {label}
    </span>
    {loading ? (
      <SkeletonLine w="w-8" />
    ) : (
      <span className="text-[15px] font-black" style={{ color }}>
        {value}
      </span>
    )}
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// Root component
// ─────────────────────────────────────────────────────────────────────────────

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
    <div
      className="flex flex-col min-h-screen"
      style={{ background: SURFACE.page, color: "#E5E7EB" }}
    >
      {/* ── Page header ───────────────────────────────────────────────────── */}
      <div
        className="px-8 pt-8 pb-0"
        style={{ borderBottom: `1px solid ${SURFACE.border}` }}
      >
        <div className="flex items-start justify-between gap-6 pb-5">
          {/* Title block */}
          <div className="flex items-center gap-4">
            <div
              className="w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"
              style={{
                background: "linear-gradient(135deg, rgba(59,123,246,0.2), rgba(139,92,246,0.2))",
                border:     "1px solid rgba(59,123,246,0.25)",
                boxShadow:  `0 0 24px ${BRAND.glow}`,
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L22 7V12C22 17 17.5 21 12 22C6.5 21 2 17 2 12V7L12 2Z"
                  stroke="url(#grad)" strokeWidth="1.5" strokeLinejoin="round"/>
                <circle cx="12" cy="12" r="3" stroke="url(#grad)" strokeWidth="1.5"/>
                <defs>
                  <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%"   stopColor={BRAND.blue}/>
                    <stop offset="100%" stopColor={BRAND.purple}/>
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <div>
              <h1
                className="text-[22px] font-black tracking-tight leading-tight"
                style={{ color: "#F9FAFB" }}
              >
                Web Intelligence
              </h1>
              <p className="text-[13px] mt-0.5" style={{ color: "#6B7280" }}>
                Boardroom-ready document &amp; operations intelligence for enterprise telecoms — powered by Bright Data
              </p>
            </div>
          </div>

          {/* Stats pills */}
          <div className="flex items-center gap-2 flex-wrap justify-end">
            {opsStats.docs !== null && (
              <StatPill label="Documents Indexed" value={opsStats.docs} color="#10B981" loading={false} />
            )}
            {opsStats.alerts !== null && (
              <StatPill label="Open Alerts" value={opsStats.alerts} color="#F59E0B" loading={false} />
            )}
            <StatPill label="Total Signals"  value={totalSignals} color={BRAND.blue}   loading={signalsLoading} />
            <StatPill label="Fraud Alerts"   value={fraudCount}   color="#EF4444"      loading={signalsLoading} />
            <StatPill label="Audit Entries"  value={auditCount}   color={BRAND.purple} loading={auditLoading}  />
            {auditData?.chain_integrity?.valid !== undefined && (
              <div
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[12px] font-bold"
                style={{
                  background: auditData.chain_integrity.valid
                    ? "rgba(16,185,129,0.08)"
                    : "rgba(239,68,68,0.08)",
                  border: `1px solid ${
                    auditData.chain_integrity.valid
                      ? "rgba(16,185,129,0.2)"
                      : "rgba(239,68,68,0.2)"
                  }`,
                  color: auditData.chain_integrity.valid ? "#10B981" : "#EF4444",
                }}
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
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
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
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
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
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
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

      {/* ── CSS animations ────────────────────────────────────────────────── */}
      <style>{`
        @keyframes ping {
          75%, 100% { transform: scale(2); opacity: 0; }
        }
        .animate-ping { animation: ping 1.5s cubic-bezier(0,0,.2,1) infinite; }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: .5; }
        }
        .animate-pulse { animation: pulse 2s cubic-bezier(.4,0,.6,1) infinite; }
        .line-clamp-2 {
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
      `}</style>
    </div>
  );
};

export default WebIntelDashboard;
