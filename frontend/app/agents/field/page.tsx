import AppShell from "@/components/layout/AppShell";
import Link from "next/link";

const STATS = [
  { label: "Active sites",          value: "4,812", sub: "across 36 states",     accent: "#4A55D4", color: "#4A55D4" },
  { label: "Rollout in progress",   value: "38",    sub: "fibre + 5G FWA sites", accent: "#0BA5EC", color: "#0BA5EC" },
  { label: "Vandalism alerts",      value: "9",     sub: "this month",            accent: "#F04438", color: "#F04438" },
  { label: "Offline bundles",       value: "14",    sub: "engineer downloads",    accent: "#17B26A", color: "#17B26A" },
];

const SITES = [
  { id: "KAN-0341", name: "Kano North BTS",      region: "Kano",          lastMaint: "Mar 12, 2025", status: "operational" as const },
  { id: "LAG-1204", name: "Ikeja Industrial BTS", region: "Lagos",         lastMaint: "Apr 18, 2025", status: "degraded"    as const },
  { id: "ABJ-0088", name: "Garki Area 11 Tower",  region: "Abuja",         lastMaint: "Feb 28, 2025", status: "operational" as const },
  { id: "PH-0312",  name: "GRA Phase 2 BTS",      region: "Port Harcourt", lastMaint: "Jan 9, 2025",  status: "operational" as const },
  { id: "KAD-0201", name: "Kaduna Central BTS",   region: "Kaduna",        lastMaint: "Apr 2, 2025",  status: "maintenance" as const },
];

const SITE_STATUS = {
  operational: { color: "var(--color-success-700)", bg: "var(--color-success-50)", label: "Operational" },
  degraded:    { color: "var(--color-danger-700)",  bg: "var(--color-danger-50)",  label: "Degraded"    },
  maintenance: { color: "var(--color-warning-700)", bg: "var(--color-warning-50)", label: "Maintenance" },
};

const BUNDLES = [
  { name: "Kano-Kaduna Rollout Q2", engineer: "Musa Garba",  size: "48 MB", docs: 34, synced: "Today 06:11" },
  { name: "Lagos Fibre Phase 3",    engineer: "Emeka Obi",   size: "62 MB", docs: 51, synced: "Yesterday"   },
  { name: "Abuja 5G FWA Sites",     engineer: "Ngozi Eze",   size: "31 MB", docs: 22, synced: "Apr 29"      },
];

export default function FieldAgentPage() {
  return (
    <AppShell
      title="Field Agent"
      subtitle="Site cards · BoQs · route maps · offline bundles · rollout"
      actions={
        <Link href="/chat?agent=Field" className="btn-primary py-2 px-[14px] text-[13px] no-underline">
          Ask Field Agent →
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
        {/* Site cards */}
        <div className="card overflow-hidden">
          <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Recent site cards</h2>
              <p className="text-xs text-gray-400 mt-[2px]">Last accessed or updated by field team</p>
            </div>
            <button className="btn-secondary py-[5px] px-3 text-xs">All sites</button>
          </div>
          <div className="py-1">
            {SITES.map((site, i) => {
              const st = SITE_STATUS[site.status];
              return (
                <div
                  key={site.id}
                  className={`flex justify-between items-center gap-3 px-5 py-3 cursor-pointer hover:bg-gray-50 transition-colors${i < SITES.length - 1 ? " border-b border-border-default" : ""}`}
                >
                  <div className="flex items-center gap-[10px] min-w-0">
                    <span className="hidden xs:inline-block font-mono text-[11px] text-brand-700 font-bold bg-brand-50 px-[7px] py-[2px] rounded-sm shrink-0">{site.id}</span>
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-gray-700 mb-[2px] truncate">{site.name}</div>
                      <div className="text-[11.5px] text-gray-400 truncate">{site.region} · Last maint: {site.lastMaint}</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-semibold px-2 py-[2px] rounded-full shrink-0" style={{ color: st.color, background: st.bg }}>{st.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Offline bundles */}
        <div className="card overflow-hidden">
          <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Offline bundles</h2>
              <p className="text-xs text-gray-400 mt-[2px]">Field-cached document sets</p>
            </div>
            <button className="btn-primary py-[5px] px-3 text-xs">+ Build</button>
          </div>
          <div className="py-1">
            {BUNDLES.map((b, i) => (
              <div
                key={b.name}
                className={`px-5 py-[13px] hover:bg-gray-50 transition-colors${i < BUNDLES.length - 1 ? " border-b border-border-default" : ""}`}
              >
                <div className="flex justify-between items-center mb-[3px] gap-2">
                  <span className="text-[13px] font-medium text-gray-700 truncate">{b.name}</span>
                  <span className="text-xs font-mono text-gray-400 shrink-0">{b.size}</span>
                </div>
                <div className="flex flex-wrap items-center gap-y-1 gap-x-[10px]">
                  <span className="text-[11.5px] text-gray-500 font-medium">{b.engineer}</span>
                  <span className="hidden xs:inline text-[11.5px] text-gray-300">·</span>
                  <span className="text-[11.5px] text-gray-400">{b.docs} docs</span>
                  <span className="hidden xs:inline text-[11.5px] text-gray-300">·</span>
                  <span className="text-[11.5px] text-gray-300 truncate">Synced {b.synced}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Rollout tracker */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border-default">
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Active rollout programmes</h2>
          <p className="text-xs text-gray-400 mt-[2px]">Sites in commissioning or BoQ review phase</p>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[800px]">
            <div className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3" style={{ gridTemplateColumns: "1fr 110px 90px 120px 110px 100px" }}>
              {["Programme", "Region", "Sites", "Lead engineer", "Target date", "Status"].map((h) => (
                <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
              ))}
            </div>
            {[
              { name: "Kano-Kaduna Fibre Rollout Q2", region: "North",  sites: 12, lead: "Musa Garba",  target: "Jun 30, 2026", status: "on-track"    },
              { name: "Lagos 5G FWA Phase 3",         region: "Lagos",  sites: 9,  lead: "Emeka Obi",   target: "Jul 15, 2026", status: "at-risk"     },
              { name: "Abuja Urban Densification",    region: "Abuja",  sites: 7,  lead: "Ngozi Eze",   target: "May 30, 2026", status: "on-track"    },
              { name: "Delta Fibre Expansion",        region: "South",  sites: 10, lead: "TBC",          target: "Aug 31, 2026", status: "not-started" },
            ].map((r, i, arr) => {
              const st = {
                "on-track":    { color: "var(--color-success-700)", bg: "var(--color-success-50)", label: "On track"    },
                "at-risk":     { color: "var(--color-warning-700)", bg: "var(--color-warning-50)", label: "At risk"     },
                "not-started": { color: "var(--color-gray-400)",    bg: "var(--color-gray-100)",   label: "Not started" },
              }[r.status]!;
              return (
                <div
                  key={r.name}
                  className={`grid items-center py-3 px-5 gap-3 hover:bg-gray-50 transition-colors${i < arr.length - 1 ? " border-b border-border-default" : ""}`}
                  style={{ gridTemplateColumns: "1fr 110px 90px 120px 110px 100px" }}
                >
                  <span className="text-[13px] font-medium text-gray-700 truncate">{r.name}</span>
                  <span className="text-xs text-gray-500">{r.region}</span>
                  <span className="text-xs font-semibold text-gray-700">{r.sites} sites</span>
                  <span className="text-xs text-gray-500">{r.lead}</span>
                  <span className="text-xs text-gray-400">{r.target}</span>
                  <span className="text-[11px] font-semibold px-2 py-[2px] rounded-full w-fit" style={{ color: st.color, background: st.bg }}>{st.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
