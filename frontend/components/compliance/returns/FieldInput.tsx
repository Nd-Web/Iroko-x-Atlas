"use client";

/**
 * Inputs for any return field, rendered from the backend field schema.
 */

import type { ReturnField, Values } from "@/lib/returns";

export function emptyRow(columns: ReturnField[]): Values {
  return Object.fromEntries(columns.map((c) => [c.key, c.type === "bool" ? false : ""]));
}

export default function FieldInput({
  field, value, onChange, optionLabels, hideLabel, autoFocus,
}: {
  field: ReturnField;
  value: unknown;
  onChange: (v: unknown) => void;
  optionLabels?: Record<string, string>;
  hideLabel?: boolean;
  autoFocus?: boolean;
}) {
  const label = !hideLabel && (
    <span className="label-base text-[13px]">
      {field.label}{field.required && <span className="text-danger-700"> *</span>}
    </span>
  );
  const help = field.help && <span className="block text-[11.5px] text-gray-400 mt-1">{field.help}</span>;

  switch (field.type) {
    case "bool":
      return (
        <label className="flex items-start gap-2.5 py-1">
          <input type="checkbox" className="mt-[3px]" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
          <span className="text-[13px] text-gray-700">{field.label}{help}</span>
        </label>
      );
    case "textarea":
      return (
        <label className="block">
          {label}
          <textarea className="input-base" rows={3} autoFocus={autoFocus} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />
          {help}
        </label>
      );
    case "select":
      return (
        <label className="block">
          {label}
          <select className="input-base" autoFocus={autoFocus} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
            <option value="">Select…</option>
            {field.options.map((o) => <option key={o} value={o}>{optionLabels?.[o] ?? o}</option>)}
          </select>
          {help}
        </label>
      );
    case "multiselect": {
      const selected = Array.isArray(value) ? (value as string[]) : [];
      return (
        <fieldset className="border-0 p-0 m-0">
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
        <label className="block">
          {label}
          <input
            className="input-base"
            autoFocus={autoFocus}
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
    <div className="flex flex-col gap-3">
      {rows.map((row, i) => (
        <div key={i} className="border border-border-default rounded-lg p-3">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[12px] font-semibold text-gray-500">#{i + 1}</span>
            <button type="button" className="text-[12px] text-danger-700" onClick={() => onChange(rows.filter((_, j) => j !== i))}>Remove</button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
            {field.columns.map((c) => (
              <div key={c.key} className={c.type === "textarea" ? "md:col-span-3" : ""}>
                <FieldInput field={c} value={row[c.key]} onChange={(v) => setRow(i, c.key, v)} />
              </div>
            ))}
          </div>
        </div>
      ))}
      <button type="button" className="btn-secondary self-start" style={{ padding: "6px 12px", fontSize: "12.5px" }}
        onClick={() => onChange([...rows, emptyRow(field.columns)])}>
        + Add {rows.length ? "another" : "a"} row
      </button>
    </div>
  );
}
