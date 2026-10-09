"use client";
/**
 * Review: everything this user may decide on, grouped. Nothing Iroko suggests
 * counts until a person with the right role confirms it; each item shows both
 * sides' exact words and Iroko's reasoning, labelled as reasoning.
 */

import { useState } from "react";
import { useGraphActions, useReviewQueue, type Anchor, type DocumentInfo, type LinkInfo, type StatusInfo } from "@/lib/compliance-graph";
import type { Selection } from "./EvidencePanel";
import { Empty, ErrorBox, Loading, QuoteBlock, StatusChip, formatDate } from "./ui";

const ROLE_LABEL: Record<string, string> = {
  regulation: "Regulation or guidance", policy: "Policy", procedure: "Procedure", evidence_record: "Evidence record", other: "Other",
};

export default function ReviewQueue({ onOpen }: { onOpen: (s: Selection) => void }) {
  const { data, isLoading, error, refetch } = useReviewQueue();
  const actions = useGraphActions();
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setFailure(null);
    try { await fn(); } catch (e) { setFailure(e instanceof Error ? e.message : "That did not work."); } finally { setBusy(null); }
  };
  if (isLoading) return <Loading label="Loading review queue" />;
  if (error || !data) return <ErrorBox error={error} onRetry={() => refetch()} />;
  const groups = data.groups.filter((g) => g.count > 0);
  if (!groups.length) return <Empty title="Nothing waiting for your review">New suggestions appear here as Iroko reads your documents and the regulator library changes.</Empty>;
  return (
    <div className="space-y-8">
      {failure && <p role="alert" className="rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700">{failure}</p>}
      {groups.map((group) => {
        const links = group.items as unknown as LinkInfo[];
        const bulkable = ["regulation_facts", "applicability"].includes(group.key)
          ? links.filter((l) => l.status?.basis === "stated" || l.relation === "applies_to").map((l) => l.id) : [];
        return (
          <section key={group.key} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-gray-900">{group.title} <span className="text-gray-500">({group.count})</span></h2>
              {bulkable.length > 1 && (
                <button className="btn-secondary text-[12px]" disabled={busy !== null}
                  onClick={() => act(`bulk-${group.key}`, () => actions.bulk(bulkable, "confirm"))}>
                  Confirm all {bulkable.length} stated in the source
                </button>
              )}
            </div>
            <ul className="space-y-3">
              {group.items.map((raw, i) => {
                if (["control_mappings", "evidence_links", "regulation_facts", "applicability"].includes(group.key)) {
                  const link = raw as unknown as LinkInfo;
                  return <LinkItem key={link.id} link={link} busy={busy === link.id} onOpen={onOpen}
                    onDecide={(decision, note) => act(link.id, () => actions.review({ id: link.id, decision, note }))} />;
                }
                if (group.key === "controls") {
                  const c = raw as { id: string; name: string; summary: string | null; quote: string | null; performer: string | null; frequency: string | null; status: StatusInfo; document: DocumentInfo | null };
                  return (
                    <Item key={c.id} title={c.name} status={c.status} onOpen={() => onOpen({ kind: "control", id: c.id })}
                      busy={busy === c.id}
                      onConfirm={() => act(c.id, () => actions.review({ kind: "control", id: c.id, decision: "confirm" }))}
                      onReject={(note) => act(c.id, () => actions.review({ kind: "control", id: c.id, decision: "reject", note }))}>
                      {c.quote && <QuoteBlock label="In your policy" anchor={{ quote: c.quote, document_title: c.document?.title }} />}
                      <p className="text-[12px] text-gray-500">{[c.performer, c.frequency].filter(Boolean).join(" · ")}</p>
                    </Item>
                  );
                }
                if (group.key === "document_roles") {
                  const d = raw as { document: DocumentInfo; role: string; role_basis: string; suggestion: string };
                  return (
                    <li key={`${d.document.id}-role`} className="card space-y-2 p-4">
                      <p className="text-[13px] text-gray-800">{d.document.title}</p>
                      <p className="text-[12px] text-gray-500">
                        Currently: {ROLE_LABEL[d.role] ?? d.role} ({d.role_basis === "uploader" ? "chosen at upload" : "suggested by Iroko"}).
                        {d.suggestion !== d.role && <> Iroko reads it as: <span className="text-gray-800">{ROLE_LABEL[d.suggestion]}</span>.</>}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {d.suggestion !== d.role && (
                          <button className="btn-primary text-[12px]" disabled={busy !== null}
                            onClick={() => act(d.document.id, () => actions.setRole(d.document.id, d.suggestion))}>Use {ROLE_LABEL[d.suggestion]}</button>
                        )}
                        <button className="btn-secondary text-[12px]" disabled={busy !== null}
                          onClick={() => act(d.document.id, () => actions.setRole(d.document.id, d.role))}>Keep {ROLE_LABEL[d.role]}</button>
                        <button className="btn-secondary text-[12px]" onClick={() => onOpen({ kind: "document", id: d.document.id })}>Open</button>
                      </div>
                    </li>
                  );
                }
                if (group.key === "effective_dates") {
                  const e = raw as { document: DocumentInfo; effective_date: string | null; anchor: Anchor | null };
                  return (
                    <li key={`${e.document.id}-effective`} className="card space-y-2 p-4">
                      <p className="text-[13px] text-gray-800">{e.document.title} takes effect {formatDate(e.effective_date)}?</p>
                      {e.anchor?.quote && <QuoteBlock anchor={e.anchor} label="In the document's words" />}
                      <div className="flex gap-2">
                        <button className="btn-primary text-[12px]" disabled={busy !== null}
                          onClick={() => act(e.document.id, () => actions.setEffective(e.document.id, e.effective_date))}>Confirm date</button>
                        <button className="btn-secondary text-[12px]" onClick={() => onOpen({ kind: "document", id: e.document.id })}>Correct it</button>
                      </div>
                    </li>
                  );
                }
                if (group.key === "share_new_version") {
                  const s = raw as { document: DocumentInfo; new_document: { id: string; title: string } };
                  return <ShareItem key={`${s.document.id}-share-${i}`} title={s.new_document.title} busy={busy !== null}
                    onShare={(note) => act(s.document.id, () => actions.shareNewVersion(s.document.id, note))} />;
                }
                return null;
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function Item({ title, status, children, onOpen, onConfirm, onReject, busy }: {
  title: string; status: StatusInfo; children?: React.ReactNode; onOpen: () => void;
  onConfirm: () => void; onReject: (note: string) => void; busy: boolean;
}) {
  const [note, setNote] = useState("");
  const [rejecting, setRejecting] = useState(false);
  return (
    <li className="card space-y-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-[13px] font-medium text-gray-900">{title}</p>
        <StatusChip status={status} />
      </div>
      {children}
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn-primary text-[12px]" disabled={busy} onClick={onConfirm}>Confirm</button>
        {rejecting ? (
          <>
            <input className="input-base max-w-xs text-[12px]" autoFocus placeholder="Why? (at least 5 characters)" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn-secondary text-[12px]" disabled={busy || note.trim().length < 5} onClick={() => onReject(note)}>Reject</button>
          </>
        ) : (
          <button className="btn-secondary text-[12px]" disabled={busy} onClick={() => setRejecting(true)}>Reject…</button>
        )}
        <button className="text-[12px] text-gray-500 underline" onClick={onOpen}>Details</button>
      </div>
    </li>
  );
}

function LinkItem({ link, busy, onOpen, onDecide }: {
  link: LinkInfo; busy: boolean; onOpen: (s: Selection) => void; onDecide: (d: "confirm" | "reject", note?: string) => void;
}) {
  return (
    <Item title={`${link.from.label ?? link.from.type} ${link.relation_label} ${link.to.label ?? link.to.type}`}
      status={link.status} busy={busy} onOpen={() => onOpen({ kind: "link", id: link.id })}
      onConfirm={() => onDecide("confirm")} onReject={(note) => onDecide("reject", note)}>
      {link.stale_reason && <p className="text-[12px] text-warning-700">{link.stale_reason}</p>}
      <div className="grid gap-2 lg:grid-cols-2">
        {link.anchors.slice(0, 2).map((a, i) => <QuoteBlock key={i} anchor={a} label={a.kind === "control" ? "Your control" : a.kind === "evidence" ? "Your record" : a.kind === "obligation" ? "Requirement" : "Source"} />)}
      </div>
      {link.rationale && <p className="text-[12px] text-gray-500"><span className="uppercase tracking-wide text-gray-400">{link.rationale_label} · </span>{link.rationale}</p>}
    </Item>
  );
}

function ShareItem({ title, busy, onShare }: { title: string; busy: boolean; onShare: (note: string) => void }) {
  const [note, setNote] = useState("");
  return (
    <li className="card space-y-2 p-4">
      <p className="text-[13px] text-gray-800">A newer version of “{title}” has been published but not shared with customer workspaces.</p>
      <p className="text-[12px] text-gray-500">Until you share it, customers keep seeing the earlier version, labelled as awaiting publication.</p>
      <div className="flex flex-wrap gap-2">
        <input className="input-base max-w-md text-[12px]" placeholder="Note for the audit trail (at least 10 characters)" value={note} onChange={(e) => setNote(e.target.value)} />
        <button className="btn-primary text-[12px]" disabled={busy || note.trim().length < 10} onClick={() => onShare(note)}>Share new version</button>
      </div>
    </li>
  );
}
