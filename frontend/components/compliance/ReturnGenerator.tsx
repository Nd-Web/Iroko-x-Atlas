"use client";

/**
 * components/compliance/ReturnGenerator.tsx
 *
 * Prepares one regulatory return: bank details (remembered), period, the
 * return's own fields or data upload, a server-side check (errors, warnings,
 * breaches needing the bank's remediation text) and the download.
 * Every form is rendered from the backend catalogue, so adding a field there
 * needs no UI change.
 */

import { useMemo, useState } from "react";
import { toast } from "sonner";
import Modal from "@/components/ui/Modal";
import {
  defaultPeriod, downloadTemplate, generateReturn, loadProfile, previewReturn, saveProfile, todayIso,
  type ReturnField, type ReturnPreview, type ReturnSpec, type ReturnsCatalog, type Values,
} from "@/lib/returns";

interface Props {
  spec: ReturnSpec;
  catalog: ReturnsCatalog;
  initialPeriod?: string;
  onClose: () => void;
}

function emptyRow(columns: ReturnField[]): Values {
  return Object.fromEntries(columns.map((c) => [c.key, c.type === "bool" ? false : ""]));
}

function initialData(spec: ReturnSpec): Values {
  return Object.fromEntries(
    spec.fields.map((f) => [f.key, f.type === "table" ? (f.required ? [emptyRow(f.columns)] : []) : f.type === "bool" ? false : f.type === "multiselect" ? [] : ""]),
  );
}

function profileComplete(fields: ReturnField[], profile: Values) {
  return fields.every((f) => !f.required || String(profile[f.key] ?? "").trim());
}

export default function ReturnGenerator({ spec, catalog, initialPeriod, onClose }: Props) {
  const [profile, setProfile] = useState<Values>(() => loadProfile());
  const [editProfile, setEditProfile] = useState(() => !profileComplete(catalog.profile_fields, loadProfile()));
  const [period, setPeriod] = useState(initialPeriod || defaultPeriod(spec.period_type));
  const [letterDate, setLetterDate] = useState(todayIso());
  const [data, setData] = useState<Values>(() => initialData(spec));
  const [file, setFile] = useState<File | null>(null);
  const [remediation, setRemediation] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<ReturnPreview | null>(null);
  const [busy, setBusy] = useState<"check" | "generate" | "template" | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);

  // Any change to the inputs invalidates the last check, so a download always
  // reflects figures the user has seen validated.
  const touch = () => { setPreview(null); setRequestError(null); };
  const updateProfile = (k: string, v: unknown) => { setProfile((p) => ({ ...p, [k]: v })); touch(); };
  const updateData = (k: string, v: unknown) => { setData((d) => ({ ...d, [k]: v })); touch(); };

  const request = useMemo(() => ({
    profile, period: spec.period_type === "event" ? undefined : period, letter_date: letterDate, data, remediation,
  }), [profile, period, letterDate, data, remediation, spec.period_type]);

  const runCheck = async () => {
    setBusy("check");
    setRequestError(null);
    saveProfile(profile);
    try {
      const result = await previewReturn(spec.id, request, file);
      setPreview(result);
      if (!result.errors.length && profileComplete(catalog.profile_fields, profile)) setEditProfile(false);
    } catch (e) {
      setRequestError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const runGenerate = async () => {
    setBusy("generate");
    setRequestError(null);
    try {
      const name = await generateReturn(spec.id, request, file);
      toast.success(`${name} downloaded`);
    } catch (e) {
      setRequestError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const remediationMissing = (preview?.remediation_required ?? []).filter((r) => !(remediation[r.code] ?? "").trim());
  const canGenerate = !!preview && preview.errors.length === 0 && remediationMissing.length === 0;

  const footer = (
    <div className="flex flex-wrap items-center justify-end gap-2 w-full">
      {requestError && <span className="text-[12.5px] text-danger-700 mr-auto">{requestError}</span>}
      <button className="btn-secondary" onClick={onClose}>Close</button>
      <button className="btn-secondary" onClick={runCheck} disabled={busy !== null}>
        {busy === "check" ? "Checking…" : preview ? "Re-check" : "Check return"}
      </button>
      <button className="btn-primary" onClick={runGenerate} disabled={!canGenerate || busy !== null}
        title={canGenerate ? undefined : "Run the check and resolve every error first"}>
        {busy === "generate" ? "Generating…" : "Generate documents"}
      </button>
    </div>
  );

  return (
    <Modal open onClose={onClose} title={spec.title} maxWidth="880px" footer={footer}>
      <div className="flex flex-col gap-6">
        <div className="text-[13px] text-gray-500 leading-[1.6]">
          <span className="font-semibold text-gray-700">{spec.regulator}</span> · {spec.frequency} · {spec.due_text}
          <div className="text-gray-400 mt-1">Filed via: {spec.channel}</div>
        </div>

        {/* Bank details */}
        <Section title="Bank details" aside={!editProfile && (
          <button className="text-[12.5px] text-brand-600 font-semibold" onClick={() => setEditProfile(true)}>Edit</button>
        )}>
          {editProfile ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {catalog.profile_fields.map((f) => (
                <FieldInput key={f.key} field={f} value={profile[f.key]} onChange={(v) => updateProfile(f.key, v)}
                  optionLabels={f.key === "licence_category" ? catalog.licence_categories : undefined}
                  wide={f.type === "textarea"} />
              ))}
              <p className="md:col-span-2 text-[12px] text-gray-400 m-0">Saved in this browser and reused for every return.</p>
            </div>
          ) : (
            <p className="text-[13px] text-gray-600 m-0">
              {String(profile.institution_name ?? "")} · {catalog.licence_categories[String(profile.licence_category)] ?? ""} · MD/CEO {String(profile.md_ceo_name ?? "")} · CCO {String(profile.cco_name ?? "")}
            </p>
          )}
        </Section>

        {/* Period */}
        <Section title={spec.period_type === "event" ? "Report date" : "Reporting period"}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {spec.period_type !== "event" && (
              <PeriodInput type={spec.period_type} value={period} onChange={(v) => { setPeriod(v); touch(); }} />
            )}
            <label className="block">
              <span className="label-base text-[13px]">Date on the letter</span>
              <input type="date" className="input-base" value={letterDate} onChange={(e) => { setLetterDate(e.target.value); touch(); }} />
            </label>
          </div>
        </Section>

        {/* Upload */}
        {spec.upload && (
          <Section title="Data upload">
            <div className="flex flex-col md:flex-row md:items-center gap-3">
              <button className="btn-secondary shrink-0" disabled={busy !== null} onClick={async () => {
                setBusy("template");
                try { await downloadTemplate(spec.id); } catch (e) { toast.error((e as Error).message); } finally { setBusy(null); }
              }}>
                {busy === "template" ? "Preparing…" : "Download input template"}
              </button>
              <input type="file" accept=".xlsx" className="text-[13px] text-gray-600"
                onChange={(e) => { setFile(e.target.files?.[0] ?? null); touch(); }} />
            </div>
            <p className="text-[12px] text-gray-400 mt-2 mb-0">Fill the template from your core banking export and upload it here. Iroko reads figures by line code, so keep column A unchanged.</p>
          </Section>
        )}

        {/* Return-specific fields */}
        {spec.fields.length > 0 && (
          <Section title="Return details">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {spec.fields.map((f) => (
                <FieldInput key={f.key} field={f} value={data[f.key]} onChange={(v) => updateData(f.key, v)}
                  wide={["textarea", "table", "multiselect"].includes(f.type)} />
              ))}
            </div>
          </Section>
        )}

        {/* Check results */}
        {preview && <PreviewPanel preview={preview} remediation={remediation} setRemediation={setRemediation} />}
      </div>
    </Modal>
  );
}

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section>
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="text-[12px] font-semibold uppercase tracking-wide text-gray-400 m-0">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

function PeriodInput({ type, value, onChange }: { type: ReturnSpec["period_type"]; value: string; onChange: (v: string) => void }) {
  const thisYear = new Date().getFullYear();
  const years = [thisYear + 1, thisYear, thisYear - 1, thisYear - 2, thisYear - 3];
  if (type === "month") {
    return (
      <label className="block">
        <span className="label-base text-[13px]">Month</span>
        <input type="month" className="input-base" value={value} onChange={(e) => onChange(e.target.value)} />
      </label>
    );
  }
  if (type === "half_year") {
    const [y, h] = value.split("-");
    return (
      <div className="grid grid-cols-2 gap-2">
        <label className="block">
          <span className="label-base text-[13px]">Year</span>
          <select className="input-base" value={y} onChange={(e) => onChange(`${e.target.value}-${h || "H1"}`)}>
            {years.map((yr) => <option key={yr} value={yr}>{yr}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="label-base text-[13px]">Half-year</span>
          <select className="input-base" value={h} onChange={(e) => onChange(`${y}-${e.target.value}`)}>
            <option value="H1">Ended 30 June</option>
            <option value="H2">Ended 31 December</option>
          </select>
        </label>
      </div>
    );
  }
  return (
    <label className="block">
      <span className="label-base text-[13px]">Year ended</span>
      <select className="input-base" value={value} onChange={(e) => onChange(e.target.value)}>
        {years.map((yr) => <option key={yr} value={yr}>{yr}</option>)}
      </select>
    </label>
  );
}

function FieldInput({
  field, value, onChange, optionLabels, wide,
}: {
  field: ReturnField; value: unknown; onChange: (v: unknown) => void; optionLabels?: Record<string, string>; wide?: boolean;
}) {
  const label = (
    <span className="label-base text-[13px]">
      {field.label}{field.required && <span className="text-danger-700"> *</span>}
    </span>
  );
  const help = field.help && <span className="block text-[11.5px] text-gray-400 mt-1">{field.help}</span>;
  const span = wide ? "md:col-span-2" : "";

  switch (field.type) {
    case "bool":
      return (
        <label className={`flex items-start gap-2.5 py-1 ${span}`}>
          <input type="checkbox" className="mt-[3px]" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
          <span className="text-[13px] text-gray-700">{field.label}{help}</span>
        </label>
      );
    case "textarea":
      return (
        <label className={`block ${span}`}>
          {label}
          <textarea className="input-base" rows={3} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />
          {help}
        </label>
      );
    case "select":
      return (
        <label className={`block ${span}`}>
          {label}
          <select className="input-base" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
            <option value="">Select…</option>
            {field.options.map((o) => <option key={o} value={o}>{optionLabels?.[o] ?? o}</option>)}
          </select>
          {help}
        </label>
      );
    case "multiselect": {
      const selected = Array.isArray(value) ? (value as string[]) : [];
      return (
        <fieldset className={`${span} border-0 p-0 m-0`}>
          {label}
          <div className="flex flex-col gap-1.5">
            {field.options.map((o) => (
              <label key={o} className="flex items-start gap-2.5 text-[13px] text-gray-700">
                <input type="checkbox" className="mt-[3px]" checked={selected.includes(o)}
                  onChange={(e) => onChange(e.target.checked ? [...selected, o] : selected.filter((s) => s !== o))} />
                {o}
              </label>
            ))}
          </div>
          {help}
        </fieldset>
      );
    }
    case "table":
      return <TableInput field={field} value={value} onChange={onChange} />;
    default:
      return (
        <label className={`block ${span}`}>
          {label}
          <input
            className="input-base"
            type={field.type === "date" ? "date" : "text"}
            inputMode={field.type === "money" || field.type === "number" ? "decimal" : undefined}
            value={String(value ?? "")}
            onChange={(e) => onChange(e.target.value)}
          />
          {help}
        </label>
      );
  }
}

function TableInput({ field, value, onChange }: { field: ReturnField; value: unknown; onChange: (v: unknown) => void }) {
  const rows = Array.isArray(value) ? (value as Values[]) : [];
  const setRow = (i: number, k: string, v: unknown) => onChange(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="md:col-span-2">
      <span className="label-base text-[13px]">
        {field.label}{field.required && <span className="text-danger-700"> *</span>}
      </span>
      <div className="flex flex-col gap-3">
        {rows.map((row, i) => (
          <div key={i} className="border border-border-default rounded-lg p-3">
            <div className="flex justify-between items-center mb-2">
              <span className="text-[12px] font-semibold text-gray-500">#{i + 1}</span>
              <button className="text-[12px] text-danger-700" onClick={() => onChange(rows.filter((_, j) => j !== i))}>Remove</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
              {field.columns.map((c) => (
                <FieldInput key={c.key} field={c} value={row[c.key]} onChange={(v) => setRow(i, c.key, v)} wide={c.type === "textarea"} />
              ))}
            </div>
          </div>
        ))}
        <button className="btn-secondary self-start" style={{ padding: "6px 12px", fontSize: "12.5px" }}
          onClick={() => onChange([...rows, emptyRow(field.columns)])}>
          + Add {rows.length ? "another" : "a"} row
        </button>
      </div>
    </div>
  );
}

function PreviewPanel({
  preview, remediation, setRemediation,
}: {
  preview: ReturnPreview; remediation: Record<string, string>; setRemediation: (fn: (r: Record<string, string>) => Record<string, string>) => void;
}) {
  return (
    <section className="flex flex-col gap-4 border-t border-border-default pt-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[14px] font-semibold text-gray-900 m-0">Check result</h3>
        <span className="text-[12px] text-gray-400">Ref {preview.reference}{preview.due ? ` · due ${preview.due}` : ""}</span>
      </div>

      {preview.errors.length > 0 && (
        <Notice tone="danger" title={`Fix ${preview.errors.length} problem${preview.errors.length > 1 ? "s" : ""} before generating`} items={preview.errors} />
      )}
      {preview.warnings.length > 0 && <Notice tone="warning" title="Review before sending" items={preview.warnings} />}

      {preview.figures.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {preview.figures.map((f) => (
            <div key={f.label} className="rounded-lg border border-border-default px-3 py-2">
              <div className="text-[11px] text-gray-400 leading-tight">{f.label}</div>
              <div className="text-[13.5px] font-semibold text-gray-800 mt-0.5 break-words">{f.value}</div>
            </div>
          ))}
        </div>
      )}

      {preview.breaches.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="text-[13px] text-gray-700">
            <span className="font-semibold text-danger-700">{preview.breaches.length} exception{preview.breaches.length > 1 ? "s" : ""}</span>{" "}will be reported to the regulator. Enter the bank&apos;s remediation plan for each — it is printed in the return as written.
          </div>
          {preview.breaches.map((b, i) => (
            <div key={`${b.code}-${i}`} className="text-[12.5px] text-gray-500"><span className="text-gray-700 font-medium">{b.title}</span> — {b.detail}</div>
          ))}
          {preview.remediation_required.concat(
            // keep already-answered groups editable after re-checks
            Object.keys(remediation).filter((c) => preview.breaches.some((b) => b.code === c) && !preview.remediation_required.some((r) => r.code === c))
              .map((c) => ({ code: c, title: preview.breaches.find((b) => b.code === c)?.group ?? preview.breaches.find((b) => b.code === c)?.title ?? c })),
          ).map((r) => (
            <label key={r.code} className="block">
              <span className="label-base text-[13px]">Remediation — {r.title}<span className="text-danger-700"> *</span></span>
              <textarea className="input-base" rows={3} value={remediation[r.code] ?? ""}
                onChange={(e) => setRemediation((m) => ({ ...m, [r.code]: e.target.value }))} />
            </label>
          ))}
        </div>
      )}

      {preview.errors.length === 0 && (
        <div className="text-[12.5px] text-gray-500 leading-[1.6]">
          <div className="font-semibold text-gray-700 mb-1">You will download</div>
          <ul className="list-disc m-0 pl-5">{preview.outputs.map((o) => <li key={o}>{o}</li>)}</ul>
        </div>
      )}
      {(preview.submission_notes.length > 0 || preview.verification_notes.length > 0) && (
        <Notice tone="info" title="Before you submit" items={[...preview.submission_notes, ...preview.verification_notes]} />
      )}
    </section>
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
