/**
 * lib/api.ts
 *
 * Client-side typed fetch helper for all backend routes.
 * Attaches the Bearer token automatically.
 *
 * IMPORTANT: This file is safe to import from "use client" components and
 * hooks.  It does NOT use next/headers — all requests go through the Next.js
 * API proxy or the direct backend URL.
 */

import { API_BASE } from "./config";

// ── Token helpers ────────────────────────────────────────────────────────────

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("iroko_token") ?? localStorage.getItem("atlas_token");
}

export function setStoredToken(token: string): void {
  localStorage.setItem("iroko_token", token);
}

export function clearStoredToken(): void {
  localStorage.removeItem("iroko_token");
  localStorage.removeItem("atlas_token");
}

export function getUser(): Record<string, unknown> | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("atlas_user");
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function setUser(user: Record<string, unknown>): void {
  localStorage.setItem("atlas_user", JSON.stringify(user));
}

// ── Base fetch ───────────────────────────────────────────────────────────────

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  const res = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401) {
    clearStoredToken();
    // Do NOT force window.location.href here — AuthContext's refreshUser() already
    // detects 401 on /api/auth/me and redirects to /login. Forcing a redirect here
    // while the proxy still sees a valid iroko_token cookie creates an infinite
    // /login → /dashboard → /login redirect loop.
    throw new Error("Unauthorised");
  }

  if (res.status === 204) return null as T;

  if (!res.ok) {
    let errorMsg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") errorMsg = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        errorMsg = body.detail[0].msg;
      }
    } catch {
      // Couldn't parse JSON, keep generic message
    }
    throw new Error(errorMsg);
  }

  return res.json() as Promise<T>;
}

// ── Convenience methods ──────────────────────────────────────────────────────

export function apiGet<T = unknown>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "GET" });
}

export function apiPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    body: body != null ? JSON.stringify(body) : undefined,
  });
}

export function apiPatch<T = unknown>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "PATCH",
    body: body != null ? JSON.stringify(body) : undefined,
  });
}

export function apiDelete<T = unknown>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "DELETE" });
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  const data = await apiFetch<{ access_token: string; user: Record<string, unknown> }>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
  setStoredToken(data.access_token);
  setUser(data.user);
  return data;
}

// ── SSE Streaming ─────────────────────────────────────────────────────────────

export type SSEEvent =
  | { type: "start"; message: string; timestamp: string }
  | { type: "agent_action"; agent: string; tool: string; description: string; timestamp: string }
  | { type: "token"; content: string }
  | { type: "complete"; answer: string; citations: Citation[]; suggested_followups: string[]; agent_trace: AgentAction[]; duration_ms: number }
  | { type: "error"; message: string };

export interface Citation {
  document_id: string;
  document_title: string;
  excerpt: string;
  relevance_score?: number;
}

export interface AgentAction {
  agent: string;
  tool: string;
  description: string;
  timestamp: string;
}

export async function askStream(
  query: string,
  conversationId: string | null,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE}/api/atlas/ask/stream-http`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, conversation_id: conversationId }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Stream failed: HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data: ")) continue;
      const payload = trimmed.slice(6);
      if (payload === "[DONE]") return;
      try {
        onEvent(JSON.parse(payload) as SSEEvent);
      } catch {
        // skip malformed event
      }
    }
  }
}

// ── Stats & Alerts ────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_documents: number;
  documents_indexed: number;
  total_queries_today: number;
  total_queries_this_week: number;
  active_alerts: number;
  critical_alerts: number;
  avg_query_response_ms: number;
}

export async function getStats(): Promise<DashboardStats> {
  return apiFetch("/api/analytics/stats");
}

export interface Alert {
  id: string;
  title: string;
  summary: string;
  severity: "critical" | "warning" | "info";
  status: string;
  alert_type: string;
  created_at: string;
}

export interface AlertList {
  alerts: Alert[];
  total: number;
  critical_count: number;
  warning_count: number;
}

export async function getAlerts(status = "new", limit = 10): Promise<AlertList> {
  return apiFetch(`/api/alerts?status=${status}&limit=${limit}`);
}

export async function acknowledgeAlert(id: string): Promise<void> {
  await apiFetch(`/api/alerts/${id}/acknowledge`, { method: "PATCH" });
}

export interface KnowledgeGap {
  id: string;
  query: string;
  confidence_score: number;
  created_at: string;
}

export async function getKnowledgeGaps(limit = 10): Promise<{ gaps: KnowledgeGap[]; total: number }> {
  return apiFetch(`/api/analytics/knowledge-gaps?limit=${limit}`);
}

// ── Network heatmap ───────────────────────────────────────────────────────────

export interface HeatmapRegion {
  region: string;
  latitude: number;
  longitude: number;
  site_count: number;
  operational: number;
  degraded: number;
  down: number;
  availability_pct: number;
  active_incidents: number;
  critical_incidents: number;
  status: "operational" | "degraded" | "down";
  subscribers: number;
}

export async function getNetworkHeatmap(): Promise<{ regions: HeatmapRegion[]; total_regions: number }> {
  return apiFetch("/api/network/heatmap");
}

// ── Fraud Intelligence ────────────────────────────────────────────────────────

export interface FraudSummary {
  total_signals: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  total_exposure_ngn: number;
  by_category: Record<string, { count: number; high_count: number; exposure_ngn: number }>;
}

export async function getFraudSummary(): Promise<FraudSummary> {
  return apiFetch("/api/fraud/summary");
}

export async function getDailyBriefing(): Promise<Record<string, unknown>> {
  return apiFetch("/api/atlas/briefing", { method: "POST" });
}

// ── Connectors ────────────────────────────────────────────────────────────────

export type ConnectorType = "sharepoint" | "onedrive" | "microsoft_teams" | "slack" | "servicenow";

export interface Connector {
  id: string;
  connector_type: ConnectorType;
  display_name: string;
  site_id: string | null;
  drive_id: string | null;
  root_folder: string;
  status: "active" | "expired" | "revoked";
  auto_sync: boolean;
  sync_interval_minutes: number;
  last_sync_at: string | null;
  document_count: number;
  created_at: string;
}

export interface DriveItem {
  id: string;
  name: string;
  item_type: "file" | "folder";
  size: number | null;
  mime_type: string | null;
  modified_at: string | null;
  web_url: string | null;
  download_url: string | null;
}

export async function getConnectorAuthUrl(
  connectorType: ConnectorType,
  redirectUri: string,
): Promise<{ auth_url: string; state: string }> {
  return apiFetch(
    `/api/connectors/auth-url?redirect_uri=${encodeURIComponent(redirectUri)}&connector_type=${connectorType}`,
  );
}

export async function createConnector(
  authCode: string,
  connectorType: ConnectorType,
  redirectUri: string,
  displayName?: string,
): Promise<Connector> {
  return apiFetch("/api/connectors", {
    method: "POST",
    body: JSON.stringify({
      auth_code: authCode,
      connector_type: connectorType,
      redirect_uri: redirectUri,
      display_name: displayName,
    }),
  });
}

export async function listConnectors(): Promise<{ connectors: Connector[]; total: number }> {
  return apiFetch("/api/connectors");
}

export async function deleteConnector(id: string): Promise<void> {
  await apiFetch(`/api/connectors/${id}`, { method: "DELETE" });
}

export async function browseConnector(
  id: string,
  folderId?: string,
): Promise<{ connector_id: string; path: string; items: DriveItem[] }> {
  const qs = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  return apiFetch(`/api/connectors/${id}/browse${qs}`);
}

export async function importFiles(
  connectorId: string,
  itemIds: string[],
  department?: string,
): Promise<{ total_imported: number; total_failed: number; results: unknown[] }> {
  return apiFetch(`/api/connectors/${connectorId}/import`, {
    method: "POST",
    body: JSON.stringify({ item_ids: itemIds, department: department ?? "" }),
  });
}

export async function triggerSync(connectorId: string): Promise<{ message: string }> {
  return apiFetch(`/api/connectors/${connectorId}/sync`, { method: "POST" });
}

// ── Re-exports for backward compat with old @/app/lib/api imports ────────────
export { getStoredToken as getToken };
export { clearStoredToken as clearToken };
export { setStoredToken as setToken };
