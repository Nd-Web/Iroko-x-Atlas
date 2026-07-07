"use client";
/**
 * components/pages/DocumentsContent.tsx — Enterprise document library.
 * File grid/list, upload zone, status tracking, and connector filtering.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { documentsService } from "@/services/documents.service";
import { cn, formatBytes, formatRelativeTime } from "@/lib/utils";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";

interface Doc {
  id: string;
  name: string;
  title?: string;
  size: number;
  type: string;
  status: "indexed" | "indexing" | "error";
  connector: string;
  tags?: string[];
  chunks?: number;
  updated_at: string;
}

// Filter chips are derived from the loaded documents (live docs carry
// department/source values, mock docs carry connector names) — see below.

// The 8 canonical indexed documents — shown when the API is not yet seeded
const MOCK_DOCS: Doc[] = [
  { id: "d1", name: "Ikeja_Cluster_RCA_Power_Outage_Q1_2026.pdf",      size: 4200000,  type: "application/pdf", status: "indexed", connector: "SharePoint", updated_at: new Date().toISOString() },
  { id: "d2", name: "TowerCo_IHS_Nigeria_Tower_Lease_Agreement.pdf",   size: 11800000, type: "application/pdf", status: "indexed", connector: "SharePoint", updated_at: new Date(Date.now() - 3600000).toISOString() },
  { id: "d3", name: "Customer_Complaints_MoMo_Deductions_Q1_2026.xlsx", size: 3600000, type: "spreadsheet",     status: "indexed", connector: "S3",         updated_at: new Date(Date.now() - 7200000).toISOString() },
  { id: "d4", name: "NCC_QoS_Quarterly_Return_Q4_2025.pdf",            size: 2900000,  type: "application/pdf", status: "indexed", connector: "OneDrive",   updated_at: new Date(Date.now() - 10800000).toISOString() },
  { id: "d5", name: "NDPA_Article_24_Processing_Record.pdf",           size: 1700000,  type: "application/pdf", status: "indexed", connector: "OneDrive",   updated_at: new Date(Date.now() - 21600000).toISOString() },
  { id: "d6", name: "Ericsson_RAN_Maintenance_SLA_2026.pdf",           size: 8400000,  type: "application/pdf", status: "indexed", connector: "SharePoint", updated_at: new Date(Date.now() - 43200000).toISOString() },
  { id: "d7", name: "Kano_Kaduna_Fibre_Route_BoQ.xlsx",                size: 5200000,  type: "spreadsheet",     status: "indexed", connector: "Local",      updated_at: new Date(Date.now() - 86400000).toISOString() },
  { id: "d8", name: "Enterprise_Customer_SLA_Register_EBU.xlsx",       size: 2300000,  type: "spreadsheet",     status: "indexed", connector: "S3",         updated_at: new Date(Date.now() - 172800000).toISOString() },
];

function normaliseStatus(status: string): Doc["status"] {
  if (status === "indexed" || status === "completed") return "indexed";
  if (status === "error" || status === "failed") return "error";
  return "indexing";
}

export default function DocumentsContent({
  onCountChange,
}: {
  onCountChange?: (count: number, live: boolean) => void;
}) {
  const router = useRouter();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("All");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<Doc | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Close the detail modal on Escape
  useEffect(() => {
    if (!selected) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setSelected(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [selected]);

  const loadDocs = useCallback((showSpinner = true) => {
    if (showSpinner) setLoading(true);
    documentsService
      .listDocuments({ page_size: 100 })
      .then((d) => {
        if (d.documents && d.documents.length > 0) {
          setDocs(
            d.documents.map((doc) => ({
              id: doc.id,
              name: doc.filename ?? doc.title ?? "Untitled document",
              title: doc.title ?? undefined,
              size: doc.file_size ?? 0,
              type: doc.file_type ?? "",
              status: normaliseStatus(doc.status ?? "indexing"),
              connector: doc.source ?? doc.department ?? "Local",
              tags: doc.tags ?? undefined,
              chunks: doc.chunk_count ?? undefined,
              // The backend list response has created_at only — updated_at may be absent.
              updated_at: doc.updated_at ?? doc.created_at ?? new Date().toISOString(),
            }))
          );
          onCountChange?.(d.total ?? d.documents.length, true);
        } else {
          setDocs(MOCK_DOCS);
          onCountChange?.(MOCK_DOCS.length, false);
        }
      })
      .catch(() => {
        // Mock data if API is not yet seeded
        setDocs(MOCK_DOCS);
        onCountChange?.(MOCK_DOCS.length, false);
      })
      .finally(() => {
        if (showSpinner) setLoading(false);
      });
  }, [onCountChange]);

  useEffect(() => {
    loadDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    const toastId = toast.loading(`Uploading ${file.name}…`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await documentsService.uploadDocument(formData);
      toast.success(`${file.name} uploaded — indexing started`, { id: toastId });
      loadDocs(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed. Please try again.", { id: toastId });
    } finally {
      setUploading(false);
    }
  };

  const filtered = docs.filter(d => filter === "All" || d.connector === filter);
  const connectorChips = ["All", ...Array.from(new Set(docs.map(d => d.connector)))];

  return (
    <div className="space-y-6">
      {/* Header / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-wrap">
          {connectorChips.map(c => (
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
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.csv"
            className="hidden"
            onChange={handleFileSelected}
          />
          <Button variant="primary" className="gap-2" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 2v12M2 8h12"/></svg>
            {uploading ? "Uploading…" : "Upload"}
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
                <span>{doc.size ? formatBytes(doc.size) : "—"}</span>
                <span>{doc.connector}</span>
              </div>
              <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-[10px] text-[#4B5563]">{formatRelativeTime(doc.updated_at)}</span>
                <button onClick={() => setSelected(doc)} className="text-[11px] font-bold text-[#3B7BF6] hover:underline">View</button>
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
                <tr key={doc.id} onClick={() => setSelected(doc)} className="hover:bg-white/[0.02] transition-colors group cursor-pointer">
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
                  <td className="px-5 py-3.5 text-[12px] text-[#6B7280] text-right font-mono">{doc.size ? formatBytes(doc.size) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Document detail modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" />
          <div
            className="relative w-full max-h-[88vh] overflow-y-auto rounded-2xl border border-white/[0.08] bg-[#0F1320] flex flex-col"
            style={{ maxWidth: 480 }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-2xl shrink-0">{selected.name.endsWith(".pdf") ? "📕" : selected.name.endsWith(".xlsx") ? "📗" : "📄"}</span>
                <div className="min-w-0">
                  <h3 className="text-[14px] font-semibold text-[#E5E7EB] truncate">{selected.title ?? selected.name}</h3>
                  <p className="text-[11px] text-[#4B5563] font-mono truncate">{selected.name}</p>
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="w-7 h-7 rounded-md flex items-center justify-center text-[#6B7280] hover:text-white hover:bg-white/5 transition-colors shrink-0">
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>

            <div className="px-5 py-5 flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                {[
                  { label: "Status", value: selected.status },
                  { label: "Source", value: selected.connector },
                  { label: "Size", value: selected.size ? formatBytes(selected.size) : "—" },
                  { label: "Indexed chunks", value: selected.chunks != null ? String(selected.chunks) : "—" },
                  { label: "Type", value: selected.type || "—" },
                  { label: "Last updated", value: formatRelativeTime(selected.updated_at) },
                ].map(f => (
                  <div key={f.label}>
                    <div className="text-[10px] font-bold text-[#4B5563] uppercase tracking-wider mb-[3px]">{f.label}</div>
                    <div className="text-[13px] font-medium text-[#D1D5DB] capitalize">{f.value}</div>
                  </div>
                ))}
              </div>

              {selected.tags && selected.tags.length > 0 && (
                <div>
                  <div className="text-[10px] font-bold text-[#4B5563] uppercase tracking-wider mb-1.5">Tags</div>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.tags.map(t => (
                      <span key={t} className="px-2 py-0.5 rounded-full text-[10.5px] font-semibold text-[#93C5FD] bg-[#3B7BF6]/10 border border-[#3B7BF6]/20">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-[12px] text-[#6B7280] leading-relaxed m-0">
                This document is chunked, embedded and indexed — every answer citing it links back
                to the exact passage.
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-white/[0.06]">
              <button onClick={() => setSelected(null)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-[#9CA3AF] border border-white/[0.08] hover:text-white hover:border-white/20 transition-all">
                Close
              </button>
              <button
                onClick={() => router.push(`/chat?q=${encodeURIComponent(`Summarise the key points of the document "${selected.title ?? selected.name}" and what actions it implies`)}`)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-bold text-white transition-all"
                style={{ background: "linear-gradient(135deg,#3B7BF6,#2563EB)" }}>
                Ask Iroko about this document →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
