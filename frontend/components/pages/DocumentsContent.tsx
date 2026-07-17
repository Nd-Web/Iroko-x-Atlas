"use client";
/**
 * components/pages/DocumentsContent.tsx — Enterprise document library.
 * File grid/list, upload zone, status tracking, and connector filtering.
 */
import { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useDocuments } from "@/app/documents/_hooks/useDocuments";
import { useUploadDocument } from "@/app/documents/_hooks/useUploadDocument";
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

// Filter chips are derived from the loaded documents (docs carry
// department/source values) — see below.

function normaliseStatus(status: string): Doc["status"] {
  if (status === "indexed" || status === "completed") return "indexed";
  if (status === "error" || status === "failed") return "error";
  return "indexing";
}

/** File-type glyph — colour-coded document icon (replaces emoji). */
function FileGlyph({ name, size = 18 }: { name: string; size?: number }) {
  const color = name.endsWith(".pdf") ? "#F87171" : name.endsWith(".xlsx") ? "#34D399" : "#9C9CA6";
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 16 16" fill="none" className="shrink-0">
      <path d="M9.5 1.5H4A1.5 1.5 0 0 0 2.5 3v10A1.5 1.5 0 0 0 4 14.5h8a1.5 1.5 0 0 0 1.5-1.5V5.5l-4-4Z" stroke={color} strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M9.5 1.5V5.5h4" stroke={color} strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

export default function DocumentsContent({
  onCountChange,
}: {
  onCountChange?: (count: number, live: boolean) => void;
}) {
  const router = useRouter();
  const [filter, setFilter] = useState("All");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [selected, setSelected] = useState<Doc | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, isPending, isError, error, refetch } = useDocuments({ page_size: 100 });
  const uploadMutation = useUploadDocument();
  const uploading = uploadMutation.isPending;

  const docs: Doc[] = useMemo(() => {
    if (!data?.documents) return [];
    return data.documents.map((doc) => ({
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
    }));
  }, [data]);

  // Report the count upward — only ever with real data from the API.
  useEffect(() => {
    if (data) onCountChange?.(data.total ?? data.documents.length, true);
  }, [data, onCountChange]);

  // Close the detail modal on Escape
  useEffect(() => {
    if (!selected) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setSelected(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [selected]);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const toastId = toast.loading(`Uploading ${file.name}…`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      // onSuccess invalidates the ["documents"] query — the list refreshes itself.
      await uploadMutation.mutateAsync(formData);
      toast.success(`${file.name} uploaded — indexing started`, { id: toastId });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed. Please try again.", { id: toastId });
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
              aria-pressed={filter === c}
              className={cn("px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all border",
                filter === c ? "bg-brand-500 text-[#0A0A0B] border-brand-500" : "text-gray-500 border-border-default hover:border-border-strong")}>
              {c}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-gray-50 p-1 rounded-lg border border-border-default">
            <button onClick={() => setView("grid")} aria-label="Grid view" aria-pressed={view === "grid"} className={cn("p-1.5 rounded-md transition-colors", view === "grid" ? "bg-brand-500 text-[#0A0A0B]" : "text-gray-400 hover:text-gray-600")}>
              <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>
            </button>
            <button onClick={() => setView("list")} aria-label="List view" aria-pressed={view === "list"} className={cn("p-1.5 rounded-md transition-colors", view === "list" ? "bg-brand-500 text-[#0A0A0B]" : "text-gray-400 hover:text-gray-600")}>
              <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 4h12M2 8h12M2 12h12"/></svg>
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
            <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 2v12M2 8h12"/></svg>
            {uploading ? "Uploading…" : "Upload"}
          </Button>
        </div>
      </div>

      {/* Loading state — skeleton cards */}
      {isPending && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4" aria-hidden="true">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="p-4 rounded-2xl border border-border-default bg-surface-card animate-pulse">
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-12 rounded-lg bg-gray-100" />
                <div className="w-14 h-4 rounded-full bg-gray-100" />
              </div>
              <div className="h-3.5 w-3/4 rounded bg-gray-100 mb-2" />
              <div className="flex justify-between">
                <div className="h-3 w-16 rounded bg-gray-100" />
                <div className="h-3 w-14 rounded bg-gray-100" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error state */}
      {!isPending && isError && (
        <div
          role="alert"
          className="rounded-2xl p-6 flex flex-col items-start gap-3"
          style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}
        >
          <div className="text-[13px] font-semibold text-[#F87171]">Documents could not be loaded</div>
          <p className="text-[12px] text-[#F87171]/80 m-0">
            {error instanceof Error ? error.message : "An unexpected error occurred."}
          </p>
          <button
            onClick={() => refetch()}
            className="px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-[#F87171] transition-all hover:brightness-110"
            style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)" }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!isPending && !isError && docs.length === 0 && (
        <div className="rounded-2xl border border-border-default bg-surface-card p-10 flex flex-col items-center text-center gap-2">
          <div className="w-12 h-14 rounded-lg bg-gray-50 border border-border-default flex items-center justify-center mb-1"><FileGlyph name="" size={22} /></div>
          <div className="text-[14px] font-semibold text-gray-800">No documents yet</div>
          <p className="text-[12px] text-gray-400 m-0 max-w-[360px]">
            Upload a PDF, DOCX, XLSX, TXT or CSV file to start building your knowledge base.
          </p>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="mt-2 px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-gray-500 border border-border-default hover:text-gray-900 hover:border-border-strong transition-all"
          >
            {uploading ? "Uploading…" : "Upload a document"}
          </button>
        </div>
      )}

      {/* Grid View */}
      {!isPending && !isError && docs.length > 0 && view === "grid" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(doc => (
            <Card key={doc.id} className="p-4 group hover:border-border-strong transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-12 rounded-lg bg-gray-50 border border-border-default flex items-center justify-center">
                  <FileGlyph name={doc.name} size={20} />
                </div>
                <div className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full",
                  doc.status === "indexed" ? "bg-success-50 text-success-500" : "bg-info-50 text-info-500 animate-pulse")}>
                  {doc.status.toUpperCase()}
                </div>
              </div>
              <h4 className="text-[13px] font-semibold text-gray-800 truncate mb-1" title={doc.name}>{doc.name}</h4>
              <div className="text-[11px] text-gray-400 flex justify-between">
                <span>{doc.size ? formatBytes(doc.size) : "—"}</span>
                <span>{doc.connector}</span>
              </div>
              <div className="mt-4 pt-3 border-t border-border-default flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-[10px] text-gray-400">{formatRelativeTime(doc.updated_at)}</span>
                <button onClick={() => setSelected(doc)} className="text-[11px] font-bold text-info-500 hover:underline">View</button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* List View */}
      {!isPending && !isError && docs.length > 0 && view === "list" && (
        <div className="rounded-2xl border border-border-default overflow-hidden bg-surface-card">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-border-default">
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">Name</th>
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">Source</th>
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider text-right">Size</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-default">
              {filtered.map(doc => (
                <tr key={doc.id} onClick={() => setSelected(doc)} className="hover:bg-gray-50 transition-colors group cursor-pointer">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <FileGlyph name={doc.name} size={16} />
                      <span className="text-[13px] text-gray-700 font-medium">{doc.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full",
                      doc.status === "indexed" ? "bg-success-50 text-success-500" : "bg-info-50 text-info-500")}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-[12px] text-gray-400">{doc.connector}</td>
                  <td className="px-5 py-3.5 text-[12px] text-gray-400 text-right font-mono">{doc.size ? formatBytes(doc.size) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Document detail modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6" onClick={() => setSelected(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" aria-hidden="true" />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={selected.title ?? selected.name}
            className="relative w-full max-h-[88vh] overflow-y-auto rounded-2xl border border-border-default bg-[#1A1A1F] flex flex-col"
            style={{ maxWidth: 480 }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border-default">
              <div className="flex items-center gap-3 min-w-0">
                <FileGlyph name={selected.name} size={22} />
                <div className="min-w-0">
                  <h3 className="text-[14px] font-semibold text-gray-800 truncate">{selected.title ?? selected.name}</h3>
                  <p className="text-[11px] text-gray-400 font-mono truncate">{selected.name}</p>
                </div>
              </div>
              <button onClick={() => setSelected(null)} aria-label="Close" className="w-7 h-7 rounded-md flex items-center justify-center text-gray-400 hover:text-gray-900 hover:bg-gray-100 transition-colors shrink-0">
                <svg aria-hidden="true" width="13" height="13" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
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
                    <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-[3px]">{f.label}</div>
                    <div className="text-[13px] font-medium text-gray-700 capitalize">{f.value}</div>
                  </div>
                ))}
              </div>

              {selected.tags && selected.tags.length > 0 && (
                <div>
                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Tags</div>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.tags.map(t => (
                      <span key={t} className="px-2 py-0.5 rounded-full text-[10.5px] font-semibold text-info-700 bg-info-50 border border-info-100">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-[12px] text-gray-400 leading-relaxed m-0">
                This document is chunked, embedded and indexed — every answer citing it links back
                to the exact passage.
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default">
              <button onClick={() => setSelected(null)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-gray-500 border border-border-default hover:text-gray-900 hover:border-border-strong transition-all">
                Close
              </button>
              <button
                onClick={() => router.push(`/chat?q=${encodeURIComponent(`Summarise the key points of the document "${selected.title ?? selected.name}" and what actions it implies`)}`)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-bold text-[#0A0A0B] bg-brand-500 hover:bg-brand-400 transition-all">
                Ask Iroko about this document →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
