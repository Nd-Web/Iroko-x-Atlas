"use client";
/**
 * app/workflows/page.tsx — Workflow management: document → insight → action.
 *
 * Tasks are auto-generated from Watchdog alerts and compliance verdicts
 * (routed to a department with an SLA deadline) and managed here on a
 * live board. Data comes exclusively from /api/workflows — no mock data.
 */
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

interface Task {
  id: string; title: string; description: string | null;
  source_type: string; alert_type: string | null; verdict: string | null;
  department: string | null; priority: string; status: string;
  sla_hours: number | null; due_date: string | null; overdue: boolean;
  assigned_to: { id: string; name: string } | null;
  suggested_actions: string[]; created_at: string | null;
}
interface WorkflowStats {
  total: number; by_status: Record<string, number>;
  open_by_priority: Record<string, number>;
  open_by_department: { department: string; open_tasks: number }[];
  overdue: number; completed_this_week: number; avg_completion_hours: number | null;
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: "#EF4444", high: "#F97316", medium: "#FACC15", low: "#6B7280",
};
const SOURCE_LABELS: Record<string, string> = {
  alert: "Auto · Watchdog", compliance: "Auto · Compliance", chat: "Chat", manual: "Manual",
};

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded-2xl border border-white/[0.06] px-5 py-4" style={{ background: "#0F1320" }}>
      <div className="text-[22px] font-bold" style={{ color: accent ?? "#E5E7EB" }}>{value}</div>
      <div className="text-[10.5px] text-[#6B7280] uppercase tracking-wider font-semibold mt-1">{label}</div>
    </div>
  );
}

function TaskCard({ task, onTransition }: { task: Task; onTransition: (id: string, status: string) => void }) {
  const pcol = PRIORITY_COLORS[task.priority] ?? "#6B7280";
  return (
    <div className="rounded-2xl border overflow-hidden transition-all duration-200 hover:border-white/20 group"
      style={{ background: "#0F1320", borderColor: "rgba(255,255,255,0.06)", borderLeft: `3px solid ${pcol}` }}>
      <div className="p-4">
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className="text-[9.5px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
            style={{ color: pcol, background: `${pcol}15`, border: `1px solid ${pcol}30` }}>
            {task.priority}
          </span>
          <span className="text-[9.5px] font-semibold px-2 py-0.5 rounded-full text-[#3B7BF6] bg-[#3B7BF6]/10 border border-[#3B7BF6]/20">
            {SOURCE_LABELS[task.source_type] ?? task.source_type}
          </span>
          {task.verdict && (
            <span className="text-[9.5px] font-bold px-2 py-0.5 rounded-full text-[#EF4444] bg-[#EF4444]/10 border border-[#EF4444]/20">
              {task.verdict}
            </span>
          )}
          {task.overdue && (
            <span className="text-[9.5px] font-bold px-2 py-0.5 rounded-full text-[#EF4444] bg-[#EF4444]/15 border border-[#EF4444]/40">
              OVERDUE
            </span>
          )}
        </div>
        <h3 className="text-[13px] font-semibold text-[#E5E7EB] leading-snug mb-1.5">{task.title}</h3>
        {task.description && (
          <p className="text-[11.5px] text-[#6B7280] leading-relaxed line-clamp-2">{task.description}</p>
        )}
        <div className="flex items-center gap-3 mt-3 text-[10px] text-[#4B5563] flex-wrap">
          {task.department && <span className="text-[#9CA3AF]">→ {task.department}</span>}
          {task.due_date && (
            <span className={task.overdue ? "text-[#EF4444] font-semibold" : ""}>
              due {formatRelativeTime(task.due_date)}
            </span>
          )}
          {task.created_at && <span>created {formatRelativeTime(task.created_at)}</span>}
        </div>
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/[0.05]">
          {task.status === "open" && (
            <button onClick={() => onTransition(task.id, "in_progress")}
              className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-[#3B7BF6] hover:bg-[#3B7BF6]/10 border border-[#3B7BF6]/20 transition-all">
              Start
            </button>
          )}
          {task.status !== "done" && task.status !== "dismissed" && (
            <button onClick={() => onTransition(task.id, "done")}
              className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-[#10B981] hover:bg-[#10B981]/10 border border-[#10B981]/20 transition-all">
              Complete
            </button>
          )}
          {(task.status === "open" || task.status === "blocked") && (
            <button onClick={() => onTransition(task.id, "dismissed")}
              className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-[#6B7280] hover:bg-white/[0.05] border border-white/[0.08] transition-all">
              Dismiss
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function WorkflowsPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [sweeping, setSweeping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [t, s] = await Promise.all([
        apiFetch<{ tasks: Task[] }>("/api/workflows/tasks?status=all&limit=200"),
        apiFetch<WorkflowStats>("/api/workflows/stats"),
      ]);
      setTasks(t.tasks);
      setStats(s);
    } catch (e) {
      setError((e as Error).message ?? "Failed to load workflows");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const transition = useCallback(async (id: string, status: string) => {
    try {
      await apiFetch(`/api/workflows/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      await load();
    } catch (e) {
      setError((e as Error).message ?? "Update failed");
    }
  }, [load]);

  const runSweep = useCallback(async () => {
    setSweeping(true); setNotice(null); setError(null);
    try {
      const r = await apiFetch<{ alerts_found: number; tasks_created: number }>(
        "/api/workflows/generate", { method: "POST" });
      setNotice(`Sweep complete — ${r.alerts_found} insights found, ${r.tasks_created} new tasks routed.`);
      await load();
    } catch (e) {
      setError((e as Error).message ?? "Sweep failed");
    } finally {
      setSweeping(false);
    }
  }, [load]);

  const columns: { key: string; title: string; filter: (t: Task) => boolean }[] = [
    { key: "open", title: "Open", filter: t => t.status === "open" || t.status === "blocked" },
    { key: "in_progress", title: "In Progress", filter: t => t.status === "in_progress" },
    { key: "done", title: "Completed", filter: t => t.status === "done" },
  ];

  return (
    <AppShell title="Workflows" subtitle="Document → insight → action: AI-generated tasks routed with owners and SLA deadlines">
      {/* Header: stats + sweep */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <StatCard label="Open tasks" value={stats ? (stats.by_status["open"] ?? 0) + (stats.by_status["blocked"] ?? 0) : "—"} />
        <StatCard label="In progress" value={stats?.by_status["in_progress"] ?? 0} accent="#3B7BF6" />
        <StatCard label="Done this week" value={stats?.completed_this_week ?? 0} accent="#10B981" />
        <StatCard label="Overdue" value={stats?.overdue ?? 0} accent={stats && stats.overdue > 0 ? "#EF4444" : undefined} />
        <div className="rounded-2xl border border-white/[0.06] px-4 py-3 flex items-center justify-center" style={{ background: "#0F1320" }}>
          <button onClick={() => void runSweep()} disabled={sweeping}
            className="w-full text-[12px] font-bold px-3 py-2.5 rounded-xl text-white bg-gradient-to-r from-[#3B7BF6] to-[#8B5CF6] hover:opacity-90 disabled:opacity-50 transition-all">
            {sweeping ? "Sweeping corpus…" : "⚡ Run Intelligence Sweep"}
          </button>
        </div>
      </div>

      {notice && (
        <div className="mb-4 text-[12px] text-[#10B981] bg-[#10B981]/10 border border-[#10B981]/25 rounded-xl px-4 py-2.5">{notice}</div>
      )}
      {error && (
        <div className="mb-4 text-[12px] text-[#EF4444] bg-[#EF4444]/10 border border-[#EF4444]/25 rounded-xl px-4 py-2.5">{error}</div>
      )}

      {/* Department load */}
      {stats && stats.open_by_department.length > 0 && (
        <div className="flex items-center gap-2 mb-5 flex-wrap">
          <span className="text-[10px] text-[#6B7280] uppercase tracking-wider font-bold">Open by department:</span>
          {stats.open_by_department.map(d => (
            <span key={d.department} className="text-[10.5px] px-2.5 py-1 rounded-full text-[#9CA3AF] bg-white/[0.04] border border-white/[0.08]">
              {d.department} · {d.open_tasks}
            </span>
          ))}
        </div>
      )}

      {/* Board */}
      {loading ? (
        <div className="text-[12px] text-[#6B7280] py-16 text-center">Loading workflow board…</div>
      ) : tasks.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-20">
          <div className="text-[14px] font-semibold text-[#9CA3AF]">No tasks yet</div>
          <p className="text-[11.5px] text-[#6B7280] max-w-sm text-center">
            Run an Intelligence Sweep — the Watchdog scans your document corpus for risks,
            deadlines and conflicts, and turns each finding into a routed task with an SLA.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {columns.map(col => {
            const colTasks = tasks.filter(col.filter);
            return (
              <div key={col.key}>
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-[12px] font-bold text-[#9CA3AF] uppercase tracking-wider">{col.title}</h2>
                  <span className="text-[10.5px] text-[#4B5563] font-semibold">{colTasks.length}</span>
                </div>
                <div className="space-y-3">
                  {colTasks.map(t => <TaskCard key={t.id} task={t} onTransition={transition} />)}
                  {colTasks.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-white/[0.06] py-8 text-center text-[11px] text-[#4B5563]">Empty</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
