import AppShell from "@/components/layout/AppShell";
import Link from "next/link";

export const metadata = { title: "Care Agent" };

const STATS = [
  { label: "MoMo deduction tickets", value: "850",    sub: "Q1 2026 · Lagos +312% vs Q4",  accent: "#38BDF8", color: "#38BDF8" },
  { label: "Disputed deductions",    value: "₦28.4M", sub: "under investigation",           accent: "#60A5FA", color: "#60A5FA" },
  { label: "Open complaints",        value: "128",    sub: "NCC-escalable: 3",              accent: "#F59E0B", color: "#F59E0B" },
  { label: "CSAT — incident day",    value: "41.2",   sub: "Ikeja outage · ~70 baseline",  accent: "#EF4444", color: "#EF4444" },
];

const PLANS = [
  { name: "Lagos — MoMo wallet deductions", price: "850", type: "MoMo",    updated: "2 hours ago" },
  { name: "Lagos — Ikeja cluster coverage",  price: "312", type: "Network", updated: "Feb 14"      },
  { name: "Abuja — data bundle billing",     price: "96",  type: "Billing", updated: "3 days ago"  },
  { name: "Kano — drop-call reports",        price: "74",  type: "Network", updated: "1 week ago"  },
  { name: "PH GRA — outage complaints",      price: "41",  type: "Network", updated: "2 weeks ago" },
];

const COMPLAINTS = [
  { type: "MoMo wallet deductions",        count: 34, pct: 27 },
  { type: "Network coverage / drop calls", count: 28, pct: 22 },
  { type: "Data bundle billing",           count: 21, pct: 16 },
  { type: "Failed recharge — airtime",     count: 18, pct: 14 },
  { type: "SIM registration & swap",       count: 12, pct: 9  },
];

const TYPE_COLORS: Record<string, string> = {
  MoMo:    "#38BDF8",
  Network: "#34D399",
  Billing: "#60A5FA",
};

export default function CareAgentPage() {
  return (
    <AppShell
      title="Care Agent"
      subtitle="MoMo complaints · coverage tickets · CSAT signals · regional queues"
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
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Regional complaint queues</h2>
              <p className="text-xs text-gray-400 mt-0.5">Live open volumes by region and category</p>
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
                    style={{ color: TYPE_COLORS[plan.type] || "var(--color-gray-500)", background: `${TYPE_COLORS[plan.type] || "#9C9CA6"}14` }}
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
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">High-priority complaint cohorts</h2>
            <p className="text-xs text-gray-400 mt-0.5">Cohorts approaching or exceeding NCC consumer-escalation thresholds</p>
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
              {["Cohort ID", "Segment", "Tickets", "Last activity", "Priority", "Action"].map((h) => (
                <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
              ))}
            </div>
            {[
              { msisdn: "COH-004421", seg: "MoMo deductions — Lagos",     arpu: "850", last: "2 hours ago", risk: "High",   action: "Review" },
              { msisdn: "COH-008812", seg: "Coverage — Ikeja cluster",    arpu: "312", last: "Feb 14",      risk: "High",   action: "Flag"   },
              { msisdn: "COH-001133", seg: "Billing — Abuja",             arpu: "96",  last: "3 days ago",  risk: "Medium", action: "Watch"  },
              { msisdn: "COH-005509", seg: "Enterprise (EBU) — Zenith Bank", arpu: "12", last: "5 days ago", risk: "Medium", action: "Watch"  },
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
                    color: row.risk === "High" ? "var(--color-danger-700)" : "var(--color-info-700)",
                    background: row.risk === "High" ? "var(--color-danger-50)" : "var(--color-info-50)",
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
