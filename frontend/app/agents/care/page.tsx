import AppShell from "@/components/layout/AppShell";
import Link from "next/link";

export const metadata = { title: "Care Agent" };

const STATS = [
  { label: "Active tariff plans", value: "34",  sub: "data, voice, MoMo, FWA",     accent: "#4A55D4", color: "#4A55D4" },
  { label: "Last tariff update",  value: "2d",   sub: "Yello Pulse revised",         accent: "#0BA5EC", color: "#0BA5EC" },
  { label: "Open complaints",     value: "128",  sub: "FCCPC-notifiable: 3",          accent: "#F79009", color: "#F79009" },
  { label: "Churn risk alerts",   value: "412",  sub: "high-value subscribers",       accent: "#F04438", color: "#F04438" },
];

const PLANS = [
  { name: "Yello Pulse 1GB",    price: "₦300",    type: "Data",  updated: "2 days ago"  },
  { name: "Yello Pulse 5GB",    price: "₦1,000",  type: "Data",  updated: "2 days ago"  },
  { name: "MoMo Transfer Plus", price: "0.5%",    type: "MoMo",  updated: "1 week ago"  },
  { name: "5G FWA Home 50Mbps", price: "₦15,000", type: "FWA",   updated: "3 days ago"  },
  { name: "TalkMore 200min",    price: "₦500",    type: "Voice", updated: "2 weeks ago" },
];

const COMPLAINTS = [
  { type: "MoMo deduction issues",      count: 34, pct: 27 },
  { type: "Data not loading",           count: 28, pct: 22 },
  { type: "Incorrect billing",          count: 21, pct: 16 },
  { type: "5G FWA connectivity drop",   count: 18, pct: 14 },
  { type: "Number porting failure",     count: 12, pct: 9  },
];

const TYPE_COLORS: Record<string, string> = {
  Data:  "#4A55D4",
  MoMo:  "#17B26A",
  FWA:   "#0BA5EC",
  Voice: "#F79009",
};

export default function CareAgentPage() {
  return (
    <AppShell
      title="Care Agent"
      subtitle="Tariffs · complaint scripts · churn signals · MoMo · 5G FWA"
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
        {/* Tariff plans */}
        <div className="card overflow-hidden">
          <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Active tariff plans</h2>
              <p className="text-xs text-gray-400 mt-0.5">Current pricing across all product lines</p>
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

      {/* Churn risk table */}
      <div className="card overflow-hidden">
        <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">High-value churn signals</h2>
            <p className="text-xs text-gray-400 mt-0.5">Subscribers with ARPU {">"} ₦15,000</p>
          </div>
          <Link href="/chat?agent=Care&q=churn" className="btn-secondary px-3 py-[5px] text-xs no-underline">
            Get script →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[800px]">
            <div
              className="grid px-5 py-[9px] bg-gray-50 border-b border-border-default gap-3"
              style={{ gridTemplateColumns: "130px 1fr 90px 110px 90px 100px" }}
            >
              {["MSISDN", "Segment", "ARPU", "Last active", "Risk", "Action"].map((h) => (
                <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
              ))}
            </div>
            {[
              { msisdn: "0801 XXX 4421", seg: "Enterprise — Lagos Zone",  arpu: "₦62,000", last: "4 days ago", risk: "High",   action: "Call" },
              { msisdn: "0703 XXX 8812", seg: "SME — Kano",               arpu: "₦28,400", last: "6 days ago", risk: "High",   action: "SMS"  },
              { msisdn: "0905 XXX 1133", seg: "Consumer — Abuja",          arpu: "₦17,900", last: "3 days ago", risk: "Medium", action: "Push" },
              { msisdn: "0812 XXX 5509", seg: "Consumer — Port Harcourt",  arpu: "₦16,200", last: "5 days ago", risk: "Medium", action: "Push" },
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
