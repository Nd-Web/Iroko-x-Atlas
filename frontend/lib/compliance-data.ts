/**
 * lib/compliance-data.ts
 *
 * Sector-keyed content for the compliance pages: summary stats, DPIA tracker,
 * DSR queue, and live-checker quick examples. Keeping this here lets the
 * Compliance Agent and Reports pages render either vertical from one source.
 */

import { Sector } from "@/lib/sector";

export interface Stat {
  label: string;
  value: string;
  sub: string;
  accent: string;
  color: string;
}

export interface Dpia {
  name: string;
  lawful: string;
  risk: "High" | "Medium" | "Low";
  status: "in-review" | "draft" | "approved";
}

export interface Dsr {
  ref: string;
  req: string;
  subject: string;
  type: string;
  received: string;
  sla: string;
  urgent: boolean;
}

// ── Summary stats ─────────────────────────────────────────────────────────────

const NETWORK_STATS: Stat[] = [
  { label: "Open DSRs",            value: "3", sub: "subscriber data requests",    accent: "#F79009", color: "#F79009" },
  { label: "Pending DPIAs",        value: "2", sub: "awaiting DPO sign-off",       accent: "#4A55D4", color: "#4A55D4" },
  { label: "NCC Filings due 30d",  value: "2", sub: "QoS & Operating Levy returns", accent: "#F04438", color: "#F04438" },
  { label: "Monitored Operators",  value: "3", sub: "Airtel · Glo · 9mobile",      accent: "#17B26A", color: "#17B26A" },
];

const FINANCIAL_STATS: Stat[] = [
  { label: "Open DSRs",            value: "3", sub: "data subject requests",       accent: "#F79009", color: "#F79009" },
  { label: "Pending DPIAs",        value: "2", sub: "awaiting DPO sign-off",       accent: "#4A55D4", color: "#4A55D4" },
  { label: "CBN Filings due 30d",  value: "2", sub: "Lending & AML returns due",   accent: "#F04438", color: "#F04438" },
  { label: "Monitored Fintechs",   value: "5", sub: "Kuda · Carbon · Moniepoint",  accent: "#17B26A", color: "#17B26A" },
];

export const STATS_BY_SECTOR: Record<Sector, Stat[]> = {
  network: NETWORK_STATS,
  financial: FINANCIAL_STATS,
};

// ── DPIA tracker ──────────────────────────────────────────────────────────────

const NETWORK_DPIA: Dpia[] = [
  { name: "Subscriber Location Analytics Pipeline", lawful: "Legitimate interest", risk: "High",   status: "in-review" },
  { name: "CDR Retention & Lawful Intercept Flow",  lawful: "Legal obligation",    risk: "High",   status: "draft"     },
  { name: "NIN-SIM Biometric Verification Flow",    lawful: "Legal obligation",    risk: "Medium", status: "approved"  },
  { name: "Network Usage Analytics Dashboard v2",   lawful: "Legitimate interest", risk: "Low",    status: "approved"  },
];

const FINANCIAL_DPIA: Dpia[] = [
  { name: "Credit Scoring ML Pipeline v3",  lawful: "Legitimate interest", risk: "High",   status: "in-review" },
  { name: "KYC Biometric Verification Flow", lawful: "Legal obligation",    risk: "High",   status: "draft"     },
  { name: "Loan Repayment Behaviour Model",  lawful: "Contract",            risk: "Medium", status: "approved"  },
  { name: "Savings Analytics Dashboard v2",  lawful: "Legitimate interest", risk: "Low",    status: "approved"  },
];

export const DPIA_BY_SECTOR: Record<Sector, Dpia[]> = {
  network: NETWORK_DPIA,
  financial: FINANCIAL_DPIA,
};

// ── Data subject request queue ────────────────────────────────────────────────

const NETWORK_DSR: Dsr[] = [
  { ref: "DSR-0041", req: "Right to access — full subscriber data & CDR export requested", subject: "Subscriber", type: "Access",        received: "Apr 30", sla: "1 day left", urgent: true  },
  { ref: "DSR-0040", req: "Right to erasure — account, location and CDR data",              subject: "Subscriber", type: "Erasure",       received: "Apr 28", sla: "3 days",     urgent: false },
  { ref: "DSR-0039", req: "Right to rectification — incorrect NIN on SIM record",           subject: "Enterprise", type: "Rectification", received: "Apr 27", sla: "4 days",     urgent: false },
];

const FINANCIAL_DSR: Dsr[] = [
  { ref: "DSR-0041", req: "Right to access — full data export requested",     subject: "Consumer",   type: "Access",        received: "Apr 30", sla: "1 day left", urgent: true  },
  { ref: "DSR-0040", req: "Right to erasure — account and transaction data",  subject: "Consumer",   type: "Erasure",       received: "Apr 28", sla: "3 days",     urgent: false },
  { ref: "DSR-0039", req: "Right to rectification — incorrect NIN on file",   subject: "Enterprise", type: "Rectification", received: "Apr 27", sla: "4 days",     urgent: false },
];

export const DSR_BY_SECTOR: Record<Sector, Dsr[]> = {
  network: NETWORK_DSR,
  financial: FINANCIAL_DSR,
};

// ── Live checker quick examples ───────────────────────────────────────────────

const NETWORK_QUICK_FILLS = [
  "Does a dropped-call rate of 3.2% in the Kano cluster breach NCC QoS thresholds?",
  "Can we retain subscriber call detail records (CDRs) for 5 years without explicit consent?",
  "Is a 30-day service bar for SIMs not linked to a NIN compliant with NCC directives?",
];

const FINANCIAL_QUICK_FILLS = [
  "Can we charge 45% monthly interest on emergency microloans?",
  "Is our 30-day agent network suspension compliant with CBN Circular 2024/001?",
  "Does collecting customer BVN without explicit written consent violate NDPA?",
];

export const QUICK_FILLS_BY_SECTOR: Record<Sector, string[]> = {
  network: NETWORK_QUICK_FILLS,
  financial: FINANCIAL_QUICK_FILLS,
};
