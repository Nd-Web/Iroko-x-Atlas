/**
 * lib/filings-data.ts
 *
 * Single source of truth for MFB/fintech regulatory filings (CBN · SEC · NDPA).
 * Both the Compliance Reports page (full grid) and Compliance Agent
 * page (summary list) import from here so the two views always agree.
 */

export interface Filing {
  name: string;
  due: string;
  status: "in-progress" | "not-started" | "clear" | "submitted";
  regulator: "CBN" | "SEC" | "NDPA";
  progress: number;
  progressColor: string;
  /** Owning team shown in the report detail view. */
  owner?: string;
  /** One-paragraph context shown in the report detail view. */
  summary?: string;
  /** Next action shown in the report detail view. */
  nextStep?: string;
}

export const REGULATORY_FILINGS: Filing[] = [
  { name: "CBN Quarterly Prudential Return Q1 2026",  due: "Apr 15, 2026", status: "in-progress", regulator: "CBN",  progress: 60,  progressColor: "#4A55D4",
    owner: "Finance/Regulatory",
    summary: "Quarterly prudential return under the CBN Revised Regulatory & Supervisory Guidelines for MFBs. Capital adequacy ratio measured at 9.1% — below the 10% CBN minimum — and must be disclosed with a remediation plan. Late submission attracts an administrative fine of up to ₦2M.",
    nextStep: "Attach the capital-remediation plan and route for CFO sign-off." },
  { name: "CBN AML/CFT Return — Q1 2026",             due: "May 15, 2026", status: "not-started", regulator: "CBN",  progress: 0,   progressColor: "#4A55D4",
    owner: "Compliance/AML",
    summary: "Quarterly Anti-Money Laundering/Combating the Financing of Terrorism return under CBN-AML-001. Includes suspicious-activity monitoring stats and sanctions-screening coverage for the quarter.",
    nextStep: "Generate the draft from the transaction-monitoring log via the Scribe agent." },
  { name: "NDPA Article 24 Annual Review 2026",       due: "Jun 30, 2026", status: "not-started", regulator: "NDPA", progress: 0,   progressColor: "#4A55D4",
    owner: "DPO / Legal",
    summary: "Annual review of the Article 24 processing record is overdue. The new loan-analytics pipeline v2 also requires a DPIA before launch.",
    nextStep: "DPO to complete the record review and sign off." },
  { name: "SEC Nigeria Investor Disclosure Q1",       due: "Jul 31, 2026", status: "clear",       regulator: "SEC",  progress: 100, progressColor: "#17B26A",
    owner: "Legal/Regulatory",
    summary: "Quarterly investor-facing disclosure for SEC-registered fintech activity. Q1 saw a +312% spike in loan-deduction complaints (850 tickets, ₦28.4M disputed) — fully documented with resolution rates.",
    nextStep: "Submitted-ready; awaiting the quarterly window." },
  { name: "CBN Single Obligor & Insider Exposure Return", due: "Jul 15, 2026", status: "in-progress", regulator: "CBN", progress: 45, progressColor: "#4A55D4",
    owner: "Credit/Regulatory",
    summary: "Quarterly exposure return confirming single-obligor and insider-lending limits under CBN-MFB-001 Section 5. Loan book compiled; exposure-limit verification pass outstanding.",
    nextStep: "Verify loan concentrations against the single-obligor limit register." },
  { name: "NDPA Breach Notification Log",             due: "Ongoing",      status: "clear",       regulator: "NDPA", progress: 100, progressColor: "#17B26A",
    owner: "DPO / Legal",
    summary: "Rolling log of notifiable personal-data events. Account-takeover and loan-fraud incidents are assessed against the 72-hour NDPC notification window.",
    nextStep: "No open notifications — continue monitoring." },
];

export const STATUS_LABELS: Record<Filing["status"], string> = {
  "in-progress": "In progress",
  "not-started": "Not started",
  "clear":       "Clear",
  "submitted":   "Submitted",
};
