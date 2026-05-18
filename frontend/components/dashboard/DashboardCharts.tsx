"use client";

import { useState, useEffect } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// ─── Fallback static data ─────────────────────────────────────────────────────

const FALLBACK_DOC_COVERAGE = [
  { type: "RCA Reports",        count: 4812, fill: "#4A55D4" },
  { type: "Vendor SLAs",        count: 3214, fill: "#2E90FA" },
  { type: "Compliance Filings", count: 2401, fill: "#17B26A" },
  { type: "Tech Manuals",       count: 8812, fill: "#0BA5EC" },
  { type: "Contracts",          count: 1922, fill: "#F79009" },
  { type: "Field Reports",      count: 3650, fill: "#9E77ED" },
];

const DOC_COLORS = ["#4A55D4", "#2E90FA", "#17B26A", "#0BA5EC", "#F79009", "#9E77ED"];

const AREA_COLOR = "#4A55D4";

// ─── Tooltips ─────────────────────────────────────────────────────────────────

function QueryTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-border-default rounded-lg shadow-md px-3 py-2.5 text-xs">
      <div className="text-gray-400 mb-0.5">{label}</div>
      <div className="text-gray-900 font-bold text-[13px]">{payload[0].value.toLocaleString()} queries</div>
    </div>
  );
}

function DocTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-border-default rounded-lg shadow-md px-3 py-2.5 text-xs">
      <div className="text-gray-400 mb-0.5">{label}</div>
      <div className="text-gray-900 font-bold text-[13px]">{payload[0].value.toLocaleString()} docs</div>
    </div>
  );
}

// ─── QueryVolumeChart ─────────────────────────────────────────────────────────

export function QueryVolumeChart({
  data,
  trendPct,
}: {
  data?: { day: string; queries: number }[];
  trendPct?: string;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const hasData = data && data.length > 0;

  return (
    <div className="card px-5 pt-5 pb-4 flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Query volume</h3>
          <p className="text-[11.5px] text-gray-400 mt-[2px]">Daily AI queries over the last 30 days</p>
        </div>
        {trendPct && (
          <span className="text-[12px] font-semibold text-success-700 bg-success-50 px-2.5 py-1 rounded-full flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M5 7.5V2.5M2.5 5l2.5-2.5L7.5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {trendPct}
          </span>
        )}
      </div>
      <div style={{ height: 200 }}>
        {mounted && hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
              <defs>
                <linearGradient id="queryGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={AREA_COLOR} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={AREA_COLOR} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F2F4F7" vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#9CA3AF" }} tickLine={false} axisLine={false} interval={2} />
              <YAxis tick={{ fontSize: 11, fill: "#9CA3AF" }} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(v >= 1000 ? 1 : 0)}${v >= 1000 ? "k" : ""}`} />
              <Tooltip content={<QueryTooltip />} cursor={{ stroke: AREA_COLOR, strokeWidth: 1, strokeDasharray: "4 2" }} />
              <Area type="monotone" dataKey="queries" stroke={AREA_COLOR} strokeWidth={2} fill="url(#queryGrad)" dot={false} activeDot={{ r: 4, fill: AREA_COLOR, stroke: "white", strokeWidth: 2 }} />
            </AreaChart>
          </ResponsiveContainer>
        ) : mounted ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-[12px] text-gray-300">No data available</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ─── DocCoverageChart ─────────────────────────────────────────────────────────

export function DocCoverageChart({
  data,
}: {
  data?: { type: string; count: number; fill?: string }[];
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const chartData = data && data.length > 0
    ? data.map((d, i) => ({ ...d, fill: d.fill ?? DOC_COLORS[i % DOC_COLORS.length] }))
    : FALLBACK_DOC_COVERAGE;

  return (
    <div className="card px-5 pt-5 pb-4 flex flex-col gap-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Document coverage</h3>
        <p className="text-[11.5px] text-gray-400 mt-[2px]">Ingested documents by category</p>
      </div>
      <div style={{ height: 200 }}>
        {mounted && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }} barSize={14}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F2F4F7" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: "#9CA3AF" }} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`} />
              <YAxis type="category" dataKey="type" tick={{ fontSize: 11, fill: "#6B7280" }} tickLine={false} axisLine={false} width={130} />
              <Tooltip content={<DocTooltip />} cursor={{ fill: "#F9FAFB" }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill ?? DOC_COLORS[i % DOC_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
