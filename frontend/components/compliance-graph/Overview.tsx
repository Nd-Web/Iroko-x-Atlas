"use client";
/**
 * Overview: what applies, how much of it is covered in the workspace's own
 * records, what is waiting for a decision, what changed and what is due.
 * Gaps are "not established in Iroko's records", never a verdict.
 */

import Link from "next/link";
import { useOverview } from "@/lib/compliance-graph";
import { COVERAGE_ORDER, COVERAGE_SHORT } from "@/lib/compliance-graph-view";
import type { Selection } from "./EvidencePanel";
import { CoverageChip, Empty, ErrorBox, Loading, SectionTitle, formatDate } from "./ui";

interface Props {
  onOpen: (s: Selection) => void;
  onTab: (tab: string, params?: Record<string, string>) => void;
  onProfile: () => void;
}

export default function Overview({ onOpen, onTab, onProfile }: Props) {
  const { data, isLoading, error, refetch } = useOverview();
  if (isLoading) return <Loading label="Loading overview" />;
  if (error || !data) return <ErrorBox error={error} onRetry={() => refetch()} />;
  const t = data.totals;
  const tiles: { label: string; value: number; hint: string; tab: string; params?: Record<string, string> }[] = [
    { label: "Requirements that apply to you", value: t.requirements_applying, hint: `${t.requirements_visible} in your library`, tab: "requirements", params: { applicability: "applying" } },
    { label: "Awaiting your review", value: t.awaiting_review, hint: "Suggestions and decisions", tab: "review" },
    { label: "Need re-review", value: t.needs_re_review, hint: "After a change", tab: "requirements", params: { coverage: "needs_re_review" } },
    { label: "Open changes", value: t.open_changes, hint: "Regulation or policy updates", tab: "changes" },
    { label: "Due in 30 days", value: t.due_30_days, hint: "Lagos time", tab: "requirements", params: { due_within: "30" } },
  ];
  const setupDone = data.setup.licence_categories && data.setup.policies_uploaded > 0 && data.setup.evidence_uploaded > 0;
  return (
    <div className="space-y-6">
      {!setupDone && (
        <section className="card space-y-3 p-4">
          <SectionTitle>Get your compliance graph ready</SectionTitle>
          <ol className="space-y-2 text-[13px]">
            <Step done={data.setup.licence_categories} title="Confirm your licence categories"
              detail={data.setup.licence_from_filing_profile ? "Taken from your filing profile — please confirm." : "Iroko uses them to decide which requirements are addressed to you."}
              action={<button className="btn-secondary text-[12px]" onClick={onProfile}>Set licence</button>} />
            <Step done={data.setup.policies_uploaded > 0} title="Upload your policies and procedures"
              detail="Iroko finds the controls in them and suggests which requirements each one addresses."
              action={<Link className="btn-secondary text-[12px]" href="/documents">Upload</Link>} />
            <Step done={data.setup.evidence_uploaded > 0} title="Upload evidence records"
              detail="Registers, reports, minutes and logs that show controls were carried out."
              action={<Link className="btn-secondary text-[12px]" href="/documents">Upload</Link>} />
            <Step done={data.setup.suggestions_to_review === 0} title="Review Iroko's suggestions"
              detail="Nothing counts as confirmed until someone in your team confirms it."
              action={<button className="btn-secondary text-[12px]" onClick={() => onTab("review")}>Review</button>} />
          </ol>
        </section>
      )}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {tiles.map((tile) => (
          <button key={tile.label} onClick={() => onTab(tile.tab, tile.params)}
            className="card p-4 text-left transition hover:border-border-strong">
            <p className="text-2xl font-semibold text-gray-900">{tile.value}</p>
            <p className="mt-1 text-[13px] text-gray-700">{tile.label}</p>
            <p className="text-[11px] text-gray-500">{tile.hint}</p>
          </button>
        ))}
      </section>

      <section className="card p-4">
        <SectionTitle>In your records</SectionTitle>
        {t.requirements_applying === 0 ? (
          <p className="text-[13px] text-gray-500">No requirements apply yet. {data.profile.category_codes.length ? "Your library may not contain regulations addressed to your licence." : "Set your licence categories first."}</p>
        ) : (
          <>
            <CoverageBar coverage={t.coverage} total={t.requirements_applying} />
            <div className="mt-3 flex flex-wrap gap-2">
              {COVERAGE_ORDER.filter((k) => t.coverage[k]).map((k) => (
                <button key={k} onClick={() => onTab("requirements", { coverage: k })} className="inline-flex items-center gap-1.5 text-[12px] text-gray-600 hover:text-gray-900">
                  <CoverageChip state={k} /> {t.coverage[k]}
                </button>
              ))}
            </div>
          </>
        )}
        <p className="mt-3 text-[11px] text-gray-500">{data.gap_wording}</p>
      </section>

      <div className="grid gap-6 xl:grid-cols-3">
        <section className="card p-4">
          <SectionTitle>Due soon</SectionTitle>
          {data.due.length === 0 ? <p className="text-[13px] text-gray-500">Nothing falls due in the next 30 days.</p> : (
            <ul className="space-y-2">
              {data.due.map((item, i) => (
                <li key={i}>
                  <button className="w-full text-left" disabled={!item.lineage_id}
                    onClick={() => item.lineage_id && onOpen({ kind: "requirement", id: item.lineage_id })}>
                    <p className="text-[13px] text-gray-800">{item.title}</p>
                    <p className={`text-[11px] ${item.overdue ? "text-warning-700" : "text-gray-500"}`}>
                      {item.overdue ? `Overdue since ${formatDate(item.date)}` : formatDate(item.date)} · {KIND_LABEL[item.kind] ?? item.kind}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card p-4">
          <SectionTitle action={<button className="text-[12px] text-gray-500 underline" onClick={() => onTab("changes")}>All changes</button>}>Recent changes</SectionTitle>
          {data.changes.length === 0 ? <p className="text-[13px] text-gray-500">No open changes affect your records.</p> : (
            <ul className="space-y-2">
              {data.changes.map((c) => (
                <li key={c.id} className="text-[13px] text-gray-800">
                  {c.summary}
                  {c.flagged > 0 && <span className="block text-[11px] text-warning-700">{c.flagged} confirmed link(s) need re-review</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card p-4">
          <SectionTitle>Not established in your records</SectionTitle>
          {data.gaps.length === 0 ? <p className="text-[13px] text-gray-500">Every applying requirement has a confirmed control and evidence linked.</p> : (
            <ul className="space-y-2">
              {data.gaps.map((g) => (
                <li key={g.lineage_id}>
                  <button className="w-full text-left" onClick={() => onOpen({ kind: "requirement", id: g.lineage_id })}>
                    <p className="line-clamp-2 text-[13px] text-gray-800">{g.summary || g.quote}</p>
                    <p className="text-[11px] text-gray-500">{g.document} · {COVERAGE_SHORT[g.coverage.state]}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {data.extraction.problems.length > 0 && (
        <section className="card p-4">
          <SectionTitle>Documents Iroko could not finish reading</SectionTitle>
          <ul className="space-y-1 text-[12px] text-gray-600">
            {data.extraction.problems.map((p) => (
              <li key={p.document_id}>{p.title} — {p.status === "deferred" ? "will retry automatically" : "failed"}{p.error ? `: ${p.error}` : ""}</li>
            ))}
          </ul>
        </section>
      )}
      {data.extraction.documents === 0 && t.requirements_visible === 0 && (
        <Empty title="Your compliance graph is empty">Upload regulations, policies and evidence on the Documents page, or ask the Iroko team to share the regulator library with your workspace.</Empty>
      )}
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  requirement: "Requirement", return: "Regulatory return", effective: "Takes effect", control_cycle: "Evidence expected",
};

function Step({ done, title, detail, action }: { done: boolean; title: string; detail: string; action: React.ReactNode }) {
  return (
    <li className="flex items-start justify-between gap-3">
      <div className="flex gap-3">
        <span aria-hidden="true" className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] ${done ? "border-success-500 text-success-700" : "border-border-strong text-gray-400"}`}>
          {done ? "✓" : ""}
        </span>
        <div>
          <p className={done ? "text-gray-500 line-through" : "text-gray-800"}>{title}</p>
          <p className="text-[12px] text-gray-500">{detail}</p>
        </div>
      </div>
      {!done && action}
    </li>
  );
}

const BAR_CLASS: Record<string, string> = {
  evidence_on_record: "bg-success-500", evidence_out_of_date: "bg-warning-500", needs_re_review: "bg-warning-500",
  evidence_suggested: "bg-info-500", control_confirmed_no_evidence: "bg-info-500", control_suggested: "bg-info-500",
  no_control_linked: "bg-gray-300",
};

function CoverageBar({ coverage, total }: { coverage: Record<string, number>; total: number }) {
  return (
    <div className="flex h-3 w-full overflow-hidden rounded-full bg-gray-100" role="img"
      aria-label={COVERAGE_ORDER.filter((k) => coverage[k]).map((k) => `${COVERAGE_SHORT[k]}: ${coverage[k]}`).join(", ")}>
      {COVERAGE_ORDER.filter((k) => coverage[k] && k !== "not_applicable").map((k) => (
        <span key={k} className={BAR_CLASS[k] ?? "bg-gray-300"} style={{ width: `${(coverage[k] / Math.max(1, total)) * 100}%` }} />
      ))}
    </div>
  );
}
