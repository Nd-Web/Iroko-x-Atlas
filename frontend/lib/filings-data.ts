/**
 * lib/filings-data.ts
 *
 * Single source of truth for regulatory filings, keyed by compliance sector.
 * Both the Compliance Reports page (full grid) and the Compliance Agent page
 * (summary list) import from here so the two views always agree.
 *
 *   - network   → MTN Nigeria filings (NCC QoS/levy/SIM returns + NDPA).
 *   - financial → Kuda MFB filings (CBN/SEC returns + NDPA).
 */

import { Sector } from "@/lib/sector";

export interface Filing {
  name: string;
  due: string;
  status: "in-progress" | "not-started" | "clear" | "submitted";
  regulator: "CBN" | "NDPA" | "SEC" | "NCC";
  progress: number;
  progressColor: string;
}

const NETWORK_FILINGS: Filing[] = [
  { name: "NCC Q2 2026 Quality of Service Return", due: "Jul 15, 2026", status: "in-progress", regulator: "NCC",  progress: 60,  progressColor: "#4A55D4" },
  { name: "NCC Annual Operating Levy Filing 2026",  due: "Jul 31, 2026", status: "not-started", regulator: "NCC",  progress: 0,   progressColor: "#4A55D4" },
  { name: "NDPA Annual Audit Return 2026",          due: "Jun 30, 2026", status: "not-started", regulator: "NDPA", progress: 0,   progressColor: "#4A55D4" },
  { name: "NCC NIN-SIM Integrity Audit Q2 2026",    due: "Jul 15, 2026", status: "in-progress", regulator: "NCC",  progress: 45,  progressColor: "#4A55D4" },
  { name: "NCC Consumer Complaints Return Q2",       due: "Jul 15, 2026", status: "clear",       regulator: "NCC",  progress: 100, progressColor: "#17B26A" },
  { name: "NDPA Breach Notification Log",            due: "Ongoing",      status: "clear",       regulator: "NDPA", progress: 100, progressColor: "#17B26A" },
];

const FINANCIAL_FILINGS: Filing[] = [
  { name: "CBN Q2 2026 Lending Return",         due: "Jul 15, 2026", status: "in-progress", regulator: "CBN",  progress: 60,  progressColor: "#4A55D4" },
  { name: "CBN Microfinance Capital Return Q2",  due: "Jul 15, 2026", status: "not-started", regulator: "CBN",  progress: 0,   progressColor: "#4A55D4" },
  { name: "NDPA Annual Audit Return 2026",       due: "Jun 30, 2026", status: "not-started", regulator: "NDPA", progress: 0,   progressColor: "#4A55D4" },
  { name: "SEC Digital Assets Activity Report",  due: "Jul 31, 2026", status: "clear",       regulator: "SEC",  progress: 100, progressColor: "#17B26A" },
  { name: "CBN AML/CFT Quarterly Return",        due: "Jul 15, 2026", status: "in-progress", regulator: "CBN",  progress: 45,  progressColor: "#4A55D4" },
  { name: "NDPA Breach Notification Log",        due: "Ongoing",      status: "clear",       regulator: "NDPA", progress: 100, progressColor: "#17B26A" },
];

export const FILINGS_BY_SECTOR: Record<Sector, Filing[]> = {
  network: NETWORK_FILINGS,
  financial: FINANCIAL_FILINGS,
};

/** Back-compat default (financial). Prefer FILINGS_BY_SECTOR[sector]. */
export const REGULATORY_FILINGS = FINANCIAL_FILINGS;

export const STATUS_LABELS: Record<Filing["status"], string> = {
  "in-progress": "In progress",
  "not-started": "Not started",
  "clear":       "Clear",
  "submitted":   "Submitted",
};
