"use client";

/**
 * app/demo/page.tsx
 *
 * Full pitch-deck product demo — enterprise document intelligence first,
 * with the fintech/MFB compliance configuration as a dedicated section.
 * Self-contained — no AppShell, no auth required.
 * Walk-through narrative with live navigation links into the real app.
 */

import { useState } from "react";
import Link from "next/link";

// ─── Design tokens ───────────────────────────────────────────────────────────

const C = {
  bg:         "#0A0A0B",
  surface:    "#131316",
  border:     "rgba(255,255,255,0.08)",
  brand:      "#FFCB05",
  brandLight: "#38BDF8",
  green:      "#10B981",
  amber:      "#F59E0B",
  red:        "#EF4444",
  muted:      "#9C9CA6",
  sub:        "#7A7A85",
  white:      "#EBEBEF",
};

// ─── Shared primitives ────────────────────────────────────────────────────────

function Tag({ children, color = C.brand }: { children: React.ReactNode; color?: string }) {
  return (
    <span style={{
      display: "inline-block", fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
      textTransform: "uppercase", color, background: `${color}18`,
      border: `1px solid ${color}35`, borderRadius: 999, padding: "3px 10px",
    }}>
      {children}
    </span>
  );
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 16, padding: "28px 26px", ...style,
    }}>
      {children}
    </div>
  );
}

function LiveLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      fontSize: 12, fontWeight: 700, color: C.brandLight,
      textDecoration: "none", padding: "5px 12px", borderRadius: 8,
      background: `${C.brandLight}15`, border: `1px solid ${C.brandLight}30`,
      transition: "background 0.15s",
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: C.green, display: "inline-block", boxShadow: `0 0 6px ${C.green}` }} />
      {children} →
    </Link>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.sub, margin: "0 0 14px" }}>
      {children}
    </p>
  );
}

function Stat({ value, label, color = C.brand }: { value: string; label: string; color?: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: "-0.04em", color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 12, color: C.sub, marginTop: 5 }}>{label}</div>
    </div>
  );
}

// ─── Step nav ─────────────────────────────────────────────────────────────────

const STEPS = [
  { id: 0, label: "The Problem" },
  { id: 1, label: "Meet Iroko" },
  { id: 2, label: "Live Dashboard" },
  { id: 3, label: "Compliance Engine" },
  { id: 4, label: "Risk Monitor" },
  { id: 5, label: "Fraud & AML" },
  { id: 6, label: "Regulatory Filings" },
  { id: 7, label: "Audit Trail" },
  { id: 8, label: "Market Intelligence" },
  { id: 9, label: "How We Onboard You" },
  { id: 10, label: "Pricing & Next Steps" },
];

// ─── Slide content ────────────────────────────────────────────────────────────

function Slide0() {
  return (
    <div style={{ maxWidth: 760, margin: "0 auto" }}>
      <Tag color={C.red}>The Problem</Tag>
      <h1 style={{ fontSize: "clamp(28px,4vw,46px)", fontWeight: 800, lineHeight: 1.15, letterSpacing: "-0.03em", margin: "20px 0 18px", color: "#F7F7F9" }}>
        Your answers exist. They&apos;re buried<br />in a thousand documents.
      </h1>
      <p style={{ fontSize: 17, color: C.muted, lineHeight: 1.7, marginBottom: 48 }}>
        Large organisations run on documents — contracts, incident reports, regulatory returns, complaint
        logs — scattered across drives, inboxes and internal systems in every format. Finding one answer
        is slow. The insight across all of them never surfaces. Decisions wait.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 48 }}>
        {[
          { stat: "Everywhere", label: "documents spread across systems", color: C.brandLight },
          { stat: "Every format", label: "PDFs, scans, spreadsheets, contracts", color: C.amber },
          { stat: "Hours", label: "to manually find a single answer", color: C.red },
          { stat: "Too late", label: "when insight finally reaches a decision", color: C.sub },
        ].map(s => (
          <Card key={s.label} style={{ padding: "22px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.04em", color: s.color, lineHeight: 1 }}>{s.stat}</div>
            <div style={{ fontSize: 12, color: C.sub, marginTop: 7 }}>{s.label}</div>
          </Card>
        ))}
      </div>

      <Card style={{ borderLeft: `3px solid ${C.red}`, padding: "20px 24px" }}>
        <p style={{ margin: 0, fontSize: 14, color: C.white, lineHeight: 1.7 }}>
          <strong style={{ color: C.red }}>The real cost:</strong> a missed contract deadline, an SLA breach
          nobody spotted, or a regulatory filing built on stale data doesn&apos;t just waste hours — it costs
          real money and, in regulated industries, your <strong style={{ color: "#F7F7F9" }}>licence</strong>.
          Iroko exists to make sure that never happens.
        </p>
      </Card>
    </div>
  );
}

function Slide1() {
  const agents = [
    { name: "Ingestion", color: C.brandLight, desc: "Pulls documents from wherever they live — SharePoint, drives, email, core systems — into one indexed corpus." },
    { name: "Understanding", color: C.green, desc: "Parses and extracts meaning regardless of format: PDFs, scans, spreadsheets, contracts. Nothing stays unreadable." },
    { name: "Analytics", color: "#FB923C", desc: "Real-time dashboards and insight generation — trends, anomalies and exposure surface before anyone asks." },
    { name: "Contextual Q&A", color: "#60A5FA", desc: "Staff ask questions in plain language and get answers sourced from the right document — with citations." },
    { name: "Compliance", color: C.red, desc: "The same engine configured for regulatory document workflows — deadlines, thresholds and audit-grade logging." },
  ];

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <Tag color={C.brand}>Meet Iroko AI</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Five agents. One platform.<br />Every document, working for you.
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 36 }}>
        Unlike generic AI tools, Iroko&apos;s agents work as a pipeline over your own verified corpus —
        every answer grounded in your documents, every action logged, nothing invented.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 14, marginBottom: 32 }}>
        {agents.map(a => (
          <Card key={a.name} style={{ padding: "20px", borderTop: `2px solid ${a.color}` }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: a.color, marginBottom: 6 }}>{a.name} Agent</div>
            <p style={{ fontSize: 13, color: C.muted, lineHeight: 1.6, margin: 0 }}>{a.desc}</p>
          </Card>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        {[
          { v: "< 2s", l: "answers with citations" },
          { v: "24/7", l: "agent monitoring" },
          { v: "100%", l: "cited & auditable" },
        ].map(s => (
          <Card key={s.l} style={{ padding: "18px 14px", textAlign: "center" }}>
            <div style={{ fontSize: 26, fontWeight: 800, color: C.brandLight, letterSpacing: "-0.04em" }}>{s.v}</div>
            <div style={{ fontSize: 11, color: C.sub, marginTop: 5 }}>{s.l}</div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Slide2() {
  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.brandLight}>Live Dashboard</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Your entire operation&apos;s knowledge on one screen
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 36 }}>
        The moment you log in, you see live operational signals from your documents — open alerts, contract and filing deadlines, complaint trends, and the intelligence feed — no configuration required.
      </p>

      {/* Mock dashboard preview */}
      <Card style={{ padding: 0, overflow: "hidden", marginBottom: 28 }}>
        <div style={{ background: "#0A0A0B", padding: "14px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.white }}>Web Intelligence Dashboard</div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            {["Regulatory", "Competitor", "Fraud", "Market"].map(t => (
              <span key={t} style={{ fontSize: 10, fontWeight: 600, color: C.sub, padding: "3px 8px", borderRadius: 6, border: `1px solid ${C.border}` }}>{t}</span>
            ))}
          </div>
        </div>
        <div style={{ padding: "20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {[
            { title: "Vendor contract expires — 28 days", cat: "contract", sev: 6 },
            { title: "Site availability below SLA — 82.7%", cat: "operations", sev: 9 },
            { title: "Payment reversal anomaly × 3 agents", cat: "fraud", sev: 7 },
            { title: "Data-protection rule update", cat: "regulatory", sev: 5 },
          ].map(s => {
            const col = s.sev >= 8 ? C.red : s.sev >= 6 ? C.amber : C.brandLight;
            return (
              <div key={s.title} style={{ background: "#0A0A0B", borderRadius: 10, padding: "12px 14px", borderLeft: `3px solid ${col}` }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: col, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>{s.cat} · {s.sev}/10</div>
                <div style={{ fontSize: 12, color: C.white, fontWeight: 500 }}>{s.title}</div>
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <LiveLink href="/dashboard">Open Live Dashboard</LiveLink>
        <LiveLink href="/insights">View Insights Feed</LiveLink>
      </div>
    </div>
  );
}

function Slide3() {
  const checks = [
    { q: "Can we charge 45% monthly interest on emergency microloans?", verdict: "NO-GO", color: C.red,   reg: "CBN Consumer Protection Framework 2022 — interest cap exceeded" },
    { q: "Is collecting BVN without explicit written consent NDPA-compliant?", verdict: "MONITOR", color: C.amber, reg: "NDPA 2023 s.25 — lawful basis required; document consent" },
    { q: "30-day agent suspension for KYC failure — compliant?", verdict: "GO", color: C.green, reg: "CBN Agent Banking Guidelines 2023 — within allowable remediation period" },
  ];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.green}>The Compliance Configuration</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        GO · MONITOR · NO-GO in under 2 seconds
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 32 }}>
        The next few sections show the same five-agent engine configured for regulated finance —
        our fintech &amp; MFB vertical. Ask any compliance question in plain English. Iroko checks it
        against CBN, SEC, NDPA, and BOFIA 2020 simultaneously — and cites the exact regulation section.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 28 }}>
        {checks.map(c => (
          <Card key={c.q} style={{ padding: "18px 20px", borderLeft: `3px solid ${c.color}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 8 }}>
              <p style={{ margin: 0, fontSize: 13, color: C.white, fontWeight: 500, lineHeight: 1.5, flex: 1 }}>"{c.q}"</p>
              <span style={{ fontSize: 11, fontWeight: 800, color: c.color, background: `${c.color}18`, border: `1px solid ${c.color}35`, borderRadius: 6, padding: "3px 10px", whiteSpace: "nowrap", flexShrink: 0 }}>{c.verdict}</span>
            </div>
            <p style={{ margin: 0, fontSize: 11, color: C.sub, lineHeight: 1.5 }}>{c.reg}</p>
          </Card>
        ))}
      </div>

      <Card style={{ background: `${C.brand}12`, border: `1px solid ${C.brand}30`, padding: "16px 20px", marginBottom: 24 }}>
        <p style={{ margin: 0, fontSize: 13, color: C.white, lineHeight: 1.7 }}>
          Every verdict is <strong style={{ color: C.brand }}>SHA-256 sealed</strong> to the audit trail with the regulation section, confidence score, and timestamp — ready for CBN examination in 60 seconds.
        </p>
      </Card>

      <LiveLink href="/compliance/reports">Try Live Compliance Check</LiveLink>
    </div>
  );
}

function Slide4() {
  const kpis = [
    { name: "Lending Compliance",  value: 94.2, threshold: 90.0, unit: "%" },
    { name: "KYC Coverage Rate",   value: 98.7, threshold: 95.0, unit: "%" },
    { name: "CAR (Avg Portfolio)", value: 12.4, threshold: 10.0, unit: "%" },
    { name: "AML Filing Rate",     value: 96.1, threshold: 95.0, unit: "%" },
  ];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.red}>Fintech Risk Operations Centre</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Real-time CBN threshold monitoring — no spreadsheets
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 32 }}>
        Four CBN-mandated KPIs tracked live against their minimum thresholds. The moment any metric drifts, the Watchdog agent fires an alert before your regulator notices.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14, marginBottom: 28 }}>
        {kpis.map(kpi => {
          const passing = kpi.value >= kpi.threshold;
          const color = passing ? C.green : C.red;
          const pct = Math.min(100, (kpi.value / (kpi.threshold * 1.5)) * 100);
          return (
            <Card key={kpi.name} style={{ padding: "20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <span style={{ fontSize: 12, color: C.sub }}>{kpi.name}</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: passing ? "#34d399" : "#f87171", background: passing ? "rgba(52,211,153,0.1)" : "rgba(248,113,113,0.1)", padding: "2px 8px", borderRadius: 999 }}>
                  {passing ? "✓ PASS" : "✗ BREACH"}
                </span>
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color, letterSpacing: "-0.04em", lineHeight: 1, marginBottom: 4 }}>
                {kpi.value}{kpi.unit}
              </div>
              <div style={{ fontSize: 11, color: C.sub, marginBottom: 10 }}>≥ {kpi.threshold}{kpi.unit} CBN min</div>
              <div style={{ height: 5, background: "rgba(255,255,255,0.06)", borderRadius: 999, overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 999, transition: "width 1s ease" }} />
              </div>
            </Card>
          );
        })}
      </div>

      <Card style={{ padding: "16px 20px", marginBottom: 24 }}>
        <p style={{ margin: 0, fontSize: 13, color: C.muted, lineHeight: 1.7 }}>
          These metrics are pulled from your core banking system nightly. No manual entry.
          When Carbon MFB's CAR hit 8.4%, Iroko detected it <strong style={{ color: C.white }}>before CBN published the enforcement action</strong>.
        </p>
      </Card>

      <LiveLink href="/agents/noc">View Risk Operations Centre</LiveLink>
    </div>
  );
}

function Slide5() {
  const flags = [
    { title: "Wallet velocity anomaly — 3 agent wallets", exposure: "₦31.4M", sev: "High", time: "48h window", action: "STR filing recommended" },
    { title: "Duplicate disbursement batch #7 entries", exposure: "₦47.3M", sev: "Critical", time: "Detected now", action: "Suspend & investigate" },
    { title: "Single-obligor exposure — ₦52M vs ₦48M filed", exposure: "₦4M gap", sev: "High", time: "Q2 2026 return", action: "Resubmit return" },
  ];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.amber}>Fraud & AML</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Catch fraud before it becomes a regulatory breach
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 32 }}>
        Iroko's Fraud Sentinel cross-references transaction patterns against NFIU typologies and CBN AML/CFT guidelines. Every flag comes with a recommended action — not just a number.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 28 }}>
        {flags.map(f => {
          const col = f.sev === "Critical" ? C.red : C.amber;
          return (
            <Card key={f.title} style={{ padding: "16px 20px", display: "flex", gap: 16, alignItems: "flex-start" }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: col, marginTop: 5, flexShrink: 0, boxShadow: `0 0 8px ${col}` }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
                  <p style={{ margin: "0 0 4px", fontSize: 13, fontWeight: 600, color: C.white }}>{f.title}</p>
                  <span style={{ fontSize: 10, fontWeight: 700, color: col, background: `${col}15`, padding: "2px 8px", borderRadius: 999, flexShrink: 0 }}>{f.sev}</span>
                </div>
                <div style={{ display: "flex", gap: 16, fontSize: 11, color: C.sub }}>
                  <span>Exposure: <strong style={{ color: C.white }}>{f.exposure}</strong></span>
                  <span>{f.time}</span>
                  <span>→ {f.action}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <Card style={{ background: `${C.amber}10`, border: `1px solid ${C.amber}30`, padding: "16px 20px", marginBottom: 24 }}>
        <p style={{ margin: 0, fontSize: 13, color: C.white, lineHeight: 1.7 }}>
          Nigeria's EFCC reported <strong style={{ color: C.amber }}>₦159B</strong> in bank fraud losses in 2023. Most were detectable from transaction patterns — but no system was watching. Iroko watches.
        </p>
      </Card>

      <LiveLink href="/insights">View Live Fraud Signals</LiveLink>
    </div>
  );
}

function Slide6() {
  const filings = [
    { name: "CBN Q2 2026 Lending Return",        due: "Jul 15, 2026", status: "In progress", progress: 60  },
    { name: "CBN Microfinance Capital Return Q2", due: "Jul 15, 2026", status: "Not started", progress: 0   },
    { name: "NDPA Annual Audit Return 2026",      due: "Jun 30, 2026", status: "Not started", progress: 0   },
    { name: "SEC Digital Assets Activity Report", due: "Jul 31, 2026", status: "Complete",    progress: 100 },
    { name: "CBN AML/CFT Quarterly Return",       due: "Jul 15, 2026", status: "In progress", progress: 45  },
    { name: "NDPA Breach Notification Log",       due: "Ongoing",      status: "Complete",    progress: 100 },
  ];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.brandLight}>Regulatory Filings</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Never miss a CBN filing deadline again
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 32 }}>
        Every return your MFB must file — CBN, SEC, NDPA — tracked in one place with live progress,
        countdown timers, and automatic reminders to your compliance team.
      </p>

      <Card style={{ padding: 0, overflow: "hidden", marginBottom: 24 }}>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}`, fontSize: 12, fontWeight: 700, color: C.sub, display: "grid", gridTemplateColumns: "1fr 100px 100px 90px", gap: 12 }}>
          <span>Filing</span><span>Due date</span><span>Status</span><span>Progress</span>
        </div>
        {filings.map((f, i) => {
          const col = f.progress === 100 ? C.green : f.progress === 0 ? C.sub : C.brand;
          return (
            <div key={f.name} style={{
              display: "grid", gridTemplateColumns: "1fr 100px 100px 90px", gap: 12,
              alignItems: "center", padding: "13px 20px",
              borderBottom: i < filings.length - 1 ? `1px solid ${C.border}` : "none",
            }}>
              <span style={{ fontSize: 12, color: C.white, fontWeight: 500 }}>{f.name}</span>
              <span style={{ fontSize: 11, color: C.sub }}>{f.due}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: col }}>{f.status}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ flex: 1, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 999 }}>
                  <div style={{ width: `${f.progress}%`, height: "100%", background: col, borderRadius: 999 }} />
                </div>
                <span style={{ fontSize: 10, color: C.sub, minWidth: 26 }}>{f.progress}%</span>
              </div>
            </div>
          );
        })}
      </Card>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <LiveLink href="/compliance/reports">Open Filings Dashboard</LiveLink>
        <LiveLink href="/agents/compliance">Compliance Agent</LiveLink>
      </div>
    </div>
  );
}

function Slide7() {
  const logs = [
    { id: "AUD-9F3A", action: "Compliance check — 45% interest rate", verdict: "NO-GO", user: "A. Okonkwo", time: "Today 14:22", hash: "a9f3…e812" },
    { id: "AUD-88C1", action: "DSR-0041 response submitted",          verdict: "GO",    user: "D. Adeyemi", time: "Today 11:05", hash: "88c1…f204" },
    { id: "AUD-7B2E", action: "CBN Q2 Lending Return — progress 60%", verdict: "—",     user: "I. Musa",    time: "Yesterday",  hash: "7b2e…aa91" },
  ];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.green}>Audit Trail</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Tamper-proof. CBN-verifiable in 60 seconds.
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 32 }}>
        Every compliance decision, filing update, and DSR response is SHA-256 hash-chained and timestamped.
        When a CBN examiner walks in, you hand them a verified PDF — not a spreadsheet.
      </p>

      <Card style={{ padding: 0, overflow: "hidden", marginBottom: 24 }}>
        <div style={{ padding: "12px 20px", borderBottom: `1px solid ${C.border}`, background: "rgba(0,0,0,0.2)", display: "grid", gridTemplateColumns: "80px 1fr 70px 80px 80px", gap: 12 }}>
          {["ID", "Action", "Verdict", "Officer", "Hash"].map(h => (
            <span key={h} style={{ fontSize: 10, fontWeight: 700, color: C.sub, textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</span>
          ))}
        </div>
        {logs.map((l, i) => {
          const col = l.verdict === "NO-GO" ? C.red : l.verdict === "GO" ? C.green : C.sub;
          return (
            <div key={l.id} style={{
              display: "grid", gridTemplateColumns: "80px 1fr 70px 80px 80px", gap: 12,
              alignItems: "center", padding: "12px 20px",
              borderBottom: i < logs.length - 1 ? `1px solid ${C.border}` : "none",
            }}>
              <span style={{ fontFamily: "monospace", fontSize: 11, color: C.brandLight }}>{l.id}</span>
              <span style={{ fontSize: 12, color: C.white }}>{l.action}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: col }}>{l.verdict}</span>
              <span style={{ fontSize: 11, color: C.sub }}>{l.user}</span>
              <span style={{ fontFamily: "monospace", fontSize: 10, color: C.sub }}>{l.hash}</span>
            </div>
          );
        })}
      </Card>

      <Card style={{ background: `${C.green}10`, border: `1px solid ${C.green}30`, padding: "16px 20px", marginBottom: 24 }}>
        <p style={{ margin: 0, fontSize: 13, color: C.white, lineHeight: 1.7 }}>
          Hash chaining means altering any record breaks every record after it.
          <strong style={{ color: C.green }}> Integrity is mathematically guaranteed</strong>, not just policy-stated.
        </p>
      </Card>

      <LiveLink href="/audit-trail">View Audit Trail</LiveLink>
    </div>
  );
}

function Slide8() {
  const intel = [
    { org: "Carbon MFB",    signal: "CAR dropped to 8.4% — breach of CBN 10% minimum",              sev: "Critical", col: C.red    },
    { org: "Moniepoint",    signal: "AML/CFT quarterly return overdue by 3 days",                    sev: "Warning",  col: C.amber  },
    { org: "Fairmoney",     signal: "CBN credit bureau check gap in Q2 loan disbursement batch",     sev: "Warning",  col: C.amber  },
    { org: "Opay PSB",      signal: "Consumer complaint SLA exceeded — potential CBN notification",  sev: "Info",     col: C.brandLight },
    { org: "Risevest",      signal: "SEC registration renewal due — 15-day window",                  sev: "Warning",  col: C.amber  },
  ];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.amber}>Market Intelligence</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Know what your competitors are missing — before they do
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 32 }}>
        Iroko's Researcher agent monitors CBN enforcement actions, NDIC reports, and public regulatory bulletins for every major MFB and fintech in Nigeria.
        This isn't just for compliance — it's a competitive edge.
      </p>

      <Card style={{ padding: 0, overflow: "hidden", marginBottom: 24 }}>
        <div style={{ padding: "12px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: C.white }}>Competitor Regulatory Signals</span>
          <span style={{ fontSize: 10, color: "#34d399", fontWeight: 700, background: "rgba(52,211,153,0.1)", padding: "2px 8px", borderRadius: 999 }}>● LIVE</span>
        </div>
        {intel.map((it, i) => (
          <div key={it.org} style={{
            display: "flex", alignItems: "flex-start", gap: 14, padding: "13px 20px",
            borderBottom: i < intel.length - 1 ? `1px solid ${C.border}` : "none",
            borderLeft: `3px solid ${it.col}`,
          }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 4, alignItems: "center" }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: C.white }}>{it.org}</span>
                <span style={{ fontSize: 10, fontWeight: 600, color: it.col, background: `${it.col}15`, padding: "1px 6px", borderRadius: 999 }}>{it.sev}</span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: C.sub }}>{it.signal}</p>
            </div>
          </div>
        ))}
      </Card>

      <Card style={{ padding: "16px 20px", marginBottom: 24 }}>
        <p style={{ margin: 0, fontSize: 13, color: C.muted, lineHeight: 1.7 }}>
          When a competitor gets sanctioned, your board wants to know <em style={{ color: C.white }}>why</em> and <em style={{ color: C.white }}>whether you're exposed to the same risk</em>.
          Iroko answers that question automatically — and in real time.
        </p>
      </Card>

      <LiveLink href="/agents/noc">View Risk Operations Centre</LiveLink>
    </div>
  );
}

function Slide9() {
  const steps = [
    { day: "Day 1", title: "Credentials & connectors", body: "You give us read-only access to your SharePoint/Google Drive and core-system API keys. Iroko indexes your documents overnight." },
    { day: "Day 1", title: "Workflow mapping", body: "Your team fills a 10-minute form: departments, filing obligations, key contacts. Regulated institutions are mapped to their regulatory calendar automatically." },
    { day: "Week 1", title: "Data pipeline live", body: "Nightly core-system export begins. Your KPI metrics populate. Watchdog starts monitoring your operational and regulatory thresholds live." },
    { day: "Week 1", title: "DSR channel configured", body: "Your compliance mailbox is connected. Every incoming data subject request auto-populates the DSR queue with a running 30-day SLA clock." },
    { day: "Ongoing", title: "Agents do the rest", body: "Insights, alerts, competitor signals, and your knowledge graph self-populate. You review and act. Iroko monitors and alerts. Zero manual data entry." },
  ];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto" }}>
      <Tag color={C.brand}>Onboarding</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Live in one week. No implementation project.
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 32 }}>
        No data seeding. No manual configuration. Everything flows from your existing systems through secure connectors.
        Your team spends zero hours on setup — only on acting on what Iroko surfaces.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 28 }}>
        {steps.map((s, i) => (
          <div key={s.title} style={{ display: "flex", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0 }}>
              <div style={{ width: 32, height: 32, borderRadius: "50%", background: C.brand, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800, color: "#0A0A0B", flexShrink: 0 }}>{i + 1}</div>
              {i < steps.length - 1 && <div style={{ width: 1, flex: 1, background: C.border, marginTop: 4 }} />}
            </div>
            <Card style={{ flex: 1, padding: "16px 18px", marginBottom: i < steps.length - 1 ? 0 : 0 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                <Tag color={s.day === "Ongoing" ? C.green : C.brand}>{s.day}</Tag>
                <span style={{ fontSize: 13, fontWeight: 700, color: C.white }}>{s.title}</span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: C.muted, lineHeight: 1.65 }}>{s.body}</p>
            </Card>
          </div>
        ))}
      </div>
    </div>
  );
}

function Slide10() {
  const tiers = [
    {
      name: "Growth",
      price: "₦350K",
      period: "/month",
      color: C.brandLight,
      features: [
        "1 institution",
        "Compliance Engine — unlimited checks",
        "Regulatory filing tracker",
        "Watchdog alerts — 3 KPIs",
        "NDPA DSR queue",
        "Audit trail — 12 months",
        "Email support",
      ],
    },
    {
      name: "Pro",
      price: "₦750K",
      period: "/month",
      color: C.green,
      badge: "Most popular",
      features: [
        "1 institution + 5 competitor watchlist",
        "All 5 agents",
        "Live CBN KPI monitoring — all metrics",
        "AML/CFT filing automation",
        "Knowledge graph",
        "Contract intelligence",
        "Audit trail — 36 months",
        "Dedicated success manager",
      ],
    },
    {
      name: "Enterprise",
      price: "Custom",
      period: "",
      color: "#A78BFA",
      features: [
        "Multi-institution / holding group",
        "Custom agent training on your corpus",
        "Direct CBS API integration",
        "White-label option",
        "SLA guarantee",
        "On-prem deployment available",
        "CBN examination support",
      ],
    },
  ];

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <Tag color={C.brandLight}>Pricing & Next Steps</Tag>
      <h2 style={{ fontSize: "clamp(24px,3.5vw,40px)", fontWeight: 800, letterSpacing: "-0.03em", margin: "18px 0 12px", color: "#F7F7F9" }}>
        Priced for the problem you&apos;re solving
      </h2>
      <p style={{ fontSize: 16, color: C.muted, lineHeight: 1.7, marginBottom: 36 }}>
        Enterprise document-intelligence engagements are scoped to your organisation.
        The fintech &amp; MFB compliance configuration ships as ready-made tiers.
      </p>

      {/* Enterprise document intelligence — custom-quoted lead */}
      <div style={{
        background: `${C.brand}14`, border: `1px solid ${C.brand}40`,
        borderRadius: 16, padding: "26px 24px", marginBottom: 28,
        display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 20,
      }}>
        <div style={{ maxWidth: 560 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.brandLight, marginBottom: 8 }}>Enterprise document intelligence</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 10 }}>
            <span style={{ fontSize: 28, fontWeight: 800, color: "#F7F7F9", letterSpacing: "-0.04em" }}>Custom-quoted</span>
            <span style={{ fontSize: 12, color: C.sub }}>for large organisations</span>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: C.muted, lineHeight: 1.65 }}>
            Scoped to document volume, systems to connect, departments to onboard, and deployment
            model (cloud, private cloud, on-prem). Every engagement starts with a working pilot
            on your own documents.
          </p>
        </div>
        <Link href="/request-demo" style={{
          fontSize: 14, fontWeight: 700, color: "#0A0A0B", textDecoration: "none",
          padding: "13px 28px", borderRadius: 10, background: C.brand,
          display: "inline-block", flexShrink: 0,
        }}>
          Book a call →
        </Link>
      </div>

      {/* Fintech & MFB compliance configuration tiers */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <Tag color={C.green}>Fintech &amp; MFB compliance configuration</Tag>
        <span style={{ fontSize: 12, color: C.sub }}>
          Less than one compliance hire (₦4–6M/year) — works 24 hours a day, never misses a circular.
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16, marginBottom: 36 }}>
        {tiers.map(t => (
          <div key={t.name} style={{
            background: C.surface, border: `1px solid ${t.color}40`,
            borderRadius: 16, padding: "24px 22px", position: "relative",
            boxShadow: "none",
          }}>
            {t.badge && (
              <div style={{ position: "absolute", top: -10, left: "50%", transform: "translateX(-50%)", fontSize: 10, fontWeight: 700, color: "#F7F7F9", background: t.color, padding: "3px 12px", borderRadius: 999, whiteSpace: "nowrap" }}>
                {t.badge}
              </div>
            )}
            <div style={{ fontSize: 13, fontWeight: 700, color: t.color, marginBottom: 10 }}>{t.name}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 20 }}>
              <span style={{ fontSize: 30, fontWeight: 800, color: "#F7F7F9", letterSpacing: "-0.04em" }}>{t.price}</span>
              <span style={{ fontSize: 12, color: C.sub }}>{t.period}</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {t.features.map(f => (
                <div key={f} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <span style={{ color: t.color, fontSize: 13, lineHeight: 1, marginTop: 2, flexShrink: 0 }}>✓</span>
                  <span style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>{f}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div style={{ background: `${C.brand}14`, border: `1px solid ${C.brand}30`, borderRadius: 16, padding: "32px 36px", textAlign: "center" }}>
        <h3 style={{ fontSize: 22, fontWeight: 800, color: "#F7F7F9", letterSpacing: "-0.02em", margin: "0 0 10px" }}>
          Start your 30-day pilot — free
        </h3>
        <p style={{ fontSize: 14, color: C.muted, margin: "0 0 24px", lineHeight: 1.65 }}>
          We onboard you with your own filing data, connect to your CBS, and run live for 30 days.
          No payment until you're satisfied. No sales pressure.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/compliance/reports" style={{ fontSize: 14, fontWeight: 700, color: "#0A0A0B", textDecoration: "none", padding: "13px 28px", borderRadius: 10, background: C.brand, display: "inline-block" }}>
            Run a Live Compliance Check →
          </Link>
          <Link href="/dashboard" style={{ fontSize: 14, fontWeight: 700, color: C.white, textDecoration: "none", padding: "13px 28px", borderRadius: 10, border: `1.5px solid ${C.border}`, display: "inline-block" }}>
            Explore the Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}

const SLIDE_COMPONENTS = [
  Slide0, Slide1, Slide2, Slide3, Slide4,
  Slide5, Slide6, Slide7, Slide8, Slide9, Slide10,
];

// ─── Page shell ───────────────────────────────────────────────────────────────

export default function DemoPage() {
  const [step, setStep] = useState(0);
  const SlideComp = SLIDE_COMPONENTS[step];

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: "#F7F7F9", fontFamily: "system-ui,-apple-system,sans-serif" }}>

      {/* Top nav */}
      <nav style={{ position: "sticky", top: 0, zIndex: 50, background: "rgba(10,10,11,0.92)", backdropFilter: "blur(12px)", borderBottom: `1px solid ${C.border}`, padding: "0 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", height: 56, display: "flex", alignItems: "center", gap: 16 }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <div style={{ width: 30, height: 30, background: C.brand, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <svg width="16" height="16" viewBox="0 0 22 22" fill="none">
                <path d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z" stroke="#0A0A0B" strokeWidth="1.5" strokeLinejoin="round" />
                <circle cx="11" cy="10.5" r="2.25" fill="#0A0A0B" />
              </svg>
            </div>
            <span style={{ fontSize: 15, fontWeight: 800, color: "#F7F7F9", letterSpacing: "-0.01em" }}>Iroko AI</span>
            <span style={{ fontSize: 10, fontWeight: 600, color: C.sub, background: C.border, padding: "2px 7px", borderRadius: 999, marginLeft: 2 }}>Product Demo</span>
          </div>

          {/* Step pills — scrollable on mobile */}
          <div style={{ flex: 1, display: "flex", gap: 4, overflowX: "auto", padding: "4px 0", scrollbarWidth: "none" }}>
            {STEPS.map(s => (
              <button key={s.id} onClick={() => setStep(s.id)} style={{
                flexShrink: 0, fontSize: 11, fontWeight: 600, padding: "5px 11px", borderRadius: 7,
                border: "none", cursor: "pointer", transition: "all 0.15s",
                background: step === s.id ? C.brand : "transparent",
                color: step === s.id ? "#0A0A0B" : C.sub,
                outline: "none",
              }}>
                {s.label}
              </button>
            ))}
          </div>

          {/* Live app link */}
          <Link href="/dashboard" style={{ flexShrink: 0, fontSize: 12, fontWeight: 700, color: "#0A0A0B", textDecoration: "none", padding: "6px 14px", borderRadius: 8, background: C.brand, display: "none" }}>
            Live App →
          </Link>
        </div>
      </nav>

      {/* Progress bar */}
      <div style={{ height: 2, background: C.border }}>
        <div style={{ height: "100%", background: C.brand, transition: "width 0.3s ease", width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </div>

      {/* Slide content */}
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "60px 24px 80px" }}>
        <SlideComp />
      </main>

      {/* Bottom navigation */}
      <div style={{ position: "sticky", bottom: 0, background: "rgba(10,10,11,0.95)", backdropFilter: "blur(12px)", borderTop: `1px solid ${C.border}`, padding: "14px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <button
            onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={step === 0}
            style={{ fontSize: 13, fontWeight: 600, color: step === 0 ? C.sub : C.white, background: "transparent", border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 18px", cursor: step === 0 ? "not-allowed" : "pointer", opacity: step === 0 ? 0.4 : 1 }}
          >
            ← Back
          </button>

          <div style={{ display: "flex", gap: 6 }}>
            {STEPS.map(s => (
              <button key={s.id} onClick={() => setStep(s.id)} style={{
                width: step === s.id ? 20 : 6, height: 6, borderRadius: 999,
                background: step === s.id ? C.brand : C.border,
                border: "none", cursor: "pointer", padding: 0, transition: "all 0.2s",
              }} />
            ))}
          </div>

          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep(s => Math.min(STEPS.length - 1, s + 1))}
              style={{ fontSize: 13, fontWeight: 700, color: "#0A0A0B", background: C.brand, border: "none", borderRadius: 8, padding: "8px 18px", cursor: "pointer" }}
            >
              Next →
            </button>
          ) : (
            <Link href="/compliance/reports" style={{ fontSize: 13, fontWeight: 700, color: "#F7F7F9", background: C.green, textDecoration: "none", borderRadius: 8, padding: "8px 18px" }}>
              Run Live Check →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
