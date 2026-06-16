import Link from "next/link";

const BG = "#0D1F14";
const BRAND = "#2E7D32";
const BRAND_LIGHT = "#4CAF50";
const MUTED = "rgba(255,255,255,0.45)";
const CARD_BG = "rgba(255,255,255,0.05)";
const CARD_BORDER = "rgba(255,255,255,0.10)";

export default function DemoPage() {
  return (
    <main style={{ background: BG, minHeight: "100vh", color: "#fff", fontFamily: "system-ui, sans-serif" }}>

      {/* Nav */}
      <nav style={{ borderBottom: `1px solid ${CARD_BORDER}`, padding: "0 40px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", height: 60, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-0.02em", color: "#fff" }}>
            <span style={{ color: BRAND_LIGHT }}>Iroko</span> AI
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <Link href="/dashboard" style={{ fontSize: 13, fontWeight: 600, color: MUTED, textDecoration: "none", padding: "7px 16px", borderRadius: 8, border: `1px solid ${CARD_BORDER}` }}>
              Dashboard
            </Link>
            <Link href="/compliance/reports" style={{ fontSize: 13, fontWeight: 600, color: "#fff", textDecoration: "none", padding: "7px 16px", borderRadius: 8, background: BRAND }}>
              Run Check →
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section style={{ maxWidth: 800, margin: "0 auto", padding: "96px 40px 72px", textAlign: "center" }}>
        <div style={{ display: "inline-block", fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", color: BRAND_LIGHT, background: "rgba(46,125,50,0.15)", border: `1px solid rgba(46,125,50,0.3)`, borderRadius: 999, padding: "5px 14px", marginBottom: 28, textTransform: "uppercase" }}>
          Built for Nigerian MFBs &amp; Fintechs
        </div>

        <h1 style={{ fontSize: "clamp(32px, 5vw, 52px)", fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 24px", color: "#fff" }}>
          Compliance Intelligence<br />
          <span style={{ color: BRAND_LIGHT }}>for African Financial Institutions</span>
        </h1>

        <p style={{ fontSize: 18, lineHeight: 1.65, color: MUTED, maxWidth: 640, margin: "0 auto 40px" }}>
          Five autonomous agents monitoring CBN · NCC · SEC regulations 24/7. Real-time verdicts. Tamper-proof audit trails. Built for Nigerian MFBs and fintechs.
        </p>

        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/dashboard" style={{ fontSize: 15, fontWeight: 700, color: "#fff", textDecoration: "none", padding: "14px 28px", borderRadius: 10, background: BRAND, display: "inline-block" }}>
            See Live Demo →
          </Link>
          <Link href="/compliance/reports" style={{ fontSize: 15, fontWeight: 700, color: "#fff", textDecoration: "none", padding: "14px 28px", borderRadius: 10, border: `1.5px solid rgba(255,255,255,0.2)`, display: "inline-block" }}>
            Run Compliance Check →
          </Link>
        </div>
      </section>

      {/* Stats bar */}
      <div style={{ borderTop: `1px solid ${CARD_BORDER}`, borderBottom: `1px solid ${CARD_BORDER}` }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 40px", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          {[
            { stat: "$1.59B", label: "annual African telecom fraud" },
            { stat: "₦12.4B", label: "active NCC fines" },
            { stat: "900+", label: "Nigerian MFBs" },
            { stat: "0", label: "platforms built for this market" },
          ].map(({ stat, label }) => (
            <div key={stat + label} style={{ padding: "28px 20px", textAlign: "center", borderRight: `1px solid ${CARD_BORDER}` }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: BRAND_LIGHT, letterSpacing: "-0.03em", lineHeight: 1 }}>{stat}</div>
              <div style={{ fontSize: 13, color: MUTED, marginTop: 6 }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Feature cards */}
      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "80px 40px" }}>
        <h2 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: MUTED, textAlign: "center", marginBottom: 48 }}>
          What Iroko AI does
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20 }}>
          {[
            {
              icon: "⚖️",
              title: "GO / NO-GO / MONITOR Verdicts",
              body: "Every compliance question answered in under 2 seconds, with the specific CBN or NCC regulation cited.",
              accent: BRAND_LIGHT,
            },
            {
              icon: "🔐",
              title: "Hash-Chained Audit Trail",
              body: "Every decision cryptographically sealed and mapped to specific regulation sections. CBN-verifiable in 60 seconds.",
              accent: "#64B5F6",
            },
            {
              icon: "🤖",
              title: "5 Autonomous Agents",
              body: "Regulatory Monitor · Competitor Watchdog · Vendor Risk · Fraud Sentinel · Market Strategist. Running 24/7.",
              accent: "#FFB74D",
            },
          ].map(({ icon, title, body, accent }) => (
            <div key={title} style={{ background: CARD_BG, border: `1px solid ${CARD_BORDER}`, borderRadius: 16, padding: "28px 26px", display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ fontSize: 28 }}>{icon}</div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: accent, margin: 0, lineHeight: 1.3 }}>{title}</h3>
              <p style={{ fontSize: 14, color: MUTED, lineHeight: 1.65, margin: 0 }}>{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA strip */}
      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "0 40px 80px" }}>
        <div style={{ background: "rgba(46,125,50,0.12)", border: `1px solid rgba(46,125,50,0.25)`, borderRadius: 16, padding: "48px 40px", textAlign: "center" }}>
          <h2 style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", margin: "0 0 12px" }}>
            Ready to see it in action?
          </h2>
          <p style={{ fontSize: 15, color: MUTED, margin: "0 0 32px" }}>
            Run a live compliance check against CBN and NCC regulations — no setup required.
          </p>
          <Link href="/compliance/reports" style={{ fontSize: 15, fontWeight: 700, color: "#fff", textDecoration: "none", padding: "14px 32px", borderRadius: 10, background: BRAND, display: "inline-block" }}>
            Run Compliance Check →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: `1px solid ${CARD_BORDER}`, padding: "24px 40px", textAlign: "center" }}>
        <p style={{ fontSize: 12, color: MUTED, margin: 0 }}>
          Powered by Azure OpenAI · Bright Data · Microsoft Semantic Kernel
        </p>
      </footer>
    </main>
  );
}
