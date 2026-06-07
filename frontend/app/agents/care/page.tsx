import AppShell from "@/components/layout/AppShell";
import Link from "next/link";

export const metadata = { title: "Care Agent" };

const STATS = [
  { label: "Active loan products",  value: "12",  sub: "lending, savings, BNPL",       accent: "#4A55D4", color: "#4A55D4" },
  { label: "Last product update",   value: "2d",   sub: "Kuda Overdraft revised",        accent: "#0BA5EC", color: "#0BA5EC" },
  { label: "Open complaints",       value: "128",  sub: "CBN-notifiable: 3",             accent: "#F79009", color: "#F79009" },
  { label: "High-risk borrowers",   value: "41",   sub: "above 5% single-obligor cap",  accent: "#F04438", color: "#F04438" },
];

const PLANS = [
  { name: "Kuda Overdraft — ₦50K limit", price: "5% p.a.",   type: "Lending", updated: "2 days ago"  },
  { name: "Carbon Loan — Personal",       price: "3% p.m.",   type: "Lending", updated: "2 days ago"  },
  { name: "Moniepoint Business Loan",     price: "2.5% p.m.", type: "Lending", updated: "1 week ago"  },
  { name: "Opay Savings — FlexSave",      price: "10% p.a.",  type: "Savings", updated: "3 days ago"  },
  { name: "Fairmoney BNPL — 30-day",      price: "4% flat",   type: "BNPL",    updated: "2 weeks ago" },
];

const COMPLAINTS = [
  { type: "Loan disbursement delays",     count: 34, pct: 27 },
  { type: "Incorrect interest charges",   count: 28, pct: 22 },
  { type: "Failed repayment deductions",  count: 21, pct: 16 },
  { type: "KYC rejection — onboarding",   count: 18, pct: 14 },
  { type: "Account restriction dispute",  count: 12, pct: 9  },
];

const TYPE_COLORS: Record<string, string> = {
  Lending: "#4A55D4",
  Savings: "#17B26A",
  BNPL:    "#0BA5EC",
};

export default function CareAgentPage() {
  return (
    <AppShell
      title="Care Agent"
      subtitle="Loan products · complaint scripts · borrower signals · KYC · BNPL"
      actions={
        <Link href="/chat?agent=Care" className="btn-primary px-[14px] py-2 text-[13px] no-underline">
          Ask Care Agent →
        </Link>
      }
    >
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[14px]">
        {STATS.map((s) => (
          <div key={s.label} className="card relative overflow-hidden px-5 py-[18px]">
            <div className="absolute inset-x-0 top-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            <div className="text-[28px] font-bold tracking-[-0.04em] leading-none mb-[5px]" style={{ color: s.color }}>{s.value}</div>
            <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{s.label}</div>
            <div className="text-[11.5px] text-gray-400">{s.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-[14px]">
        {/* Loan products */}
        <div className="card overflow-hidden">
          <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Active loan products</h2>
              <p className="text-xs text-gray-400 mt-0.5">Current rates across all fintech product lines</p>
            </div>
            <button className="btn-secondary px-3 py-[5px] text-xs">View all</button>
          </div>
          <div className="py-1">
            {PLANS.map((plan, i) => (
              <div key={plan.name} className={`flex justify-between items-center gap-3 px-5 py-[11px]${i < PLANS.length - 1 ? " border-b border-border-default" : ""}`}>
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-gray-700 mb-[2px] truncate">{plan.name}</div>
                  <div className="text-[11.5px] text-gray-400">Updated {plan.updated}</div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className="hidden xs:inline-block text-[11px] font-semibold px-2 py-px rounded-full"
                    style={{ color: TYPE_COLORS[plan.type] || "var(--color-gray-500)", background: `${TYPE_COLORS[plan.type] || "#888"}14` }}
                  >{plan.type}</span>
                  <span className="text-[13px] font-bold text-gray-800 font-mono">{plan.price}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Complaint breakdown */}
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-border-default">
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Complaint breakdown</h2>
            <p className="text-xs text-gray-400 mt-0.5">Rolling 30-day window · 128 total open</p>
          </div>
          <div className="px-5 py-4 flex flex-col gap-[14px]">
            {COMPLAINTS.map((c) => (
              <div key={c.type}>
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-[13px] font-medium text-gray-700">{c.type}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-600">{c.count}</span>
                    <span className="text-[11px] text-gray-400">{c.pct}%</span>
                  </div>
                </div>
                <div className="h-[5px] bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-brand-400 rounded-full transition-[width] duration-300" style={{ width: `${c.pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* High-risk borrower table */}
      <div className="card overflow-hidden">
        <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">High-risk borrower signals</h2>
            <p className="text-xs text-gray-400 mt-0.5">Borrowers approaching or exceeding single-obligor CBN limit</p>
          </div>
          <Link href="/chat?agent=Care&q=high-risk" className="btn-secondary px-3 py-[5px] text-xs no-underline">
            Get script →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[800px]">
            <div
              className="grid px-5 py-[9px] bg-gray-50 border-b border-border-default gap-3"
              style={{ gridTemplateColumns: "130px 1fr 90px 110px 90px 100px" }}
            >
              {["Borrower ID", "Segment", "Exposure", "Last activity", "Risk", "Action"].map((h) => (
                <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
              ))}
            </div>
            {[
              { msisdn: "BRW-004421", seg: "SME Loan — Lagos",          arpu: "₦62M",  last: "4 days ago", risk: "High",   action: "Review" },
              { msisdn: "BRW-008812", seg: "Personal Loan — Kano",       arpu: "₦28M",  last: "6 days ago", risk: "High",   action: "Flag"   },
              { msisdn: "BRW-001133", seg: "BNPL — Abuja",               arpu: "₦17M",  last: "3 days ago", risk: "Medium", action: "Watch"  },
              { msisdn: "BRW-005509", seg: "Business Loan — PH",         arpu: "₦16M",  last: "5 days ago", risk: "Medium", action: "Watch"  },
            ].map((row, i, arr) => (
              <div
                key={row.msisdn}
                className={`grid px-5 py-3 gap-3 items-center hover:bg-gray-50 transition-colors${i < arr.length - 1 ? " border-b border-border-default" : ""}`}
                style={{ gridTemplateColumns: "130px 1fr 90px 110px 90px 100px" }}
              >
                <span className="font-mono text-xs text-brand-700 font-semibold">{row.msisdn}</span>
                <span className="text-[13px] text-gray-600">{row.seg}</span>
                <span className="text-[13px] font-semibold text-gray-800 font-mono">{row.arpu}</span>
                <span className="text-xs text-gray-400">{row.last}</span>
                <span
                  className="text-[11px] font-semibold px-2 py-0.5 rounded-full w-fit"
                  style={{
                    color: row.risk === "High" ? "var(--color-danger-700)" : "var(--color-warning-700)",
                    background: row.risk === "High" ? "var(--color-danger-50)" : "var(--color-warning-50)",
                  }}
                >{row.risk}</span>
                <button className="btn-secondary px-3 py-1 text-xs">{row.action}</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
