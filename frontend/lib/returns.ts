/**
 * lib/returns.ts
 *
 * Client types and calls for regulatory returns (/api/returns/*). The backend
 * catalogue and draft state are the source of truth: the UI renders whatever
 * questions, imports and checks the server says a filing needs.
 */

"use client";

import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

export type FieldType =
  | "text" | "textarea" | "date" | "number" | "money"
  | "select" | "multiselect" | "bool" | "table";

export interface ReturnField {
  key: string;
  label: string;
  type: FieldType;
  required: boolean;
  options: string[];
  help: string;
  columns: ReturnField[];
}

export interface DatasetSpec {
  kind: "trial_balance" | "loan_book" | "transactions";
  label: string;
  ask: string;
  help: string;
  required: boolean;
}

export interface ReturnSpec {
  id: string;
  title: string;
  short_title: string;
  regulator: "CBN" | "NFIU" | "NDIC" | "NDPC";
  recipient: string[];
  channel: string;
  frequency: string;
  period_type: "month" | "half_year" | "year" | "event";
  due_text: string;
  legal_basis: string[];
  sources: string[];
  summary: string;
  outputs: string[];
  fields: ReturnField[];
  upload: string | null;
  generator: boolean;
  submission_notes: string[];
  verification_notes: string[];
  datasets: DatasetSpec[];
  /** False when the workspace's declared licence is not among this return's filers. */
  applicable?: boolean;
}

export type FilingStatus = "not_started" | "draft" | "generated" | "submitted";

export interface DeadlineItem {
  return_id: string;
  title: string;
  regulator: string;
  period: string;
  period_label: string;
  due: string;
  days_left: number;
  generator: boolean;
  status: FilingStatus;
  draft_id: string | null;
  submitted_on?: string | null;
  applicable?: boolean;
}

export interface ReturnsCatalog {
  returns: ReturnSpec[];
  profile_fields: ReturnField[];
  licence_categories: Record<string, string>;
  calendar: DeadlineItem[];
  profile_missing: string[];
  today: string;
  holiday_note: string;
}

export type Values = Record<string, unknown>;

export interface Source {
  kind: "memory" | "carried" | "document" | "derived" | "profile" | "import" | "user";
  label: string;
  confirmed: boolean;
  quote?: string;
  document_id?: string;
}

export interface Question {
  key: string;
  label: string;
  type: FieldType;
  required: boolean;
  ask: string;
  help: string;
  options: string[];
  columns: ReturnField[];
  quick: { label: string; value: unknown }[];
}

export interface FilledItem {
  key: string;
  label: string;
  type: FieldType;
  value: unknown;
  source: Source;
  options: string[];
  columns: ReturnField[];
}

export interface TbAccount { code: string; name: string; net: number; line: string | null; how: string }
export interface ReviewLoan {
  row: number; borrower_id: string; borrower_name: string; borrower_type: string;
  insider: boolean; insider_relationship: string; outstanding: number; days_past_due: number;
}

export interface DatasetState extends DatasetSpec {
  status: "missing" | "needs_columns" | "needs_review" | "ready";
  file_name?: string;
  headers?: string[];
  columns?: Record<string, number>;
  needs_columns?: string[];
  notes?: string[];
  accounts?: TbAccount[];
  unmapped?: number;
  ai_mapped?: number;
  count?: number;
  total?: number;
  review?: ReviewLoan[];
}

export interface CheckResult {
  reference: string;
  errors: string[];
  warnings: string[];
  breaches: { code: string; title: string; detail: string; group?: string }[];
  remediation_required: { code: string; title: string }[];
  figures: { label: string; value: string }[];
  ready: boolean;
  outputs: string[];
  submission_notes: string[];
  verification_notes: string[];
}

export interface DraftState {
  draft: {
    id: string; return_id: string; period: string; period_label: string; status: FilingStatus;
    reference: string | null; submission_ref: string | null; submitted_on: string | null;
    letter_date: string; due: string | null; days_left: number | null; updated_at: string | null;
  };
  progress: { done: number; total: number };
  profile: Values;
  profile_missing: string[];
  questions: Question[];
  items: FilledItem[];
  optional: Question[];
  unconfirmed: string[];
  datasets: DatasetState[];
  remediation: Record<string, string>;
  check: CheckResult | null;
  blocking: string[];
  ready: boolean;
  can_search_documents: boolean;
  found?: number;
}

export const RETURNS_CATALOG_KEY = ["returns", "catalog"];
export const draftKey = (id: string) => ["returns", "draft", id];

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (Array.isArray(body.errors) && body.errors.length) return body.errors.join(" ");
    if (typeof body.detail === "string") return body.detail;
  } catch { /* not JSON */ }
  return `Request failed (HTTP ${res.status}).`;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await detail(res));
  return res.json() as Promise<T>;
}

export function useReturnsCatalog() {
  return useQuery({
    queryKey: RETURNS_CATALOG_KEY,
    queryFn: async () => json<ReturnsCatalog>(await fetch("/api/returns/catalog")),
    staleTime: 1000 * 60 * 5,
  });
}

export function useDraft(id: string | null) {
  return useQuery({
    queryKey: draftKey(id ?? "none"),
    queryFn: async () => json<DraftState>(await fetch(`/api/returns/drafts/${id}`)),
    enabled: !!id,
    staleTime: 1000 * 30,
  });
}

/** Keeps the cached draft in step with every server response. */
export function useDraftCache() {
  const qc = useQueryClient();
  return useMemo(() => ({
    put: (state: DraftState) => {
      qc.setQueryData(draftKey(state.draft.id), state);
      qc.invalidateQueries({ queryKey: RETURNS_CATALOG_KEY });
    },
  }), [qc]);
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export const api = {
  open: async (return_id: string, period?: string) =>
    json<DraftState>(await fetch("/api/returns/drafts", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ return_id, period }) })),
  patch: async (id: string, body: { answers?: Values; confirm?: string[]; clear?: string[]; remediation?: Record<string, string>; letter_date?: string }) =>
    json<DraftState>(await fetch(`/api/returns/drafts/${id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(body) })),
  importFile: async (id: string, kind: string, file: File) => {
    const fd = new FormData();
    fd.set("file", file);
    return json<DraftState>(await fetch(`/api/returns/drafts/${id}/import/${kind}`, { method: "POST", body: fd }));
  },
  columns: async (id: string, kind: string, columns: Record<string, number>) =>
    json<DraftState>(await fetch(`/api/returns/drafts/${id}/columns/${kind}`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ columns }) })),
  review: async (id: string, kind: string, changes: Values, confirm: boolean) =>
    json<DraftState>(await fetch(`/api/returns/drafts/${id}/review/${kind}`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ changes, confirm }) })),
  find: async (id: string) => json<DraftState>(await fetch(`/api/returns/drafts/${id}/find`, { method: "POST" })),
  suggest: async (id: string, code: string) =>
    json<{ suggestion: string }>(await fetch(`/api/returns/drafts/${id}/suggest`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ code }) })),
  submitted: async (id: string, submission_ref: string, submitted_on: string) =>
    json<DraftState>(await fetch(`/api/returns/drafts/${id}/submitted`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ submission_ref, submitted_on }) })),
  saveProfile: async (profile: Values) =>
    json<{ profile: Values; missing: string[] }>(await fetch("/api/returns/profile", { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(profile) })),
  events: async (returnId: string) =>
    json<{ drafts: { id: string; period: string; status: FilingStatus; created_at: string; subject: string; reference: string | null }[] }>(
      await fetch(`/api/returns/events/${returnId}`)),
  /** Generates the documents and triggers the download. Returns the file name. */
  generate: async (id: string): Promise<string> => {
    const res = await fetch(`/api/returns/drafts/${id}/generate`, { method: "POST" });
    if (!res.ok) throw new Error(await detail(res));
    const disposition = res.headers.get("content-disposition") ?? "";
    const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? "return.docx";
    download(await res.blob(), name);
    return name;
  },
};

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ─── Formatting ──────────────────────────────────────────────────────────────

export function formatNaira(n: number): string {
  return `₦${n.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function formatValue(type: FieldType, value: unknown, columns: ReturnField[] = []): string {
  if (value === null || value === undefined || value === "") return "—";
  switch (type) {
    case "bool": return value ? "Yes" : "No";
    case "money": return formatNaira(Number(value));
    case "number": return Number(value).toLocaleString("en-NG");
    case "date": return formatDate(String(value));
    case "multiselect": return Array.isArray(value) ? value.join("; ") : String(value);
    case "table": {
      const rows = Array.isArray(value) ? value as Values[] : [];
      const first = columns[0]?.key;
      const names = first ? rows.map((r) => String(r[first] ?? "")).filter(Boolean) : [];
      return `${rows.length} ${rows.length === 1 ? "entry" : "entries"}${names.length ? `: ${names.slice(0, 4).join(", ")}${names.length > 4 ? "…" : ""}` : ""}`;
    }
    default: return String(value);
  }
}

/** The most recently closed period — the one a bank is usually filing. */
export function defaultPeriod(type: ReturnSpec["period_type"], today = new Date()): string {
  const y = today.getFullYear();
  const m = today.getMonth();
  if (type === "month") {
    const d = new Date(y, m - 1, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }
  if (type === "half_year") return m >= 6 ? `${y}-H1` : `${y - 1}-H2`;
  if (type === "year") return String(y - 1);
  return "";
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function filingHref(returnId: string, opts: { period?: string; draft?: string | null } = {}): string {
  const q = new URLSearchParams();
  if (opts.draft) q.set("draft", opts.draft);
  else if (opts.period) q.set("period", opts.period);
  const s = q.toString();
  return `/compliance/returns/${returnId}${s ? `?${s}` : ""}`;
}

export const REGULATOR_NAMES: Record<string, string> = {
  CBN: "Central Bank of Nigeria",
  NFIU: "Nigerian Financial Intelligence Unit",
  NDIC: "Nigeria Deposit Insurance Corporation",
  NDPC: "Nigeria Data Protection Commission",
};

export const STATUS_LABEL: Record<FilingStatus, string> = {
  not_started: "Not started",
  draft: "In progress",
  generated: "Ready to submit",
  submitted: "Submitted",
};

export const MMFBR_LINES: { code: string; label: string }[] = [
  ["A01", "Cash in vault"], ["A02", "Balances with the CBN"], ["A03", "Balances with banks and OFIs"],
  ["A04", "Placements (≤ 90 days)"], ["A05", "Treasury bills and FGN securities"], ["A06", "Other investments"],
  ["A07", "Loans and advances — gross"], ["A08", "Impairment allowance on loans"], ["A09", "Subsidiaries and associates"],
  ["A10", "Other assets"], ["A11", "Property, plant and equipment"], ["A12", "Intangible assets"], ["A13", "Deferred tax assets"],
  ["L01", "Demand deposits"], ["L02", "Savings deposits"], ["L03", "Time / term deposits"], ["L04", "Other deposits"],
  ["L05", "Borrowings from banks and OFIs"], ["L06", "On-lending and other borrowings"], ["L07", "Income tax payable"],
  ["L08", "Deferred tax liabilities"], ["L09", "Other liabilities"],
  ["E01", "Paid-up share capital"], ["E02", "Share premium"], ["E03", "Statutory reserve"], ["E04", "Regulatory risk reserve"],
  ["E05", "Retained earnings"], ["E06", "Other reserves"],
  ["I01", "Interest income — loans"], ["I02", "Interest income — placements/securities"], ["I03", "Fees and commission"],
  ["I04", "Other operating income"], ["X01", "Interest expense — deposits"], ["X02", "Interest expense — borrowings"],
  ["X03", "Impairment charge"], ["X04", "Staff costs"], ["X05", "Depreciation and amortisation"],
  ["X06", "Other operating expenses"], ["X07", "Income tax expense"], ["NONE", "Not reported"],
].map(([code, label]) => ({ code, label }));
