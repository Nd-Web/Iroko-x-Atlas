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
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning_steps?: AgentStep[];
  citations?: ChatCitation[];
  risk_score?: number;
  timestamp: string;
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

// The four canonical demo questions — each is guaranteed to hit rich seeded
// data (Ikeja RCA, vendor contracts, MoMo complaints, NCC QoS return).
export const DEFAULT_SUGGESTED_PROMPTS: SuggestedPrompt[] = [
  {
    label: "What caused the Ikeja outage?",
    query: "What caused the Ikeja cluster power outage and what did it cost us?",
    icon: "⚡",
  },
  {
    label: "Contracts expiring soon",
    query: "Which vendor contracts expire in the next 90 days?",
    icon: "📄",
  },
  {
    label: "MoMo complaints trend",
    query: "Summarise the MoMo deduction complaints trend in Lagos this quarter",
    icon: "📈",
  },
  {
    label: "NCC QoS return readiness",
    query: "Are we ready to submit the NCC QoS return for Q1 2026?",
    icon: "📋",
  },
];
