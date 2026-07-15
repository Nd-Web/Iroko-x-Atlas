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
  <div className={`h-3 rounded-md animate-pulse bg-white/[0.06] ${w}`} />
);

export const SkeletonCard: FC = () => (
  <div className="rounded-xl p-4 space-y-3 bg-[#141824] border border-white/[0.06]">
    <SkeletonLine w="w-3/4" />
    <SkeletonLine w="w-full" />
    <SkeletonLine w="w-1/2" />
  </div>
);

export const ErrorBanner: FC<{ message: string; onDismiss?: () => void }> = ({
  message, onDismiss,
}) => (
  <div className="flex items-start gap-3 px-4 py-3 rounded-xl text-sm bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.25)] text-[#FCA5A5]">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5 text-[#EF4444]" aria-hidden="true">
      <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M8 6.5v3M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
    <span className="flex-1 leading-snug">{message}</span>
    {onDismiss && (
      <button
        onClick={onDismiss}
        className="text-[#EF4444] hover:text-white transition-colors shrink-0 mt-0.5"
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
  <span className="flex items-center gap-1.5 text-[10px] font-bold tracking-wide uppercase px-2 py-0.5 rounded-full text-[#10B981] bg-[rgba(16,185,129,0.1)] border border-[rgba(16,185,129,0.2)]">
    <PulsingDot dotClass="bg-[#10B981]" />
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
    className={`relative flex items-center gap-2 px-5 py-3 text-sm font-semibold transition-all duration-200 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3B7BF6] border-b-2 ${
      active
        ? "text-[#E5E7EB] border-[#3B7BF6]"
        : "text-[#6B7280] border-transparent"
    }`}
    aria-selected={active}
    role="tab"
  >
    <span className={active ? "text-[#3B7BF6]" : "text-[#6B7280]"} aria-hidden="true">
      {icon}
    </span>
    {label}
    {count !== undefined && count > 0 && (
      <span
        className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center ${
          active ? "bg-[rgba(59,123,246,0.2)] text-[#3B7BF6]" : "bg-white/[0.06] text-[#9CA3AF]"
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
}> = ({ label, value, valueClass = "text-[#6B7280]", loading }) => (
  <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#141824] border border-white/[0.06]">
    <span className="text-[10px] font-bold uppercase tracking-wider text-[#4B5563]">
      {label}
    </span>
    {loading ? (
      <SkeletonLine w="w-8" />
    ) : (
      <span className={`text-[15px] font-black ${valueClass}`}>{value}</span>
    )}
  </div>
);
