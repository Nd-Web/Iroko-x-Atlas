/**
 * lib/filings-data.ts
 *
 * Single source of truth for Kuda MFB regulatory filings.
 * Both the Compliance Reports page (full grid) and Fintech Compliance Agent
 * page (summary list) import from here so the two views always agree.
 */

export interface Filing {
  name: string;
  due: string;
  status: "in-progress" | "not-started" | "clear" | "submitted";
  regulator: "CBN" | "NDPA" | "SEC";
  progress: number;
  progressColor: string;
}

export const REGULATORY_FILINGS: Filing[] = [
  { name: "CBN Q2 2026 Lending Return",         due: "Jul 15, 2026", status: "in-progress", regulator: "CBN",  progress: 60,  progressColor: "#4A55D4" },
  { name: "CBN Microfinance Capital Return Q2",  due: "Jul 15, 2026", status: "not-started", regulator: "CBN",  progress: 0,   progressColor: "#4A55D4" },
  { name: "NDPA Annual Audit Return 2026",       due: "Jun 30, 2026", status: "not-started", regulator: "NDPA", progress: 0,   progressColor: "#4A55D4" },
  { name: "SEC Digital Assets Activity Report",  due: "Jul 31, 2026", status: "clear",       regulator: "SEC",  progress: 100, progressColor: "#17B26A" },
  { name: "CBN AML/CFT Quarterly Return",        due: "Jul 15, 2026", status: "in-progress", regulator: "CBN",  progress: 45,  progressColor: "#4A55D4" },
  { name: "NDPA Breach Notification Log",        due: "Ongoing",      status: "clear",       regulator: "NDPA", progress: 100, progressColor: "#17B26A" },
];

export const STATUS_LABELS: Record<Filing["status"], string> = {
  "in-progress": "In progress",
  "not-started": "Not started",
  "clear":       "Clear",
  "submitted":   "Submitted",
};
