/**
 * lib/returns.ts
 *
 * Client types and calls for regulatory returns (/api/returns/*). The backend
 * catalogue is the single source of truth for which returns exist, their
 * deadlines and the fields each one needs; the UI renders from it.
 */

"use client";

import { useQuery } from "@tanstack/react-query";

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
}

export interface DeadlineItem {
  return_id: string;
  title: string;
  regulator: string;
  period: string;
  period_label: string;
  due: string;
  days_left: number;
  generator: boolean;
}

export interface ReturnsCatalog {
  returns: ReturnSpec[];
  profile_fields: ReturnField[];
  licence_categories: Record<string, string>;
  calendar: DeadlineItem[];
  today: string;
  holiday_note: string;
}

export interface ReturnPreview {
  return_id: string;
  title: string;
  reference: string;
  period: string | null;
  due: string | null;
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

export type Values = Record<string, unknown>;

export interface ReturnRequest {
  profile: Values;
  period?: string;
  letter_date?: string;
  data: Values;
  remediation: Record<string, string>;
}

export const RETURNS_CATALOG_KEY = ["returns", "catalog"];

export function useReturnsCatalog() {
  return useQuery({
    queryKey: RETURNS_CATALOG_KEY,
    queryFn: async (): Promise<ReturnsCatalog> => {
      const res = await fetch("/api/returns/catalog");
      if (!res.ok) throw new Error(`Could not load the returns catalogue (HTTP ${res.status}).`);
      return res.json();
    },
    staleTime: 1000 * 60 * 30,
  });
}

function formData(req: ReturnRequest, file: File | null): FormData {
  const fd = new FormData();
  fd.set("payload", JSON.stringify(req));
  if (file) fd.set("file", file);
  return fd;
}

async function detail(res: Response): Promise<string[]> {
  try {
    const body = await res.json();
    if (Array.isArray(body.errors) && body.errors.length) return body.errors;
    if (typeof body.detail === "string") return [body.detail];
  } catch { /* not JSON */ }
  return [`Request failed (HTTP ${res.status}).`];
}

export async function previewReturn(id: string, req: ReturnRequest, file: File | null): Promise<ReturnPreview> {
  const res = await fetch(`/api/returns/${id}/preview`, { method: "POST", body: formData(req, file) });
  if (!res.ok) throw new Error((await detail(res)).join(" "));
  return res.json();
}

/** Generates the return and triggers the browser download. Returns the file name. */
export async function generateReturn(id: string, req: ReturnRequest, file: File | null): Promise<string> {
  const res = await fetch(`/api/returns/${id}/generate`, { method: "POST", body: formData(req, file) });
  if (!res.ok) throw new Error((await detail(res)).join(" "));
  const disposition = res.headers.get("content-disposition") ?? "";
  const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? `${id}.docx`;
  download(await res.blob(), name);
  return name;
}

export async function downloadTemplate(id: string): Promise<void> {
  const res = await fetch(`/api/returns/${id}/template`);
  if (!res.ok) throw new Error((await detail(res)).join(" "));
  download(await res.blob(), `iroko-${id}-input.xlsx`);
}

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

// ─── Institution profile (entered once, reused by every return) ──────────────

const PROFILE_KEY = "iroko.returns.profile";

export function loadProfile(): Values {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as Values) : {};
  } catch {
    return {};
  }
}

export function saveProfile(profile: Values) {
  try {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  } catch { /* storage unavailable — the profile simply isn't remembered */ }
}

// ─── Periods ─────────────────────────────────────────────────────────────────

/** The most recently closed period — the one a bank is usually filing. */
export function defaultPeriod(type: ReturnSpec["period_type"], today = new Date()): string {
  const y = today.getFullYear();
  const m = today.getMonth(); // 0-based
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

export const REGULATOR_NAMES: Record<string, string> = {
  CBN: "Central Bank of Nigeria",
  NFIU: "Nigerian Financial Intelligence Unit",
  NDIC: "Nigeria Deposit Insurance Corporation",
  NDPC: "Nigeria Data Protection Commission",
};
