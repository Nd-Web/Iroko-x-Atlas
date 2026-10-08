"use client";

/**
 * components/compliance/returns/FilingWorkspace.tsx
 *
 * One regulatory return, prepared by Iroko with the compliance officer:
 *   1. Iroko asks only what it could not work out — one question at a time
 *   2. drop the core banking exports; check how Iroko read them
 *   3. confirm what Iroko filled in (each value shows where it came from)
 *   4. review the check, add remediation for any exception
 *   5. generate, submit to the regulator, record the reference
 * Every change is saved as it happens, so the officer can stop and resume.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";
import DataImports from "@/components/compliance/returns/DataImports";
import FieldInput, { emptyRow } from "@/components/compliance/returns/FieldInput";
import ProfileForm from "@/components/compliance/returns/ProfileForm";
import {
  api, filingHref, formatDate, formatValue, REGULATOR_NAMES, STATUS_LABEL, todayIso, useDraft, useDraftCache,
  useReturnsCatalog, type DraftState, type FilledItem, type Question, type ReturnField, type ReturnSpec,
} from "@/lib/returns";

interface Props { returnId: string; period?: string; draftId?: string }

export default function FilingWorkspace({ returnId, period, draftId }: Props) {
  const router = useRouter();
  const { data: catalog } = useReturnsCatalog();
  const spec = catalog?.returns.find((r) => r.id === returnId);
  const [openedId, setOpenedId] = useState<string | null>(draftId ?? null);
  const [openError, setOpenError] = useState<string | null>(null);
  const cache = useDraftCache();
  const opening = useRef(false);

  // Open (or resume) the draft once, then keep its id in the URL so a refresh resumes it.
  useEffect(() => {
    if (draftId || opening.current) return;
    opening.current = true;
    api.open(returnId, period)
      .then((s) => {
        cache.put(s);
        setOpenedId(s.draft.id);
        router.replace(filingHref(returnId, { draft: s.draft.id }), { scroll: false });
      })
      .catch((e: Error) => setOpenError(e.message));
  }, [draftId, returnId, period, router, cache]);

  const { data: state, error } = useDraft(openedId);
  const title = spec?.short_title ?? "Regulatory return";

  return (
    <AppShell title={title} subtitle={spec ? `${REGULATOR_NAMES[spec.regulator]} · ${spec.frequency}` : "Compliance"}>
      <Link href="/compliance/reports" className="text-[12.5px] text-brand-600 font-semibold no-underline self-start">← All returns</Link>
      {(openError || error) && (
        <div className="card px-5 py-4 text-[13px] text-danger-700">{openError ?? (error as Error).message}</div>
      )}
      {!state || !spec || !catalog ? (
        !(openError || error) && <div className="card h-56 animate-pulse" aria-busy="true" aria-label="Preparing the return" />
      ) : (
        <Workspace spec={spec} state={state} profileFields={catalog.profile_fields} licenceCategories={catalog.licence_categories} />
      )}
    </AppShell>
  );
}

function Workspace({ spec, state, profileFields, licenceCategories }: {
  spec: ReturnSpec; state: DraftState; profileFields: ReturnField[]; licenceCategories: Record<string, string>;
}) {
  const cache = useDraftCache();
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<DraftState>, success?: string) => {
    setBusy(true);
    try {
      const next = await fn();
      cache.put(next);
      if (success) toast.success(success);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [cache]);
  const id = state.draft.id;
  const pct = state.progress.total ? Math.round((state.progress.done / state.progress.total) * 100) : 0;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-6 items-start">
      <div className="flex flex-col gap-6 min-w-0">
        {/* Header */}
        <div className="card px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[11px] font-bold text-brand-700 bg-brand-50 px-2 py-[2px] rounded-full">{spec.regulator}</span>
                <span className="text-[12px] text-gray-400">{state.draft.period_label}</span>
              </div>
              <h2 className="text-[16px] font-semibold text-gray-900 m-0 leading-snug">{spec.title}</h2>
              <p className="text-[12.5px] text-gray-500 mt-1 mb-0">{spec.due_text}</p>
            </div>
            <div className="text-right shrink-0">
              <div className="text-[12px] font-semibold text-gray-700">{STATUS_LABEL[state.draft.status]}</div>
              {state.draft.due && (
                <div className={`text-[12px] ${(state.draft.days_left ?? 99) <= 3 ? "text-danger-700" : "text-gray-400"}`}>
                  Due {formatDate(state.draft.due)}{state.draft.days_left !== null && state.draft.days_left >= 0 ? ` · ${state.draft.days_left} day${state.draft.days_left === 1 ? "" : "s"} left` : state.draft.days_left !== null ? " · overdue" : ""}
                </div>
              )}
            </div>
          </div>
          <div className="mt-4">
            <div className="flex justify-between text-[12px] text-gray-500 mb-1.5">
              <span>Iroko has prepared {state.progress.done} of {state.progress.total}</span>
              <span>{pct}%</span>
            </div>
            <div className="h-[6px] bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-brand-500 transition-[width] duration-500" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>

        {state.profile_missing.length > 0 && (
          <Section title="Your bank's details" subtitle="Needed once for every return's letterhead.">
            <div className="card px-5 py-4">
              <ProfileForm fields={profileFields} licenceCategories={licenceCategories} initial={state.profile}
                onSaved={() => run(() => api.patch(id, {}))} />
            </div>
          </Section>
        )}

        {state.questions.length > 0 && (
          <Section title="Iroko needs you" subtitle={`${state.questions.length} question${state.questions.length > 1 ? "s" : ""} Iroko couldn't answer from your records.`}>
            <QuestionFlow state={state} run={run} busy={busy} />
          </Section>
        )}

        {state.datasets.length > 0 && (
          <Section title="Your data" subtitle="Drop the exports exactly as your core banking system produces them.">
            <DataImports state={state} run={run} busy={busy} />
          </Section>
        )}

        {state.items.length > 0 && <FilledSection state={state} run={run} busy={busy} />}

        {state.check && <CheckSection state={state} run={run} busy={busy} />}

        {state.optional.length > 0 && <OptionalSection state={state} run={run} busy={busy} />}
      </div>

      <ReadyPanel spec={spec} state={state} run={run} busy={busy} />
    </div>
  );
}

function Section({ title, subtitle, children, aside }: { title: string; subtitle?: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-semibold text-gray-900 m-0 tracking-[-0.01em]">{title}</h3>
          {subtitle && <p className="text-[12.5px] text-gray-400 m-0 mt-0.5">{subtitle}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

// ─── Questions ───────────────────────────────────────────────────────────────

type Run = (fn: () => Promise<DraftState>, success?: string) => Promise<void>;

function initialValue(q: Question): unknown {
  if (q.type === "table") return [emptyRow(q.columns)];
  if (q.type === "multiselect") return [];
  if (q.type === "bool") return false;
  return "";
}

function hasValue(q: Question, v: unknown): boolean {
  if (q.type === "bool") return true;
  if (q.type === "table") return Array.isArray(v) && v.some((r) => Object.values(r as object).some((x) => x !== "" && x !== false && x !== null));
  if (q.type === "multiselect") return Array.isArray(v) && v.length > 0;
  return String(v ?? "").trim() !== "";
}

function QuestionFlow({ state, run, busy }: { state: DraftState; run: Run; busy: boolean }) {
  const q = state.questions[0];
  const [values, setValues] = useState<Record<string, unknown>>({});
  const value = q.key in values ? values[q.key] : initialValue(q);
  const save = (v: unknown) => run(() => api.patch(state.draft.id, { answers: { [q.key]: v } }));
  const [searched, setSearched] = useState(false);
  const next = state.questions.slice(1, 4);
  const field: ReturnField = { key: q.key, label: q.label, type: q.type, required: q.required, options: q.options, help: q.help, columns: q.columns };

  return (
    <div className="flex flex-col gap-3">
      {state.can_search_documents && !searched && (
        <div className="card px-5 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <p className="text-[13px] text-gray-600 m-0">Iroko can look through your policies, minutes and reports for some of these answers first.</p>
          <button className="btn-secondary shrink-0" disabled={busy}
            onClick={async () => {
              setSearched(true);
              await run(async () => {
                const s = await api.find(state.draft.id);
                toast[s.found ? "success" : "info"](s.found ? `Found ${s.found} answer${s.found > 1 ? "s" : ""} in your documents — please confirm below` : "Nothing definite in your documents — Iroko will ask you instead");
                return s;
              });
            }}>
            {busy ? "Searching…" : "Search my documents"}
          </button>
        </div>
      )}
      <div className="card px-5 py-5 flex flex-col gap-4" style={{ borderColor: "var(--color-brand-500)" }}>
        <div className="text-[11.5px] font-semibold uppercase tracking-wide text-brand-600">
          Question 1 of {state.questions.length}
        </div>
        <div className="text-[16px] font-semibold text-gray-900 leading-snug">{q.ask}</div>
        {q.quick.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {q.quick.map((choice) => (
              <button key={choice.label} className="btn-secondary" disabled={busy} onClick={() => save(choice.value)}>
                {choice.label}
              </button>
            ))}
          </div>
        )}
        {!(q.type === "bool" && q.quick.length > 0) && (
          <form onSubmit={(e) => { e.preventDefault(); if (hasValue(q, value)) save(value); }} className="flex flex-col gap-3">
            {q.quick.length > 0 && <div className="text-[12px] text-gray-400">or enter it:</div>}
            <FieldInput field={field} hideLabel={q.type !== "bool"} autoFocus value={value}
              onChange={(v) => setValues((m) => ({ ...m, [q.key]: v }))} />
            <button type="submit" className="btn-primary self-start" disabled={busy || !hasValue(q, value)}>
              {busy ? "Saving…" : "Save and continue"}
            </button>
          </form>
        )}
      </div>
      {next.length > 0 && (
        <div className="text-[12px] text-gray-400 px-1">
          Then: {next.map((n) => n.label).join(" · ")}{state.questions.length > 4 ? " · …" : ""}
        </div>
      )}
    </div>
  );
}

// ─── What Iroko filled ───────────────────────────────────────────────────────

const SOURCE_STYLE: Record<string, string> = {
  document: "text-info-700 bg-info-50",
  memory: "text-brand-700 bg-brand-50",
  carried: "text-brand-700 bg-brand-50",
  derived: "text-brand-700 bg-brand-50",
  profile: "text-brand-700 bg-brand-50",
  user: "text-gray-500 bg-gray-100",
  import: "text-gray-500 bg-gray-100",
};

function FilledSection({ state, run, busy }: { state: DraftState; run: Run; busy: boolean }) {
  const pending = state.unconfirmed.length;
  return (
    <Section
      title="What Iroko filled in"
      subtitle={pending ? `Check ${pending} answer${pending > 1 ? "s" : ""} Iroko took from your records.` : "Everything here is confirmed."}
      aside={pending > 1 ? (
        <button className="btn-secondary shrink-0" style={{ padding: "6px 12px", fontSize: "12.5px" }} disabled={busy}
          onClick={() => run(() => api.patch(state.draft.id, { confirm: state.unconfirmed }), "All confirmed")}>
          All look right
        </button>
      ) : undefined}
    >
      <div className="card overflow-hidden">
        {state.items.map((item, i) => (
          <FilledRow key={item.key} item={item} draftId={state.draft.id} run={run} busy={busy} last={i === state.items.length - 1} />
        ))}
      </div>
    </Section>
  );
}

function FilledRow({ item, draftId, run, busy, last }: { item: FilledItem; draftId: string; run: Run; busy: boolean; last: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<unknown>(item.value);
  const field: ReturnField = { key: item.key, label: item.label, type: item.type, required: false, options: item.options, help: "", columns: item.columns };
  return (
    <div className={`px-5 py-3.5 flex flex-col gap-2${last ? "" : " border-b border-border-default"}`}>
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[12px] text-gray-400">{item.label}</div>
          {!editing && <div className="text-[13.5px] text-gray-800 font-medium break-words">{formatValue(item.type, item.value, item.columns)}</div>}
          <div className="flex flex-wrap items-center gap-1.5 mt-1">
            <span className={`text-[10.5px] font-semibold px-1.5 py-[1px] rounded ${SOURCE_STYLE[item.source.kind] ?? SOURCE_STYLE.user}`}>{item.source.label}</span>
            {item.source.confirmed && item.source.kind !== "user" && <span className="text-[10.5px] text-success-700">✓ Confirmed</span>}
          </div>
          {item.source.quote && (
            <blockquote className="m-0 mt-1.5 pl-3 border-l-2 border-border-default text-[12px] text-gray-500 italic">“{item.source.quote}”</blockquote>
          )}
        </div>
        {!editing && (
          <div className="flex items-center gap-2 shrink-0">
            {!item.source.confirmed && (
              <button className="btn-primary" style={{ padding: "5px 12px", fontSize: "12.5px" }} disabled={busy}
                onClick={() => run(() => api.patch(draftId, { confirm: [item.key] }))}>
                Looks right
              </button>
            )}
            <button className="btn-secondary" style={{ padding: "5px 12px", fontSize: "12.5px" }} onClick={() => { setDraft(item.value); setEditing(true); }}>
              Change
            </button>
          </div>
        )}
      </div>
      {editing && (
        <form className="flex flex-col gap-2.5" onSubmit={(e) => {
          e.preventDefault();
          run(() => api.patch(draftId, { answers: { [item.key]: draft } })).then(() => setEditing(false));
        }}>
          <FieldInput field={field} hideLabel={item.type !== "bool"} value={draft} onChange={setDraft} autoFocus />
          <div className="flex gap-2">
            <button type="submit" className="btn-primary" style={{ padding: "6px 14px", fontSize: "12.5px" }} disabled={busy}>Save</button>
            <button type="button" className="btn-secondary" style={{ padding: "6px 14px", fontSize: "12.5px" }} onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}

function OptionalSection({ state, run, busy }: { state: DraftState; run: Run; busy: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <Section title="Optional details" subtitle="Add these only if they apply."
      aside={<button className="text-[12.5px] text-brand-600 font-semibold" onClick={() => setOpen((v) => !v)}>{open ? "Hide" : `Show ${state.optional.length}`}</button>}>
      {open && (
        <div className="card px-5 py-4 flex flex-col gap-4">
          {state.optional.map((q) => <OptionalField key={q.key} q={q} draftId={state.draft.id} run={run} busy={busy} />)}
        </div>
      )}
    </Section>
  );
}

function OptionalField({ q, draftId, run, busy }: { q: Question; draftId: string; run: Run; busy: boolean }) {
  const [value, setValue] = useState<unknown>(initialValue(q));
  const field: ReturnField = { key: q.key, label: q.label, type: q.type, required: false, options: q.options, help: q.help, columns: q.columns };
  return (
    <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); run(() => api.patch(draftId, { answers: { [q.key]: value } })); }}>
      <FieldInput field={field} value={value} onChange={setValue} />
      <button type="submit" className="btn-secondary self-start" style={{ padding: "5px 12px", fontSize: "12.5px" }} disabled={busy || !hasValue(q, value)}>Add</button>
    </form>
  );
}

// ─── Check and remediation ───────────────────────────────────────────────────

function CheckSection({ state, run, busy }: { state: DraftState; run: Run; busy: boolean }) {
  const check = state.check!;
  const groups = Array.from(new Map(check.breaches.map((b) => [b.code, b.group ?? b.title])).entries());
  return (
    <Section title="Iroko's check" subtitle="The figures and tests that will appear in the return.">
      {check.errors.length > 0 && <Notice tone="danger" title="Fix before generating" items={check.errors} />}
      {check.warnings.length > 0 && <Notice tone="warning" title="Review before sending" items={check.warnings} />}
      {check.figures.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {check.figures.map((f) => (
            <div key={f.label} className="card px-3 py-2.5">
              <div className="text-[11px] text-gray-400 leading-tight">{f.label}</div>
              <div className="text-[13.5px] font-semibold text-gray-800 mt-0.5 break-words">{f.value}</div>
            </div>
          ))}
        </div>
      )}
      {check.breaches.length > 0 && (
        <div className="card px-5 py-4 flex flex-col gap-4">
          <div className="text-[13px] text-gray-700">
            <span className="font-semibold text-danger-700">{check.breaches.length} exception{check.breaches.length > 1 ? "s" : ""}</span>{" "}
            will be reported. The regulator expects the bank&apos;s plan for each — Iroko can draft it for you to edit.
          </div>
          <ul className="list-disc m-0 pl-5 text-[12.5px] text-gray-500 leading-[1.6]">
            {check.breaches.map((b, i) => <li key={i}><span className="text-gray-700 font-medium">{b.title}</span> — {b.detail}</li>)}
          </ul>
          {groups.map(([code, title]) => (
            <RemediationEditor key={code} code={code} title={title} draftId={state.draft.id} saved={state.remediation[code] ?? ""} run={run} busy={busy} />
          ))}
        </div>
      )}
    </Section>
  );
}

function RemediationEditor({ code, title, draftId, saved, run, busy }: { code: string; title: string; draftId: string; saved: string; run: Run; busy: boolean }) {
  const [text, setText] = useState(saved);
  const [suggesting, setSuggesting] = useState(false);
  const dirty = text.trim() !== saved.trim();
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="label-base text-[13px] m-0">Remediation plan — {title}{!saved && <span className="text-danger-700"> *</span>}</span>
        <button className="text-[12.5px] text-brand-600 font-semibold" disabled={suggesting}
          onClick={async () => {
            setSuggesting(true);
            try { setText((await api.suggest(draftId, code)).suggestion); toast.info("Iroko drafted a plan — edit it so it says exactly what the bank will do"); }
            catch (e) { toast.error((e as Error).message); }
            finally { setSuggesting(false); }
          }}>
          {suggesting ? "Drafting…" : text ? "Redraft with Iroko" : "Draft it with Iroko"}
        </button>
      </div>
      <textarea className="input-base" rows={3} value={text} onChange={(e) => setText(e.target.value)}
        placeholder="What the bank will do, who is responsible, and by when." />
      {dirty && (
        <button className="btn-primary self-start" style={{ padding: "6px 14px", fontSize: "12.5px" }} disabled={busy || !text.trim()}
          onClick={() => run(() => api.patch(draftId, { remediation: { [code]: text } }), "Plan saved")}>
          Save plan
        </button>
      )}
    </div>
  );
}

function Notice({ tone, title, items }: { tone: "danger" | "warning" | "info"; title: string; items: string[] }) {
  const styles = {
    danger: "border-danger-500/40 bg-danger-50 text-danger-700",
    warning: "border-warning-500/40 bg-warning-50 text-warning-700",
    info: "border-border-default bg-transparent text-gray-500",
  }[tone];
  return (
    <div className={`rounded-lg border px-4 py-3 ${styles}`}>
      <div className="text-[12.5px] font-semibold mb-1.5">{title}</div>
      <ul className="list-disc m-0 pl-5 text-[12.5px] leading-[1.6]">{items.map((t, i) => <li key={i}>{t}</li>)}</ul>
    </div>
  );
}

// ─── Ready panel ─────────────────────────────────────────────────────────────

function ReadyPanel({ spec, state, run, busy }: { spec: ReturnSpec; state: DraftState; run: Run; busy: boolean }) {
  const [generating, setGenerating] = useState(false);
  const [ref, setRef] = useState(state.draft.submission_ref ?? "");
  const [on, setOn] = useState(state.draft.submitted_on ?? todayIso());
  const id = state.draft.id;
  const generated = state.draft.status === "generated" || state.draft.status === "submitted";
  const channel = spec.regulator === "NFIU" ? "goAML" : spec.channel.toLowerCase().includes("fina") ? "FinA" : "submission";

  return (
    <aside className="xl:sticky xl:top-2 flex flex-col gap-4">
      <div className="card px-5 py-4 flex flex-col gap-3">
        <h3 className="text-[14px] font-semibold text-gray-900 m-0">{state.ready ? "Ready to generate" : "Before Iroko can generate"}</h3>
        {state.ready ? (
          <p className="text-[12.5px] text-gray-500 m-0">Every answer is in and confirmed, and the check passed.</p>
        ) : (
          <ul className="m-0 pl-0 list-none flex flex-col gap-1.5">
            {state.blocking.map((b) => (
              <li key={b} className="text-[12.5px] text-gray-600 flex gap-2"><span className="text-gray-300">○</span>{b}</li>
            ))}
          </ul>
        )}
        <label className="block">
          <span className="label-base text-[12.5px]">Date on the letter</span>
          <input type="date" className="input-base" value={state.draft.letter_date} disabled={busy}
            onChange={(e) => e.target.value && run(() => api.patch(id, { letter_date: e.target.value }))} />
        </label>
        <button className="btn-primary" disabled={!state.ready || generating || busy}
          onClick={async () => {
            setGenerating(true);
            try {
              const name = await api.generate(id);
              toast.success(`${name} downloaded`);
              await run(() => api.patch(id, {}));
            } catch (e) { toast.error((e as Error).message); }
            finally { setGenerating(false); }
          }}>
          {generating ? "Generating…" : generated ? "Generate again" : "Generate documents"}
        </button>
        {spec.outputs.length > 0 && (
          <ul className="list-disc m-0 pl-5 text-[12px] text-gray-400 leading-[1.6]">{spec.outputs.map((o) => <li key={o}>{o}</li>)}</ul>
        )}
      </div>

      {generated && (
        <div className="card px-5 py-4 flex flex-col gap-3">
          {state.draft.status === "submitted" ? (
            <>
              <h3 className="text-[14px] font-semibold text-success-700 m-0">✓ Submitted</h3>
              <p className="text-[12.5px] text-gray-500 m-0">
                {state.draft.submitted_on ? `On ${formatDate(state.draft.submitted_on)}` : ""}{state.draft.submission_ref ? ` · ref ${state.draft.submission_ref}` : ""}
              </p>
            </>
          ) : (
            <>
              <h3 className="text-[14px] font-semibold text-gray-900 m-0">After you submit</h3>
              <p className="text-[12.5px] text-gray-500 m-0">Record the {channel} reference so the calendar shows this return as filed.</p>
              <input className="input-base" placeholder={`${channel} reference (optional)`} value={ref} onChange={(e) => setRef(e.target.value)} />
              <input type="date" className="input-base" value={on} onChange={(e) => setOn(e.target.value)} />
              <button className="btn-secondary" disabled={busy}
                onClick={() => run(() => api.submitted(id, ref, on), "Marked as submitted")}>
                Mark as submitted
              </button>
            </>
          )}
        </div>
      )}

      {(spec.submission_notes.length > 0 || spec.verification_notes.length > 0) && (
        <Notice tone="info" title="Before you submit" items={[...spec.submission_notes, ...spec.verification_notes]} />
      )}
    </aside>
  );
}
