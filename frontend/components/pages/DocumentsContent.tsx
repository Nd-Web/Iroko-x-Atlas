"use client";
/**
 * components/pages/DocumentsContent.tsx — Enterprise document library.
 * File grid/list, upload zone, status tracking, and connector filtering.
 */
import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { cn, formatBytes, formatRelativeTime } from "@/lib/utils";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

interface Doc {
  id: string;
  name: string;
  size: number;
  type: string;
  status: "indexed" | "indexing" | "error";
  connector: string;
  updated_at: string;
}

const CONNECTORS = ["All", "SharePoint", "OneDrive", "S3", "Local", "Google Drive"];

export default function DocumentsContent() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("All");
  const [view, setView] = useState<"grid" | "list">("grid");

  useEffect(() => {
    setLoading(true);
    apiFetch<{ documents: Doc[] }>("/api/documents")
      .then(d => { if (d.documents) setDocs(d.documents); })
      .catch(() => {
        // Mock data if API is not yet seeded
        setDocs([
          { id: "d1", name: "IHS_Nigeria_Tower_Lease_2024.pdf", size: 14500000, type: "application/pdf", status: "indexed", connector: "SharePoint", updated_at: new Date().toISOString() },
          { id: "d2", name: "Ericsson_RAN_Maintenance_SLA.pdf", size: 8200000, type: "application/pdf", status: "indexed", connector: "OneDrive", updated_at: new Date(Date.now()-3600000).toISOString() },
          { id: "d3", name: "NCC_Quarterly_QoS_Report_Q4.xlsx", size: 4100000, type: "spreadsheet", status: "indexing", connector: "S3", updated_at: new Date(Date.now()-7200000).toISOString() },
          { id: "d4", name: "Procurement_Policy_v3.2.docx", size: 1200000, type: "word", status: "indexed", connector: "Local", updated_at: new Date(Date.now()-86400000).toISOString() },
        ]);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = docs.filter(d => filter === "All" || d.connector === filter);

  return (
    <div className="space-y-6">
      {/* Header / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-wrap">
          {CONNECTORS.map(c => (
            <button key={c} onClick={() => setFilter(c)}
              className={cn("px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all border",
                filter === c ? "bg-[#3B7BF6] text-white border-[#3B7BF6]" : "text-[#9CA3AF] border-white/[0.08] hover:border-white/20")}>
              {c}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-white/[0.04] p-1 rounded-lg border border-white/[0.08]">
            <button onClick={() => setView("grid")} className={cn("p-1.5 rounded-md transition-colors", view === "grid" ? "bg-[#3B7BF6] text-white" : "text-[#4B5563] hover:text-[#9CA3AF]")}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>
            </button>
            <button onClick={() => setView("list")} className={cn("p-1.5 rounded-md transition-colors", view === "list" ? "bg-[#3B7BF6] text-white" : "text-[#4B5563] hover:text-[#9CA3AF]")}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 4h12M2 8h12M2 12h12"/></svg>
            </button>
          </div>
          <Button variant="primary" className="gap-2">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 2v12M2 8h12"/></svg>
            Upload
          </Button>
        </div>
      </div>

      {/* Grid View */}
      {view === "grid" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(doc => (
            <Card key={doc.id} className="p-4 group hover:border-[#3B7BF6]/40 transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-12 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-xl">
                  {doc.name.endsWith(".pdf") ? "📕" : doc.name.endsWith(".xlsx") ? "📗" : "📄"}
                </div>
                <div className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full",
                  doc.status === "indexed" ? "bg-emerald-400/10 text-emerald-400" : "bg-amber-400/10 text-amber-400 animate-pulse")}>
                  {doc.status.toUpperCase()}
                </div>
              </div>
              <h4 className="text-[13px] font-semibold text-[#E5E7EB] truncate mb-1" title={doc.name}>{doc.name}</h4>
              <div className="text-[11px] text-[#4B5563] flex justify-between">
                <span>{formatBytes(doc.size)}</span>
                <span>{doc.connector}</span>
              </div>
              <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-[10px] text-[#4B5563]">{formatRelativeTime(doc.updated_at)}</span>
                <button className="text-[11px] font-bold text-[#3B7BF6] hover:underline">View</button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* List View */}
      {view === "list" && (
        <div className="rounded-2xl border border-white/[0.06] overflow-hidden bg-[#0F1320]">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-white/[0.06]">
                <th className="px-5 py-3 text-[11px] font-bold text-[#4B5563] uppercase tracking-wider">Name</th>
                <th className="px-5 py-3 text-[11px] font-bold text-[#4B5563] uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-[11px] font-bold text-[#4B5563] uppercase tracking-wider">Source</th>
                <th className="px-5 py-3 text-[11px] font-bold text-[#4B5563] uppercase tracking-wider text-right">Size</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {filtered.map(doc => (
                <tr key={doc.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{doc.name.endsWith(".pdf") ? "📕" : doc.name.endsWith(".xlsx") ? "📗" : "📄"}</span>
                      <span className="text-[13px] text-[#D1D5DB] font-medium">{doc.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full",
                      doc.status === "indexed" ? "bg-emerald-400/10 text-emerald-400" : "bg-amber-400/10 text-amber-400")}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-[12px] text-[#6B7280]">{doc.connector}</td>
                  <td className="px-5 py-3.5 text-[12px] text-[#6B7280] text-right font-mono">{formatBytes(doc.size)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
