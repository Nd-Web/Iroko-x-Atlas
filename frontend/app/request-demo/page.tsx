"use client";

import { useState } from "react";
import Link from "next/link";

const LOGO = (
  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
    <div style={{
      width: 36, height: 36, borderRadius: 10, flexShrink: 0,
      background: "#4A55D4",
      boxShadow: "0 0 0 1px rgba(255,255,255,0.12), 0 4px 12px rgba(74,85,212,0.4)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
        <path d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round" fill="none" />
        <circle cx="11" cy="10.5" r="2.25" fill="white" />
      </svg>
    </div>
    <div>
      <p style={{ fontSize: 15, fontWeight: 700, color: "#fff", margin: 0 }}>Iroko AI</p>
      <p style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", margin: 0 }}>Fintech RegIntel</p>
    </div>
  </div>
);

type DemoType = "live" | "recorded" | "deck";

export default function RequestDemoPage() {
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading]     = useState(false);
  const [demoTypes, setDemoTypes] = useState<DemoType[]>([]);
  const [form, setForm] = useState({
    company:   "",
    contact:   "",
    email:     "",
    phone:     "",
    role:      "",
    size:      "",
    licenceTier: "",
    message:   "",
  });

  function toggle(type: DemoType) {
    setDemoTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (demoTypes.length === 0) return;
    setLoading(true);
    setTimeout(() => { setLoading(false); setSubmitted(true); }, 1200);
  }

  /* ── shared styles ── */
  const field: React.CSSProperties = {
    width: "100%", boxSizing: "border-box",
    background: "#131825",
    border: "1px solid rgba(255,255,255,0.14)",
    borderRadius: 10, padding: "12px 14px",
    fontSize: 14, color: "#fff",
    outline: "none",
    fontFamily: "inherit",
  };
  const label: React.CSSProperties = {
    display: "block", fontSize: 12, fontWeight: 600,
    color: "rgba(255,255,255,0.55)", marginBottom: 7,
    textTransform: "uppercase", letterSpacing: "0.05em",
  };

  /* ── success screen ── */
  if (submitted) {
    return (
      <div style={{ background: "#080B14", minHeight: "100vh", fontFamily: "DM Sans, ui-sans-serif, sans-serif", color: "#fff", display: "flex", flexDirection: "column" }}>
        <header style={{ height: 56, display: "flex", alignItems: "center", padding: "0 24px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <Link href="/" style={{ textDecoration: "none" }}>{LOGO}</Link>
        </header>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <div style={{ textAlign: "center", maxWidth: 440 }}>
            <div style={{
              width: 72, height: 72, borderRadius: "50%", margin: "0 auto 28px",
              background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.3)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <path d="M6 16l8 8 12-12" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h1 style={{ fontSize: 30, fontWeight: 900, letterSpacing: "-0.03em", margin: "0 0 14px" }}>Request received</h1>
            <p style={{ fontSize: 15, color: "rgba(255,255,255,0.45)", lineHeight: 1.75, margin: "0 0 10px" }}>
              We&apos;ve logged your request for:
            </p>
            <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap", marginBottom: 28 }}>
              {demoTypes.includes("live")     && <span style={pill("#818CF8")}>Live demo</span>}
              {demoTypes.includes("recorded") && <span style={pill("#34D399")}>Recorded demo</span>}
              {demoTypes.includes("deck")     && <span style={pill("#F59E0B")}>Slide deck</span>}
            </div>
            <p style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", lineHeight: 1.7, margin: "0 0 32px" }}>
              A specialist from the Iroko AI team will reach out to <strong style={{ color: "rgba(255,255,255,0.7)" }}>{form.email}</strong> within 24 hours.
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
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "#080B14", minHeight: "100vh", fontFamily: "DM Sans, ui-sans-serif, sans-serif", color: "#fff" }}>

      {/* Glow */}
      <div style={{
        position: "fixed", top: -160, left: "50%", transform: "translateX(-50%)",
        width: 800, height: 600, borderRadius: "50%", pointerEvents: "none",
        background: "radial-gradient(circle, rgba(74,85,212,0.18) 0%, transparent 70%)",
      }} />

      {/* Navbar */}
      <header style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 50,
        height: 56, display: "flex", alignItems: "center", padding: "0 24px",
        background: "rgba(8,11,20,0.9)", backdropFilter: "blur(16px)",
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

      <main style={{ paddingTop: 88, paddingBottom: 80, paddingLeft: 24, paddingRight: 24 }}>
        <div style={{ maxWidth: 640, margin: "0 auto", position: "relative" }}>

          {/* Page header */}
          <div style={{ marginBottom: 40, paddingTop: 24 }}>
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "5px 12px", borderRadius: 99, marginBottom: 20,
              background: "rgba(74,85,212,0.12)", border: "1px solid rgba(74,85,212,0.28)",
              fontSize: 12, fontWeight: 600, color: "#818CF8",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34D399", display: "inline-block" }} />
              Invite-only · No payment needed
            </div>
            <h1 style={{ fontSize: "clamp(28px,4vw,42px)", fontWeight: 900, letterSpacing: "-0.035em", margin: "0 0 14px", lineHeight: 1.1 }}>
              Request a demo
            </h1>
            <p style={{ fontSize: 15, color: "rgba(255,255,255,0.45)", lineHeight: 1.75, margin: 0, maxWidth: 480 }}>
              Tell us about your organisation and choose how you&apos;d like to see Iroko AI in action. We&apos;ll follow up within 24 hours.
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 0 }}>

            {/* ── Section 1: Company ── */}
            <Section label="Company details">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <Field label="Company / institution name *">
                  <input required name="company" value={form.company} onChange={handleChange}
                    placeholder="Zenith MFB" style={field} />
                </Field>
                <Field label="Company size">
                  <select name="size" value={form.size} onChange={handleChange}
                    style={{ ...field, color: form.size ? "#fff" : "rgba(255,255,255,0.35)" }}>
                    <option value="">Select size</option>
                    <option>1 – 10 employees</option>
                    <option>11 – 50 employees</option>
                    <option>51 – 200 employees</option>
                    <option>201 – 500 employees</option>
                    <option>500+ employees</option>
                  </select>
                </Field>
              </div>
              <Field label="CBN licence tier">
                <select name="licenceTier" value={form.licenceTier} onChange={handleChange}
                  style={{ ...field, color: form.licenceTier ? "#fff" : "rgba(255,255,255,0.35)" }}>
                  <option value="">Select tier (optional)</option>
                  <option>Unit MFB</option>
                  <option>State MFB</option>
                  <option>National MFB</option>
                  <option>PSB / Payment Service Bank</option>
                  <option>Fintech (non-MFB)</option>
                </select>
              </Field>
            </Section>

            {/* ── Section 2: Contact ── */}
            <Section label="Your contact details">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <Field label="Full name *">
                  <input required name="contact" value={form.contact} onChange={handleChange}
                    placeholder="Ada Okonkwo" style={field} />
                </Field>
                <Field label="Role *">
                  <select required name="role" value={form.role} onChange={handleChange}
                    style={{ ...field, color: form.role ? "#fff" : "rgba(255,255,255,0.35)" }}>
                    <option value="" disabled>Select role</option>
                    <option>Chief Compliance Officer</option>
                    <option>Compliance Manager</option>
                    <option>Legal & Risk</option>
                    <option>CEO / MD</option>
                    <option>CTO / IT Lead</option>
                    <option>Other</option>
                  </select>
                </Field>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <Field label="Work email *">
                  <input required type="email" name="email" value={form.email} onChange={handleChange}
                    placeholder="ada@mfb.ng" style={field} />
                </Field>
                <Field label="Phone number">
                  <input type="tel" name="phone" value={form.phone} onChange={handleChange}
                    placeholder="+234 801 000 0000" style={field} />
                </Field>
              </div>
            </Section>

            {/* ── Section 3: Demo type ── */}
            <Section label="What would you like to receive? *">
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <DemoOption
                  active={demoTypes.includes("live")}
                  onToggle={() => toggle("live")}
                  icon={
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                      <circle cx="9" cy="9" r="7.5" stroke="#818CF8" strokeWidth="1.4"/>
                      <path d="M7 6.5l5 2.5-5 2.5V6.5Z" fill="#818CF8"/>
                    </svg>
                  }
                  title="Live demo"
                  desc="A tailored 30-minute walkthrough with a compliance specialist — your data, your workflows."
                  color="#818CF8"
                />
                <DemoOption
                  active={demoTypes.includes("recorded")}
                  onToggle={() => toggle("recorded")}
                  icon={
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                      <rect x="1.5" y="4" width="11" height="10" rx="2" stroke="#34D399" strokeWidth="1.4"/>
                      <path d="M12.5 7l4-2v8l-4-2V7Z" stroke="#34D399" strokeWidth="1.4" strokeLinejoin="round"/>
                    </svg>
                  }
                  title="Recorded demo"
                  desc="Watch a full product walkthrough on your own schedule — sent directly to your inbox."
                  color="#34D399"
                />
                <DemoOption
                  active={demoTypes.includes("deck")}
                  onToggle={() => toggle("deck")}
                  icon={
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                      <rect x="2" y="2.5" width="14" height="13" rx="2" stroke="#F59E0B" strokeWidth="1.4"/>
                      <path d="M5 7h8M5 10h6M5 13h4" stroke="#F59E0B" strokeWidth="1.4" strokeLinecap="round"/>
                    </svg>
                  }
                  title="Slide deck"
                  desc="Download our product overview and compliance capability deck — shareable with your leadership team."
                  color="#F59E0B"
                />
              </div>
              {demoTypes.length === 0 && (
                <p style={{ fontSize: 12, color: "#EF4444", marginTop: 8 }}>Please select at least one option.</p>
              )}
            </Section>

            {/* ── Section 4: Message ── */}
            <Section label="Anything specific you'd like covered?" last>
              <textarea
                name="message" value={form.message} onChange={handleChange}
                placeholder="e.g. We want to see how Iroko handles CBN filing deadlines and automated KYC gap detection for a national MFB…"
                rows={4}
                style={{ ...field, resize: "vertical", lineHeight: 1.65 }}
              />
            </Section>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || demoTypes.length === 0}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                fontSize: 15, fontWeight: 700, color: "#fff",
                padding: "14px 24px", borderRadius: 10, width: "100%",
                background: (loading || demoTypes.length === 0) ? "rgba(74,85,212,0.45)" : "#4A55D4",
                border: "1px solid rgba(255,255,255,0.12)",
                boxShadow: demoTypes.length > 0 ? "0 0 28px rgba(74,85,212,0.35)" : "none",
                cursor: (loading || demoTypes.length === 0) ? "not-allowed" : "pointer",
                marginTop: 8,
              }}
            >
              {loading ? "Submitting…" : (
                <>
                  Submit request
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </>
              )}
            </button>
            <p style={{ fontSize: 12, color: "rgba(255,255,255,0.22)", textAlign: "center", marginTop: 14 }}>
              No credit card required · Iroko AI is invite-only
            </p>

          </form>
        </div>
      </main>
    </div>
  );
}

/* ── helper components ── */

function Section({ label, children, last }: { label: string; children: React.ReactNode; last?: boolean }) {
  return (
    <div style={{
      borderBottom: last ? "none" : "1px solid rgba(255,255,255,0.07)",
      paddingBottom: 28, marginBottom: 28,
    }}>
      <p style={{
        fontSize: 11, fontWeight: 700, textTransform: "uppercase",
        letterSpacing: "0.1em", color: "rgba(255,255,255,0.3)",
        margin: "0 0 18px",
      }}>
        {label}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{
        display: "block", fontSize: 12, fontWeight: 600,
        color: "rgba(255,255,255,0.55)", marginBottom: 7,
      }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function DemoOption({
  active, onToggle, icon, title, desc, color,
}: {
  active: boolean;
  onToggle: () => void;
  icon: React.ReactNode;
  title: string;
  desc: string;
  color: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      style={{
        display: "flex", alignItems: "flex-start", gap: 14,
        padding: "16px 18px", borderRadius: 12, cursor: "pointer",
        background: active ? `${color}10` : "#0F1420",
        border: active ? `1.5px solid ${color}55` : "1.5px solid rgba(255,255,255,0.09)",
        textAlign: "left", width: "100%",
        transition: "border-color 0.15s, background 0.15s",
      }}
    >
      {/* Checkbox */}
      <div style={{
        width: 20, height: 20, borderRadius: 6, flexShrink: 0, marginTop: 1,
        border: active ? `2px solid ${color}` : "2px solid rgba(255,255,255,0.2)",
        background: active ? color : "transparent",
        display: "flex", alignItems: "center", justifyContent: "center",
        transition: "all 0.15s",
      }}>
        {active && (
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
            <path d="M2 5.5l2.5 2.5 4.5-4.5" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
      {/* Icon */}
      <div style={{
        width: 36, height: 36, borderRadius: 9, flexShrink: 0,
        background: `${color}12`, border: `1px solid ${color}25`,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {icon}
      </div>
      {/* Text */}
      <div style={{ flex: 1 }}>
        <p style={{ fontSize: 14, fontWeight: 700, color: "#fff", margin: "0 0 4px" }}>{title}</p>
        <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", margin: 0, lineHeight: 1.55 }}>{desc}</p>
      </div>
    </button>
  );
}

function pill(color: string): React.CSSProperties {
  return {
    fontSize: 12, fontWeight: 600, padding: "4px 12px", borderRadius: 99,
    background: `${color}18`, color, border: `1px solid ${color}35`,
  };
}
