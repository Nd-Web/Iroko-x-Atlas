"use client";

/**
 * components/compliance/UpcomingDeadlines.tsx
 *
 * Compact views of the regulatory returns calendar for the Compliance Agent
 * page: two stat cards and the next deadlines list.
 */

import Link from "next/link";
import { DaysLeft } from "@/components/compliance/RegulatoryReturns";
import { useReturnsCatalog } from "@/lib/returns";

function StatCard({ value, label, sub, accent }: { value: string; label: string; sub: string; accent: string }) {
  return (
    <div className="card relative overflow-hidden py-[18px] px-5">
      <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: accent }} />
      <div className="text-[28px] font-bold tracking-[-0.04em] leading-none mb-[5px]" style={{ color: accent }}>{value}</div>
      <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{label}</div>
      <div className="text-[11.5px] text-gray-400 truncate">{sub}</div>
    </div>
  );
}

export function DeadlineStats() {
  const { data } = useReturnsCatalog();
  const due30 = data?.calendar.filter((d) => d.days_left <= 30) ?? [];
  const next = data?.calendar[0];
  return (
    <>
      <StatCard value={data ? String(due30.length) : "…"} label="Returns due in 30 days" accent="#EF4444"
        sub={due30.length ? due30.map((d) => d.title).filter((t, i, a) => a.indexOf(t) === i).join(" · ") : "Nothing due in the next 30 days"} />
      <StatCard value={next ? (next.days_left === 0 ? "Today" : `${next.days_left}d`) : "…"} label="Next deadline" accent="#22C55E"
        sub={next ? `${next.title} — ${next.period_label}` : "Loading the regulatory calendar"} />
    </>
  );
}

export default function UpcomingDeadlines({ limit = 6 }: { limit?: number }) {
  const { data, isLoading, error } = useReturnsCatalog();
  return (
    <div className="card overflow-hidden">
      <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
        <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Regulatory deadlines</h2>
        <Link href="/compliance/reports" className="text-[12.5px] text-brand-600 no-underline font-semibold flex items-center gap-1">
          Prepare returns
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M2.5 6h7M7 3.5l2.5 2.5L7 8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </Link>
      </div>
      <div className="py-2">
        {isLoading && <div className="h-40 mx-5 my-2 rounded-lg bg-gray-100 animate-pulse" />}
        {error && <p className="px-5 py-3 text-[13px] text-gray-500 m-0">The regulatory calendar could not be loaded.</p>}
        {data?.calendar.slice(0, limit).map((d, i, arr) => (
          <div key={`${d.return_id}-${d.period}`} className={`flex justify-between items-center gap-3 py-[11px] px-5${i < arr.length - 1 ? " border-b border-border-default" : ""}`}>
            <div className="min-w-0">
              <div className="text-[13px] font-medium text-gray-700 mb-[3px] truncate">{d.title}</div>
              <div className="flex items-center gap-1.5">
                <span className="bg-gray-100 px-1.5 rounded text-[10.5px] font-bold text-gray-500">{d.regulator}</span>
                <span className="text-[11.5px] text-gray-400 truncate">{d.period_label} · due {new Date(`${d.due}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>
              </div>
            </div>
            <DaysLeft days={d.days_left} />
          </div>
        ))}
      </div>
    </div>
  );
}
