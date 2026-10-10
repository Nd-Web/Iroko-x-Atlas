"use client";
/**
 * Shared pieces of the compliance graph UI: chips, the quote block every
 * relationship shows its evidence in, and loading/empty/error states.
 */

import type { ReactNode } from "react";
import type { Anchor, StatusInfo } from "@/lib/compliance-graph";
import {
  APPLICABILITY_SHORT, COVERAGE_SHORT, TONE_CLASS, applicabilityTone, coverageTone, statusShortLabel, statusTone,
  type Tone,
} from "@/lib/compliance-graph-view";

export function Chip({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${TONE_CLASS[tone]}`}>
      {children}
    </span>
  );
}

export function StatusChip({ status, full = false }: { status: StatusInfo | null | undefined; full?: boolean }) {
  if (!status) return null;
  return <Chip tone={statusTone(status)} title={status.label}>{full ? status.label : statusShortLabel(status)}</Chip>;
}

export function CoverageChip({ state, label }: { state: string; label?: string }) {
  return <Chip tone={coverageTone(state)} title={label}>{COVERAGE_SHORT[state] ?? state}</Chip>;
}

export function ApplicabilityChip({ state, label }: { state: string; label?: string }) {
  return <Chip tone={applicabilityTone(state)} title={label}>{APPLICABILITY_SHORT[state] ?? state}</Chip>;
}

export function QuoteBlock({ anchor, label }: { anchor: Anchor; label?: string }) {
  const meta = [
    anchor.document_title,
    anchor.reference,
    anchor.page_number ? `page ${anchor.page_number}` : null,
    anchor.section,
  ].filter(Boolean).join(" · ");
  const dates = [
    anchor.published_date ? `Published ${anchor.published_date}` : null,
    // A date Iroko inferred ("takes effect immediately" = the letter's date) never reads as a stated one.
    anchor.effective_date ? `Effective ${anchor.effective_date}${anchor.effective_basis === "suggested" ? " (suggested by Iroko)"
      : anchor.effective_basis === "confirmed" ? " (confirmed)" : ""}` : null,
  ].filter(Boolean).join(" · ");
  return (
    <figure className="rounded-lg border border-border-default bg-surface-page/60 p-3">
      {label && <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-400">{label}</p>}
      <blockquote className="text-[13px] leading-relaxed text-gray-800">
        {anchor.quote ? `“${anchor.quote}”` : <span className="text-gray-400">No exact words recorded</span>}
      </blockquote>
      {(meta || dates) && (
        <figcaption className="mt-2 space-y-0.5 text-[11px] text-gray-500">
          {meta && <p>{meta}</p>}
          {dates && <p>{dates}</p>}
          {anchor.awaiting_publication && <p className="text-warning-700">A newer version of this document is awaiting publication.</p>}
        </figcaption>
      )}
    </figure>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-label={label}>
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-14 animate-pulse rounded-xl border border-border-default bg-gray-50" />
      ))}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="flex items-start justify-between gap-3 rounded-xl border border-danger-200 bg-danger-50 px-4 py-3 text-sm text-danger-700">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="shrink-0 underline underline-offset-2">Try again</button>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-border-strong px-6 py-10 text-center">
      <p className="text-sm font-medium text-gray-800">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-xl text-[13px] text-gray-500">{children}</div>}
    </div>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="text-sm font-semibold text-gray-900">{children}</h2>
      {action}
    </div>
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
