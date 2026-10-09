/**
 * types/chat.ts
 *
 * TypeScript types for the Iroko AI chat interface.
 */

import type { AgentStep } from "./api";

// ── Core chat types ───────────────────────────────────────────────────────────

export interface ChatCitation {
  document_id: string;
  document_title: string;
  excerpt?: string;
  source_url?: string | null;
  chunk_id?: string;
  /** Includes source_kind "iroko_record" + record_url for compliance-graph records. */
  provenance?: Record<string, unknown>;
}

/** The user's verdict on one answer; feeds evaluation and improvement. */
export interface AnswerFeedbackState {
  helpful: boolean;
  reason?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  answer_status?: string;
  reasoning_steps?: AgentStep[];
  citations?: ChatCitation[];
  risk_score?: number;
  timestamp: string;
  interrupted?: boolean;
  suggested_followups?: string[];
  /** Server id of a saved answer; feedback can only be given once it exists. */
  message_id?: string;
  feedback?: AnswerFeedbackState | null;
}

export interface ChatConversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at?: string;
  isPinned?: boolean;
}

// ── Streaming event types ─────────────────────────────────────────────────────

export type StreamEventType = "step" | "final" | "error" | "start" | "token";

export interface StreamStepEvent {
  type: "step";
  agent: string;
  status: "thinking" | "done" | "handoff";
  message: string;
  timestamp: string;
}

export interface StreamFinalEvent {
  type: "final";
  response: string;
  risk_score: number;
  confidence?: string;
  citations?: unknown[];
  reasoning_steps?: AgentStep[];
  timestamp: string;
}

export interface StreamErrorEvent {
  type: "error";
  message: string;
  timestamp: string;
}

export interface StreamStartEvent {
  type: "start";
  message: string;
  timestamp: string;
}

export interface StreamTokenEvent {
  type: "token";
  content: string;
}

export type StreamEvent =
  | StreamStepEvent
  | StreamFinalEvent
  | StreamErrorEvent
  | StreamStartEvent
  | StreamTokenEvent;

// ── UI state types ────────────────────────────────────────────────────────────

export type ChatStatus = "idle" | "streaming" | "error";

export interface SuggestedPrompt {
  label: string;
  query: string;
  icon?: string;
}

// Starting points, not claims about available documents or compliance status.
export const DEFAULT_SUGGESTED_PROMPTS: SuggestedPrompt[] = [
  {
    label: "Understand a regulation",
    query: "Explain the key CBN requirements for a Nigerian microfinance bank, citing the available sources and identifying any gaps.",
  },
  {
    label: "See your document library",
    query: "What documents do you have?",
  },
  {
    label: "Check recent regulatory changes",
    query: "Check official sources for recent Nigerian financial regulatory changes relevant to MFBs and fintechs. State the dates and applicability limits.",
  },
  {
    label: "Explore a compliance risk",
    query: "Help me investigate a compliance risk for my institution. Ask for the licence category and specific breach before estimating any penalty.",
  },
];
