/**
 * lib/compliance-graph.ts
 *
 * Types, queries and actions for the compliance knowledge graph
 * (/api/compliance-graph/*, through the same-origin proxy). The backend is the
 * source of truth for what applies, what is covered and who may decide; the UI
 * renders what it says and refreshes after every decision.
 */

"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

const BASE = "/api/compliance-graph";
const JSON_HEADERS = { "Content-Type": "application/json" };

export type Basis = "stated" | "suggested" | "manual" | "inherited";
export type ReviewStatus = "proposed" | "confirmed" | "rejected" | "needs_re_review";

export interface StatusInfo {
  basis: Basis | null;
  basis_label?: string | null;
  review_status: ReviewStatus;
  review_label?: string | null;
  label: string;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
}

export interface DocumentInfo {
  id: string;
  title: string;
  status?: string;
  role?: string | null;
  role_label?: string | null;
  role_basis?: string | null;
  role_suggestion?: string | null;
  regulator?: string | null;
  reference?: string | null;
  published_date?: string | null;
  effective_date?: string | null;
  effective_basis?: string | null;
  shared?: boolean;
  awaiting_publication?: boolean;
  extraction_status?: string | null;
}

export interface RequirementRow {
  lineage_id: string;
  id: string;
  quote: string;
  summary: string | null;
  kind: string;
  topics: string[];
  page_number: number | null;
  section: string | null;
  chunk_id: string | null;
  addressee_codes: string[];
  review_status: string;
  document: DocumentInfo;
  applicability: { state: string; label: string; note?: string | null };
  coverage: {
    state: string; label: string; partial: boolean; controls_confirmed: number; controls_suggested: number;
    evidence_confirmed: number; evidence_suggested: number; latest_evidence: string | null;
  };
  owner: { user_id: string | null; name: string | null; team: string | null };
  due: { date: string | null; basis: string | null; description: string | null };
}

export interface RequirementsPage {
  items: RequirementRow[];
  total: number;
  page: number;
  page_size: number;
  facets: { coverage: Record<string, number>; applicability: Record<string, number>; regulator: Record<string, number> };
}

export interface Anchor {
  kind?: string;
  side?: string;
  document_id?: string;
  document_title?: string | null;
  reference?: string | null;
  page_number?: number | null;
  quote?: string | null;
  span?: string | null;
  section?: string | null;
  published_date?: string | null;
  effective_date?: string | null;
  effective_basis?: string | null;
  awaiting_publication?: boolean;
  cue?: string | null;
}

export interface Endpoint { type: string; id: string; label?: string; available?: boolean }

export interface HistoryItem { at: string | null; action: string; actor: string; from: string | null; to: string | null; note: string | null }

export interface LinkInfo {
  id: string;
  relation: string;
  relation_label: string;
  layer: "library" | "workspace";
  from: Endpoint;
  to: Endpoint;
  attributes: Record<string, unknown>;
  status: StatusInfo;
  stale_reason: string | null;
  rationale: string | null;
  rationale_label: string | null;
  anchors: Anchor[];
  has_proposal: boolean;
  can_review: boolean;
  proposal?: Record<string, unknown> | null;
  history?: HistoryItem[];
}

export interface ControlRow {
  id: string;
  name: string;
  summary: string | null;
  quote: string | null;
  frequency: string | null;
  evidence_expected: string | null;
  topics: string[];
  status: string;
  owner: { user_id: string | null; name: string | null; team: string | null };
  performer: string | null;
  document: DocumentInfo | null;
  page_number: number | null;
  section: string | null;
  review: StatusInfo;
  has_proposal: boolean;
  requirements_confirmed: number;
  requirements_suggested: number;
  evidence_confirmed: number;
  evidence_suggested: number;
  latest_evidence: string | null;
}

export interface DueItem {
  kind: "requirement" | "return" | "effective" | "control_cycle";
  date: string;
  overdue?: boolean;
  title: string;
  lineage_id?: string;
  document?: string | null;
  basis?: string | null;
  return_id?: string;
  regulator?: string;
  draft_status?: string | null;
  document_id?: string;
  control_id?: string;
}

export interface ImpactInfo {
  id: string;
  kind: string;
  summary: string;
  status: "open" | "acknowledged" | "withdrawn";
  created_at: string | null;
  acknowledged_at: string | null;
  flagged: number;
  links: { id: string; relation: string; status: string; stale_reason: string | null }[];
  controls: { id: string; name: string; owner_user_id: string | null; owner_team: string | null }[];
  changes: { lineage_id: string; old_quote: string | null; new_quote: string | null; removed: boolean }[];
  trigger_document: DocumentInfo | null;
  subject_document: DocumentInfo | null;
}

export interface Overview {
  profile: { category_codes: string[]; basis: string | null; labels: string[] };
  totals: {
    requirements_visible: number; requirements_applying: number; applicability: Record<string, number>;
    coverage: Record<string, number>; awaiting_review: number; needs_re_review: number; open_changes: number;
    due_30_days: number;
  };
  coverage_labels: Record<string, string>;
  reviews: Record<string, number>;
  gaps: { lineage_id: string; summary: string | null; quote: string; coverage: RequirementRow["coverage"]; document: string | null }[];
  gap_wording: string;
  changes: ImpactInfo[];
  due: DueItem[];
  setup: { licence_categories: boolean; licence_from_filing_profile: boolean; policies_uploaded: number;
           evidence_uploaded: number; suggestions_to_review: number };
  extraction: { documents: number; by_status: Record<string, number>;
                problems: { document_id: string; title: string; status: string; error: string | null }[] };
}

export interface ReviewGroup {
  key: string;
  title: string;
  count: number;
  // Items differ by group: links, controls, documents (see ReviewQueue.tsx).
  items: Record<string, unknown>[];
}

export interface GraphNode {
  id: string; type: string; key: string; label: string; lane: number; sublabel?: string | null;
  status?: string | null; awaiting_publication?: boolean; document_id?: string;
}
export interface GraphEdge {
  id: string; from: string; to: string; relation: string; label: string; style: string;
  basis?: string; review_status?: string;
}
export interface Neighbourhood { focus: string; nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean; lanes: string[] }

export interface Category { code: string; label: string; sector: string }
export interface Person { id: string; name: string; email: string; role: string }

export interface RequirementDetail {
  requirement: RequirementRow & { unavailable?: boolean };
  versions: { id: string; quote: string; document: DocumentInfo | null; status: string; page_number: number | null; section: string | null }[];
  links: LinkInfo[];
  addressees: LinkInfo[];
  history: HistoryItem[];
  can_decide: boolean;
}

export interface ControlDetail {
  control: ControlRow;
  anchor_history: { document_id: string; quote: string; replaced_at: string }[];
  proposal: Record<string, unknown> | null;
  links: LinkInfo[];
  history: HistoryItem[];
  can_review: boolean;
}

export interface DocumentDetail {
  document: DocumentInfo;
  facts: Record<string, unknown>;
  effective_anchor: Anchor | null;
  requirements: number;
  links: LinkInfo[];
  history: HistoryItem[];
}

// ─── Fetch helpers ───────────────────────────────────────────────────────────

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch { /* not JSON */ }
  return `Request failed (HTTP ${res.status}).`;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", credentials: "include" });
  if (!res.ok) throw new Error(await detail(res));
  return res.json() as Promise<T>;
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method, headers: JSON_HEADERS, body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store", credentials: "include",
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json() as Promise<T>;
}

function query(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const cgKey = ["compliance-graph"] as const;

// ─── Queries ─────────────────────────────────────────────────────────────────

export function useOverview() {
  return useQuery({ queryKey: [...cgKey, "overview"], queryFn: () => get<Overview>("/overview") });
}

export interface RequirementFilters {
  q?: string; regulator?: string; document_id?: string; topic?: string; applicability?: string;
  coverage?: string; owner?: string; due_within?: number | null;
}

export function useRequirements(filters: RequirementFilters, page: number, pageSize = 25) {
  const qs = query({ ...filters, page, page_size: pageSize });
  return useQuery({ queryKey: [...cgKey, "requirements", qs], queryFn: () => get<RequirementsPage>(`/requirements${qs}`) });
}

export function useControls(includeRetired = false) {
  return useQuery({
    queryKey: [...cgKey, "controls", includeRetired],
    queryFn: () => get<{ items: ControlRow[] }>(`/controls${query({ include_retired: includeRetired ? "true" : "" })}`),
  });
}

export function useReviewQueue() {
  return useQuery({ queryKey: [...cgKey, "review"], queryFn: () => get<{ groups: ReviewGroup[] }>("/review-queue") });
}

export function useImpacts(status?: "open" | "acknowledged") {
  return useQuery({
    queryKey: [...cgKey, "impacts", status ?? "all"],
    queryFn: () => get<{ items: ImpactInfo[] }>(`/impacts${query({ status })}`),
  });
}

export function useDue(days = 30) {
  return useQuery({
    queryKey: [...cgKey, "due", days],
    queryFn: () => get<{ items: DueItem[]; event_driven: { lineage_id: string; title: string; description: string | null }[] }>(`/due?days=${days}`),
  });
}

export function useProfile() {
  return useQuery({
    queryKey: [...cgKey, "profile"],
    queryFn: () => get<{ category_codes: string[]; basis: string | null; labels: string[]; can_edit: boolean }>("/profile"),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: [...cgKey, "categories"],
    queryFn: () => get<{ declarable: Category[]; topics: { code: string; label: string }[] }>("/categories"),
    staleTime: 1000 * 60 * 60,
  });
}

export function usePeople() {
  return useQuery({ queryKey: [...cgKey, "people"], queryFn: () => get<{ items: Person[] }>("/people"), staleTime: 60_000 });
}

export function useLinkDetail(id: string | null) {
  return useQuery({ queryKey: [...cgKey, "link", id], enabled: !!id, queryFn: () => get<LinkInfo>(`/links/${id}`) });
}

export function useRequirementDetail(lineage: string | null) {
  return useQuery({
    queryKey: [...cgKey, "requirement", lineage], enabled: !!lineage,
    queryFn: () => get<RequirementDetail>(`/requirements/${lineage}`),
  });
}

export function useControlDetail(id: string | null) {
  return useQuery({ queryKey: [...cgKey, "control", id], enabled: !!id, queryFn: () => get<ControlDetail>(`/controls/${id}`) });
}

export function useDocumentDetail(id: string | null) {
  return useQuery({ queryKey: [...cgKey, "document", id], enabled: !!id, queryFn: () => get<DocumentDetail>(`/documents/${id}`) });
}

export function useNeighbourhood(type: string | null, id: string | null, depth: number, includeSuggested: boolean) {
  return useQuery({
    queryKey: [...cgKey, "hood", type, id, depth, includeSuggested], enabled: !!type && !!id,
    queryFn: () => get<Neighbourhood>(`/neighbourhood${query({ type, id, depth, include_suggested: includeSuggested ? "true" : "false" })}`),
  });
}

export function useGraphSearch(q: string) {
  return useQuery({
    queryKey: [...cgKey, "search", q], enabled: q.trim().length >= 2,
    queryFn: () => get<{
      instruments: { id: string; title: string; reference: string | null; role: string }[];
      requirements: { lineage_id: string; summary: string | null; quote: string }[];
      controls: { id: string; name: string }[];
      evidence: { id: string; title: string }[];
    }>(`/search${query({ q })}`),
  });
}

// ─── Actions ─────────────────────────────────────────────────────────────────

export interface ReviewBody { kind?: "link" | "requirement" | "control"; id: string; decision: "confirm" | "reject" | "reopen"; note?: string; edits?: Record<string, unknown> }

export function useGraphActions() {
  const qc = useQueryClient();
  return useMemo(() => {
    const refresh = async <T,>(p: Promise<T>) => {
      const result = await p;
      await qc.invalidateQueries({ queryKey: cgKey });
      return result;
    };
    return {
      review: (body: ReviewBody) => refresh(send("POST", "/review", { kind: "link", ...body })),
      bulk: (ids: string[], decision: "confirm" | "reject", note?: string) =>
        refresh(send<{ decided: number }>("POST", "/review/bulk", { ids, decision, note })),
      acceptProposal: (linkId: string) => refresh(send("POST", `/links/${linkId}/accept-proposal`)),
      createLink: (body: { relation: "addresses" | "evidences"; from_type: "control" | "document"; from_id: string; to_type: "obligation" | "control"; to_id: string; attributes?: Record<string, unknown>; note?: string }) =>
        refresh(send<LinkInfo>("POST", "/links", body)),
      createControl: (body: Record<string, unknown>) => refresh(send<ControlDetail>("POST", "/controls", body)),
      updateControl: (id: string, body: Record<string, unknown>) => refresh(send<ControlDetail>("PATCH", `/controls/${id}`, body)),
      setStatus: (lineage: string, body: Record<string, unknown>) => refresh(send<RequirementDetail>("PUT", `/requirements/${lineage}/status`, body)),
      setRole: (documentId: string, role: string, note?: string) => refresh(send("POST", `/documents/${documentId}/role`, { role, note })),
      setEffective: (documentId: string, effective_date: string | null, note?: string) =>
        refresh(send("POST", `/documents/${documentId}/effective-date`, { effective_date, note })),
      shareNewVersion: (documentId: string, note: string) => refresh(send("POST", `/documents/${documentId}/share-new-version`, { note })),
      setProfile: (category_codes: string[]) => refresh(send("PUT", "/profile", { category_codes })),
      acknowledge: (impactId: string, note?: string) => refresh(send("POST", `/impacts/${impactId}/acknowledge`, { note })),
    };
  }, [qc]);
}

/** Download the audit pack (.xlsx) through the binary-safe proxy. */
export async function downloadAuditPack(): Promise<void> {
  const res = await fetch(`${BASE}/export.xlsx`, { cache: "no-store", credentials: "include" });
  if (!res.ok) throw new Error(await detail(res));
  const blob = await res.blob();
  const match = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = match?.[1] ?? "iroko-audit-pack.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
