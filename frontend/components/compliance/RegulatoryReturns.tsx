"use client";

/**
 * components/compliance/RegulatoryReturns.tsx
 *
 * The bank's regulatory filings: what is due, how far each one is, and a way
 * into Iroko's filing workspace for every return.
 */

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Modal from "@/components/ui/Modal";
import ProfileForm from "@/components/compliance/returns/ProfileForm";
import {
  api, defaultPeriod, filingHref, formatDate, REGULATOR_NAMES, RETURNS_CATALOG_KEY, STATUS_LABEL, useReturnsCatalog,
  type DeadlineItem, type FilingStatus, type ReturnSpec,
} from "@/lib/returns";

export function DaysLeft({ days }: { days: number }) {
  const tone = days <= 3 ? "text-danger-700 bg-danger-50" : days <= 14 ? "text-warning-700 bg-warning-50" : "text-gray-500 bg-gray-100";
  const label = days === 0 ? "Due today" : days === 1 ? "1 day left" : `${days} days left`;
  return <span className={`text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0 ${tone}`}>{label}</span>;
}

function StatusChip({ status }: { status: FilingStatus }) {
  const tone = {
    not_started: "text-gray-500 bg-gray-100",
    draft: "text-info-700 bg-info-50",
    generated: "text-warning-700 bg-warning-50",
    submitted: "text-success-700 bg-success-50",
  }[status];
  return <span className={`text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0 ${tone}`}>{status === "submitted" ? "✓ Submitted" : STATUS_LABEL[status]}</span>;
}

const ACTION: Record<FilingStatus, string> = { not_started: "Start", draft: "Continue", generated: "Finish", submitted: "View" };

export default function RegulatoryReturns() {
  const { data: catalog, isLoading, error, refetch } = useReturnsCatalog();
  const [editProfile, setEditProfile] = useState(false);
  const qc = useQueryClient();

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

  const deadlines = catalog.calendar.filter((d) => d.status !== "submitted" || d.days_left <= 7).slice(0, 8);
  const periodic = catalog.returns.filter((r) => r.period_type !== "event");
  const events = catalog.returns.filter((r) => r.period_type === "event");

  return (
    <div className="flex flex-col gap-6">
      {/* Bank details */}
      {catalog.profile_missing.length > 0 && (
        <div className="card px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3" style={{ borderColor: "var(--color-brand-500)" }}>
          <div>
            <div className="text-[14px] font-semibold text-gray-900">First, your bank&apos;s details</div>
            <p className="text-[12.5px] text-gray-500 m-0 mt-0.5">Entered once for your whole team — Iroko prints them on every return.</p>
          </div>
          <button className="btn-primary shrink-0" onClick={() => setEditProfile(true)}>Add bank details</button>
        </div>
      )}

      {/* Upcoming deadlines */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border-default flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em] m-0">Upcoming regulatory deadlines</h2>
            <p className="text-[12.5px] text-gray-400 mt-[3px] mb-0 max-w-[720px]">{catalog.holiday_note}</p>
          </div>
          {catalog.profile_missing.length === 0 && (
            <button className="text-[12.5px] text-brand-600 font-semibold" onClick={() => setEditProfile(true)}>Bank details</button>
          )}
        </div>
        <div>
          {deadlines.map((d: DeadlineItem, i) => (
            <div key={`${d.return_id}-${d.period}`} className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 px-5 py-3${i < deadlines.length - 1 ? " border-b border-border-default" : ""}`}>
              <div className="min-w-0">
                <div className="text-[13px] font-medium text-gray-800 truncate">{d.title}</div>
                <div className="flex items-center gap-1.5 mt-[2px]">
                  <span className="bg-gray-100 px-1.5 rounded text-[10.5px] font-bold text-gray-500">{d.regulator}</span>
                  <span className="text-[11.5px] text-gray-400">{d.period_label} · due {formatDate(d.due)}</span>
                </div>
              </div>
              <div className="flex items-center gap-2.5 shrink-0">
                <StatusChip status={d.status} />
                {d.status !== "submitted" && <DaysLeft days={d.days_left} />}
                {d.generator ? (
                  <Link href={filingHref(d.return_id, { period: d.period, draft: d.draft_id })}
                    className={`${d.status === "not_started" ? "btn-primary" : "btn-secondary"} no-underline`} style={{ padding: "5px 14px", fontSize: "12.5px" }}>
                    {ACTION[d.status]}
                  </Link>
                ) : (
                  <span className="text-[11.5px] text-gray-400 w-[70px] text-right">Tracked only</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Event-driven reports */}
      <div>
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em] m-0">When something happens</h2>
          <p className="text-[13px] text-gray-400 mt-[3px] mb-0">Reports with short statutory windows — start one the moment you need it.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
          {events.map((r) => <EventCard key={r.id} spec={r} />)}
        </div>
      </div>

      {/* Periodic returns */}
      <div>
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em] m-0">All returns Iroko prepares</h2>
          <p className="text-[13px] text-gray-400 mt-[3px] mb-0">Iroko starts each one from your records and earlier filings, then asks you only what it can&apos;t find.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-[14px]">
          {periodic.map((r) => <ReturnCard key={r.id} spec={r} calendar={catalog.calendar} />)}
        </div>
      </div>

      <Modal open={editProfile} onClose={() => setEditProfile(false)} title="Your bank's details" maxWidth="720px">
        <ProfileEditor fields={catalog.profile_fields} licenceCategories={catalog.licence_categories}
          onSaved={(missing) => { qc.invalidateQueries({ queryKey: RETURNS_CATALOG_KEY }); if (!missing.length) setEditProfile(false); }} />
      </Modal>
    </div>
  );
}

/** Loads the saved profile before showing the form, so edits start from it. */
function ProfileEditor({ fields, licenceCategories, onSaved }: {
  fields: Parameters<typeof ProfileForm>[0]["fields"]; licenceCategories: Record<string, string>; onSaved: (missing: string[]) => void;
}) {
  const { data } = useQuery({
    queryKey: ["returns", "profile"],
    queryFn: async () => {
      const res = await fetch("/api/returns/profile");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<{ profile: Record<string, unknown> }>;
    },
  });
  if (!data) return <div className="h-40 animate-pulse rounded-lg bg-gray-100" />;
  return <ProfileForm fields={fields} licenceCategories={licenceCategories} initial={data.profile} onSaved={onSaved} />;
}

function EventCard({ spec }: { spec: ReturnSpec }) {
  const { data } = useQuery({ queryKey: ["returns", "events", spec.id], queryFn: () => api.events(spec.id), staleTime: 1000 * 60 });
  const recent = data?.drafts.slice(0, 3) ?? [];
  return (
    <div className="card flex flex-col gap-3 px-[22px] py-5">
      <div className="flex justify-between items-start gap-2">
        <span className="text-[11px] font-bold text-brand-700 bg-brand-50 px-2 py-[2px] rounded-full" title={REGULATOR_NAMES[spec.regulator]}>{spec.regulator}</span>
        <span className="text-[11.5px] text-gray-400 text-right">{spec.id === "nfiu-str" ? "Within 24 hours" : "Within 7 days"}</span>
      </div>
      <h3 className="text-sm font-semibold text-gray-800 leading-[1.4] m-0">{spec.title}</h3>
      <p className="text-[12.5px] text-gray-500 leading-[1.55] m-0">{spec.summary}</p>
      {recent.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Recent</div>
          {recent.map((d) => (
            <Link key={d.id} href={filingHref(spec.id, { draft: d.id })} className="flex items-center justify-between gap-2 text-[12.5px] no-underline text-gray-600 hover:text-gray-900">
              <span className="truncate">{d.subject || "Draft"} · {formatDate(d.created_at)}</span>
              <StatusChip status={d.status} />
            </Link>
          ))}
        </div>
      )}
      <Link href={`/compliance/returns/${spec.id}`} className="btn-primary mt-auto no-underline text-center" style={{ padding: "7px 14px", fontSize: "12.5px" }}>
        {spec.id === "nfiu-str" ? "Report a suspicious transaction" : "Prepare a CTR batch"}
      </Link>
    </div>
  );
}

function ReturnCard({ spec, calendar }: { spec: ReturnSpec; calendar: DeadlineItem[] }) {
  const [showBasis, setShowBasis] = useState(false);
  const next = calendar.find((d) => d.return_id === spec.id && d.status !== "submitted");
  const period = next?.period ?? defaultPeriod(spec.period_type);
  return (
    <div className="card flex flex-col gap-3 px-[22px] py-5">
      <div className="flex justify-between items-start gap-2">
        <span className="text-[11px] font-bold text-brand-700 bg-brand-50 px-2 py-[2px] rounded-full" title={REGULATOR_NAMES[spec.regulator]}>{spec.regulator}</span>
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
        <Link href={filingHref(spec.id, { period, draft: next?.draft_id })} className="btn-primary mt-auto no-underline text-center" style={{ padding: "7px 14px", fontSize: "12.5px" }}>
          {next && next.status !== "not_started" ? `Continue — ${next.period_label}` : next ? `Prepare — ${next.period_label}` : "Prepare return"}
        </Link>
      ) : (
        <div className="mt-auto text-[12px] text-gray-400">{spec.channel} — Iroko tracks the deadline.</div>
      )}
    </div>
  );
}
