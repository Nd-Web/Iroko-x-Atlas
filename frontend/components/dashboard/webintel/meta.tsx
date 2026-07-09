/**
 * components/dashboard/webintel/meta.tsx
 *
 * Category / verdict metadata + small formatting helpers.
 * All colours are expressed as Tailwind utility classes using the original
 * Iroko dark palette (page #080B14, card #0F1320, elevated #141824).
 * Category mapping: regulatory→#3B7BF6, competitor→#F59E0B,
 * vendor_risk→#8B5CF6, fraud→#EF4444, market→#10B981.
 */

import React, { type ReactNode } from "react";
import type { SignalCategory } from "./types";

export interface CategoryMeta {
  label: string;
  /** Icon / label text colour */
  text: string;
  /** Pulsing dot fill */
  dot: string;
  /** Signal-card left accent border */
  leftBorder: string;
  /** Tinted chip (count badge / signal-type tag) */
  chip: string;
  icon: ReactNode;
}

export const CATEGORY_META: Record<SignalCategory, CategoryMeta> = {
  regulatory: {
    label: "Regulatory",
    text: "text-[#3B7BF6]",
    dot: "bg-[#3B7BF6]",
    leftBorder: "border-l-[#3B7BF6]",
    chip: "bg-[rgba(59,123,246,0.08)] text-[#3B7BF6] border border-[rgba(59,123,246,0.19)]",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z"
          stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  competitor: {
    label: "Competitor",
    text: "text-[#F59E0B]",
    dot: "bg-[#F59E0B]",
    leftBorder: "border-l-[#F59E0B]",
    chip: "bg-[rgba(245,158,11,0.08)] text-[#F59E0B] border border-[rgba(245,158,11,0.19)]",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  vendor_risk: {
    label: "Vendor Risk",
    text: "text-[#8B5CF6]",
    dot: "bg-[#8B5CF6]",
    leftBorder: "border-l-[#8B5CF6]",
    chip: "bg-[rgba(139,92,246,0.08)] text-[#8B5CF6] border border-[rgba(139,92,246,0.19)]",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M8 2L2 5v4c0 3.3 2.7 5.3 6 6 3.3-.7 6-2.7 6-6V5L8 2Z"
          stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M8 6v3M8 10.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  fraud: {
    label: "Fraud",
    text: "text-[#EF4444]",
    dot: "bg-[#EF4444]",
    leftBorder: "border-l-[#EF4444]",
    chip: "bg-[rgba(239,68,68,0.08)] text-[#EF4444] border border-[rgba(239,68,68,0.19)]",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M8 6.5v3M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  market: {
    label: "Market Intel",
    text: "text-[#10B981]",
    dot: "bg-[#10B981]",
    leftBorder: "border-l-[#10B981]",
    chip: "bg-[rgba(16,185,129,0.08)] text-[#10B981] border border-[rgba(16,185,129,0.19)]",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M2 12L6 8l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="14" cy="5" r="1.5" fill="currentColor"/>
      </svg>
    ),
  },
};

export interface VerdictMeta {
  /** Verdict banner background tint */
  bannerBg: string;
  /** Verdict card outer border */
  border: string;
  /** Verdict headline / confidence text */
  text: string;
  /** Icon colour wrapper */
  iconText: string;
  /** Outer-card glow shadow */
  glow: string;
  /** Small verdict pill (audit table) */
  pill: string;
  label: string;
  icon: ReactNode;
}

export const VERDICT_META: Record<string, VerdictMeta> = {
  GO: {
    bannerBg: "bg-[rgba(16,185,129,0.08)]",
    border: "border-[rgba(16,185,129,0.3)]",
    text: "text-[#10B981]",
    iconText: "text-[#10B981]",
    glow: "shadow-[0_0_32px_rgba(16,185,129,0.2)]",
    pill: "bg-[rgba(16,185,129,0.08)] border border-[rgba(16,185,129,0.3)] text-[#10B981]",
    label: "✅ GO — Proceed with confidence",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M8 12l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  "NO-GO": {
    bannerBg: "bg-[rgba(239,68,68,0.08)]",
    border: "border-[rgba(239,68,68,0.3)]",
    text: "text-[#EF4444]",
    iconText: "text-[#EF4444]",
    glow: "shadow-[0_0_32px_rgba(239,68,68,0.2)]",
    pill: "bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.3)] text-[#EF4444]",
    label: "🚫 NO-GO — Action required immediately",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M15 9l-6 6M9 9l6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
  },
  MONITOR: {
    bannerBg: "bg-[rgba(245,158,11,0.08)]",
    border: "border-[rgba(245,158,11,0.3)]",
    text: "text-[#F59E0B]",
    iconText: "text-[#F59E0B]",
    glow: "shadow-[0_0_32px_rgba(245,158,11,0.2)]",
    pill: "bg-[rgba(245,158,11,0.08)] border border-[rgba(245,158,11,0.3)] text-[#F59E0B]",
    label: "⚠️ MONITOR — Flag for human review",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M12 8v5M12 15.5h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
  },
};

export function verdictMeta(v: string): VerdictMeta {
  return VERDICT_META[v] ?? VERDICT_META["MONITOR"];
}

/** Tinted badge classes for a signal risk level. */
export function riskBadgeClasses(level?: string): string {
  if (!level) return "text-[#6B7280] bg-[rgba(107,114,128,0.09)] border border-[rgba(107,114,128,0.21)]";
  const l = level.toUpperCase();
  if (l === "HIGH")   return "text-[#EF4444] bg-[rgba(239,68,68,0.09)] border border-[rgba(239,68,68,0.21)]";
  if (l === "MEDIUM") return "text-[#F59E0B] bg-[rgba(245,158,11,0.09)] border border-[rgba(245,158,11,0.21)]";
  return "text-[#10B981] bg-[rgba(16,185,129,0.09)] border border-[rgba(16,185,129,0.21)]";
}

export function formatTime(iso?: string): string {
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

export function truncate(str: string, n: number): string {
  return str.length > n ? str.slice(0, n) + "…" : str;
}
