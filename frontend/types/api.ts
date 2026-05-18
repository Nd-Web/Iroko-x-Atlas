/**
 * types/api.ts
 *
 * Full TypeScript type definitions for all Iroko AI API responses.
 * These mirror the backend Pydantic / SQLAlchemy models exactly.
 */

// ── Core entities ─────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "analyst" | "viewer" | "superadmin";
  org_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  plan: "starter" | "professional" | "enterprise";
  created_at: string;
}

export interface Document {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  file_size: number | null;
  department: string | null;
  tags: string[];
  status: "pending" | "processing" | "indexed" | "failed";
  blob_url: string | null;
  chunk_count: number;
  error_message: string | null;
  uploaded_by_id: string | null;
  created_at: string;
  updated_at: string;
  query_count?: number;
}

export interface Alert {
  id: string;
  title: string;
  summary: string;
  severity: "critical" | "warning" | "info";
  status: "new" | "acknowledged" | "resolved" | "dismissed";
  alert_type: string;
  suggested_actions: string[];
  related_document_ids: string[];
  organisation: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface AlertList {
  alerts: Alert[];
  total: number;
  critical_count: number;
  warning_count: number;
}

export interface Insight {
  id: string;
  org_id: string | null;
  document_id: string | null;
  title: string;
  summary: string;
  category: string;
  severity: number; // 1–10
  agent_source: string;
  status: "new" | "reviewed" | "dismissed";
  created_at: string;
}

export interface InsightListResponse {
  insights: Insight[];
  total: number;
  page: number;
  page_size: number;
}

export interface DataSource {
  id: string;
  org_id: string | null;
  name: string;
  type: "sharepoint" | "servicenow" | "slack" | "teams" | "onedrive" | "upload";
  status: "connected" | "disconnected" | "syncing" | "error";
  last_sync_at: string | null;
  config: Record<string, unknown>;
  created_at: string;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  reasoning_steps: AgentStep[] | null;
  risk_score: number | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

// ── Agents ────────────────────────────────────────────────────────────────────

export interface AgentStep {
  agent: string;
  status: "thinking" | "done" | "handoff" | "error";
  message: string;
  timestamp: string;
}

export interface AgentStatus {
  name: string;
  display_name: string;
  last_run: string | null;
  total_runs: number;
  avg_response_time: number;
  status: "idle" | "running" | "error";
}

export interface AgentStatusResponse {
  agents: AgentStatus[];
  timestamp: string;
}

export interface ReasoningChainResponse {
  query: string;
  reasoning_chain: AgentStep[];
  final_response: string;
  risk_score: number;
  confidence: "high" | "medium" | "low";
  duration_ms: number;
}

// ── Search ────────────────────────────────────────────────────────────────────

export interface SearchResult {
  content: string;
  source: string;
  score: number;
  document_id: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface AnalyticsData {
  total_documents: number;
  documents_indexed: number;
  total_queries_today: number;
  total_queries_this_week: number;
  active_alerts: number;
  critical_alerts: number;
  avg_query_response_ms: number;
}

// ── Connectors ────────────────────────────────────────────────────────────────

export type ConnectorType =
  | "sharepoint"
  | "onedrive"
  | "microsoft_teams"
  | "slack"
  | "servicenow";

export type ConnectorStatus = "active" | "expired" | "revoked";

export interface Connector {
  id: string;
  connector_type: ConnectorType;
  display_name: string;
  site_id: string | null;
  drive_id: string | null;
  root_folder: string;
  status: ConnectorStatus;
  auto_sync: boolean;
  sync_interval_minutes: number;
  last_sync_at: string | null;
  document_count: number;
  created_at: string;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ── Network intelligence ──────────────────────────────────────────────────────

export interface NetworkSite {
  id: string;
  name: string;
  region: string;
  latitude: number;
  longitude: number;
  status: "operational" | "degraded" | "down";
  active_incidents: number;
}

export interface NetworkHealthResponse {
  overall_score: number; // 0–100
  ran_health: number;
  core_health: number;
  transmission_health: number;
  sites: NetworkSite[];
  timestamp: string;
}
