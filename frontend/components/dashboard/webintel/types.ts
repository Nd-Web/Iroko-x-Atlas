/**
 * components/dashboard/webintel/types.ts
 *
 * Shared TypeScript interfaces for the Web Intelligence dashboard.
 */

export type SignalCategory =
  | "regulatory"
  | "competitor"
  | "vendor_risk"
  | "fraud"
  | "market";

export interface Signal {
  id?: string;
  title: string;
  snippet?: string;
  description?: string;
  url?: string;
  source?: string;
  risk_level?: "HIGH" | "MEDIUM" | "LOW" | string;
  detected_at?: string;
  signal_type?: string;
}

export interface SignalsResponse {
  regulatory: Signal[];
  competitor: Signal[];
  vendor_risk: Signal[];
  fraud: Signal[];
  market: Signal[];
  mock?: boolean;
}

export interface VerdictViolation {
  regulation_id: string;
  section: string;
  reason: string;
}

export interface VerdictOutput {
  verdict: "GO" | "NO-GO" | "MONITOR" | string;
  compliant: boolean;
  confidence_score?: number;
  violations: VerdictViolation[];
  recommended_actions?: string[];
  ncc_refs?: string[];
  finding?: {
    summary?: string;
    action_type?: string;
    ncc_regulation_ref?: string;
  };
  color?: string;
  label?: string;
  generated_at?: string;
}

export interface AuditEntry {
  id: string;
  agent_name: string;
  action_type: string;
  decision_summary: string;
  verdict?: string;
  ncc_ref?: string;
  confidence?: number;
  workspace_id?: string;
  chain_hash?: string;
  previous_hash?: string;
  created_at: string;
}

export interface AuditTrailResponse {
  entries: AuditEntry[];
  total?: number;
  chain_valid?: boolean;
  chain_integrity?: {
    valid: boolean;
    checked_entries: number;
    broken_at?: string;
  };
}

export type TabId = "signals" | "compliance" | "audit";
