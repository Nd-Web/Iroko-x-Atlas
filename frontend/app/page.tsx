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
      <p className="text-[10px] text-white/40 leading-none mt-0.5">Fintech RegIntel</p>
    </div>
  </div>
);

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
            {["Features", "Use Cases", "Compliance"].map((l) => (
              <a key={l} href={`#${l.toLowerCase().replace(" ", "-")}`}
                style={{ fontSize: 13, fontWeight: 500, color: "rgba(255,255,255,0.45)", textDecoration: "none", transition: "color .15s" }}
                onMouseEnter={e => (e.currentTarget.style.color = "#fff")}
                onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.45)")}>
                {l}
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
          {["Features", "Use Cases", "Compliance"].map((l) => (
            <a key={l} href={`#${l.toLowerCase().replace(" ", "-")}`} onClick={() => setOpen(false)}
              style={{ fontSize: 14, fontWeight: 500, color: "rgba(255,255,255,0.6)", textDecoration: "none", padding: "10px 12px", borderRadius: 8 }}>
              {l}
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
            CBN · SEC · NDPA — Real-time compliance intelligence
          </div>

          {/* Headline */}
          <h1 style={{
            fontSize: "clamp(36px, 5vw, 60px)", fontWeight: 900,
            lineHeight: 1.08, letterSpacing: "-0.035em",
            margin: "0 0 20px", maxWidth: 720,
          }}>
            AI that keeps your fintech{" "}
            <span style={{
              background: "linear-gradient(135deg, #818CF8 0%, #4A55D4 100%)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>
              compliant by default.
            </span>
          </h1>

          <p style={{ fontSize: 17, color: "rgba(255,255,255,0.45)", lineHeight: 1.75, maxWidth: 520, margin: "0 0 36px" }}>
            Iroko AI monitors CBN and SEC regulations in real time, surfaces compliance gaps before they become violations,
            and answers your team&apos;s questions with cited evidence — not guesses.
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
            <Link href="/dashboard" style={{
              display: "inline-flex", alignItems: "center",
              fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.55)", textDecoration: "none",
              padding: "11px 22px", borderRadius: 10,
              background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)",
            }}>
              View live demo
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
              { n: "200+", label: "Regulations monitored" },
              { n: "5",    label: "Specialist AI agents" },
              { n: "98%",  label: "Detection accuracy" },
              { n: "<2s",  label: "Query response time" },
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
                    { label: "Compliance Score", value: "94.2%", color: "#34D399" },
                    { label: "Active Incidents", value: "4",     color: "#EF4444" },
                    { label: "Regulations",      value: "212",   color: "#818CF8" },
                    { label: "Documents",        value: "1,840", color: "#60A5FA" },
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
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginBottom: 12 }}>Compliance Health</div>
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
                      { label: "Lending limit — CBN threshold", color: "#EF4444" },
                      { label: "KYC gap — Q2 onboarding",       color: "#F59E0B" },
                      { label: "AML return due in 12 days",      color: "#F59E0B" },
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

      {/* ── Features ── */}
      <section id="features" style={{ padding: "96px 24px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ marginBottom: 48 }}>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#4A55D4", marginBottom: 12 }}>Platform</p>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
              <h2 style={{ fontSize: "clamp(24px,3vw,34px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.15, margin: 0, maxWidth: 460 }}>
                Everything your compliance team needs
              </h2>
              <p style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", maxWidth: 320, lineHeight: 1.7, margin: 0 }}>
                A multi-agent system built on Azure OpenAI that turns regulatory complexity into structured, actionable intelligence.
              </p>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
            {[
              { color: "#818CF8", title: "Multi-agent reasoning", desc: "5 specialist agents — Retriever, Analyst, Strategist, Validator, Narrator — collaborate on every query to produce verified, cited answers.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3"/><circle cx="2" cy="4" r="1.3" stroke="currentColor" strokeWidth="1.3"/><circle cx="14" cy="4" r="1.3" stroke="currentColor" strokeWidth="1.3"/><circle cx="14" cy="12" r="1.3" stroke="currentColor" strokeWidth="1.3"/><circle cx="2" cy="12" r="1.3" stroke="currentColor" strokeWidth="1.3"/><path d="M3.3 4.7L6.3 6.7M12.7 4.7L9.7 6.7M12.7 11.3L9.7 9.3M3.3 11.3L6.3 9.3" stroke="currentColor" strokeWidth="1"/></svg> },
              { color: "#34D399", title: "CBN / SEC monitoring",   desc: "Real-time scanning of lending limits, KYC/AML requirements, capital adequacy ratios and filing deadlines for Nigerian microfinance banks.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1L13 3.5V8.5C13 11.5 10.8 14 8 15C5.2 14 3 11.5 3 8.5V3.5L8 1Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/><path d="M5.5 8l2 2 3.5-3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg> },
              { color: "#60A5FA", title: "Cite-first AI answers",  desc: "Every response is grounded in your uploaded regulatory corpus with document citations, confidence scores and suggested next actions.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="1.5" width="12" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M5 6h6M5 8.5h6M5 11h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg> },
              { color: "#F59E0B", title: "Audit-grade logging",    desc: "Cryptographically chained records of every query, answer and user action — meeting CBN, SEC and NDPA audit requirements.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5L14 4.5V9C14 12 11.5 14.5 8 15.5C4.5 14.5 2 12 2 9V4.5L8 1.5Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/><path d="M5.5 8l1.5 1.5 3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg> },
              { color: "#F97316", title: "Live web intelligence",  desc: "Real-time signal pipeline surfaces competitor regulatory incidents, CBN press releases and NCC directives as they are published.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/><path d="M8 4.5V8l2 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg> },
              { color: "#A78BFA", title: "Knowledge graph",        desc: "Entity relationships between regulations, vendors, contracts and incidents visualised as a live graph — spot compound risks instantly.", icon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="5" r="2" stroke="currentColor" strokeWidth="1.3"/><circle cx="3" cy="12.5" r="1.5" stroke="currentColor" strokeWidth="1.3"/><circle cx="13" cy="12.5" r="1.5" stroke="currentColor" strokeWidth="1.3"/><path d="M6.5 6.5L3.8 11M9.5 6.5L12.2 11M4.5 12.5h7" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg> },
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

      {/* ── Use cases ── */}
      <section id="use-cases" style={{ padding: "96px 24px", background: "#060910" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#4A55D4", marginBottom: 12 }}>Built for your role</p>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 40 }}>
            <h2 style={{ fontSize: "clamp(24px,3vw,34px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.15, margin: 0 }}>
              The right intelligence for every team
            </h2>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
            {[
              {
                role: "Compliance Officers", color: "#34D399",
                items: ["CBN lending limit breach alerts", "KYC / AML gap detection", "Regulatory deadline tracker", "SAR filing reminders", "Capital adequacy monitoring"],
              },
              {
                role: "NOC Engineers", color: "#60A5FA",
                items: ["Network availability heatmap", "Site-level incident dashboard", "SLA breach early warning", "Real-time outage correlation", "Agent deployment status"],
              },
              {
                role: "Legal & Risk", color: "#A78BFA",
                items: ["Contract clause risk scoring", "Regulatory change impact analysis", "Audit-ready evidence packages", "SEC disclosure monitoring", "Vendor obligation tracking"],
              },
            ].map(({ role, color, items }) => (
              <div key={role} style={{
                borderRadius: 14, padding: "22px",
                background: "rgba(255,255,255,0.025)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}>
                <div style={{
                  display: "inline-flex", fontSize: 12, fontWeight: 700,
                  padding: "4px 10px", borderRadius: 99, marginBottom: 18,
                  background: `${color}15`, color, border: `1px solid ${color}28`,
                }}>
                  {role}
                </div>
                <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                  {items.map((item) => (
                    <li key={item} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "rgba(255,255,255,0.45)" }}>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                        <path d="M2.5 7l3 3 6-6" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
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
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.12em", color: "#818CF8", marginBottom: 16 }}>Compliance-first architecture</p>
              <h2 style={{ fontSize: "clamp(22px,3vw,30px)", fontWeight: 900, letterSpacing: "-0.025em", lineHeight: 1.2, margin: "0 0 16px", maxWidth: 440 }}>
                Designed for CBN & NDPA inspection readiness
              </h2>
              <p style={{ fontSize: 14, color: "rgba(255,255,255,0.38)", lineHeight: 1.75, margin: "0 0 24px", maxWidth: 440 }}>
                Every interaction is logged to an immutable audit trail. Token-level traceability,
                role-based access control and data residency options ensure you are always ready for a regulatory inspection.
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
                Ready to put compliance on autopilot?
              </h2>
              <p style={{ fontSize: 15, color: "rgba(255,255,255,0.38)", maxWidth: 420, margin: "0 auto 36px", lineHeight: 1.7 }}>
                Iroko AI is invite-only. Request access and a compliance specialist will reach out within 24 hours.
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
            © 2026 Iroko AI · TeKnowledge × Microsoft Agentic AI Hackathon
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
