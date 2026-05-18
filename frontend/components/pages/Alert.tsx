"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

// ─── Types ────────────────────────────────────────────────────────────────────

interface RawAlert {
  id?: string;
  title?: string;
  summary?: string;
  severity?: string;
  status?: string;
  alert_type?: string;
  metadata?: Record<string, unknown>;
  extra_metadata?: {
    days_remaining?: number | null;
    due_date?: string;
    filing?: string;
    reference?: string;
    required_action?: string;
    document_id?: string;
    [key: string]: unknown;
  };
  suggested_actions?: string[];
  draft_content?: string;
  related_document_ids?: string[];
  created_at?: string;
}

interface AlertsResponse {
  alerts?: RawAlert[];
  total?: number;
  critical_count?: number;
  warning_count?: number;
}

interface AlertRecord {
  id: string;
  cluster: string;
  desc: string;
  severity: string;
  status: string;
  alert_type: string;
  age: string;
  sla: string;
  timeline: string[];
}

// ─── Base stats config ───────────────────────────────────────────────────────

const BASE_STATS = [
  {
    label: "Total alerts",
    value: "0",
    sub: "No data available",
    accent: "#4A55D4",
  },
  {
    label: "Critical",
    value: "0",
    sub: "No data available",
    accent: "#F04438",
  },
  {
    label: "Warning",
    value: "0",
    sub: "No data available",
    accent: "#F79009",
  },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function relativeAge(dateStr: string): string {
  const ms = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

function mapToAlertRecord(a: RawAlert, idx: number): AlertRecord {
  const rawStatus = (a.status ?? "").toLowerCase();
  const status = rawStatus === "acknowledged" ? "investigating" : "open";
  const severity = (a.severity ?? "warning").toLowerCase();
  const metadata = a.metadata ?? {};
  const monthlyValue = metadata.monthly_value;
  const slaValue =
    monthlyValue != null && !Number.isNaN(Number(monthlyValue))
      ? `₦${Number(monthlyValue).toLocaleString()}`
      : "—";
  const rawId = a.id ?? "";
  return {
    id: rawId
      ? `ALT-${rawId.slice(0, 8).toUpperCase()}`
      : `ALT-${String(idx + 1).padStart(8, "0")}`,
    cluster:
      (typeof metadata.cluster === "string" ? metadata.cluster : undefined) ??
      (typeof metadata.location === "string" ? metadata.location : undefined) ??
      "Unknown",
    desc: a.title ?? "No description available",
    severity: ["critical", "warning"].includes(severity) ? severity : "warning",
    status,
    alert_type: a.alert_type ?? "compliance_gap",
    age: a.created_at ? relativeAge(a.created_at) : "—",
    sla: slaValue,
    timeline: a.suggested_actions ?? [],
  };
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SEV: Record<string, { color: string; bg: string }> = {
  critical: { color: "var(--color-danger-700)", bg: "var(--color-danger-50)" },
  high: { color: "var(--color-warning-700)", bg: "var(--color-warning-50)" },
  warning: { color: "var(--color-warning-700)", bg: "var(--color-warning-50)" },
  medium: { color: "var(--color-info-700)", bg: "var(--color-info-50)" },
  low: { color: "var(--color-success-700)", bg: "var(--color-success-50)" },
};

const COL = "100px 1fr 90px 110px 60px 110px";
const PAGE_SIZE = 15;

// ─── Component ────────────────────────────────────────────────────────────────

export default function AlertsContent() {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [kpiStats, setKpiStats] = useState(BASE_STATS);
  const [selected, setSelected] = useState<AlertRecord | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  // Applied filter state
  const [filterSeverity, setFilterSeverity] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterType, setFilterType] = useState("all");

  // Pending state (inside modal before Apply)
  const [pendingSeverity, setPendingSeverity] = useState("all");
  const [pendingStatus, setPendingStatus] = useState("all");
  const [pendingType, setPendingType] = useState("all");

  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const filtersActive =
    filterSeverity !== "all" || filterStatus !== "all" || filterType !== "all";

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const pageNumbers: (number | "...")[] = (() => {
    if (totalPages <= 7)
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    if (page <= 4) return [1, 2, 3, 4, 5, "...", totalPages];
    if (page >= totalPages - 3)
      return [1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
    return [1, "...", page - 1, page, page + 1, "...", totalPages];
  })();

  const openFilter = () => {
    setPendingSeverity(filterSeverity);
    setPendingStatus(filterStatus);
    setPendingType(filterType);
    setFilterOpen(true);
  };

  const applyFilters = () => {
    setFilterSeverity(pendingSeverity);
    setFilterStatus(pendingStatus);
    setFilterType(pendingType);
    setPage(1);
    setFilterOpen(false);
  };

  const resetFilters = () => {
    setPendingSeverity("all");
    setPendingStatus("all");
    setPendingType("all");
    setFilterSeverity("all");
    setFilterStatus("all");
    setFilterType("all");
    setPage(1);
    setFilterOpen(false);
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelected(null);
        setFilterOpen(false);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  useEffect(() => {
    const loadAlerts = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          limit: String(PAGE_SIZE),
          offset: String((page - 1) * PAGE_SIZE),
        });
        if (filterSeverity !== "all") params.set("severity", filterSeverity);
        if (filterType !== "all") params.set("alert_type", filterType);
        if (filterStatus !== "all")
          params.set(
            "status",
            filterStatus === "open" ? "new" : "acknowledged"
          );

        const res = await fetch(`/api/alerts?${params}`);
        const json: AlertsResponse | null = res.ok ? await res.json() : null;
        const raw: RawAlert[] = json?.alerts ?? [];
        const totalCount = json?.total ?? raw.length;
        const criticalCount =
          json?.critical_count ??
          raw.filter((a) => (a.severity ?? "").toLowerCase() === "critical")
            .length;
        const warningCount =
          json?.warning_count ??
          raw.filter((a) => (a.severity ?? "").toLowerCase() === "warning")
            .length;

        setTotal(totalCount);
        setAlerts(raw.map(mapToAlertRecord));
        setKpiStats(
          totalCount === 0
            ? [
                { ...BASE_STATS[0], value: "0", sub: "No alerts" },
                { ...BASE_STATS[1], value: "0", sub: "No critical alerts" },
                { ...BASE_STATS[2], value: "0", sub: "No warnings" },
              ]
            : [
                {
                  ...BASE_STATS[0],
                  value: totalCount.toString(),
                  sub: "All active alerts",
                },
                {
                  ...BASE_STATS[1],
                  value: criticalCount.toString(),
                  sub: "Immediate action required",
                },
                {
                  ...BASE_STATS[2],
                  value: warningCount.toString(),
                  sub: "Require review",
                },
              ]
        );
      } finally {
        setLoading(false);
      }
    };

    void loadAlerts();
  }, [page, filterSeverity, filterStatus, filterType]);

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-[14px]">
        {loading
          ? BASE_STATS.map((s) => (
              <div
                key={s.label}
                className="card relative overflow-hidden py-[18px] px-5"
              >
                <div
                  className="absolute top-0 inset-x-0 h-[2px] opacity-30 animate-pulse"
                  style={{ background: s.accent }}
                />
                <div className="h-8 w-16 rounded-md bg-gray-200 animate-pulse mb-[5px]" />
                <div className="h-3 w-20 rounded bg-gray-100 animate-pulse mb-[5px]" />
                <div className="h-3 w-24 rounded bg-gray-100 animate-pulse" />
              </div>
            ))
          : kpiStats.map((s) => (
              <div
                key={s.label}
                className="card relative overflow-hidden py-[18px] px-5"
              >
                <div
                  className="absolute top-0 inset-x-0 h-[2px] opacity-80"
                  style={{ background: s.accent }}
                />
                <div
                  className="text-[28px] font-bold tracking-[-0.04em] leading-none mb-[5px]"
                  style={{ color: s.accent }}
                >
                  {s.value}
                </div>
                <div className="text-[13px] font-medium text-gray-500 mb-[2px]">
                  {s.label}
                </div>
                <div className="text-[11.5px] text-gray-400">{s.sub}</div>
              </div>
            ))}
      </div>

      {/* Alerts table */}
      <div className="card">
        <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">
              Active alerts
            </h2>
            <p className="text-xs text-gray-400 mt-[2px]">
              Watchdog alerts · refreshed on load
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline-block w-[7px] h-[7px] rounded-full bg-danger-500" />
            <button
              onClick={openFilter}
              className="btn-secondary py-1.5 px-3 text-[12.5px] flex items-center gap-1.5"
            >
              Filter
              {filtersActive && (
                <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
              )}
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <div className="min-w-[900px]">
            <div
              className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3"
              style={{ gridTemplateColumns: COL }}
            >
              {[
                "ID",
                "Description",
                "Severity",
                "Status",
                "Age",
                "SLA Exposure",
              ].map((h) => (
                <span
                  key={h}
                  className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]"
                >
                  {h}
                </span>
              ))}
            </div>

            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="grid items-center py-[13px] px-5 gap-3 border-b border-border-default"
                  style={{ gridTemplateColumns: COL }}
                >
                  <div className="h-3 w-20 rounded bg-gray-200 animate-pulse" />
                  <div className="h-3 w-full rounded bg-gray-200 animate-pulse" />
                  <div className="h-5 w-14 rounded-full bg-gray-200 animate-pulse" />
                  <div className="h-3 w-16 rounded bg-gray-200 animate-pulse" />
                  <div className="h-3 w-8 rounded bg-gray-200 animate-pulse" />
                  <div className="h-3 w-14 rounded bg-gray-200 animate-pulse" />
                </div>
              ))
            ) : alerts.length === 0 ? (
              <div className="px-5 py-8 text-center text-[13px] text-gray-400">
                {filtersActive ? "No alerts match the selected filters." : "No alerts available."}
              </div>
            ) : (
              alerts.map((alert) => {
                const s = SEV[alert.severity] ?? SEV.medium;
                return (
                  <div
                    key={alert.id}
                    onClick={() => setSelected(alert)}
                    className="grid items-center py-[13px] px-5 gap-3 border-b border-border-default cursor-pointer hover:bg-gray-50 transition-colors"
                    style={{ gridTemplateColumns: COL }}
                  >
                    <span className="font-mono text-xs text-brand-700 font-semibold">
                      {alert.id}
                    </span>
                    <span className="text-[13px] text-gray-700 overflow-hidden text-ellipsis whitespace-nowrap">
                      {alert.desc}
                    </span>
                    <span
                      className="text-[11px] font-semibold px-2 py-[2px] rounded-full w-fit"
                      style={{ color: s.color, background: s.bg }}
                    >
                      {alert.severity.charAt(0).toUpperCase() +
                        alert.severity.slice(1)}
                    </span>
                    <div className="flex items-center gap-[5px]">
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{
                          background:
                            alert.status === "investigating"
                              ? "var(--color-warning-500)"
                              : "var(--color-danger-500)",
                        }}
                      />
                      <span className="text-xs text-gray-500 capitalize">
                        {alert.status}
                      </span>
                    </div>
                    <span className="text-xs text-gray-400 font-mono">
                      {alert.age}
                    </span>
                    <span className="text-xs font-bold text-danger-700">
                      {alert.sla}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {!loading && totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-border-default">
            <span className="text-xs text-gray-400">
              Showing{" "}
              {(page - 1) * PAGE_SIZE + 1}–
              {Math.min(page * PAGE_SIZE, total)} of{" "}
              {total}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => p - 1)}
                disabled={page === 1}
                className="size-7 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-base leading-none"
              >
                ‹
              </button>
              {pageNumbers.map((n, i) =>
                n === "..." ? (
                  <span
                    key={`ellipsis-${i}`}
                    className="size-7 flex items-center justify-center text-xs text-gray-400"
                  >
                    …
                  </span>
                ) : (
                  <button
                    key={n}
                    onClick={() => setPage(n as number)}
                    className={`size-7 flex items-center justify-center rounded-md text-xs font-medium transition-colors ${
                      page === n
                        ? "bg-brand-50 text-brand-700"
                        : "text-gray-500 hover:bg-gray-100"
                    }`}
                  >
                    {n}
                  </button>
                )
              )}
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page === totalPages}
                className="size-7 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-base leading-none"
              >
                ›
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Alert detail modal */}
      {selected &&
        (() => {
          const s = SEV[selected.severity] ?? SEV.medium;
          return (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6"
              onClick={() => setSelected(null)}
            >
              <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
              <div
                className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[90vh] overflow-hidden"
                style={{ maxWidth: "560px" }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
                  <div className="min-w-0">
                    <h2 className="text-sm font-semibold text-gray-900 truncate">
                      {selected.id}
                    </h2>
                    <p className="text-[11.5px] text-gray-400 mt-0.5">
                      Alert details
                    </p>
                  </div>
                  <button
                    onClick={() => setSelected(null)}
                    className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400 transition-colors"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path
                        d="M2 2l10 10M12 2L2 12"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-5">
                  {/* Status row */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="text-[11px] font-semibold px-2 py-[2px] rounded-full"
                      style={{ color: s.color, background: s.bg }}
                    >
                      {selected.severity.charAt(0).toUpperCase() +
                        selected.severity.slice(1)}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span
                        className="w-1.5 h-1.5 rounded-full"
                        style={{
                          background:
                            selected.status === "investigating"
                              ? "var(--color-warning-500)"
                              : "var(--color-danger-500)",
                        }}
                      />
                      <span className="text-[12.5px] text-gray-600 capitalize font-medium">
                        {selected.status}
                      </span>
                    </div>
                    <span className="ml-auto text-xs text-gray-400 font-mono">
                      {selected.age} ago
                    </span>
                  </div>

                  {/* Description */}
                  <div className="bg-gray-50 rounded-lg border border-border-default px-4 py-3 text-[13.5px] text-gray-800 font-medium leading-relaxed">
                    {selected.desc}
                  </div>

                  {/* Metadata grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {[
                      { label: "Alert type", value: selected.alert_type.replace(/_/g, " ") },
                      { label: "SLA exposure", value: selected.sla },
                    ].map((m) => (
                      <div
                        key={m.label}
                        className="bg-gray-50 rounded-lg px-3 py-2.5"
                      >
                        <div className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-0.5">
                          {m.label}
                        </div>
                        <div className="text-[13px] font-semibold text-gray-700">
                          {m.value}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Suggested actions */}
                  {selected.timeline.length > 0 && (
                    <div>
                      <div className="text-[12px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-2.5">
                        Suggested actions
                      </div>
                      <div className="flex flex-col gap-2">
                        {selected.timeline.map((t, i) => (
                          <div
                            key={i}
                            className="flex gap-2.5 text-[13px] text-gray-600"
                          >
                            <span className="size-5 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center text-[10px] font-bold shrink-0 mt-[1px]">
                              {i + 1}
                            </span>
                            {t}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div>
                    <div className="text-[12px] font-bold text-gray-400 uppercase tracking-[0.06em] mb-2.5">
                      Actions
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <Link
                        href={`/chat?q=${encodeURIComponent(`Investigate alert ${selected.id}: ${selected.desc}. Severity: ${selected.severity}, status: ${selected.status}.`)}`}
                        className="btn-primary no-underline text-[12.5px] py-2 px-3"
                        onClick={() => setSelected(null)}
                      >
                        Ask Agent
                      </Link>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end px-5 py-4 border-t border-border-default shrink-0">
                  <button
                    className="btn-secondary"
                    onClick={() => setSelected(null)}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          );
        })()}

      {/* Filter modal */}
      {filterOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6"
          onClick={() => setFilterOpen(false)}
        >
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full overflow-hidden"
            style={{ maxWidth: "400px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
              <h2 className="text-sm font-semibold text-gray-900">
                Filter alerts
              </h2>
              <button
                onClick={() => setFilterOpen(false)}
                className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M2 2l10 10M12 2L2 12"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
            <div className="px-5 py-5 flex flex-col gap-4">
              <div>
                <label className="label-base">Severity</label>
                <select
                  className="input-base appearance-none"
                  value={pendingSeverity}
                  onChange={(e) => setPendingSeverity(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="critical">Critical</option>
                  <option value="warning">Warning</option>
                </select>
              </div>
              <div>
                <label className="label-base">Status</label>
                <select
                  className="input-base appearance-none"
                  value={pendingStatus}
                  onChange={(e) => setPendingStatus(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="open">Open</option>
                  <option value="investigating">Investigating</option>
                </select>
              </div>
              <div>
                <label className="label-base">Alert type</label>
                <select
                  className="input-base appearance-none"
                  value={pendingType}
                  onChange={(e) => setPendingType(e.target.value)}
                >
                  <option value="all">All</option>
                  <option value="compliance_gap">Compliance gap</option>
                  <option value="policy_conflict">Policy conflict</option>
                  <option value="regulatory_deadline">Regulatory deadline</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default">
              <button className="btn-secondary" onClick={resetFilters}>
                Reset
              </button>
              <button className="btn-primary" onClick={applyFilters}>
                Apply filters
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
