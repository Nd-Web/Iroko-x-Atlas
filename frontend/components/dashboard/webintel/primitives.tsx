"use client";
/**
 * components/dashboard/webintel/primitives.tsx
 *
 * Small shared building blocks: pulsing dot, skeletons, error banner,
 * live badge, tab button and header stat pill.
 */

import React, { type FC, type ReactNode } from "react";

export const PulsingDot: FC<{ dotClass: string }> = ({ dotClass }) => (
  <span className="relative flex h-2 w-2 shrink-0" aria-hidden="true">
    <span
      className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 ${dotClass}`}
    />
    <span className={`relative inline-flex rounded-full h-2 w-2 ${dotClass}`} />
  </span>
);

export const SkeletonLine: FC<{ w?: string }> = ({ w = "w-full" }) => (
  <div className={`h-3 rounded-md animate-pulse bg-gray-100 ${w}`} />
);

export const SkeletonCard: FC = () => (
  <div className="rounded-xl p-4 space-y-3 bg-surface-card border border-border-default shadow-xs">
    <SkeletonLine w="w-3/4" />
    <SkeletonLine w="w-full" />
    <SkeletonLine w="w-1/2" />
  </div>
);

export const ErrorBanner: FC<{ message: string; onDismiss?: () => void }> = ({
  message, onDismiss,
}) => (
  <div className="flex items-start gap-3 px-4 py-3 rounded-xl text-sm bg-danger-50 border border-danger-200 text-danger-700">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5 text-danger-500" aria-hidden="true">
      <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M8 6.5v3M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
    <span className="flex-1 leading-snug">{message}</span>
    {onDismiss && (
      <button
        onClick={onDismiss}
        className="text-danger-500 hover:text-danger-700 transition-colors shrink-0 mt-0.5"
        aria-label="Dismiss error"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M10.5 3.5l-7 7M3.5 3.5l7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </button>
    )}
  </div>
);

// Shimmer badge for live status
export const LiveBadge: FC = () => (
  <span className="flex items-center gap-1.5 text-[10px] font-bold tracking-wide uppercase px-2 py-0.5 rounded-full text-success-700 bg-success-50 border border-success-100">
    <PulsingDot dotClass="bg-success-500" />
    Live
  </span>
);

// Tab button
export const TabButton: FC<{
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
  count?: number;
}> = ({ active, onClick, icon, label, count }) => (
  <button
    onClick={onClick}
    className={`relative flex items-center gap-2 px-5 py-3 text-sm font-semibold transition-all duration-200 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 border-b-2 ${
      active
        ? "text-gray-900 border-brand-600"
        : "text-gray-500 border-transparent hover:text-gray-800"
    }`}
    aria-selected={active}
    role="tab"
  >
    <span className={active ? "text-brand-600" : "text-gray-400"} aria-hidden="true">
      {icon}
    </span>
    {label}
    {count !== undefined && count > 0 && (
      <span
        className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center ${
          active ? "bg-brand-50 text-brand-700" : "bg-gray-100 text-gray-500"
        }`}
      >
        {count}
      </span>
    )}
  </button>
);

// Header stat pill
export const StatPill: FC<{
  label: string;
  value: string | number;
  valueClass?: string;
  loading: boolean;
}> = ({ label, value, valueClass = "text-gray-500", loading }) => (
  <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-card border border-border-default shadow-xs">
    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
      {label}
    </span>
    {loading ? (
      <SkeletonLine w="w-8" />
    ) : (
      <span className={`text-[15px] font-black ${valueClass}`}>{value}</span>
    )}
  </div>
);
