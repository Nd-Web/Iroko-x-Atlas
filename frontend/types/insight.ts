/**
 * types/insight.ts
 *
 * TypeScript types for the Iroko AI Insights feature.
 */

// ── Core insight type ─────────────────────────────────────────────────────────

export type InsightStatus = "new" | "reviewed" | "dismissed";

export interface Insight {
  id: string;
  org_id: string | null;
  document_id?: string | null;
  title: string;
  summary: string;
  category: string;
  severity: number; // 1 (low) – 10 (critical)
  agent_source: string;
  status: InsightStatus;
  created_at: string;
}

// ── Filters ───────────────────────────────────────────────────────────────────

export interface InsightFilters {
  category?: string;
  severity_min?: number;
  severity_max?: number;
  status?: InsightStatus | "all";
  search?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

export const INSIGHT_CATEGORIES = [
  "All",
  "SLA",
  "compliance",
  "contract",
  "network",
  "complaints",
  "fraud",
  "regulatory",
] as const;

export type InsightCategory = (typeof INSIGHT_CATEGORIES)[number];

/** Map a severity 1–10 to a colour hex for dark-theme rendering. */
export function getSeverityColor(severity: number): string {
  if (severity >= 8) return "#EF4444"; // red
  if (severity >= 5) return "#F59E0B"; // amber
  return "#10B981";                    // green
}

/** Return a label for a severity band. */
export function getSeverityLabel(severity: number): string {
  if (severity >= 8) return "Critical";
  if (severity >= 5) return "High";
  if (severity >= 3) return "Medium";
  return "Low";
}
