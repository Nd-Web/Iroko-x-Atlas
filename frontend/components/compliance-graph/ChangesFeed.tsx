"use client";
/** Changes: what a new regulation version, an amendment or a policy update means for your records. */

import { useState } from "react";
import { useGraphActions, useImpacts } from "@/lib/compliance-graph";
import type { Selection } from "./EvidencePanel";
import { Empty, ErrorBox, Loading, QuoteBlock, formatDate } from "./ui";

export default function ChangesFeed({ onOpen }: { onOpen: (s: Selection) => void }) {
  const [status, setStatus] = useState<"open" | "acknowledged">("open");
  const { data, isLoading, error, refetch } = useImpacts(status);
  const actions = useGraphActions();
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const acknowledge = async (id: string) => {
    setBusy(id);
    setFailure(null);
    try { await actions.acknowledge(id); } catch (e) { setFailure(e instanceof Error ? e.message : "Not saved."); } finally { setBusy(null); }
  };
  return (
    <div className="space-y-4">
      <div className="flex gap-2" role="tablist" aria-label="Change status">
        {(["open", "acknowledged"] as const).map((s) => (
          <button key={s} role="tab" aria-selected={status === s} onClick={() => setStatus(s)}
            className={`rounded-full border px-3 py-1 text-[12px] ${status === s ? "border-brand-500 text-gray-900" : "border-border-default text-gray-500"}`}>
            {s === "open" ? "Needs attention" : "Acknowledged"}
          </button>
        ))}
      </div>
      {failure && <p role="alert" className="text-[12px] text-danger-700">{failure}</p>}
      {isLoading ? <Loading label="Loading changes" /> : error ? <ErrorBox error={error} onRetry={() => refetch()} /> : !data?.items.length ? (
        <Empty title={status === "open" ? "No changes need your attention" : "Nothing acknowledged yet"}>
          When a regulation gets a new version or is amended, or one of your policies changes, Iroko shows here which of your confirmed links need another look.
        </Empty>
      ) : (
        <ul className="space-y-4">
          {data.items.map((impact) => (
            <li key={impact.id} className="card space-y-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-[13px] font-medium text-gray-900">{impact.summary}</p>
                  <p className="text-[11px] text-gray-500">{formatDate(impact.created_at)}{impact.flagged ? ` · ${impact.flagged} confirmed link(s) marked for re-review` : ""}</p>
                </div>
                {impact.status === "open" && (
                  <button className="btn-secondary text-[12px]" disabled={busy === impact.id} onClick={() => acknowledge(impact.id)}>Acknowledge</button>
                )}
              </div>
              {impact.changes.map((c) => (
                <div key={c.lineage_id} className="grid gap-2 lg:grid-cols-2">
                  {c.old_quote && <QuoteBlock label={c.removed ? "Removed wording" : "Earlier wording"} anchor={{ quote: c.old_quote }} />}
                  {c.new_quote && <QuoteBlock label="New wording" anchor={{ quote: c.new_quote }} />}
                </div>
              ))}
              {impact.controls.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {impact.controls.map((c) => (
                    <button key={c.id} className="rounded-full border border-border-default px-2.5 py-1 text-[12px] text-gray-700 hover:border-border-strong"
                      onClick={() => onOpen({ kind: "control", id: c.id })}>{c.name}</button>
                  ))}
                </div>
              )}
              {impact.links.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {impact.links.slice(0, 8).map((l) => (
                    <button key={l.id} className="text-[12px] text-gray-500 underline" onClick={() => onOpen({ kind: "link", id: l.id })}>
                      Open affected link
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
