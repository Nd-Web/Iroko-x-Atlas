import AppShell from "@/components/layout/AppShell";
import Link from "next/link";
import ApiKeyPanel from "@/components/compliance/ApiKeyPanel";
import { REGULATORY_FILINGS, STATUS_LABELS } from "@/lib/filings-data";

const STATS = [
  { label: "Open DSRs",           value: "3",  sub: "data subject requests",      accent: "#F79009", color: "#F79009" },
  { label: "Pending DPIAs",       value: "2",  sub: "awaiting DPO sign-off",      accent: "#4A55D4", color: "#4A55D4" },
  { label: "CBN Filings due 30d", value: "2",  sub: "Lending & AML returns due",  accent: "#F04438", color: "#F04438" },
  { label: "Monitored Fintechs",  value: "5",  sub: "Kuda · Carbon · Moniepoint", accent: "#17B26A", color: "#17B26A" },
];

export default function ComplianceAgentPage() {
  return (
    <AppShell
      title="Fintech Compliance Agent"
      subtitle="CBN · SEC · NDPA · DPO console · DPIA wizard · filing history"
      actions={
        <Link href="/chat?agent=Compliance" className="btn-primary py-2 px-[14px] text-[13px] no-underline">
          Ask Compliance Agent →
        </Link>
      }
    >
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[14px]">
        {STATS.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-[18px] px-5">
            <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            <div className="text-[28px] font-bold tracking-[-0.04em] leading-none mb-[5px]" style={{ color: s.color }}>{s.value}</div>
            <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{s.label}</div>
            <div className="text-[11.5px] text-gray-400">{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-[14px]">
        {/* Regulatory filings */}
        <div className="card overflow-hidden">
          <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Regulatory filings</h2>
            <Link href="/compliance/reports" className="text-[12.5px] text-brand-600 no-underline font-semibold flex items-center gap-1">
              All reports
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2.5 6h7M7 3.5l2.5 2.5L7 8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </Link>
          </div>
          <div className="py-2">
            {REGULATORY_FILINGS.map((f, i, arr) => {
              const st = {
                "in-progress": { color: "var(--color-brand-700)",   bg: "var(--color-brand-50)"   },
                "not-started": { color: "var(--color-gray-400)",    bg: "var(--color-gray-100)"   },
                clear:         { color: "var(--color-success-700)", bg: "var(--color-success-50)" },
                submitted:     { color: "var(--color-success-700)", bg: "var(--color-success-50)" },
              }[f.status]!;
              const dueLabel = f.status === "submitted"
                ? `Submitted: ${f.due}`
                : `Due: ${f.due}`;
              return (
                <div key={f.name} className={`flex justify-between items-center gap-3 py-[11px] px-5${i < arr.length - 1 ? " border-b border-border-default" : ""}`}>
                  <div className="min-w-0">
                    <div className="text-[13px] font-medium text-gray-700 mb-[3px] truncate">{f.name}</div>
                    <div className="flex items-center gap-1.5">
                      <span className="bg-gray-100 px-1.5 rounded text-[10.5px] font-bold text-gray-500">{f.regulator}</span>
                      <span className="text-[11.5px] text-gray-400">{dueLabel}</span>
                    </div>
                  </div>
                  <span className="text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0" style={{ color: st.color, background: st.bg }}>{STATUS_LABELS[f.status]}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* DPIA tracker */}
        <div className="card overflow-hidden">
          <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">DPIA tracker</h2>
            <button className="btn-secondary py-[5px] px-3 text-xs">+ New DPIA</button>
          </div>
          <div className="py-2">
            {[
              { name: "Credit Scoring ML Pipeline v3",  lawful: "Legitimate interest", risk: "High",   status: "in-review" },
              { name: "KYC Biometric Verification Flow", lawful: "Legal obligation",    risk: "High",   status: "draft"     },
              { name: "Loan Repayment Behaviour Model",  lawful: "Contract",            risk: "Medium", status: "approved"  },
              { name: "Savings Analytics Dashboard v2",  lawful: "Legitimate interest", risk: "Low",    status: "approved"  },
            ].map((d, i, arr) => {
              const st = {
                "in-review": { color: "var(--color-info-700)",    bg: "var(--color-info-50)",    label: "In review" },
                draft:       { color: "var(--color-warning-700)", bg: "var(--color-warning-50)", label: "Draft"     },
                approved:    { color: "var(--color-success-700)", bg: "var(--color-success-50)", label: "Approved"  },
              }[d.status]!;
              return (
                <div key={d.name} className={`flex justify-between items-center gap-3 py-[11px] px-5${i < arr.length - 1 ? " border-b border-border-default" : ""}`}>
                  <div className="min-w-0">
                    <div className="text-[13px] font-medium text-gray-700 mb-[3px] truncate">{d.name}</div>
                    <div className="text-[11.5px] text-gray-400 truncate">
                      {d.lawful} ·{" "}
                      <span className={`font-semibold ${d.risk === "High" ? "text-danger-700" : d.risk === "Medium" ? "text-warning-700" : "text-success-700"}`}>
                        {d.risk} risk
                      </span>
                    </div>
                  </div>
                  <span className="text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0" style={{ color: st.color, background: st.bg }}>{st.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* API key */}
      <ApiKeyPanel />

      {/* DSR queue */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border-default">
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Data subject request queue</h2>
          <p className="text-xs text-gray-400 mt-[2px]">Must respond within 30 days of receipt</p>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[800px]">
            <div className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3" style={{ gridTemplateColumns: "90px 1fr 120px 100px 90px 90px" }}>
              {["Ref", "Request", "Subject", "Type", "Received", "SLA"].map((h) => (
                <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
              ))}
            </div>
            {[
              { ref: "DSR-0041", req: "Right to access — full data export requested",     subject: "Consumer",   type: "Access",        received: "Apr 30", sla: "1 day left", urgent: true  },
              { ref: "DSR-0040", req: "Right to erasure — account and transaction data",  subject: "Consumer",   type: "Erasure",       received: "Apr 28", sla: "3 days",     urgent: false },
              { ref: "DSR-0039", req: "Right to rectification — incorrect NIN on file",   subject: "Enterprise", type: "Rectification", received: "Apr 27", sla: "4 days",     urgent: false },
            ].map((dsr, i, arr) => (
              <div
                key={dsr.ref}
                className={`grid items-center py-3 px-5 gap-3 hover:bg-gray-50 transition-colors${i < arr.length - 1 ? " border-b border-border-default" : ""}`}
                style={{ gridTemplateColumns: "90px 1fr 120px 100px 90px 90px" }}
              >
                <span className="font-mono text-xs text-brand-700 font-semibold">{dsr.ref}</span>
                <span className="text-[13px] text-gray-700 overflow-hidden text-ellipsis whitespace-nowrap">{dsr.req}</span>
                <span className="text-xs text-gray-500">{dsr.subject}</span>
                <span className="text-xs text-gray-500">{dsr.type}</span>
                <span className="text-xs text-gray-400">{dsr.received}</span>
                <span className={`text-xs font-bold ${dsr.urgent ? "text-danger-700" : "text-success-700"}`}>{dsr.sla}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
