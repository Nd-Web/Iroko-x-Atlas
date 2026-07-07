/**
 * lib/filings-data.ts
 *
 * Single source of truth for telecom regulatory filings (NCC · NDPA · FCCPC).
 * Both the Compliance Reports page (full grid) and Compliance Agent
 * page (summary list) import from here so the two views always agree.
 */

export interface Filing {
  name: string;
  due: string;
  status: "in-progress" | "not-started" | "clear" | "submitted";
  regulator: "NCC" | "NDPA" | "FCCPC";
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
  { name: "NCC QoS Quarterly Return Q1 2026",       due: "Apr 14, 2026", status: "in-progress", regulator: "NCC",   progress: 60,  progressColor: "#4A55D4",
    owner: "Legal/Regulatory",
    summary: "Quarterly quality-of-service return. Ikeja cluster availability hit 82.7% during the February feeder outage — below the NCC minimum of 95% — and must be disclosed with the RCA. Late submission attracts ₦5M per day.",
    nextStep: "Attach the Ikeja RCA disclosure and route for sign-off." },
  { name: "NCC Major Incident Report — Ikeja Outage", due: "Jul 15, 2026", status: "not-started", regulator: "NCC",   progress: 0,   progressColor: "#4A55D4",
    owner: "Network Operations",
    summary: "Major-incident report for INC-2026-IKJ-0147 (AES feeder failure, IHS diesel backup SLA miss). Six macro sites affected; drop-call rate peaked at 12.4%.",
    nextStep: "Generate the draft from the RCA document via the Scribe agent." },
  { name: "NDPA Article 24 Annual Review 2026",      due: "Jun 30, 2026", status: "not-started", regulator: "NDPA",  progress: 0,   progressColor: "#4A55D4",
    owner: "DPO / Legal",
    summary: "Annual review of the Article 24 processing record is overdue. The MoMo analytics pipeline v2 also requires a DPIA before launch.",
    nextStep: "DPO to complete the record review and sign off." },
  { name: "FCCPC Consumer Complaints Report Q1",     due: "Jul 31, 2026", status: "clear",       regulator: "FCCPC", progress: 100, progressColor: "#17B26A",
    owner: "Customer Experience",
    summary: "Quarterly consumer-complaints report. Q1 saw a +312% spike in MoMo deduction complaints in Lagos (850 tickets, ₦28.4M disputed) — fully documented with resolution rates.",
    nextStep: "Submitted-ready; awaiting the quarterly window." },
  { name: "NCC Subscriber Data Return Q2",           due: "Jul 15, 2026", status: "in-progress", regulator: "NCC",   progress: 45,  progressColor: "#4A55D4",
    owner: "Legal/Regulatory",
    summary: "Quarterly subscriber registration and data return for Q2 2026. Regional counts compiled; verification pass outstanding.",
    nextStep: "Verify regional subscriber counts against the registration database." },
  { name: "NDPA Breach Notification Log",            due: "Ongoing",      status: "clear",       regulator: "NDPA",  progress: 100, progressColor: "#17B26A",
    owner: "DPO / Legal",
    summary: "Rolling log of notifiable personal-data events. SIM-swap and MoMo agent incidents are assessed against the 72-hour NDPC notification window.",
    nextStep: "No open notifications — continue monitoring." },
];

export const STATUS_LABELS: Record<Filing["status"], string> = {
  "in-progress": "In progress",
  "not-started": "Not started",
  "clear":       "Clear",
  "submitted":   "Submitted",
};
