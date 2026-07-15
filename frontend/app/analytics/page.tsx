import AppShell from "@/components/layout/AppShell";
import { apiRequest } from "@/lib/api-client";

export const metadata = { title: "Analytics" };

// ─── Types ────────────────────────────────────────────────────────────────────

interface OverviewData {
  queries_week?: number;
  avg_response_ms?: number;
  watchdog_alert_rate?: number;
  agent_usage_breakdown?: Record<string, number>;
}

interface DashboardStatsData {
  total_documents?: number;
  documents_indexed?: number;
  total_queries_today?: number;
  total_queries_this_week?: number;
  active_alerts?: number;
  critical_alerts?: number;
  avg_query_response_ms?: number;
}

// ─── Static fallbacks ─────────────────────────────────────────────────────────

const FALLBACK_STATS = [
  { label: "Queries this week",  value: "8,412", delta: "+14%", deltaUp: true,  accent: "#4A55D4" },
  { label: "Avg latency",        value: "1.84s", delta: "−6%",  deltaUp: true,  accent: "#17B26A" },
  { label: "Documents indexed",  value: "8",     delta: "",     deltaUp: true,  accent: "#17B26A" },
  { label: "Active alerts",      value: "6",     delta: "",     deltaUp: false, accent: "#F04438" },
];

const FALLBACK_AGENTS = [
  { name: "Strategist", count: 3421, pct: 41, color: "#4A55D4" },
  { name: "Researcher", count: 1842, pct: 22, color: "#2E90FA" },
  { name: "Analyst",    count: 1204, pct: 14, color: "#17B26A" },
  { name: "Scribe",     count: 988,  pct: 12, color: "#F79009" },
  { name: "Watchdog",   count: 957,  pct: 11, color: "#F04438" },
];

const AGENT_COLORS: Record<string, string> = {
  Strategist: "#4A55D4",
  Researcher: "#2E90FA",
  Analyst:    "#17B26A",
  Scribe:     "#F79009",
  Watchdog:   "#F04438",
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export default async function AnalyticsPage() {
  const [overviewResult, statsResult] = await Promise.all([
    apiRequest<OverviewData>("/api/analytics/overview"),
    apiRequest<DashboardStatsData>("/api/analytics/stats"),
  ]);
  const overview = overviewResult.error === null ? overviewResult.data : null;
  const liveStats = statsResult.error === null ? statsResult.data : null;

  // ── KPI stats — all four tiles backed by live endpoints where available ──
  const stats = overview || liveStats
    ? [
        {
          label: "Queries this week",
          value:
            (overview?.queries_week ?? liveStats?.total_queries_this_week)?.toLocaleString() ??
            "8,412",
          delta: "+14%",
          deltaUp: true,
          accent: "#4A55D4",
        },
        {
          label: "Avg latency",
          value: (() => {
            const ms = overview?.avg_response_ms ?? liveStats?.avg_query_response_ms;
            return ms != null ? `${(ms / 1000).toFixed(2)}s` : "1.84s";
          })(),
          delta: "−6%",
          deltaUp: true,
          accent: "#17B26A",
        },
        {
          label: "Documents indexed",
          value: (liveStats?.documents_indexed ?? liveStats?.total_documents)?.toLocaleString() ?? "8",
          delta: "",
          deltaUp: true,
          accent: "#17B26A",
        },
        {
          label: "Active alerts",
          value: liveStats?.active_alerts?.toLocaleString() ?? "6",
          delta: liveStats?.critical_alerts ? `${liveStats.critical_alerts} critical` : "",
          deltaUp: false,
          accent: "#F04438",
        },
      ]
    : FALLBACK_STATS;

  // ── Agent usage bars — breakdown is a { AgentName: count } object ──
  let agents = FALLBACK_AGENTS;
  if (overview?.agent_usage_breakdown) {
    const breakdown = overview.agent_usage_breakdown;
    const total = Object.values(breakdown).reduce((s, v) => s + v, 0);
    const mapped = Object.entries(breakdown).map(([name, count]) => ({
      name,
      count,
      pct: total > 0 ? Math.round((count / total) * 100) : 0,
      color: AGENT_COLORS[name] ?? "#4A55D4",
    }));
    if (mapped.length > 0) agents = mapped;
  }

  const totalAgentQueries = agents.reduce((s, a) => s + a.count, 0);

  return (
    <AppShell
      title="Analytics"
      subtitle="Usage trends · retrieval quality · latency · agent utilisation"
    >
      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[14px]">
        {stats.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-[18px] px-5">
            <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            <div className="flex items-start justify-between mb-[10px]">
              <div className="text-[28px] font-bold text-gray-900 tracking-[-0.04em] leading-none">
                {s.value}
              </div>
              {s.delta && (
                <span className={`text-xs font-semibold px-2 py-[2px] rounded-full mt-[2px] ${s.deltaUp ? "text-success-700 bg-success-50" : "text-danger-700 bg-danger-50"}`}>
                  {s.delta}
                </span>
              )}
            </div>
            <div className="text-[13px] font-medium text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-[14px]">
        {/* By agent */}
        <div className="card py-5 md:py-[22px] px-5 md:px-6">
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em] mb-1">
            Queries by agent
          </h2>
          <p className="text-xs text-gray-400 mb-5">
            Last 7 days · {totalAgentQueries.toLocaleString()} total
          </p>
          <div className="flex flex-col gap-3.5">
            {agents.map((a) => (
              <div key={a.name}>
                <div className="flex justify-between items-center mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-[2px] inline-block shrink-0" style={{ background: a.color }} />
                    <span className="text-[13px] font-medium text-gray-700">{a.name}</span>
                  </div>
                  <div className="flex items-center gap-[10px]">
                    <span className="text-xs text-gray-400">{a.count.toLocaleString()}</span>
                    <span className="text-xs font-semibold text-gray-500 w-8 text-right">{a.pct}%</span>
                  </div>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${a.pct}%`, background: a.color }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
