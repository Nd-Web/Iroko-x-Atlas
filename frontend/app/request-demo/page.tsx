"use client";

import { useState } from "react";
import Link from "next/link";

const LOGO = (
  <div className="flex items-center gap-2.5">
    <div
      style={{
        width: 36, height: 36, borderRadius: 10,
        background: "#4A55D4",
        boxShadow: "0 0 0 1px rgba(255,255,255,0.12), 0 4px 12px rgba(74,85,212,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
        <path d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round" fill="none" />
        <circle cx="11" cy="10.5" r="2.25" fill="white" />
      </svg>
    </div>
    <div>
      <p style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: 0, letterSpacing: "-0.01em" }}>Iroko AI</p>
      <p style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", margin: 0 }}>Fintech RegIntel</p>
    </div>
  </div>
);

export default function RequestDemoPage() {
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    institution: "",
    role: "",
    licenceTier: "",
    message: "",
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setSubmitted(true);
    }, 1200);
  }

  const inputStyle: React.CSSProperties = {
    width: "100%", boxSizing: "border-box",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 10, padding: "11px 14px",
    fontSize: 14, color: "#fff",
    outline: "none",
    transition: "border-color 0.15s",
  };

  const labelStyle: React.CSSProperties = {
    display: "block", fontSize: 12, fontWeight: 600,
    color: "rgba(255,255,255,0.5)", marginBottom: 6,
    letterSpacing: "0.02em",
  };

  return (
    <div style={{ background: "#080B14", minHeight: "100vh", fontFamily: "DM Sans, ui-sans-serif, sans-serif", color: "#fff" }}>

      {/* Navbar */}
      <header style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 50,
        height: 56, display: "flex", alignItems: "center", padding: "0 24px",
        background: "rgba(8,11,20,0.85)", backdropFilter: "blur(16px)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        <div style={{ maxWidth: 1100, width: "100%", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Link href="/" style={{ textDecoration: "none" }}>{LOGO}</Link>
          <Link href="/login" style={{
            fontSize: 13, fontWeight: 600, color: "#fff", textDecoration: "none",
            padding: "7px 16px", borderRadius: 8,
            background: "#4A55D4", border: "1px solid rgba(255,255,255,0.12)",
          }}>
            Sign in
          </Link>
        </div>
      </header>

      {/* Background glow */}
      <div style={{
        position: "fixed", top: -120, left: "50%", transform: "translateX(-50%)",
        width: 700, height: 500, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(74,85,212,0.22) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      <main style={{ paddingTop: 100, paddingBottom: 80, paddingLeft: 24, paddingRight: 24 }}>
        <div style={{ maxWidth: 560, margin: "0 auto" }}>

          {submitted ? (
            <div style={{ textAlign: "center", padding: "48px 0" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%", margin: "0 auto 24px",
                background: "rgba(52,211,153,0.12)", border: "1px solid rgba(52,211,153,0.3)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                  <path d="M5 14l7 7 11-11" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <h1 style={{ fontSize: 28, fontWeight: 900, letterSpacing: "-0.03em", margin: "0 0 12px" }}>Request received</h1>
              <p style={{ fontSize: 15, color: "rgba(255,255,255,0.45)", lineHeight: 1.75, margin: "0 0 32px", maxWidth: 400, marginLeft: "auto", marginRight: "auto" }}>
                A compliance specialist from the Iroko AI team will reach out within 24 hours to schedule your live demo.
              </p>
              <Link href="/" style={{
                display: "inline-flex", alignItems: "center", gap: 8,
                fontSize: 14, fontWeight: 600, color: "#fff", textDecoration: "none",
                padding: "10px 22px", borderRadius: 10,
                background: "#4A55D4", border: "1px solid rgba(255,255,255,0.12)",
              }}>
                ← Back to home
              </Link>
            </div>
          ) : (
            <>
              {/* Header */}
              <div style={{ marginBottom: 36 }}>
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: 8,
                  padding: "5px 12px", borderRadius: 99, marginBottom: 20,
                  background: "rgba(74,85,212,0.12)", border: "1px solid rgba(74,85,212,0.28)",
                  fontSize: 12, fontWeight: 600, color: "#818CF8",
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34D399" }} />
                  Invite-only · 30-day pilot free
                </div>
                <h1 style={{ fontSize: "clamp(28px,4vw,40px)", fontWeight: 900, letterSpacing: "-0.035em", margin: "0 0 14px", lineHeight: 1.1 }}>
                  Request a live demo
                </h1>
                <p style={{ fontSize: 15, color: "rgba(255,255,255,0.45)", lineHeight: 1.75, margin: 0 }}>
                  Tell us a bit about your institution and we&apos;ll tailor the demo to your compliance setup. A specialist will respond within 24 hours.
                </p>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                  <div>
                    <label style={labelStyle}>Full name *</label>
                    <input
                      required name="name" value={form.name} onChange={handleChange}
                      placeholder="Ada Okonkwo"
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Work email *</label>
                    <input
                      required type="email" name="email" value={form.email} onChange={handleChange}
                      placeholder="ada@mfb.ng"
                      style={inputStyle}
                    />
                  </div>
                </div>

                <div>
                  <label style={labelStyle}>Institution name *</label>
                  <input
                    required name="institution" value={form.institution} onChange={handleChange}
                    placeholder="e.g. Zenith MFB"
                    style={inputStyle}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                  <div>
                    <label style={labelStyle}>Your role *</label>
                    <select
                      required name="role" value={form.role} onChange={handleChange}
                      style={{ ...inputStyle, appearance: "none" }}
                    >
                      <option value="" disabled>Select role</option>
                      <option>Chief Compliance Officer</option>
                      <option>Compliance Manager</option>
                      <option>Legal & Risk</option>
                      <option>CEO / MD</option>
                      <option>CTO / IT Lead</option>
                      <option>Other</option>
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>CBN licence tier</label>
                    <select
                      name="licenceTier" value={form.licenceTier} onChange={handleChange}
                      style={{ ...inputStyle, appearance: "none" }}
                    >
                      <option value="">Select tier (optional)</option>
                      <option>Unit MFB</option>
                      <option>State MFB</option>
                      <option>National MFB</option>
                      <option>PSB / Payment Service Bank</option>
                      <option>Fintech (non-MFB)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label style={labelStyle}>What compliance challenge should we focus on?</label>
                  <textarea
                    name="message" value={form.message} onChange={handleChange}
                    placeholder="e.g. We struggle to track CBN filing deadlines and want to automate our KYC gap detection…"
                    rows={4}
                    style={{ ...inputStyle, resize: "vertical", lineHeight: 1.6 }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                    fontSize: 14, fontWeight: 700, color: "#fff",
                    padding: "13px 24px", borderRadius: 10,
                    background: loading ? "rgba(74,85,212,0.6)" : "#4A55D4",
                    border: "1px solid rgba(255,255,255,0.12)",
                    boxShadow: "0 0 28px rgba(74,85,212,0.3)",
                    cursor: loading ? "not-allowed" : "pointer",
                    transition: "background 0.15s",
                    width: "100%",
                  }}
                >
                  {loading ? "Submitting…" : (
                    <>
                      Request demo
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </>
                  )}
                </button>

                <p style={{ fontSize: 12, color: "rgba(255,255,255,0.25)", textAlign: "center", margin: 0 }}>
                  No payment required · Iroko AI is invite-only
                </p>
              </form>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
