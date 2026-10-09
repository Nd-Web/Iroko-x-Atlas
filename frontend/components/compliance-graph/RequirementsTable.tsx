"use client";
/** Requirements: a searchable, filterable table. A row opens the Evidence panel. */

import { useEffect, useState } from "react";
import { useRequirements, type RequirementFilters } from "@/lib/compliance-graph";
import { APPLICABILITY_SHORT, COVERAGE_ORDER, COVERAGE_SHORT } from "@/lib/compliance-graph-view";
import type { Selection } from "./EvidencePanel";
import { ApplicabilityChip, CoverageChip, Empty, ErrorBox, Loading, formatDate } from "./ui";

interface Props {
  initial: RequirementFilters;
  onOpen: (s: Selection) => void;
}

export default function RequirementsTable({ initial, onOpen }: Props) {
  const [filters, setFilters] = useState<RequirementFilters>(initial);
  const [search, setSearch] = useState(initial.q ?? "");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => { setFilters((f) => ({ ...f, q: search || undefined })); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);
  const { data, isLoading, error, refetch, isFetching } = useRequirements(filters, page);
  const set = (key: keyof RequirementFilters, value: string) => { setFilters((f) => ({ ...f, [key]: value || undefined })); setPage(1); };
  const regulators = Object.keys(data?.facets.regulator ?? {}).sort();
  return (
    <div className="space-y-4">
      <div className="grid gap-2 md:grid-cols-[2fr_1fr_1fr_1fr_1fr]">
        <input className="input-base" placeholder="Search requirements, instruments or references" value={search}
          onChange={(e) => setSearch(e.target.value)} aria-label="Search requirements" />
        <select className="input-base" value={filters.applicability ?? ""} onChange={(e) => set("applicability", e.target.value)} aria-label="Applicability">
          <option value="">Any applicability</option>
          <option value="applying">Applies or likely applies</option>
          {Object.keys(APPLICABILITY_SHORT).map((k) => <option key={k} value={k}>{APPLICABILITY_SHORT[k]}</option>)}
        </select>
        <select className="input-base" value={filters.coverage ?? ""} onChange={(e) => set("coverage", e.target.value)} aria-label="In your records">
          <option value="">Any coverage</option>
          {COVERAGE_ORDER.map((k) => <option key={k} value={k}>{COVERAGE_SHORT[k]}</option>)}
        </select>
        <select className="input-base" value={filters.regulator ?? ""} onChange={(e) => set("regulator", e.target.value)} aria-label="Regulator">
          <option value="">Any regulator</option>
          {regulators.map((r) => <option key={r} value={r === "Other" ? "" : r}>{r}</option>)}
        </select>
        <select className="input-base" value={filters.owner === "none" ? "none" : String(filters.due_within ?? "")}
          onChange={(e) => {
            const v = e.target.value;
            setFilters((f) => ({ ...f, owner: v === "none" ? "none" : undefined, due_within: v && v !== "none" ? Number(v) : undefined }));
            setPage(1);
          }} aria-label="More filters">
          <option value="">Any owner or date</option>
          <option value="none">No owner recorded</option>
          <option value="30">Due within 30 days</option>
          <option value="90">Due within 90 days</option>
        </select>
      </div>
      {isLoading ? <Loading label="Loading requirements" /> : error ? <ErrorBox error={error} onRetry={() => refetch()} /> : !data?.items.length ? (
        <Empty title="No requirements match">Try clearing a filter. Requirements appear once regulations in your library have been read.</Empty>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-border-default">
            <table className="table-base min-w-[860px]">
              <thead>
                <tr>
                  <th>Requirement</th>
                  <th>Instrument</th>
                  <th>Applies to you</th>
                  <th>In your records</th>
                  <th>Owner</th>
                  <th>Next due</th>
                </tr>
              </thead>
              <tbody className={isFetching ? "opacity-70" : ""}>
                {data.items.map((r) => (
                  <tr key={r.lineage_id} className="cursor-pointer" onClick={() => onOpen({ kind: "requirement", id: r.lineage_id })}>
                    <td className="max-w-[420px]">
                      <button className="text-left" onClick={(e) => { e.stopPropagation(); onOpen({ kind: "requirement", id: r.lineage_id }); }}>
                        <span className="line-clamp-2 text-[13px] text-gray-800">{r.summary || r.quote}</span>
                      </button>
                      {r.coverage.partial && <span className="text-[11px] text-gray-500">Partly addressed</span>}
                    </td>
                    <td className="text-[12px] text-gray-600">
                      <span className="line-clamp-2">{r.document.title}</span>
                      <span className="text-gray-500">{[r.document.regulator, r.page_number ? `p. ${r.page_number}` : null].filter(Boolean).join(" · ")}</span>
                      {r.document.awaiting_publication && <span className="block text-warning-700">Newer version awaiting publication</span>}
                    </td>
                    <td><ApplicabilityChip state={r.applicability.state} label={r.applicability.label} /></td>
                    <td><CoverageChip state={r.coverage.state} label={r.coverage.label} /></td>
                    <td className="text-[12px] text-gray-600">{r.owner.name || r.owner.team || <span className="text-gray-400">—</span>}</td>
                    <td className="text-[12px] text-gray-600">{r.due.date ? formatDate(r.due.date) : <span className="text-gray-400">{r.due.description ? "Event-driven" : "—"}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-[12px] text-gray-500">
            <span>{data.total} requirement(s)</span>
            <div className="flex gap-2">
              <button className="btn-secondary text-[12px]" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
              <button className="btn-secondary text-[12px]" disabled={page * data.page_size >= data.total} onClick={() => setPage((p) => p + 1)}>Next</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
