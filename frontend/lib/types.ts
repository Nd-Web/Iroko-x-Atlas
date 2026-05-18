/**
 * lib/types.ts
 *
 * Shared TypeScript types that mirror the AtlasCore API response shapes.
 * Import from here instead of duplicating type definitions across files.
 */

/** A registered user as returned by /api/auth/me and /api/auth/login */
export interface User {
  id: string;
  email: string;
  full_name: string;
  organisation: string;
  department: string;
  /** e.g. "superadmin" | "admin" | "analyst" | "viewer" */
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

/** Response body for /api/auth/login and /api/auth/accept-invite */
export interface AuthTokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

/** Response body for GET /api/auth/invite/{token} */
export interface InviteTokenPayload {
  valid: boolean;
  email: string;
  role: string;
  department: string;
  invited_by: string;
  expires_at: string;
}

/** A single invitation record from GET /api/auth/invitations */
export interface Invitation {
  id: string;
  email: string;
  role: string;
  department: string;
  invited_by: string;
  expires_at: string;
  used_at: string | null;
  created_at: string;
}

/** Response body for GET /api/auth/invitations */
export interface InvitationsResponse {
  invitations: Invitation[];
  total: number;
}

/** Payload for PATCH /api/auth/me */
export interface UpdateMePayload {
  full_name?: string;
  department?: string;
  role?: string;
}

/** Response body for GET /api/users */
export interface UserListResponse {
  users: User[];
  total: number;
}

/** Payload for PATCH /api/users/{user_id} */
export interface UpdateUserRequest {
  full_name?: string;
  organisation?: string;
  department?: string;
  role?: string;
}

/** Payload for POST /api/auth/invite */
export interface InviteRequest {
  email: string;
  role: string;
  department: string;
  personal_message?: string;
}

/** Payload for POST /api/auth/accept-invite */
export interface AcceptInviteRequest {
  token: string;
  full_name: string;
  password: string;
}

// ─── Atlas AI types ───────────────────────────────────────────────────────────

/** A single step in the multi-agent execution trace */
export interface AgentTraceStep {
  agent: string;
  tool: string;
  description: string;
  args?: Record<string, unknown>;
  result_preview?: string | null;
  duration_ms?: number | null;
  timestamp: string;
}

/** A cited source chunk returned by the AI */
export interface Citation {
  id?: string;
  source: string;
  excerpt: string;
  chunk_id?: string;
  document_id?: string;
  relevance_score?: number;
}

/** Request body for POST /api/atlas/ask and POST /api/atlas/ask/stream */
export interface AtlasAskRequest {
  query: string;
  conversation_id?: string;
  department_filter?: string;
  stream?: boolean;
}

/** One region's live network health — returned in map_data on network queries */
export interface RegionHealth {
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

/** Response body for POST /api/atlas/ask (non-streaming) */
export interface AtlasAskResponse {
  conversation_id: string;
  message_id: string;
  agent_name?: string;
  answer: string;
  agent_trace: AgentTraceStep[];
  citations: Citation[];
  suggested_followups: string[];
  duration_ms: number;
  duration_text?: string;
  created_at: string;
  map_data?: RegionHealth[];
  fraud_data?: FraudSummary;
}

/** A single conversation summary from GET /api/atlas/conversations */
export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

/** Response body for GET /api/atlas/conversations */
export interface ConversationsResponse {
  conversations: ConversationSummary[];
}

// ─── Document types ──────────────────────────────────────────────────────────

/** A single document record as returned by /api/documents and /api/documents/{id} */
export interface DocumentResponse {
  id: string;
  filename: string;
  file_type: string | null;
  doc_type: string | null;
  department: string | null;
  status: string;
  language: string | null;
  classification: string | null;
  file_size: number | null;
  page_count: number | null;
  source: string | null;
  blob_url: string | null;
  created_at: string;
  updated_at: string;
}

/** Response body for GET /api/documents */
export interface DocumentListResponse {
  documents: DocumentResponse[];
  total: number;
  page: number;
  page_size: number;
}

/** Request body for POST /api/documents/search */
export interface DocumentSearchRequest {
  q: string;
  top?: number;
  doc_type?: string | null;
  classification?: string | null;
  source?: string | null;
  rerank?: boolean;
}

/** A single result from the hybrid search endpoint */
export interface DocumentSearchResult {
  chunk_id: string;
  doc_id: string;
  title: string;
  excerpt: string | null;
  source: string | null;
  blob_url: string | null;
  department: string | null;
  doc_type: string | null;
  language: string | null;
  classification: string | null;
  chunk_index: number;
  search_score: number | null;
  rerank_score: number | null;
  created_at: string;
  highlights?: string[];
}

/** Response body for GET|POST /api/documents/search */
export interface DocumentSearchResponse {
  query: string;
  total_hits: number;
  results: DocumentSearchResult[];
  knowledge_gap: boolean;
  confidence: number;
}

/** Response body for GET /api/documents/analytics */
export interface DocumentAnalyticsResponse {
  total_documents: number;
  total_chunks: number;
  total_size_bytes: number;
  indexed_rate: number;
  status_breakdown: {
    indexed: number;
    processing: number;
    failed: number;
    pending: number;
  };
  by_file_type: { file_type: string; count: number }[];
  by_department: { department: string; count: number }[];
  upload_trend: { date: string; count: number }[];
  failed_documents: {
    id: string;
    title: string;
    filename: string;
    error_message: string;
    created_at: string;
  }[];
}

// ─── Analytics types ─────────────────────────────────────────────────────────

/** A single activity entry from GET /api/analytics/activity */
export interface ActivityItem {
  id: string;
  user_name: string;
  user_email: string;
  action: string;
  resource: string;
  details: Record<string, string>;
  /** ISO-8601 timestamp */
  timestamp: string;
}

/** Response body for GET /api/analytics/activity */
export interface ActivityFeedResponse {
  activities: ActivityItem[];
  total: number;
}

// ─── Fraud Intelligence types ─────────────────────────────────────────────────

export interface FraudSignal {
  id: string;
  category: string;
  risk: "HIGH" | "MEDIUM" | "LOW";
  title: string;
  detail: string;
  region: string | null;
  amount_ngn: number | null;
  detected_at: string;
  status: string;
  doc_ref: string;
}

export interface FraudSummary {
  total_signals: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  total_exposure_ngn: number;
  by_category: Record<string, { count: number; high_count: number; exposure_ngn: number }>;
  signals: FraudSignal[];
}

// ─── SSE event shapes (POST /api/atlas/ask/stream-http) ──────────────────────

export interface SseStartEvent {
  type: "start";
  message: string;
  timestamp: string;
}

export interface SseAgentActionEvent {
  type: "agent_action";
  agent: string;
  tool: string;
  description: string;
  timestamp: string;
}

export interface SseTokenEvent {
  type: "token";
  content: string;
}

/** The final SSE event — mirrors AtlasAskResponse plus a type discriminant */
export interface SseCompleteEvent extends AtlasAskResponse {
  type: "complete";
}

export type SseEvent =
  | SseStartEvent
  | SseAgentActionEvent
  | SseTokenEvent
  | SseCompleteEvent;
