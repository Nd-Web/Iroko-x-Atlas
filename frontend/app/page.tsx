"use client";

import Link from "next/link";
import { useState, useEffect } from "react";

// ── Animated counter ──────────────────────────────────────────────────────────
function Counter({ to, suffix = "" }: { to: number; suffix?: string }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let start = 0;
    const step = Math.ceil(to / 60);
    const timer = setInterval(() => {
      start += step;
      if (start >= to) { setVal(to); clearInterval(timer); }
      else setVal(start);
    }, 16);
    return () => clearInterval(timer);
  }, [to]);
  return <>{val.toLocaleString()}{suffix}</>;
}

// ── Logo ──────────────────────────────────────────────────────────────────────
function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
        style={{
          background: "linear-gradient(135deg, #4A55D4, #818CF8)",
          boxShadow: "0 0 0 1px rgba(255,255,255,0.12), 0 4px 14px rgba(74,85,212,0.45)",
        }}
      >
        <svg width="18" height="18" viewBox="0 0 22 22" fill="none">
          <path d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round" fill="none" />
          <circle cx="11" cy="10.5" r="2.25" fill="white" />
        </svg>
      </div>
      <span className="text-[17px] font-bold text-white tracking-tight">Iroko AI</span>
    </div>
  );
}

// ── Feature card ──────────────────────────────────────────────────────────────
function FeatureCard({ icon, title, desc, accent }: { icon: React.ReactNode; title: string; desc: string; accent: string }) {
  return (
    <div
      className="rounded-2xl p-6 flex flex-col gap-4 transition-transform duration-200 hover:-translate-y-0.5"
      style={{ background: "#0F1320", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <div
        className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: `${accent}18`, border: `1px solid ${accent}30` }}
      >
        <span style={{ color: accent }}>{icon}</span>
      </div>
      <div>
        <h3 className="text-[14px] font-semibold text-white mb-1.5">{title}</h3>
        <p className="text-[13px] text-[#6B7280] leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function Stat({ value, suffix, label }: { value: number; suffix?: string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1 py-6 px-4">
      <div className="text-[36px] font-black text-white leading-none tracking-tight">
        <Counter to={value} suffix={suffix} />
      </div>
      <div className="text-[12px] text-[#6B7280] text-center">{label}</div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen" style={{ background: "#080B14", fontFamily: "DM Sans, sans-serif" }}>

      {/* ── Nav ── */}
      <nav
        className="fixed top-0 inset-x-0 z-50 flex items-center justify-between px-6 md:px-10 h-16"
        style={{ background: "rgba(8,11,20,0.85)", backdropFilter: "blur(12px)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <Logo />

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-8">
          {["Features", "Use Cases", "Compliance", "Pricing"].map(l => (
            <a key={l} href={`#${l.toLowerCase().replace(" ", "-")}`}
              className="text-[13px] font-medium text-[#9CA3AF] hover:text-white transition-colors no-underline">
              {l}
            </a>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          <Link href="/login"
            className="text-[13px] font-semibold text-[#9CA3AF] hover:text-white transition-colors no-underline px-4 py-2">
            Sign in
          </Link>
          <Link href="/login"
            className="text-[13px] font-semibold text-white no-underline px-4 py-2 rounded-lg transition-all"
            style={{ background: "#4A55D4", border: "1px solid #3D44B8" }}
            onMouseEnter={e => (e.currentTarget.style.background = "#3D44B8")}
            onMouseLeave={e => (e.currentTarget.style.background = "#4A55D4")}>
            Get access
          </Link>
        </div>

        {/* Mobile burger */}
        <button className="md:hidden text-[#9CA3AF] p-1" onClick={() => setMenuOpen(v => !v)}>
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            {menuOpen
              ? <path d="M4 4l14 14M18 4L4 18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              : <><path d="M3 6h16M3 11h16M3 16h16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></>}
          </svg>
        </button>
      </nav>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="fixed inset-x-0 top-16 z-40 p-4 flex flex-col gap-1 md:hidden"
          style={{ background: "#0C1018", borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
          {["Features", "Use Cases", "Compliance", "Pricing"].map(l => (
            <a key={l} href={`#${l.toLowerCase().replace(" ", "-")}`}
              onClick={() => setMenuOpen(false)}
              className="text-[14px] font-medium text-[#9CA3AF] hover:text-white px-3 py-2.5 rounded-lg hover:bg-white/5 no-underline transition-colors">
              {l}
            </a>
          ))}
          <div className="mt-2 pt-3 border-t border-white/[0.07] flex flex-col gap-2">
            <Link href="/login" className="btn-secondary text-center text-[13px] no-underline py-2.5"
              style={{ background: "transparent", color: "#9CA3AF", border: "1px solid rgba(255,255,255,0.12)" }}>
              Sign in
            </Link>
            <Link href="/login" className="text-[13px] font-semibold text-white text-center no-underline px-4 py-2.5 rounded-lg"
              style={{ background: "#4A55D4" }}>
              Get access
            </Link>
          </div>
        </div>
      )}

      {/* ── Hero ── */}
      <section className="relative flex flex-col items-center justify-center text-center px-6 pt-36 pb-24 overflow-hidden">
        {/* Glow blobs */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute top-[-80px] left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full opacity-20"
            style={{ background: "radial-gradient(circle, #4A55D4 0%, transparent 70%)" }} />
          <div className="absolute top-[200px] left-[-100px] w-[400px] h-[400px] rounded-full opacity-10"
            style={{ background: "radial-gradient(circle, #818CF8 0%, transparent 70%)" }} />
          <div className="absolute top-[100px] right-[-80px] w-[350px] h-[350px] rounded-full opacity-10"
            style={{ background: "radial-gradient(circle, #6172F3 0%, transparent 70%)" }} />
        </div>

        {/* Badge */}
        <div className="relative mb-6 inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-[12px] font-semibold"
          style={{ background: "rgba(74,85,212,0.15)", border: "1px solid rgba(74,85,212,0.35)", color: "#818CF8" }}>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Built for African Fintechs · CBN / SEC Compliance
        </div>

        <h1 className="relative text-[38px] md:text-[56px] lg:text-[64px] font-black text-white leading-[1.1] tracking-tight max-w-4xl mb-6">
          Enterprise AI for{" "}
          <span style={{ background: "linear-gradient(135deg, #818CF8, #4A55D4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Fintech Compliance
          </span>
        </h1>

        <p className="relative text-[16px] md:text-[18px] text-[#9CA3AF] leading-relaxed max-w-2xl mb-10">
          Iroko AI monitors CBN and SEC regulations in real time, surfaces compliance gaps before they become violations,
          and gives your team cite-first answers grounded in your verified regulatory corpus.
        </p>

        <div className="relative flex flex-col sm:flex-row items-center gap-3">
          <Link href="/login"
            className="w-full sm:w-auto text-[15px] font-semibold text-white no-underline px-7 py-3.5 rounded-xl transition-all"
            style={{ background: "linear-gradient(135deg, #4A55D4, #6172F3)", boxShadow: "0 0 30px rgba(74,85,212,0.4)" }}
            onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 0 40px rgba(74,85,212,0.6)")}
            onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 0 30px rgba(74,85,212,0.4)")}>
            Request access →
          </Link>
          <Link href="/dashboard"
            className="w-full sm:w-auto text-[15px] font-semibold text-[#9CA3AF] hover:text-white no-underline px-7 py-3.5 rounded-xl transition-all"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)" }}>
            View live demo
          </Link>
        </div>

        {/* Social proof */}
        <p className="relative mt-6 text-[12px] text-[#4B5563]">
          Invite-only · Trusted by compliance teams at leading Nigerian fintechs
        </p>
      </section>

      {/* ── Stats ── */}
      <section className="px-6 md:px-10 pb-16">
        <div className="max-w-5xl mx-auto rounded-2xl overflow-hidden grid grid-cols-2 md:grid-cols-4 divide-x divide-y md:divide-y-0"
          style={{ background: "#0F1320", border: "1px solid rgba(255,255,255,0.07)", borderColor: "rgba(255,255,255,0.07)" }}>
          <Stat value={200} suffix="+" label="CBN / SEC regulations monitored" />
          <Stat value={98} suffix="%" label="Compliance detection accuracy" />
          <Stat value={5} label="AI agents working in parallel" />
          <Stat value={14} label="Languages & dialects supported" />
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="px-6 md:px-10 py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-[12px] font-bold uppercase tracking-widest text-[#4A55D4] mb-3">Platform capabilities</p>
            <h2 className="text-[30px] md:text-[38px] font-black text-white tracking-tight mb-4">
              Everything your compliance team needs
            </h2>
            <p className="text-[15px] text-[#6B7280] max-w-xl mx-auto leading-relaxed">
              A multi-agent system built on Azure OpenAI that turns regulatory complexity into structured, actionable intelligence.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <FeatureCard
              accent="#818CF8"
              icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2L15 5.5V11.5L10 15L5 11.5V5.5L10 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/><circle cx="10" cy="8.5" r="1.75" fill="currentColor"/></svg>}
              title="Multi-agent reasoning"
              desc="5 specialised AI agents — Retriever, Analyst, Strategist, Validator, Narrator — collaborate on every query to produce verified, cite-first answers."
            />
            <FeatureCard
              accent="#34D399"
              icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2L17 5.5V11C17 14.5 14 17 10 18C6 17 3 14.5 3 11V5.5L10 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/><path d="M7 10l2 2 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              title="CBN / SEC compliance monitoring"
              desc="Real-time scanning of lending limits, KYC/AML requirements, capital adequacy ratios and regulatory deadlines specific to Nigerian microfinance."
            />
            <FeatureCard
              accent="#F59E0B"
              icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2.5l1.5 4.5H16l-3.75 2.75 1.5 4.5L10 11.5l-3.75 2.75 1.5-4.5L4 7h4.5L10 2.5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/></svg>}
              title="Cite-first AI answers"
              desc="Every response is grounded in your uploaded regulatory corpus with document citations, confidence scores and suggested follow-up actions."
            />
            <FeatureCard
              accent="#60A5FA"
              icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><rect x="2" y="3" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="1.4"/><path d="M6 8h8M6 11h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>}
              title="Audit-grade logging"
              desc="Cryptographically chained audit trail for every query, answer and user action. Meets CBN, SEC and NDPA requirements out of the box."
            />
            <FeatureCard
              accent="#F97316"
              icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.4"/><path d="M10 6v4l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>}
              title="Real-time signal monitoring"
              desc="Live web intelligence pipeline surfaces competitor regulatory incidents, CBN press releases and NCC directives as they're published."
            />
            <FeatureCard
              accent="#A78BFA"
              icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.4"/><circle cx="3.5" cy="5" r="1.5" stroke="currentColor" strokeWidth="1.4"/><circle cx="16.5" cy="5" r="1.5" stroke="currentColor" strokeWidth="1.4"/><circle cx="16.5" cy="15" r="1.5" stroke="currentColor" strokeWidth="1.4"/><circle cx="3.5" cy="15" r="1.5" stroke="currentColor" strokeWidth="1.4"/><path d="M5 5.5L8.5 8.5M15 5.5L11.5 8.5M15 14.5L11.5 11.5M5 14.5L8.5 11.5" stroke="currentColor" strokeWidth="1.2"/></svg>}
              title="Knowledge graph"
              desc="Entity relationships between regulations, vendors, contracts and incidents visualised as a live graph — spot compound risks instantly."
            />
          </div>
        </div>
      </section>

      {/* ── Use cases ── */}
      <section id="use-cases" className="px-6 md:px-10 py-20" style={{ background: "#0A0D16" }}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-[12px] font-bold uppercase tracking-widest text-[#4A55D4] mb-3">Built for your team</p>
            <h2 className="text-[30px] md:text-[38px] font-black text-white tracking-tight">
              The right intelligence for every role
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              {
                role: "Compliance Officers",
                color: "#34D399",
                bg: "#34D39915",
                items: ["CBN lending limit breach alerts", "KYC/AML gap detection", "Regulatory deadline tracker", "Automated SAR filing reminders"],
              },
              {
                role: "NOC Engineers",
                color: "#60A5FA",
                bg: "#60A5FA15",
                items: ["Network availability heatmap", "Site-level incident dashboard", "SLA breach early warning", "Real-time outage correlation"],
              },
              {
                role: "Legal & Risk Teams",
                color: "#A78BFA",
                bg: "#A78BFA15",
                items: ["Contract clause risk scoring", "Regulatory change impact analysis", "Audit-ready evidence packages", "SEC disclosure monitoring"],
              },
            ].map(({ role, color, bg, items }) => (
              <div key={role} className="rounded-2xl p-6 flex flex-col gap-5"
                style={{ background: "#0F1320", border: "1px solid rgba(255,255,255,0.07)" }}>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[12px] font-bold w-fit"
                  style={{ background: bg, color }}>
                  {role}
                </div>
                <ul className="flex flex-col gap-3">
                  {items.map(item => (
                    <li key={item} className="flex items-start gap-2.5 text-[13px] text-[#9CA3AF]">
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
                        <circle cx="8" cy="8" r="7" fill={color} fillOpacity="0.15"/>
                        <path d="M5 8l2 2 4-4" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
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

      {/* ── Compliance section ── */}
      <section id="compliance" className="px-6 md:px-10 py-20">
        <div className="max-w-5xl mx-auto rounded-3xl p-10 md:p-14 flex flex-col md:flex-row items-center gap-10"
          style={{ background: "linear-gradient(135deg, #0F1320 0%, #131829 100%)", border: "1px solid rgba(74,85,212,0.25)" }}>
          <div className="flex-1 min-w-0">
            <p className="text-[12px] font-bold uppercase tracking-widest text-[#818CF8] mb-4">Compliance-first architecture</p>
            <h2 className="text-[28px] md:text-[34px] font-black text-white tracking-tight mb-5 leading-tight">
              Designed to meet Nigerian regulatory standards
            </h2>
            <p className="text-[14px] text-[#6B7280] leading-relaxed mb-7">
              Every interaction is logged to an immutable audit trail. Token-level traceability, role-based access controls,
              and data residency options ensure you're always ready for a CBN or NDPA inspection.
            </p>
            <div className="flex flex-wrap gap-2">
              {["CBN MFB Guidelines", "SEC Nigeria", "NDPA 2023", "FCCPC", "NCC Directives"].map(tag => (
                <span key={tag} className="text-[12px] font-semibold px-3 py-1 rounded-full"
                  style={{ background: "rgba(74,85,212,0.15)", color: "#818CF8", border: "1px solid rgba(74,85,212,0.3)" }}>
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <div className="shrink-0 grid grid-cols-2 gap-3 w-full md:w-[260px]">
            {[
              { label: "Audit logs", icon: "📋", color: "#818CF8" },
              { label: "Role-based access", icon: "🔐", color: "#34D399" },
              { label: "Data residency", icon: "🌍", color: "#60A5FA" },
              { label: "Token tracing", icon: "🔗", color: "#F59E0B" },
            ].map(({ label, icon, color }) => (
              <div key={label} className="rounded-xl p-4 flex flex-col gap-2"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <span className="text-2xl">{icon}</span>
                <span className="text-[12px] font-semibold" style={{ color }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="px-6 md:px-10 py-20 text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-[30px] md:text-[40px] font-black text-white tracking-tight mb-5 leading-tight">
            Ready to put compliance on autopilot?
          </h2>
          <p className="text-[15px] text-[#6B7280] mb-10 leading-relaxed">
            Iroko AI is invite-only. Request access and a compliance specialist will reach out within 24 hours.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link href="/login"
              className="w-full sm:w-auto text-[15px] font-semibold text-white no-underline px-8 py-4 rounded-xl transition-all"
              style={{ background: "linear-gradient(135deg, #4A55D4, #6172F3)", boxShadow: "0 0 30px rgba(74,85,212,0.35)" }}>
              Request access →
            </Link>
            <a href="mailto:admin@iroko.ai"
              className="w-full sm:w-auto text-[15px] font-semibold text-[#9CA3AF] hover:text-white no-underline px-8 py-4 rounded-xl transition-all"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)" }}>
              Contact sales
            </a>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="px-6 md:px-10 py-10 border-t" style={{ borderColor: "rgba(255,255,255,0.07)" }}>
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-5">
          <Logo />
          <p className="text-[12px] text-[#4B5563] text-center">
            © 2026 Iroko AI. Built for the TeKnowledge × Microsoft Agentic AI Hackathon.
          </p>
          <div className="flex items-center gap-5">
            {["Privacy", "Terms", "Contact"].map(l => (
              <a key={l} href="#" className="text-[12px] text-[#4B5563] hover:text-[#9CA3AF] no-underline transition-colors">{l}</a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
