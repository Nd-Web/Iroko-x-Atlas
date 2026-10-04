"use client";

/**
 * components/compliance/RegulatoryReturns.tsx
 *
 * The regulatory returns a microfinance bank files, with real deadlines from
 * the backend calendar, and the generator for each one.
 */

import { useCallback, useState } from "react";
import ReturnGenerator from "@/components/compliance/ReturnGenerator";
import { REGULATOR_NAMES, useReturnsCatalog, type DeadlineItem, type ReturnSpec } from "@/lib/returns";

function formatDue(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function DaysLeft({ days }: { days: number }) {
  const tone = days <= 3 ? "text-danger-700 bg-danger-50" : days <= 14 ? "text-warning-700 bg-warning-50" : "text-gray-500 bg-gray-100";
  const label = days === 0 ? "Due today" : days === 1 ? "1 day left" : `${days} days left`;
  return <span className={`text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0 ${tone}`}>{label}</span>;
}

export default function RegulatoryReturns() {
  const { data: catalog, isLoading, error, refetch } = useReturnsCatalog();
  const [open, setOpen] = useState<{ spec: ReturnSpec; period?: string } | null>(null);
  const close = useCallback(() => setOpen(null), []);

  if (isLoading) {
    return <div className="card h-48 animate-pulse" aria-busy="true" aria-label="Loading regulatory returns" />;
  }
  if (error || !catalog) {
    return (
      <div className="card px-5 py-4 text-[13px] text-gray-500 flex items-center justify-between gap-3">
        <span>Regulatory returns could not be loaded.</span>
        <button className="btn-secondary" style={{ padding: "6px 12px", fontSize: "12.5px" }} onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  const byId = Object.fromEntries(catalog.returns.map((r) => [r.id, r]));
  const deadlines = catalog.calendar.slice(0, 8);
  const event = catalog.returns.filter((r) => r.period_type === "event");
  const periodic = catalog.returns.filter((r) => r.period_type !== "event");

  return (
    <div className="flex flex-col gap-6">
      {/* Upcoming deadlines */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border-default">
          <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em] m-0">Upcoming regulatory deadlines</h2>
          <p className="text-[12.5px] text-gray-400 mt-[3px] mb-0">{catalog.holiday_note}</p>
        </div>
        <div>
          {deadlines.map((d: DeadlineItem, i) => (
            <div key={`${d.return_id}-${d.period}`} className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 px-5 py-3${i < deadlines.length - 1 ? " border-b border-border-default" : ""}`}>
              <div className="min-w-0">
                <div className="text-[13px] font-medium text-gray-800 truncate">{d.title}</div>
                <div className="flex items-center gap-1.5 mt-[2px]">
                  <span className="bg-gray-100 px-1.5 rounded text-[10.5px] font-bold text-gray-500">{d.regulator}</span>
                  <span className="text-[11.5px] text-gray-400">{d.period_label} · due {formatDue(d.due)}</span>
                </div>
              </div>
              <div className="flex items-center gap-2.5 shrink-0">
                <DaysLeft days={d.days_left} />
                {d.generator ? (
                  <button className="btn-secondary" style={{ padding: "5px 12px", fontSize: "12.5px" }}
                    onClick={() => setOpen({ spec: byId[d.return_id], period: d.period })}>
                    Prepare
                  </button>
                ) : (
                  <span className="text-[11.5px] text-gray-400 w-[70px] text-right">Tracked only</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Catalogue */}
      <div>
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em] m-0">Returns Iroko prepares</h2>
          <p className="text-[13px] text-gray-400 mt-[3px] mb-0">Each return is produced as a ready-to-sign letter with schedules under your bank&apos;s letterhead, after its figures are checked against the regulatory limits.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
          {[...periodic, ...event].map((r) => (
            <ReturnCard key={r.id} spec={r} onPrepare={() => setOpen({ spec: r })} />
          ))}
        </div>
      </div>

      {open && <ReturnGenerator spec={open.spec} catalog={catalog} initialPeriod={open.period} onClose={close} />}
    </div>
  );
}

function ReturnCard({ spec, onPrepare }: { spec: ReturnSpec; onPrepare: () => void }) {
  const [showBasis, setShowBasis] = useState(false);
  return (
    <div className="card flex flex-col gap-3 px-[22px] py-5">
      <div className="flex justify-between items-start gap-2">
        <span className="text-[11px] font-bold text-brand-700 bg-brand-50 px-2 py-[2px] rounded-full" title={REGULATOR_NAMES[spec.regulator]}>
          {spec.regulator}
        </span>
        <span className="text-[11.5px] text-gray-400 text-right">{spec.frequency}</span>
      </div>
      <h3 className="text-sm font-semibold text-gray-800 leading-[1.4] m-0">{spec.title}</h3>
      <p className="text-[12.5px] text-gray-500 leading-[1.55] m-0">{spec.summary}</p>
      <p className="text-[12px] text-gray-400 leading-[1.5] m-0"><span className="font-semibold text-gray-500">Due:</span> {spec.due_text}</p>
      <button className="text-left text-[12px] text-brand-600 font-semibold" onClick={() => setShowBasis((v) => !v)} aria-expanded={showBasis}>
        {showBasis ? "Hide legal basis" : "Legal basis"}
      </button>
      {showBasis && (
        <ul className="list-disc m-0 pl-4 text-[12px] text-gray-500 leading-[1.55]">
          {spec.legal_basis.map((b) => <li key={b}>{b}</li>)}
        </ul>
      )}
      {spec.generator ? (
        <button className="btn-primary mt-auto" style={{ padding: "7px 14px", fontSize: "12.5px" }} onClick={onPrepare}>
          Prepare return
        </button>
      ) : (
        <div className="mt-auto text-[12px] text-gray-400">{spec.channel} — Iroko tracks the deadline.</div>
      )}
    </div>
  );
}
