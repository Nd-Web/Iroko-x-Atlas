"use client";
/**
 * The Evidence panel: one drawer for every item in the graph. It always shows
 * the exact source words, the document and version they come from, how the
 * item was established (stated / suggested / entered / confirmed), Iroko's
 * reasoning clearly labelled, the history, and only the actions the server
 * says this user may take.
 */

import { useEffect, useMemo, useState } from "react";
import {
  useControlDetail, useControls, useDocumentDetail, useGraphActions, useGraphSearch, useLinkDetail, usePeople,
  useRequirementDetail, type HistoryItem, type LinkInfo,
} from "@/lib/compliance-graph";
import { ApplicabilityChip, CoverageChip, Empty, ErrorBox, Loading, QuoteBlock, StatusChip, formatDate } from "./ui";

export type Selection = { kind: "link" | "requirement" | "control" | "document"; id: string } | null;

interface PanelProps {
  selection: Selection;
  onClose: () => void;
  onOpen: (selection: Selection) => void;
}

export default function EvidencePanel({ selection, onClose, onOpen }: PanelProps) {
  useEffect(() => {
    if (!selection) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selection, onClose]);
  if (!selection) return null;
  const title = { link: "Relationship", requirement: "Requirement", control: "Control", document: "Document" }[selection.kind];
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label={`${title} details`}>
      <button aria-label="Close details" className="absolute inset-0 bg-black/50" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-[560px] flex-col border-l border-border-default bg-surface-card shadow-2xl">
        <header className="flex items-center justify-between gap-3 border-b border-border-default px-5 py-4">
          <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="rounded-lg px-2 py-1 text-[13px] text-gray-500 hover:bg-gray-100 hover:text-gray-900">Close</button>
        </header>
        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {selection.kind === "link" && <LinkView id={selection.id} onOpen={onOpen} />}
          {selection.kind === "requirement" && <RequirementView id={selection.id} onOpen={onOpen} />}
          {selection.kind === "control" && <ControlView id={selection.id} onOpen={onOpen} />}
          {selection.kind === "document" && <DocumentView id={selection.id} onOpen={onOpen} />}
        </div>
      </aside>
    </div>
  );
}

// ─── Small pieces ────────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 text-[13px]">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-gray-800">{children}</dd>
    </div>
  );
}

function History({ items }: { items: HistoryItem[] | undefined }) {
  if (!items?.length) return null;
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">History</h3>
      <ol className="space-y-2 border-l border-border-default pl-4">
        {items.map((h, i) => (
          <li key={i} className="text-[12px] text-gray-600">
            <span className="text-gray-400">{formatDate(h.at)} · </span>
            <span className="text-gray-800">{h.actor}</span> {h.action.replace(/_/g, " ")}
            {h.to && h.from !== h.to ? <span className="text-gray-500"> → {h.to.replace(/_/g, " ")}</span> : null}
            {h.note ? <span className="block text-gray-500">“{h.note}”</span> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

function ActionError({ error }: { error: string | null }) {
  return error ? <p role="alert" className="text-[12px] text-danger-700">{error}</p> : null;
}

function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "That did not work."); } finally { setBusy(false); }
  };
  return { busy, error, run };
}

function LinkList({ links, onOpen, empty }: { links: LinkInfo[]; onOpen: PanelProps["onOpen"]; empty?: string }) {
  if (!links.length) return empty ? <p className="text-[12px] text-gray-500">{empty}</p> : null;
  return (
    <ul className="space-y-2">
      {links.map((link) => (
        <li key={link.id}>
          <button onClick={() => onOpen({ kind: "link", id: link.id })}
            className="w-full rounded-lg border border-border-default px-3 py-2 text-left hover:border-border-strong hover:bg-gray-50">
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-[13px] text-gray-800">
                {link.from.label ?? link.from.type} <span className="text-gray-500">{link.relation_label}</span> {link.to.label ?? link.to.type}
              </span>
              <StatusChip status={link.status} />
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// ─── Relationship ────────────────────────────────────────────────────────────

const SIDE_LABEL: Record<string, string> = {
  control: "Your control", obligation: "Requirement", evidence: "Your record", document: "Instrument",
};

function LinkView({ id, onOpen }: { id: string; onOpen: PanelProps["onOpen"] }) {
  const { data, isLoading, error, refetch } = useLinkDetail(id);
  const actions = useGraphActions();
  const { busy, error: actionError, run } = useAction();
  const [note, setNote] = useState("");
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={() => refetch()} />;
  const decide = (decision: "confirm" | "reject" | "reopen", edits?: Record<string, unknown>) =>
    run(() => actions.review({ id: data.id, decision, note: note || undefined, edits }));
  const coverage = data.attributes?.coverage as string | undefined;
  return (
    <>
      <div className="space-y-2">
        <p className="text-[15px] font-medium leading-snug text-gray-900">
          {data.from.label ?? data.from.type} <span className="text-gray-500">{data.relation_label}</span> {data.to.label ?? data.to.type}
        </p>
        <StatusChip status={data.status} full />
        {data.stale_reason && <p className="text-[12px] text-warning-700">{data.stale_reason}</p>}
      </div>
      <section className="space-y-3">
        {data.anchors.map((anchor, i) => (
          <QuoteBlock key={i} anchor={anchor} label={SIDE_LABEL[anchor.kind ?? ""] ?? (anchor.side === "from" ? "Source" : "Target")} />
        ))}
        {!data.anchors.length && <p className="text-[12px] text-gray-500">No exact words are recorded for this item.</p>}
      </section>
      {data.rationale && (
        <section className="rounded-lg border border-dashed border-border-strong p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">{data.rationale_label}</p>
          <p className="mt-1 text-[13px] text-gray-700">{data.rationale}</p>
        </section>
      )}
      {(coverage || data.attributes?.period_start || data.attributes?.period_end) && (
        <dl className="space-y-1.5">
          {coverage && <Field label="Coverage">{coverage === "partial" ? "Partly addresses" : "Addresses in full"}</Field>}
          {(data.attributes?.period_start || data.attributes?.period_end) ? (
            <Field label="Period covered">{formatDate(String(data.attributes.period_start ?? ""))} – {formatDate(String(data.attributes.period_end ?? ""))}</Field>
          ) : null}
        </dl>
      )}
      <div className="flex flex-wrap gap-2">
        {data.from.type === "obligation" && <button className="btn-secondary text-[12px]" onClick={() => onOpen({ kind: "requirement", id: data.from.id })}>Open requirement</button>}
        {data.to.type === "obligation" && <button className="btn-secondary text-[12px]" onClick={() => onOpen({ kind: "requirement", id: data.to.id })}>Open requirement</button>}
        {data.from.type === "control" && <button className="btn-secondary text-[12px]" onClick={() => onOpen({ kind: "control", id: data.from.id })}>Open control</button>}
        {data.to.type === "control" && <button className="btn-secondary text-[12px]" onClick={() => onOpen({ kind: "control", id: data.to.id })}>Open control</button>}
        {data.to.type === "document" && <button className="btn-secondary text-[12px]" onClick={() => onOpen({ kind: "document", id: data.to.id })}>Open instrument</button>}
      </div>
      {data.can_review && (
        <section className="space-y-3 rounded-xl border border-border-default p-3">
          <h3 className="text-[12px] font-semibold text-gray-800">Your decision</h3>
          <textarea className="input-base min-h-[64px] text-[13px]" placeholder="Note (required to reject)" value={note}
            onChange={(e) => setNote(e.target.value)} />
          {(data.relation === "addresses" || data.relation === "evidences") && (
            <div className="flex items-center gap-2 text-[12px] text-gray-600">
              <span>Coverage:</span>
              {(["full", "partial"] as const).map((c) => (
                <button key={c} disabled={busy} onClick={() => decide("confirm", { coverage: c })}
                  className={`rounded-full border px-2.5 py-1 ${coverage === c ? "border-brand-500 text-gray-900" : "border-border-default"}`}>
                  {c === "full" ? "Addresses in full" : "Partly"}
                </button>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {data.status.review_status !== "confirmed" && <button className="btn-primary text-[12px]" disabled={busy} onClick={() => decide("confirm")}>Confirm</button>}
            {data.status.review_status !== "rejected" && <button className="btn-secondary text-[12px]" disabled={busy || note.trim().length < 5} onClick={() => decide("reject")}>Reject</button>}
            {(data.status.review_status === "confirmed" || data.status.review_status === "rejected") && (
              <button className="btn-secondary text-[12px]" disabled={busy} onClick={() => decide("reopen")}>Reopen</button>
            )}
            {data.has_proposal && <button className="btn-secondary text-[12px]" disabled={busy} onClick={() => run(() => actions.acceptProposal(data.id))}>Use Iroko&apos;s newer reading</button>}
          </div>
          <ActionError error={actionError} />
        </section>
      )}
      <History items={data.history} />
    </>
  );
}

// ─── Requirement ─────────────────────────────────────────────────────────────

function RequirementView({ id, onOpen }: { id: string; onOpen: PanelProps["onOpen"] }) {
  const { data, isLoading, error, refetch } = useRequirementDetail(id);
  const people = usePeople();
  const controls = useControls();
  const actions = useGraphActions();
  const { busy, error: actionError, run } = useAction();
  const [note, setNote] = useState("");
  const [controlId, setControlId] = useState("");
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={() => refetch()} />;
  const r = data.requirement;
  const controlLinks = data.links.filter((l) => l.relation === "addresses");
  const evidenceLinks = data.links.filter((l) => l.relation === "evidences");
  const otherLinks = data.links.filter((l) => !["addresses", "evidences"].includes(l.relation));
  const save = (body: Record<string, unknown>) => run(() => actions.setStatus(r.lineage_id, body));
  return (
    <>
      <QuoteBlock label="The requirement, in the regulator's words" anchor={{
        quote: r.quote, document_title: r.document?.title, reference: r.document?.reference, page_number: r.page_number,
        section: r.section, published_date: r.document?.published_date, effective_date: r.document?.effective_date,
        effective_basis: r.document?.effective_basis, awaiting_publication: r.document?.awaiting_publication,
      }} />
      {r.summary && (
        <p className="text-[13px] text-gray-700"><span className="text-[11px] uppercase tracking-wide text-gray-400">Iroko&apos;s summary · </span>{r.summary}</p>
      )}
      {r.unavailable ? (
        <p className="text-[13px] text-warning-700">This requirement is no longer in a current version available to you.</p>
      ) : (
        <dl className="space-y-1.5">
          <Field label="Applies to you"><ApplicabilityChip state={r.applicability.state} label={r.applicability.label} /> <span className="ml-1 text-gray-500">{r.applicability.label}</span>{r.applicability.note ? <span className="block text-gray-500">“{r.applicability.note}”</span> : null}</Field>
          <Field label="In your records"><CoverageChip state={r.coverage.state} label={r.coverage.label} /> <span className="ml-1 text-gray-500">{r.coverage.label}</span></Field>
          <Field label="Owner">{r.owner.name || r.owner.team || <span className="text-gray-500">No owner recorded in Iroko</span>}</Field>
          <Field label="Next due">{r.due.date ? formatDate(r.due.date) : <span className="text-gray-500">{r.due.description || "No date stated"}</span>}</Field>
        </dl>
      )}
      <section className="space-y-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Your controls</h3>
        <LinkList links={controlLinks} onOpen={onOpen} empty="No control linked in Iroko's records." />
      </section>
      <section className="space-y-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Your evidence</h3>
        <LinkList links={evidenceLinks} onOpen={onOpen} empty="No evidence linked directly to this requirement." />
      </section>
      {otherLinks.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Reporting and related</h3>
          <LinkList links={otherLinks} onOpen={onOpen} />
        </section>
      )}
      {data.versions.length > 1 && (
        <section className="space-y-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Earlier wording</h3>
          {data.versions.slice(0, -1).reverse().map((v) => (
            <QuoteBlock key={v.id} anchor={{ quote: v.quote, document_title: v.document?.title, page_number: v.page_number, section: v.section }} />
          ))}
        </section>
      )}
      {data.can_decide && !r.unavailable && (
        <section className="space-y-3 rounded-xl border border-border-default p-3">
          <h3 className="text-[12px] font-semibold text-gray-800">Your workspace&apos;s decisions</h3>
          <div className="flex flex-wrap gap-2">
            <button className="btn-secondary text-[12px]" disabled={busy} onClick={() => save({ applicability: "applies", note })}>It applies to us</button>
            <button className="btn-secondary text-[12px]" disabled={busy || note.trim().length < 5} onClick={() => save({ applicability: "not_applicable", note })}>Not applicable to us</button>
            {r.applicability.state.startsWith("applies_decided") || r.applicability.state === "not_applicable" ? (
              <button className="btn-secondary text-[12px]" disabled={busy} onClick={() => save({ applicability: "" })}>Clear decision</button>
            ) : null}
          </div>
          <input className="input-base text-[13px]" placeholder="Why (required for not applicable)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="text-[12px] text-gray-500">Owner
              <select className="input-base mt-1 text-[13px]" defaultValue={r.owner.user_id ?? ""} disabled={busy}
                onChange={(e) => save({ owner_user_id: e.target.value || null })}>
                <option value="">No owner</option>
                {people.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label className="text-[12px] text-gray-500">Team
              <input className="input-base mt-1 text-[13px]" defaultValue={r.owner.team ?? ""} disabled={busy}
                onBlur={(e) => e.target.value !== (r.owner.team ?? "") && save({ owner_team: e.target.value })} />
            </label>
            <label className="text-[12px] text-gray-500">Next due date
              <input type="date" className="input-base mt-1 text-[13px]" defaultValue={r.due.basis === "owner" ? r.due.date ?? "" : ""}
                disabled={busy} onChange={(e) => save({ next_due_date: e.target.value || null })} />
            </label>
            <label className="text-[12px] text-gray-500">Repeats
              <select className="input-base mt-1 text-[13px]" defaultValue="" disabled={busy} onChange={(e) => save({ recurrence: e.target.value || null })}>
                <option value="">Does not repeat</option>
                {["monthly", "quarterly", "semiannual", "annual"].map((x) => <option key={x} value={x}>{x}</option>)}
              </select>
            </label>
          </div>
          <div className="flex gap-2">
            <select className="input-base text-[13px]" value={controlId} onChange={(e) => setControlId(e.target.value)}>
              <option value="">Link one of your controls…</option>
              {controls.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <button className="btn-secondary shrink-0 text-[12px]" disabled={!controlId || busy}
              onClick={() => run(() => actions.createLink({ relation: "addresses", from_type: "control", from_id: controlId, to_type: "obligation", to_id: r.lineage_id }))}>
              Link
            </button>
          </div>
          <ActionError error={actionError} />
        </section>
      )}
      <History items={data.history} />
    </>
  );
}

// ─── Control ─────────────────────────────────────────────────────────────────

function ControlView({ id, onOpen }: { id: string; onOpen: PanelProps["onOpen"] }) {
  const { data, isLoading, error, refetch } = useControlDetail(id);
  const people = usePeople();
  const actions = useGraphActions();
  const { busy, error: actionError, run } = useAction();
  const [note, setNote] = useState("");
  const [search, setSearch] = useState("");
  const results = useGraphSearch(search);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={() => refetch()} />;
  const c = data.control;
  return (
    <>
      <div className="space-y-2">
        <p className="text-[15px] font-medium text-gray-900">{c.name}</p>
        <StatusChip status={c.review} full />
        {c.status === "retired" && <p className="text-[12px] text-warning-700">Retired: no longer in the latest policy.</p>}
      </div>
      {c.quote && <QuoteBlock label="In your policy" anchor={{ quote: c.quote, document_title: c.document?.title, page_number: c.page_number, section: c.section }} />}
      {c.summary && <p className="text-[13px] text-gray-700"><span className="text-[11px] uppercase tracking-wide text-gray-400">Summary · </span>{c.summary}</p>}
      <dl className="space-y-1.5">
        <Field label="Owner">{c.owner.name || c.owner.team || <span className="text-gray-500">No owner recorded</span>}</Field>
        <Field label="Performed by">{c.performer || <span className="text-gray-500">Not stated</span>}</Field>
        <Field label="Frequency">{c.frequency || <span className="text-gray-500">Not stated</span>}</Field>
        <Field label="Record it produces">{c.evidence_expected || <span className="text-gray-500">Not stated</span>}</Field>
        <Field label="Latest evidence">{c.latest_evidence ? formatDate(c.latest_evidence) : <span className="text-gray-500">None linked</span>}</Field>
      </dl>
      <section className="space-y-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Requirements and evidence</h3>
        <LinkList links={data.links} onOpen={onOpen} empty="Not linked to any requirement yet." />
      </section>
      {data.anchor_history.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Earlier wording</h3>
          {data.anchor_history.slice().reverse().map((h, i) => <QuoteBlock key={i} anchor={{ quote: h.quote }} />)}
        </section>
      )}
      <section className="space-y-3 rounded-xl border border-border-default p-3">
        <h3 className="text-[12px] font-semibold text-gray-800">Manage</h3>
        {data.can_review && c.review.review_status !== "confirmed" && (
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary text-[12px]" disabled={busy} onClick={() => run(() => actions.review({ kind: "control", id: c.id, decision: "confirm" }))}>Confirm control</button>
            <input className="input-base flex-1 text-[13px]" placeholder="Why reject?" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn-secondary text-[12px]" disabled={busy || note.trim().length < 5} onClick={() => run(() => actions.review({ kind: "control", id: c.id, decision: "reject", note }))}>Reject</button>
          </div>
        )}
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-[12px] text-gray-500">Owner
            <select className="input-base mt-1 text-[13px]" defaultValue={c.owner.user_id ?? ""} disabled={busy}
              onChange={(e) => run(() => actions.updateControl(c.id, { owner_user_id: e.target.value || null }))}>
              <option value="">No owner</option>
              {people.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="text-[12px] text-gray-500">Frequency
            <select className="input-base mt-1 text-[13px]" defaultValue={c.frequency ?? ""} disabled={busy}
              onChange={(e) => run(() => actions.updateControl(c.id, { frequency: e.target.value || null }))}>
              <option value="">Not stated</option>
              {["daily", "weekly", "monthly", "quarterly", "semiannual", "annual", "event", "once"].map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
          </label>
        </div>
        <div className="space-y-2">
          <input className="input-base text-[13px]" placeholder="Find a requirement this control addresses…" value={search} onChange={(e) => setSearch(e.target.value)} />
          {results.data?.requirements.slice(0, 5).map((req) => (
            <button key={req.lineage_id} disabled={busy}
              className="block w-full rounded-lg border border-border-default px-3 py-2 text-left text-[12px] text-gray-700 hover:bg-gray-50"
              onClick={() => run(() => actions.createLink({ relation: "addresses", from_type: "control", from_id: c.id, to_type: "obligation", to_id: req.lineage_id }))}>
              Link: {req.summary || req.quote.slice(0, 140)}
            </button>
          ))}
        </div>
        <button className="btn-secondary text-[12px]" disabled={busy}
          onClick={() => run(() => actions.updateControl(c.id, { status: c.status === "retired" ? "active" : "retired" }))}>
          {c.status === "retired" ? "Reactivate" : "Retire control"}
        </button>
        <ActionError error={actionError} />
      </section>
      <History items={data.history} />
    </>
  );
}

// ─── Document ────────────────────────────────────────────────────────────────

const ROLES: [string, string][] = [
  ["regulation", "Regulation or guidance"], ["policy", "Our policy"], ["procedure", "Our procedure"],
  ["evidence_record", "Evidence record"], ["other", "Other"],
];

function DocumentView({ id, onOpen }: { id: string; onOpen: PanelProps["onOpen"] }) {
  const { data, isLoading, error, refetch } = useDocumentDetail(id);
  const actions = useGraphActions();
  const { busy, error: actionError, run } = useAction();
  const [effective, setEffective] = useState("");
  const evidence = useMemo(() => (data?.facts?.evidence ?? null) as Record<string, string | null> | null, [data]);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={() => refetch()} />;
  const d = data.document;
  return (
    <>
      <div className="space-y-1">
        <p className="text-[15px] font-medium text-gray-900">{d.title}</p>
        <p className="text-[12px] text-gray-500">{[d.role_label, d.regulator, d.reference].filter(Boolean).join(" · ")}</p>
        {d.awaiting_publication && <p className="text-[12px] text-warning-700">A newer version of this document is awaiting publication.</p>}
      </div>
      <dl className="space-y-1.5">
        <Field label="Published">{d.published_date ? formatDate(d.published_date) : <span className="text-gray-500">Not recorded</span>}</Field>
        <Field label="Takes effect">
          {d.effective_date ? `${formatDate(d.effective_date)} (${d.effective_basis === "confirmed" ? "confirmed" : d.effective_basis === "stated" ? "stated in the document" : "suggested by Iroko"})` : <span className="text-gray-500">Not established</span>}
        </Field>
        {data.requirements > 0 && <Field label="Requirements">{data.requirements}</Field>}
        {evidence && <Field label="Shows">{evidence.activity}</Field>}
        {evidence && (evidence.period_start || evidence.period_end) && <Field label="Period">{formatDate(evidence.period_start)} – {formatDate(evidence.period_end)}</Field>}
      </dl>
      {data.effective_anchor?.quote && <QuoteBlock label="Effective date, in the document's words" anchor={data.effective_anchor} />}
      <section className="space-y-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">Relationships</h3>
        <LinkList links={data.links} onOpen={onOpen} empty="No relationships recorded." />
      </section>
      <section className="space-y-3 rounded-xl border border-border-default p-3">
        <h3 className="text-[12px] font-semibold text-gray-800">Document facts</h3>
        <label className="block text-[12px] text-gray-500">What is this document?
          <select className="input-base mt-1 text-[13px]" defaultValue={d.role ?? ""} disabled={busy}
            onChange={(e) => e.target.value && run(() => actions.setRole(d.id, e.target.value))}>
            <option value="" disabled>Choose…</option>
            {ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          {d.role_suggestion && <span className="mt-1 block text-gray-500">Iroko suggests: {ROLES.find(([v]) => v === d.role_suggestion)?.[1]}</span>}
        </label>
        {d.role === "regulation" && (
          <div className="flex items-end gap-2">
            <label className="flex-1 text-[12px] text-gray-500">Confirm the effective date
              <input type="date" className="input-base mt-1 text-[13px]" value={effective || d.effective_date || ""} onChange={(e) => setEffective(e.target.value)} />
            </label>
            <button className="btn-secondary text-[12px]" disabled={busy} onClick={() => run(() => actions.setEffective(d.id, effective || d.effective_date || null))}>Confirm</button>
          </div>
        )}
        <ActionError error={actionError} />
      </section>
      <History items={data.history} />
    </>
  );
}

export function NothingSelected() {
  return <Empty title="Select an item">Choose a requirement, control or relationship to see its exact source words and history.</Empty>;
}
