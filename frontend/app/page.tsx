"use client";

import Link from "next/link";
import { useState } from "react";

const LOGO = (
  <div className="flex items-center gap-2.5">
    <div
      className="size-9 rounded-[10px] flex items-center justify-center shrink-0"
      style={{
        background: "#4A55D4",
        boxShadow: "0 0 0 1px rgba(255,255,255,0.12), 0 4px 12px rgba(74,85,212,0.4)",
      }}
    >
      <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
        <path d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round" fill="none" />
        <circle cx="11" cy="10.5" r="2.25" fill="white" />
      </svg>
    </div>
    <div>
      <p className="text-[15px] font-bold text-white tracking-tight leading-none">Iroko AI</p>
      <p className="text-[10px] text-white/40 leading-none mt-0.5">Document Intelligence</p>
    </div>
  </div>
);

const NAV_LINKS = [
  { label: "Platform",  href: "#features" },
  { label: "Verticals", href: "#use-cases" },
  { label: "Compliance", href: "#compliance" },
  { label: "Pricing",   href: "#pricing" },
];

export default function HomePage() {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ background: "#080B14", minHeight: "100vh", fontFamily: "DM Sans, ui-sans-serif, sans-serif", color: "#fff" }}>

      {/* ── Navbar ── */}
      <header style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 50,
        height: 56,
        display: "flex", alignItems: "center",
        padding: "0 24px",
        background: "rgba(8,11,20,0.8)",
        backdropFilter: "blur(16px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        <div style={{ maxWidth: 1100, width: "100%", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {LOGO}

          <nav style={{ display: "flex", alignItems: "center", gap: 28 }} className="hidden md:flex">
            {NAV_LINKS.map(({ label, href }) => (
              <a key={label} href={href}
                style={{ fontSize: 13, fontWeight: 500, color: "rgba(255,255,255,0.45)", textDecoration: "none", transition: "color .15s" }}
                onMouseEnter={e => (e.currentTarget.style.color = "#fff")}
                onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.45)")}>
                {label}
              </a>
            ))}
          </nav>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }} className="hidden md:flex">
            <Link href="/login" style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.5)", textDecoration: "none", padding: "7px 14px", borderRadius: 8, transition: "color .15s" }}>
              Sign in
            </Link>
            <Link href="/login" style={{
              fontSize: 13, fontWeight: 600, color: "#fff", textDecoration: "none",
              padding: "7px 16px", borderRadius: 8,
              background: "#4A55D4", border: "1px solid rgba(255,255,255,0.12)",
            }}>
              Request access
            </Link>
          </div>

          {/* Mobile burger */}
          <button onClick={() => setOpen(v => !v)} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.5)", padding: 4 }} className="md:hidden">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              {open
                ? <path d="M4 4l12 12M16 4L4 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                : <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />}
            </svg>
          </button>
        </div>
      </header>

      {/* Mobile menu */}
      {open && (
        <div style={{
          position: "fixed", top: 56, left: 0, right: 0, zIndex: 40,
          background: "#0C111D", borderBottom: "1px solid rgba(255,255,255,0.07)",
          padding: 16, display: "flex", flexDirection: "column", gap: 4,
        }} className="md:hidden">
          {NAV_LINKS.map(({ label, href }) => (
            <a key={label} href={href} onClick={() => setOpen(false)}
              style={{ fontSize: 14, fontWeight: 500, color: "rgba(255,255,255,0.6)", textDecoration: "none", padding: "10px 12px", borderRadius: 8 }}>
              {label}
            </a>
          ))}
          <div style={{ marginTop: 8, paddingTop: 12, borderTop: "1px solid rgba(255,255,255,0.07)", display: "flex", flexDirection: "column", gap: 8 }}>
            <Link href="/login" style={{ textAlign: "center", fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.6)", textDecoration: "none", padding: "10px", borderRadius: 8, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>Sign in</Link>
            <Link href="/login" style={{ textAlign: "center", fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none", padding: "10px", borderRadius: 8, background: "#4A55D4" }}>Request access</Link>
          </div>
        </div>
      )}

      {/* ── Hero ── */}
      <section style={{ position: "relative", paddingTop: 140, paddingBottom: 80, paddingLeft: 24, paddingRight: 24, overflow: "hidden" }}>
        {/* Grid lines background */}
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none",
          backgroundImage: "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          maskImage: "radial-gradient(ellipse 80% 60% at 50% 0%, black 0%, transparent 100%)",
        }} />
        {/* Glow */}
        <div style={{
          position: "absolute", top: -100, left: "50%", transform: "translateX(-50%)",
          width: 800, height: 500, borderRadius: "50%",
          background: "radial-gradient(circle, rgba(74,85,212,0.3) 0%, transparent 70%)",
          pointerEvents: "none",
        }} />

        <div style={{ maxWidth: 1100, margin: "0 auto", position: "relative" }}>
          {/* Badge */}
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "5px 12px", borderRadius: 99, marginBottom: 24,
            background: "rgba(74,85,212,0.12)", border: "1px solid rgba(74,85,212,0.28)",
            fontSize: 12, fontWeight: 600, color: "#818CF8",
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34D399", flexShrink: 0, animation: "pulse 2s ease infinite" }} />
            Five AI agents · Real-time enterprise document intelligence
          </div>

          {/* Headline */}
          <h1 style={{
            fontSize: "clamp(36px, 5vw, 60px)", fontWeight: 900,
            lineHeight: 1.08, letterSpacing: "-0.035em",
            margin: "0 0 20px", maxWidth: 720,
          }}>
            Turn scattered documents into{" "}
            <span style={{
              background: "linear-gradient(135deg, #818CF8 0%, #4A55D4 100%)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>
              real-time answers.
            </span>
          </h1>

          <p style={{ fontSize: 17, color: "rgba(255,255,255,0.45)", lineHeight: 1.75, maxWidth: 520, margin: "0 0 36px" }}>
            Iroko AI ingests the documents spread across your organisation&apos;s systems, understands them
            in any format, and answers your team&apos;s questions with cited evidence — while live dashboards
            turn what&apos;s inside them into operational insight.
          </p>

          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <Link href="/login" style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none",
              padding: "11px 22px", borderRadius: 10,
              background: "#4A55D4", border: "1px solid rgba(255,255,255,0.12)",
              boxShadow: "0 0 32px rgba(74,85,212,0.35)",
            }}>
              Request access
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
            <Link href="/request-demo" style={{
              display: "inline-flex", alignItems: "center",
              fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.55)", textDecoration: "none",
              padding: "11px 22px", borderRadius: 10,
              background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)",
            }}>
              Request live demo
            </Link>
          </div>

          {/* Stats row */}
          <div style={{
            marginTop: 56, display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 1, background: "rgba(255,255,255,0.06)",
            borderRadius: 16, overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.06)",
          }}>
            {[
              { n: "5",    label: "Specialist AI agents" },
              { n: "<2s",  label: "Query response time" },
              { n: "98%",  label: "Detection accuracy" },
              { n: "24/7", label: "Real-time monitoring" },
            ].map(({ n, label }) => (
              <div key={label} style={{ padding: "20px 24px", background: "#0C111D" }}>
                <div style={{ fontSize: 30, fontWeight: 900, letterSpacing: "-0.03em", lineHeight: 1 }}>{n}</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginTop: 6 }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Dashboard preview */}
          <div style={{
            marginTop: 56, borderRadius: 16, overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.08)",
            boxShadow: "0 32px 80px rgba(0,0,0,0.6)",
          }}>
            {/* Browser chrome */}
            <div style={{
              background: "#131825", padding: "10px 14px",
              borderBottom: "1px solid rgba(255,255,255,0.06)",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#EF4444", opacity: 0.7 }} />
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#F59E0B", opacity: 0.7 }} />
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#34D399", opacity: 0.7 }} />
              <div style={{
                marginLeft: 10, flex: 1, maxWidth: 260, height: 22, borderRadius: 6,
                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.07)",
                display: "flex", alignItems: "center", paddingLeft: 10,
                fontSize: 11, color: "rgba(255,255,255,0.25)",
              }}>
                irokoai.site/dashboard
              </div>
            </div>
            {/* Mock UI */}
            <div style={{ background: "#080B14", padding: 20, display: "flex", gap: 14, minHeight: 240 }}>
              {/* Sidebar mock */}
              <div style={{ width: 44, flexShrink: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                {[0.9, 0.4, 0.4, 0.4, 0.4, 0.4].map((o, i) => (
                  <div key={i} style={{ height: 8, borderRadius: 4, background: `rgba(74,85,212,${o})` }} />
                ))}
              </div>
              {/* Main content mock */}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
                {/* Top stat cards */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                  {[
                    { label: "Ops Health Score",  value: "94.2%", color: "#34D399" },
                    { label: "Active Incidents",  value: "4",     color: "#EF4444" },
                    { label: "Insights This Week", value: "212",  color: "#818CF8" },
                    { label: "Documents Indexed", value: "1,840", color: "#60A5FA" },
                  ].map(({ label, value, color }) => (
                    <div key={label} style={{
                      borderRadius: 10, padding: "12px 14px",
                      background: "#0F1320", border: "1px solid rgba(255,255,255,0.07)",
                    }}>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", marginBottom: 6 }}>{label}</div>
                      <div style={{ fontSize: 20, fontWeight: 800, color, letterSpacing: "-0.02em" }}>{value}</div>
                    </div>
                  ))}
                </div>
                {/* Chart mock + incident list */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, flex: 1 }}>
                  <div style={{ borderRadius: 10, background: "#0F1320", border: "1px solid rgba(255,255,255,0.07)", padding: 14 }}>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginBottom: 12 }}>Operational Health</div>
                    {/* Mini bar chart */}
                    <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 60 }}>
                      {[65, 80, 72, 88, 76, 94, 90, 85].map((h, i) => (
                        <div key={i} style={{ flex: 1, height: `${h}%`, borderRadius: 3, background: i === 5 ? "#4A55D4" : "rgba(74,85,212,0.3)" }} />
                      ))}
                    </div>
                  </div>
                  <div style={{ borderRadius: 10, background: "#0F1320", border: "1px solid rgba(255,255,255,0.07)", padding: 14 }}>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginBottom: 10 }}>Active Incidents</div>
                    {[
                      { label: "Cluster availability below SLA",   color: "#EF4444" },
                      { label: "Vendor contract expires in 28 days", color: "#F59E0B" },
                      { label: "Regulatory return due in 12 days",  color: "#F59E0B" },
                    ].map(({ label, color }) => (
                      <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />
                        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.45)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Problem ── */}
      <section style={{ padding: "80px 24px 0" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{
            borderRadius: 20, padding: "48px",
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.07)",
          }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#4A55D4", marginBottom: 12 }}>The problem</p>
            <h2 style={{ fontSize: "clamp(22px,3vw,30px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.2, margin: "0 0 16px", maxWidth: 560 }}>
              Your organisation&apos;s answers exist. They&apos;re just buried in a thousand documents.
            </h2>
            <p style={{ fontSize: 14.5, color: "rgba(255,255,255,0.42)", lineHeight: 1.8, margin: 0, maxWidth: 680 }}>
              Large organisations run on documents — contracts, incident reports, regulatory returns,
              complaint logs, spreadsheets — scattered across drives, inboxes and internal systems in
              every format imaginable. Finding one answer means someone digging for hours; the insight
              trapped across thousands of them never surfaces at all, and decisions wait. Iroko AI was
              built to close that gap: every document, one engine, answers in seconds.
            </p>
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section id="features" style={{ padding: "96px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ marginBottom: 48 }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#4A55D4", marginBottom: 12 }}>How it works</p>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
              <h2 style={{ fontSize: "clamp(24px,3vw,34px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.15, margin: 0, maxWidth: 460 }}>
                Five agents turn documents into decisions
              </h2>
              <p style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", maxWidth: 320, lineHeight: 1.7, margin: 0 }}>
                A multi-agent system built on Azure OpenAI that turns your scattered documents into structured, actionable intelligence.
              </p>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
            {[
              { color: "#818CF8", title: "Ingestion agent",     desc: "Pulls documents from wherever they live across your organisation — SharePoint, drives, email, core systems — into one indexed corpus.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 2v8M5 7l3 3 3-3M2.5 12.5h11" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg> },
              { color: "#34D399", title: "Understanding agent", desc: "Parses and extracts meaning regardless of format — PDFs, scans, spreadsheets, contracts — so nothing is unreadable to your team again.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="1.5" width="12" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M5 6h6M5 8.5h6M5 11h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg> },
              { color: "#F97316", title: "Analytics agent",     desc: "Real-time dashboards and insight generation — not just search. Trends, anomalies and exposure surface before anyone asks.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 13.5h12M4 13V8M8 13V4M12 13V6.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg> },
              { color: "#60A5FA", title: "Contextual Q&A agent", desc: "Staff ask questions in plain language and get answers sourced from the right document — with citations, confidence scores and next actions.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M13.5 8A5.5 5.5 0 1 1 8 2.5 5.5 5.5 0 0 1 13.5 8Z" stroke="currentColor" strokeWidth="1.3"/><path d="M6.3 6.3a1.8 1.8 0 0 1 3.5.6c0 1.1-1.8 1.4-1.8 2.3M8 11.2h.01" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg> },
              { color: "#F59E0B", title: "Compliance agent",    desc: "The same engine, configurable for regulatory and compliance document workflows — audit-grade logging, filing deadlines and inspection readiness.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5L14 4.5V9C14 12 11.5 14.5 8 15.5C4.5 14.5 2 12 2 9V4.5L8 1.5Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/><path d="M5.5 8l1.5 1.5 3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg> },
              { color: "#A78BFA", title: "Knowledge graph",     desc: "Entity relationships between documents, vendors, contracts and incidents visualised as a live graph — spot compound risks instantly.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="5" r="2" stroke="currentColor" strokeWidth="1.3"/><circle cx="3" cy="12.5" r="1.5" stroke="currentColor" strokeWidth="1.3"/><circle cx="13" cy="12.5" r="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M6.5 6.5L3.8 11M9.5 6.5L12.2 11M4.5 12.5h7" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg> },
            ].map(({ color, title, desc, icon }) => (
              <div key={title} style={{
                borderRadius: 14, padding: "20px 22px",
                background: "rgba(255,255,255,0.025)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}>
                <div style={{
                  width: 34, height: 34, borderRadius: 9, marginBottom: 14,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: `${color}18`, border: `1px solid ${color}28`, color,
                }}>
                  {icon}
                </div>
                <p style={{ fontSize: 14, fontWeight: 600, color: "#fff", margin: "0 0 8px" }}>{title}</p>
                <p style={{ fontSize: 13, color: "rgba(255,255,255,0.38)", lineHeight: 1.7, margin: 0 }}>{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Verticals ── */}
      <section id="use-cases" style={{ padding: "96px 24px", background: "#060910" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#4A55D4", marginBottom: 12 }}>Where Iroko runs</p>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 40 }}>
            <h2 style={{ fontSize: "clamp(24px,3vw,34px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.15, margin: 0 }}>
              Built for organisations that run on documents
            </h2>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 12 }}>
            {/* Primary vertical */}
            <div style={{
              borderRadius: 14, padding: "26px",
              background: "linear-gradient(135deg, rgba(74,85,212,0.12) 0%, rgba(74,85,212,0.03) 100%)",
              border: "1px solid rgba(74,85,212,0.3)",
            }}>
              <div style={{
                display: "inline-flex", fontSize: 12, fontWeight: 700,
                padding: "4px 10px", borderRadius: 99, marginBottom: 14,
                background: "rgba(129,140,248,0.15)", color: "#818CF8", border: "1px solid rgba(129,140,248,0.28)",
              }}>
                Enterprise document intelligence
              </div>
              <p style={{ fontSize: 14.5, color: "rgba(255,255,255,0.5)", lineHeight: 1.7, margin: "0 0 18px" }}>
                For large organisations — telecoms, utilities, logistics, any operations-heavy business —
                where critical knowledge lives in fragmented documents and slow answers cost real money.
              </p>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                {["Real-time workflow analytics across departments", "Plain-language Q&A over contracts, reports and returns", "Vendor SLA and contract-expiry monitoring", "Incident and complaint-trend correlation", "Audit-grade trace of every answer"].map((item) => (
                  <li key={item} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "rgba(255,255,255,0.45)" }}>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                      <path d="M2.5 7l3 3 6-6" stroke="#818CF8" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", lineHeight: 1.6, margin: "18px 0 0", paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                The same engine can also be configured for mobile-money-style regulatory document handling.
              </p>
            </div>

            {/* Secondary vertical */}
            <div style={{
              borderRadius: 14, padding: "26px",
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(255,255,255,0.07)",
            }}>
              <div style={{
                display: "inline-flex", fontSize: 12, fontWeight: 700,
                padding: "4px 10px", borderRadius: 99, marginBottom: 14,
                background: "rgba(52,211,153,0.12)", color: "#34D399", border: "1px solid rgba(52,211,153,0.25)",
              }}>
                Fintech &amp; MFB regulatory compliance
              </div>
              <p style={{ fontSize: 14.5, color: "rgba(255,255,255,0.5)", lineHeight: 1.7, margin: "0 0 18px" }}>
                The compliance configuration of the engine — purpose-built for Nigerian microfinance
                banks and fintechs regulated by the CBN and SEC.
              </p>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                {["CBN lending limit breach alerts", "KYC / AML gap detection", "Regulatory deadline tracker", "SAR filing reminders", "Capital adequacy monitoring"].map((item) => (
                  <li key={item} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "rgba(255,255,255,0.45)" }}>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                      <path d="M2.5 7l3 3 6-6" stroke="#34D399" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", lineHeight: 1.6, margin: "18px 0 0", paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                See <a href="#compliance" style={{ color: "#34D399", textDecoration: "none" }}>compliance architecture</a> and <a href="#pricing" style={{ color: "#34D399", textDecoration: "none" }}>fintech pricing</a> below.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Compliance ── */}
      <section id="compliance" style={{ padding: "96px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{
            borderRadius: 20, padding: "48px",
            background: "linear-gradient(135deg, rgba(74,85,212,0.1) 0%, rgba(74,85,212,0.03) 100%)",
            border: "1px solid rgba(74,85,212,0.22)",
            display: "grid", gridTemplateColumns: "1fr auto", gap: 48, alignItems: "center",
          }} className="flex-wrap-reverse">
            <div>
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#818CF8", marginBottom: 16 }}>The compliance configuration</p>
              <h2 style={{ fontSize: "clamp(22px,3vw,30px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.2, margin: "0 0 16px", maxWidth: 440 }}>
                The same engine, ready for CBN &amp; NDPA inspection
              </h2>
              <p style={{ fontSize: 14, color: "rgba(255,255,255,0.38)", lineHeight: 1.75, margin: "0 0 24px", maxWidth: 440 }}>
                For regulated finance teams, the document-intelligence engine runs in its compliance
                configuration: every interaction logged to an immutable audit trail, token-level
                traceability, role-based access control and data residency options — so you are
                always ready for a regulatory inspection.
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {["CBN MFB Guidelines", "SEC Nigeria", "NDPA 2023", "FCCPC", "NCC Directives"].map((tag) => (
                  <span key={tag} style={{
                    fontSize: 11, fontWeight: 600, padding: "4px 10px", borderRadius: 99,
                    background: "rgba(74,85,212,0.12)", color: "#818CF8", border: "1px solid rgba(74,85,212,0.22)",
                  }}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, minWidth: 220 }}>
              {[
                { label: "Immutable audit logs",  icon: "📋", color: "#818CF8" },
                { label: "Role-based access",      icon: "🔐", color: "#34D399" },
                { label: "Data residency",         icon: "🌍", color: "#60A5FA" },
                { label: "Token-level tracing",    icon: "🔗", color: "#F59E0B" },
              ].map(({ label, icon, color }) => (
                <div key={label} style={{
                  borderRadius: 12, padding: "16px",
                  background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                }}>
                  <div style={{ fontSize: 20, marginBottom: 8 }}>{icon}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, color, lineHeight: 1.4 }}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Credibility ── */}
      <section style={{ padding: "0 24px 96px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#4A55D4", marginBottom: 12 }}>Proven, not promised</p>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 32 }}>
            <h2 style={{ fontSize: "clamp(24px,3vw,34px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.15, margin: 0, maxWidth: 520 }}>
              The engine has already been tested against the field
            </h2>
            <p style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", maxWidth: 340, lineHeight: 1.7, margin: 0 }}>
              The five-agent document-intelligence engine behind Iroko AI has been judged in open competition — twice.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 12 }}>
            {[
              { n: "4th of 200+ teams", label: "TeKnowledge × Microsoft Agentic AI Hackathon Finale", color: "#818CF8" },
              { n: "Best Student Award", label: "YPIT Artificial Future Hackathon", color: "#34D399" },
            ].map(({ n, label, color }) => (
              <div key={label} style={{
                borderRadius: 14, padding: "26px",
                background: "rgba(255,255,255,0.025)",
                border: "1px solid rgba(255,255,255,0.07)",
                borderLeft: `3px solid ${color}`,
              }}>
                <div style={{ fontSize: 24, fontWeight: 900, letterSpacing: "-0.02em", color, marginBottom: 8 }}>{n}</div>
                <div style={{ fontSize: 13.5, color: "rgba(255,255,255,0.45)", lineHeight: 1.6 }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" style={{ padding: "96px 24px", background: "#060910" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#4A55D4", marginBottom: 12 }}>Pricing</p>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 40 }}>
            <h2 style={{ fontSize: "clamp(24px,3vw,34px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.15, margin: 0 }}>
              Priced for the problem you&apos;re solving
            </h2>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 12 }}>
            {/* Enterprise — primary */}
            <div style={{
              borderRadius: 14, padding: "28px",
              background: "linear-gradient(135deg, rgba(74,85,212,0.12) 0%, rgba(74,85,212,0.03) 100%)",
              border: "1px solid rgba(74,85,212,0.3)",
              display: "flex", flexDirection: "column",
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#818CF8", marginBottom: 10 }}>Enterprise document intelligence</div>
              <div style={{ fontSize: 30, fontWeight: 900, letterSpacing: "-0.03em", marginBottom: 6 }}>Custom-quoted</div>
              <p style={{ fontSize: 13.5, color: "rgba(255,255,255,0.42)", lineHeight: 1.7, margin: "0 0 20px" }}>
                Scoped to your organisation — document volume, systems to connect, departments to
                onboard, and deployment model. Every engagement starts with a working pilot.
              </p>
              <ul style={{ listStyle: "none", margin: "0 0 24px", padding: 0, display: "flex", flexDirection: "column", gap: 9 }}>
                {["All five agents + knowledge graph", "Connectors to your existing systems", "Real-time analytics dashboards", "On-prem or private-cloud options", "Dedicated onboarding team"].map((item) => (
                  <li key={item} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "rgba(255,255,255,0.45)" }}>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                      <path d="M2.5 7l3 3 6-6" stroke="#818CF8" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
              <Link href="/request-demo" style={{
                marginTop: "auto", textAlign: "center",
                fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none",
                padding: "11px 22px", borderRadius: 10,
                background: "#4A55D4", border: "1px solid rgba(255,255,255,0.12)",
                boxShadow: "0 0 24px rgba(74,85,212,0.3)",
              }}>
                Book a call
              </Link>
            </div>

            {/* Fintech — secondary vertical */}
            <div style={{
              borderRadius: 14, padding: "28px",
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(255,255,255,0.07)",
              display: "flex", flexDirection: "column",
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#34D399", marginBottom: 10 }}>Fintech &amp; MFB compliance</div>
              <div style={{ fontSize: 30, fontWeight: 900, letterSpacing: "-0.03em", marginBottom: 6 }}>
                From ₦350K<span style={{ fontSize: 15, fontWeight: 600, color: "rgba(255,255,255,0.35)" }}>/month</span>
              </div>
              <p style={{ fontSize: 13.5, color: "rgba(255,255,255,0.42)", lineHeight: 1.7, margin: "0 0 20px" }}>
                The compliance configuration for CBN/SEC-regulated institutions —
                Growth at ₦350K/month, Pro at ₦750K/month, and custom enterprise plans
                for holding groups.
              </p>
              <ul style={{ listStyle: "none", margin: "0 0 24px", padding: 0, display: "flex", flexDirection: "column", gap: 9 }}>
                {["Unlimited compliance checks", "Live CBN KPI monitoring (Pro)", "AML/CFT filing automation (Pro)", "Audit trail — 12 to 36 months", "30-day free pilot"].map((item) => (
                  <li key={item} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "rgba(255,255,255,0.45)" }}>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                      <path d="M2.5 7l3 3 6-6" stroke="#34D399" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
              <Link href="/demo" style={{
                marginTop: "auto", textAlign: "center",
                fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.6)", textDecoration: "none",
                padding: "11px 22px", borderRadius: 10,
                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)",
              }}>
                See the full tier breakdown
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section style={{ padding: "96px 24px", background: "#060910" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{
            borderRadius: 20, padding: "64px 48px", textAlign: "center",
            background: "#0C111D", border: "1px solid rgba(255,255,255,0.07)",
            position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", top: -100, left: "50%", transform: "translateX(-50%)",
              width: 600, height: 400, borderRadius: "50%",
              background: "radial-gradient(circle, rgba(74,85,212,0.18) 0%, transparent 70%)",
              pointerEvents: "none",
            }} />
            <div style={{ position: "relative" }}>
              <h2 style={{ fontSize: "clamp(26px,4vw,42px)", fontWeight: 900, letterSpacing: "-0.03em", lineHeight: 1.1, margin: "0 0 16px" }}>
                Ready to give your team real-time answers?
              </h2>
              <p style={{ fontSize: 15, color: "rgba(255,255,255,0.38)", maxWidth: 420, margin: "0 auto 36px", lineHeight: 1.7 }}>
                Iroko AI is invite-only. Request access and our team will reach out within 24 hours
                to scope a pilot on your own documents.
              </p>
              <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
                <Link href="/login" style={{
                  display: "inline-flex", alignItems: "center", gap: 8,
                  fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none",
                  padding: "11px 24px", borderRadius: 10,
                  background: "#4A55D4", border: "1px solid rgba(255,255,255,0.12)",
                  boxShadow: "0 0 28px rgba(74,85,212,0.3)",
                }}>
                  Request access
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </Link>
                <a href="mailto:admin@iroko.ai" style={{
                  display: "inline-flex", alignItems: "center",
                  fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.5)", textDecoration: "none",
                  padding: "11px 24px", borderRadius: 10,
                  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)",
                }}>
                  Contact sales
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{ padding: "28px 24px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          {LOGO}
          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.2)", margin: 0 }}>
            © 2026 Iroko AI · 4th of 200+ teams — TeKnowledge × Microsoft Agentic AI Hackathon Finale
          </p>
          <div style={{ display: "flex", gap: 20 }}>
            {["Privacy", "Terms", "Contact"].map((l) => (
              <a key={l} href="#" style={{ fontSize: 12, color: "rgba(255,255,255,0.25)", textDecoration: "none" }}>{l}</a>
            ))}
          </div>
        </div>
      </footer>

      <style>{`@keyframes pulse { 0%,100%{opacity:.5}50%{opacity:1} }`}</style>
    </div>
  );
}
