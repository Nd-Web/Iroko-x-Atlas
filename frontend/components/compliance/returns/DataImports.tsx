"use client";

/**
 * Drop-in imports for core banking exports (trial balance, loan book, cash
 * transactions) and the review Iroko asks for afterwards: the GL → MMFBR
 * mapping, inferred borrower types and insiders, or a column it couldn't find.
 */

import { useRef, useState } from "react";
import { api, formatNaira, MMFBR_LINES, type DatasetState, type DraftState, type ReviewLoan } from "@/lib/returns";

type Run = (fn: () => Promise<DraftState>, success?: string) => Promise<void>;

const COMPACT = { padding: "6px 10px", fontSize: "12.5px" };

const HOW_LABEL: Record<string, string> = {
  "Accounting rule": "mapped by accounting rules",
  "Your mapping from a previous month": "from your earlier months",
  "Iroko AI — please confirm": "suggested by Iroko AI",
  "Confirmed by you": "confirmed by you",
  "Set by you": "set by you",
  "Not mapped — choose a line": "need a line",
};

const COLUMN_CHOICES: Record<string, { key: string; label: string }[]> = {
  trial_balance: [
    { key: "code", label: "GL code" }, { key: "name", label: "Account name" },
    { key: "debit", label: "Debit" }, { key: "credit", label: "Credit" }, { key: "balance", label: "Balance (if no debit/credit)" },
  ],
  loan_book: [
    { key: "borrower_name", label: "Borrower name" }, { key: "borrower_id", label: "Customer ID" },
    { key: "outstanding", label: "Outstanding balance" }, { key: "dpd", label: "Days past due" },
  ],
  transactions: [
    { key: "date", label: "Transaction date" }, { key: "customer_name", label: "Customer name" }, { key: "amount", label: "Amount" },
  ],
};

export default function DataImports({ state, run, busy }: { state: DraftState; run: Run; busy: boolean }) {
  return (
    <div className="flex flex-col gap-4">
      {state.datasets.map((ds) => (
        <DatasetCard key={ds.kind} draftId={state.draft.id} ds={ds} run={run} busy={busy} />
      ))}
    </div>
  );
}

function StatusPill({ status }: { status: DatasetState["status"] }) {
  const map = {
    missing: ["Waiting for file", "text-gray-500 bg-gray-100"],
    needs_columns: ["Needs a column", "text-warning-700 bg-warning-50"],
    needs_review: ["Check Iroko's work", "text-warning-700 bg-warning-50"],
    ready: ["Ready", "text-success-700 bg-success-50"],
  } as const;
  const [label, cls] = map[status];
  return <span className={`text-[11px] font-semibold px-2 py-[2px] rounded-full ${cls}`}>{label}</span>;
}

function DatasetCard({ draftId, ds, run, busy }: { draftId: string; ds: DatasetState; run: Run; busy: boolean }) {
  const [replacing, setReplacing] = useState(false);
  const showDrop = ds.status === "missing" || replacing;
  return (
    <div className="card px-5 py-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[14px] font-semibold text-gray-900">{ds.label}</div>
          <div className="text-[12.5px] text-gray-500 mt-0.5">{ds.file_name ? ds.file_name : ds.ask}</div>
        </div>
        <StatusPill status={ds.status} />
      </div>

      {showDrop && (
        <DropZone help={ds.help} disabled={busy}
          onFile={(f) => run(() => api.importFile(draftId, ds.kind, f), `${ds.label} read`).then(() => setReplacing(false))} />
      )}

      {!showDrop && ds.notes && ds.notes.length > 0 && (
        <ul className="list-disc m-0 pl-5 text-[12.5px] text-gray-500 leading-[1.6]">{ds.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
      )}

      {!showDrop && ds.status === "needs_columns" && <ColumnPicker draftId={draftId} ds={ds} run={run} busy={busy} />}
      {!showDrop && ds.kind === "trial_balance" && ds.status !== "needs_columns" && <MappingReview draftId={draftId} ds={ds} run={run} busy={busy} />}
      {!showDrop && ds.kind === "loan_book" && ds.status !== "needs_columns" && <LoanReview draftId={draftId} ds={ds} run={run} busy={busy} />}

      {!showDrop && (
        <button className="text-[12px] text-brand-600 font-semibold self-start" onClick={() => setReplacing(true)}>Replace file</button>
      )}
    </div>
  );
}

function DropZone({ help, onFile, disabled }: { help: string; onFile: (f: File) => void; disabled: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => !disabled && input.current?.click()}
      onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !disabled) input.current?.click(); }}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f && !disabled) onFile(f); }}
      className={`rounded-xl border-2 border-dashed px-5 py-6 text-center cursor-pointer transition-colors ${over ? "border-brand-500 bg-brand-50" : "border-border-default hover:border-brand-500/60"} ${disabled ? "opacity-60 cursor-wait" : ""}`}
    >
      <div className="text-[13.5px] font-semibold text-gray-800">{disabled ? "Reading…" : "Drop the file here, or click to choose"}</div>
      <div className="text-[12px] text-gray-400 mt-1 max-w-[460px] mx-auto">{help}</div>
      <input ref={input} type="file" accept=".xlsx,.xlsm,.csv,.txt" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </div>
  );
}

function ColumnPicker({ draftId, ds, run, busy }: { draftId: string; ds: DatasetState; run: Run; busy: boolean }) {
  const [picks, setPicks] = useState<Record<string, number>>(ds.columns ?? {});
  const headers = ds.headers ?? [];
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[13px] text-gray-700 m-0">
        Iroko couldn&apos;t find the <strong>{(ds.needs_columns ?? []).join(" and ")}</strong> column. Which column is it?
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        {(COLUMN_CHOICES[ds.kind] ?? []).map((c) => (
          <label key={c.key} className="block">
            <span className="label-base text-[12.5px]">{c.label}</span>
            <select className="input-base" value={picks[c.key] ?? ""} onChange={(e) => setPicks((p) => ({ ...p, [c.key]: Number(e.target.value) }))}>
              <option value="">—</option>
              {headers.map((h, i) => <option key={i} value={i}>{h || `Column ${i + 1}`}</option>)}
            </select>
          </label>
        ))}
      </div>
      <button className="btn-primary self-start" disabled={busy} onClick={() => run(() => api.columns(draftId, ds.kind, picks), "Columns updated")}>
        Use these columns
      </button>
    </div>
  );
}

function MappingReview({ draftId, ds, run, busy }: { draftId: string; ds: DatasetState; run: Run; busy: boolean }) {
  const [showAll, setShowAll] = useState(false);
  const accounts = ds.accounts ?? [];
  const attention = accounts.filter((a) => !a.line || a.how.startsWith("Iroko AI"));
  const shown = showAll ? accounts : attention;
  const byHow = accounts.reduce<Record<string, number>>((m, a) => {
    const label = HOW_LABEL[a.how] ?? a.how.toLowerCase();
    return { ...m, [label]: (m[label] ?? 0) + 1 };
  }, {});
  const setLine = (code: string, line: string) => run(() => api.review(draftId, "trial_balance", { lines: { [code]: line } }, false));

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[12.5px] text-gray-500">
        {accounts.length} accounts — {Object.entries(byHow).map(([how, n]) => `${n} ${how}`).join(" · ")}
      </div>
      {ds.status === "needs_review" && (
        <p className="text-[13px] text-gray-700 m-0">
          {attention.length
            ? <>Check the <strong>{attention.length}</strong> account{attention.length > 1 ? "s" : ""} below, then confirm. Iroko remembers your mapping for next month.</>
            : "Every account was mapped from your past choices or accounting rules. Confirm to continue."}
        </p>
      )}
      {shown.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border-default">
          <table className="w-full text-[12.5px] min-w-[620px]">
            <thead>
              <tr className="text-left text-gray-400 border-b border-border-default">
                <th className="font-semibold px-3 py-2">GL</th>
                <th className="font-semibold px-3 py-2">Account</th>
                <th className="font-semibold px-3 py-2 text-right">Balance</th>
                <th className="font-semibold px-3 py-2">MMFBR line</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((a) => (
                <tr key={a.code} className="border-b border-border-default last:border-0">
                  <td className="px-3 py-1.5 font-mono text-gray-500">{a.code}</td>
                  <td className="px-3 py-1.5 text-gray-700">
                    {a.name}
                    <div className={`text-[11px] ${a.line ? "text-gray-400" : "text-danger-700"}`}>{a.how}</div>
                  </td>
                  <td className="px-3 py-1.5 text-right text-gray-700 whitespace-nowrap">
                    {formatNaira(Math.abs(a.net))} {a.net > 0 ? "Dr" : a.net < 0 ? "Cr" : ""}
                  </td>
                  <td className="px-3 py-1.5">
                    <select className="input-base" style={COMPACT} value={a.line ?? ""} disabled={busy}
                      onChange={(e) => setLine(a.code, e.target.value)}>
                      <option value="">Choose a line…</option>
                      {MMFBR_LINES.map((l) => <option key={l.code} value={l.code}>{l.code === "NONE" ? l.label : `${l.code} · ${l.label}`}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {ds.status === "needs_review" && (
          <button className="btn-primary" disabled={busy || (ds.unmapped ?? 0) > 0}
            title={(ds.unmapped ?? 0) > 0 ? "Choose a line for every unmapped account first" : undefined}
            onClick={() => run(() => api.review(draftId, "trial_balance", {}, true), "Mapping confirmed — Iroko will reuse it next month")}>
            Confirm mapping
          </button>
        )}
        <button className="text-[12px] text-brand-600 font-semibold" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Show only accounts that need you" : `Show all ${accounts.length} accounts`}
        </button>
      </div>
    </div>
  );
}

const BORROWER_TYPES = ["Individual", "Group", "Cooperative", "Corporate"];

function LoanReview({ draftId, ds, run, busy }: { draftId: string; ds: DatasetState; run: Run; busy: boolean }) {
  const loans: ReviewLoan[] = ds.review ?? [];
  const change = (row: number, patch: Partial<ReviewLoan>) =>
    run(() => api.review(draftId, "loan_book", { loans: { [row]: patch } }, false));
  if (ds.status === "ready") {
    return <div className="text-[12.5px] text-gray-500">{ds.count} loans · {formatNaira(ds.total ?? 0)}</div>;
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[13px] text-gray-700 m-0">
        Here are the largest exposures and every borrower Iroko classed as a group, cooperative, company or insider. Correct anything wrong, then confirm.
      </p>
      <div className="overflow-x-auto rounded-lg border border-border-default max-h-[360px] overflow-y-auto">
        <table className="w-full text-[12.5px] min-w-[620px]">
          <thead className="sticky top-0 bg-surface-card">
            <tr className="text-left text-gray-400 border-b border-border-default">
              <th className="font-semibold px-3 py-2">Borrower</th>
              <th className="font-semibold px-3 py-2 text-right">Outstanding</th>
              <th className="font-semibold px-3 py-2 text-right">DPD</th>
              <th className="font-semibold px-3 py-2">Type</th>
              <th className="font-semibold px-3 py-2">Insider</th>
            </tr>
          </thead>
          <tbody>
            {loans.map((l) => (
              <tr key={l.row} className="border-b border-border-default last:border-0">
                <td className="px-3 py-1.5 text-gray-700">{l.borrower_name}{l.insider_relationship && <div className="text-[11px] text-gray-400">{l.insider_relationship}</div>}</td>
                <td className="px-3 py-1.5 text-right whitespace-nowrap">{formatNaira(l.outstanding)}</td>
                <td className="px-3 py-1.5 text-right">{l.days_past_due}</td>
                <td className="px-3 py-1.5">
                  <select className="input-base" style={COMPACT} value={l.borrower_type} disabled={busy}
                    onChange={(e) => change(l.row, { borrower_type: e.target.value })}>
                    {BORROWER_TYPES.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </td>
                <td className="px-3 py-1.5">
                  <input type="checkbox" checked={l.insider} disabled={busy} aria-label={`${l.borrower_name} is an insider`}
                    onChange={(e) => change(l.row, { insider: e.target.checked })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="btn-primary self-start" disabled={busy}
        onClick={() => run(() => api.review(draftId, "loan_book", {}, true), "Loan book confirmed")}>
        Looks right
      </button>
    </div>
  );
}
