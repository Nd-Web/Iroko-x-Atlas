/**
 * types/chat.ts
 *
 * TypeScript types for the Iroko AI chat interface.
 */

import type { AgentStep } from "./api";

// ── Core chat types ───────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning_steps?: AgentStep[];
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

export const DEFAULT_SUGGESTED_PROMPTS: SuggestedPrompt[] = [
  {
    label: "Summarise today's alerts",
    query: "Give me a summary of all active alerts generated today",
    icon: "🔔",
  },
  {
    label: "Any SLA breaches this week?",
    query: "Are there any SLA breaches or violations reported this week?",
    icon: "📋",
  },
  {
    label: "Show high-risk contracts",
    query: "Which contracts have a high risk score or are expiring soon?",
    icon: "📄",
  },
  {
    label: "Network incidents today",
    query: "What network incidents or outages have been reported today?",
    icon: "📡",
  },
];
