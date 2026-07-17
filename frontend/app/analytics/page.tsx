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

interface ProductivityData {
  queries: { today: number; this_week: number; total: number; avg_answer_seconds: number | null };
  time_saved: { hours_last_30d: number; baseline_minutes_per_manual_search: number; note: string };
  documents: { indexed_total: number; chunks_searchable: number; indexed_this_week: number };
  workflow: { tasks_total: number; tasks_open: number; tasks_completed_this_week: number; tasks_auto_generated: number };
}

const AGENT_COLORS: Record<string, string> = {
  Strategist: "#4A55D4",
  Researcher: "#2E90FA",
  Analyst:    "#17B26A",
  Scribe:     "#F79009",
  Watchdog:   "#F04438",
};

// ─── Page ─────────────────────────────────────────────────────────────────────
// All numbers on this page come from live endpoints. When a metric has no
// data yet it renders 0 / "—" honestly — there are no fabricated fallbacks.

export default async function AnalyticsPage() {
  const [overviewResult, statsResult, prodResult] = await Promise.all([
    apiRequest<OverviewData>("/api/analytics/overview"),
    apiRequest<DashboardStatsData>("/api/analytics/stats"),
    apiRequest<ProductivityData>("/api/analytics/productivity"),
  ]);
  const overview = overviewResult.error === null ? overviewResult.data : null;
  const liveStats = statsResult.error === null ? statsResult.data : null;
  const prod = prodResult.error === null ? prodResult.data : null;

  // ── KPI tiles — live values, honest zeros when empty ──
  const avgMs = overview?.avg_response_ms ?? liveStats?.avg_query_response_ms;
  const stats = [
    {
      label: "Queries this week",
      value: (overview?.queries_week ?? liveStats?.total_queries_this_week ?? 0).toLocaleString(),
      delta: "",
      deltaUp: true,
      accent: "#4A55D4",
    },
    {
      label: "Avg answer time",
      value: avgMs != null && avgMs > 0 ? `${(avgMs / 1000).toFixed(2)}s` : "—",
      delta: "",
      deltaUp: true,
      accent: "#17B26A",
    },
    {
      label: "Documents indexed",
      value: (liveStats?.documents_indexed ?? liveStats?.total_documents ?? 0).toLocaleString(),
      delta: "",
      deltaUp: true,
      accent: "#17B26A",
    },
    {
      label: "Active alerts",
      value: (liveStats?.active_alerts ?? 0).toLocaleString(),
      delta: liveStats?.critical_alerts ? `${liveStats.critical_alerts} critical` : "",
      deltaUp: false,
      accent: "#F04438",
    },
  ];

  // ── Agent usage bars — live breakdown only; hidden when there is no data ──
  let agents: { name: string; count: number; pct: number; color: string }[] = [];
  if (overview?.agent_usage_breakdown) {
    const breakdown = overview.agent_usage_breakdown;
    const total = Object.values(breakdown).reduce((s, v) => s + v, 0);
    agents = Object.entries(breakdown).map(([name, count]) => ({
      name,
      count,
      pct: total > 0 ? Math.round((count / total) * 100) : 0,
      color: AGENT_COLORS[name] ?? "#4A55D4",
    }));
  }
  const totalAgentQueries = agents.reduce((s, a) => s + a.count, 0);

  return (
    <AppShell
      title="Analytics"
      subtitle="Live usage · productivity impact · latency · agent utilisation"
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

      {/* Productivity impact — the metric the platform exists to move */}
      {prod && (
        <div className="card py-5 md:py-[22px] px-5 md:px-6">
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em] mb-1">
            Productivity impact
          </h2>
          <p className="text-xs text-gray-400 mb-5">
            Measured from real query and workflow activity · manual-search baseline {prod.time_saved.baseline_minutes_per_manual_search} min
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-[24px] font-bold text-gray-900 leading-none">
                {prod.time_saved.hours_last_30d}h
              </div>
              <div className="text-xs text-gray-500 mt-1.5">Staff time saved · 30 days</div>
            </div>
            <div>
              <div className="text-[24px] font-bold text-gray-900 leading-none">
                {prod.queries.avg_answer_seconds != null ? `${prod.queries.avg_answer_seconds}s` : "—"}
              </div>
              <div className="text-xs text-gray-500 mt-1.5">Avg time-to-answer (vs {prod.time_saved.baseline_minutes_per_manual_search} min manual)</div>
            </div>
            <div>
              <div className="text-[24px] font-bold text-gray-900 leading-none">
                {prod.documents.chunks_searchable.toLocaleString()}
              </div>
              <div className="text-xs text-gray-500 mt-1.5">Knowledge chunks searchable across {prod.documents.indexed_total} documents</div>
            </div>
            <div>
              <div className="text-[24px] font-bold text-gray-900 leading-none">
                {prod.workflow.tasks_auto_generated.toLocaleString()}
              </div>
              <div className="text-xs text-gray-500 mt-1.5">Tasks auto-generated · {prod.workflow.tasks_completed_this_week} completed this week</div>
            </div>
          </div>
          <p className="text-[10.5px] text-gray-400 mt-4 leading-relaxed">{prod.time_saved.note}</p>
        </div>
      )}

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
          {agents.length === 0 ? (
            <p className="text-xs text-gray-400 py-6 text-center">
              No agent activity recorded yet — usage appears here as questions are asked.
            </p>
          ) : (
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
          )}
        </div>
      </div>
    </AppShell>
  );
}
