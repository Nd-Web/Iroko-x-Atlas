/**
 * components/dashboard/webintel/meta.tsx
 *
 * Category / verdict metadata + small formatting helpers.
 * All colours are expressed as Tailwind utility classes backed by the
 * design tokens declared in app/globals.css (@theme block).
 * Category mapping: regulatory→brand, competitor→warning, vendor_risk→info,
 * fraud→danger, market→success.
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
    text: "text-brand-700",
    dot: "bg-brand-500",
    leftBorder: "border-l-brand-500",
    chip: "bg-brand-50 text-brand-700 border border-brand-100",
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
    text: "text-warning-700",
    dot: "bg-warning-500",
    leftBorder: "border-l-warning-500",
    chip: "bg-warning-50 text-warning-700 border border-warning-100",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  vendor_risk: {
    label: "Vendor Risk",
    text: "text-info-700",
    dot: "bg-info-500",
    leftBorder: "border-l-info-500",
    chip: "bg-info-50 text-info-700 border border-info-100",
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
    text: "text-danger-700",
    dot: "bg-danger-500",
    leftBorder: "border-l-danger-500",
    chip: "bg-danger-50 text-danger-700 border border-danger-100",
    icon: (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M8 6.5v3M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  market: {
    label: "Market Intel",
    text: "text-success-700",
    dot: "bg-success-500",
    leftBorder: "border-l-success-500",
    chip: "bg-success-50 text-success-700 border border-success-100",
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
  /** Small verdict pill (audit table) */
  pill: string;
  label: string;
  icon: ReactNode;
}

export const VERDICT_META: Record<string, VerdictMeta> = {
  GO: {
    bannerBg: "bg-success-50",
    border: "border-success-100",
    text: "text-success-700",
    iconText: "text-success-500",
    pill: "bg-success-50 border border-success-100 text-success-700",
    label: "✅ GO — Proceed with confidence",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M8 12l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  "NO-GO": {
    bannerBg: "bg-danger-50",
    border: "border-danger-200",
    text: "text-danger-700",
    iconText: "text-danger-500",
    pill: "bg-danger-50 border border-danger-100 text-danger-700",
    label: "🚫 NO-GO — Action required immediately",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8"/>
        <path d="M15 9l-6 6M9 9l6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
  },
  MONITOR: {
    bannerBg: "bg-warning-50",
    border: "border-warning-100",
    text: "text-warning-700",
    iconText: "text-warning-500",
    pill: "bg-warning-50 border border-warning-100 text-warning-700",
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
  if (!level) return "text-gray-500 bg-gray-50 border border-border-default";
  const l = level.toUpperCase();
  if (l === "HIGH")   return "text-danger-700 bg-danger-50 border border-danger-100";
  if (l === "MEDIUM") return "text-warning-700 bg-warning-50 border border-warning-100";
  return "text-success-700 bg-success-50 border border-success-100";
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
