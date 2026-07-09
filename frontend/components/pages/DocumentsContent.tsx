"use client";
/**
 * components/pages/DocumentsContent.tsx — Enterprise document library.
 * File grid/list, upload zone, status tracking, and connector filtering.
 * Data comes exclusively from the documents API via react-query — the page
 * renders four honest states: loading, error (with retry), empty, and data.
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

function normaliseStatus(status: string): Doc["status"] {
  if (status === "indexed" || status === "completed") return "indexed";
  if (status === "error" || status === "failed") return "error";
  return "indexing";
}

function fileEmoji(name: string) {
  return name.endsWith(".pdf") ? "📕" : name.endsWith(".xlsx") ? "📗" : "📄";
}

const statusBadge: Record<Doc["status"], string> = {
  indexed: "bg-success-50 text-success-700",
  indexing: "bg-warning-50 text-warning-700 animate-pulse",
  error: "bg-danger-50 text-danger-700",
};

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

  const { data, isPending, isError, error, refetch, isRefetching } = useDocuments({ page_size: 100 });
  const upload = useUploadDocument();
  const uploading = upload.isPending;

  const docs: Doc[] = useMemo(
    () =>
      (data?.documents ?? []).map((doc) => ({
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
      })),
    [data]
  );

  // Report the live count upstream whenever a fresh list arrives.
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
      await upload.mutateAsync(formData); // hook invalidates the documents list on success
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
          {docs.length > 0 && connectorChips.map(c => (
            <button key={c} onClick={() => setFilter(c)} aria-pressed={filter === c}
              className={cn("px-3 py-1.5 rounded-full text-[12px] font-semibold transition-all border",
                filter === c
                  ? "bg-brand-600 text-white border-brand-600 shadow-xs"
                  : "bg-surface-card text-gray-500 border-border-default hover:border-border-strong hover:text-gray-700")}>
              {c}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-gray-50 p-1 rounded-lg border border-border-default">
            <button onClick={() => setView("grid")} aria-label="Grid view" aria-pressed={view === "grid"}
              className={cn("p-1.5 rounded-md transition-colors", view === "grid" ? "bg-brand-600 text-white shadow-xs" : "text-gray-400 hover:text-gray-600")}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>
            </button>
            <button onClick={() => setView("list")} aria-label="List view" aria-pressed={view === "list"}
              className={cn("p-1.5 rounded-md transition-colors", view === "list" ? "bg-brand-600 text-white shadow-xs" : "text-gray-400 hover:text-gray-600")}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M2 4h12M2 8h12M2 12h12"/></svg>
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
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M8 2v12M2 8h12"/></svg>
            {uploading ? "Uploading…" : "Upload"}
          </Button>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div role="alert" className="rounded-xl bg-danger-50 border border-danger-200 text-danger-700 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold m-0">Documents could not be loaded</p>
            <p className="text-[13px] mt-0.5 mb-0">
              {error instanceof Error ? error.message : "The document service did not respond. Check your connection and try again."}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isRefetching}
            className="shrink-0 self-start sm:self-auto px-3.5 py-2 rounded-lg text-[12.5px] font-semibold text-danger-700 bg-surface-card border border-danger-200 hover:bg-danger-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
            {isRefetching ? "Retrying…" : "Retry"}
          </button>
        </div>
      )}

      {/* Loading state */}
      {!isError && isPending && (
        <div aria-busy="true" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="p-4">
              <div className="animate-pulse">
                <div className="flex items-start justify-between mb-4">
                  <div className="w-10 h-12 rounded-lg bg-gray-100" />
                  <div className="w-14 h-4 rounded-full bg-gray-100" />
                </div>
                <div className="h-3.5 w-3/4 rounded bg-gray-100 mb-2" />
                <div className="h-3 w-1/2 rounded bg-gray-100" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isError && !isPending && docs.length === 0 && (
        <Card className="p-10 flex flex-col items-center text-center">
          <div className="w-12 h-14 rounded-lg bg-gray-50 border border-border-default flex items-center justify-center text-2xl mb-4" aria-hidden="true">📄</div>
          <h3 className="text-[15px] font-semibold text-gray-900 m-0">No documents yet</h3>
          <p className="text-[13px] text-gray-500 mt-1 mb-4 max-w-sm">
            Upload a PDF, DOCX, XLSX, CSV or TXT file to start building your indexed knowledge base.
          </p>
          <Button variant="secondary" className="gap-2" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M8 2v12M2 8h12"/></svg>
            Upload your first document
          </Button>
        </Card>
      )}

      {/* No results for the active filter */}
      {!isError && !isPending && docs.length > 0 && filtered.length === 0 && (
        <Card className="p-8 text-center">
          <p className="text-[13px] text-gray-500 m-0">No documents match the “{filter}” filter.</p>
        </Card>
      )}

      {/* Grid View */}
      {!isError && !isPending && filtered.length > 0 && view === "grid" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(doc => (
            <Card key={doc.id} className="p-4 group hover:border-border-strong hover:shadow-sm transition-all">
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-12 rounded-lg bg-gray-50 border border-border-default flex items-center justify-center text-xl" aria-hidden="true">
                  {fileEmoji(doc.name)}
                </div>
                <div className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full", statusBadge[doc.status])}>
                  {doc.status.toUpperCase()}
                </div>
              </div>
              <h4 className="text-[13px] font-semibold text-gray-900 truncate mb-1" title={doc.name}>{doc.name}</h4>
              <div className="text-[11px] text-gray-400 flex justify-between">
                <span>{doc.size ? formatBytes(doc.size) : "—"}</span>
                <span>{doc.connector}</span>
              </div>
              <div className="mt-4 pt-3 border-t border-border-default flex items-center justify-between opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                <span className="text-[10px] text-gray-400">{formatRelativeTime(doc.updated_at)}</span>
                <button onClick={() => setSelected(doc)} className="text-[11px] font-bold text-brand-600 hover:text-brand-700 hover:underline">View</button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* List View */}
      {!isError && !isPending && filtered.length > 0 && view === "list" && (
        <div className="rounded-2xl border border-border-default overflow-hidden bg-surface-card shadow-xs">
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
                      <span className="text-lg" aria-hidden="true">{fileEmoji(doc.name)}</span>
                      <span className="text-[13px] text-gray-800 font-medium">{doc.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full", statusBadge[doc.status])}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-[12px] text-gray-500">{doc.connector}</td>
                  <td className="px-5 py-3.5 text-[12px] text-gray-500 text-right font-mono">{doc.size ? formatBytes(doc.size) : "—"}</td>
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
            role="dialog"
            aria-modal="true"
            aria-label={selected.title ?? selected.name}
            className="relative w-full max-w-[480px] max-h-[88vh] overflow-y-auto rounded-2xl border border-border-default bg-surface-card shadow-md flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border-default">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-2xl shrink-0" aria-hidden="true">{fileEmoji(selected.name)}</span>
                <div className="min-w-0">
                  <h3 className="text-[14px] font-semibold text-gray-900 truncate">{selected.title ?? selected.name}</h3>
                  <p className="text-[11px] text-gray-400 font-mono truncate">{selected.name}</p>
                </div>
              </div>
              <button onClick={() => setSelected(null)} aria-label="Close document details"
                className="w-7 h-7 rounded-md flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors shrink-0">
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
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
                    <div className="text-[13px] font-medium text-gray-800 capitalize">{f.value}</div>
                  </div>
                ))}
              </div>

              {selected.tags && selected.tags.length > 0 && (
                <div>
                  <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Tags</div>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.tags.map(t => (
                      <span key={t} className="px-2 py-0.5 rounded-full text-[10.5px] font-semibold text-brand-700 bg-brand-50 border border-brand-100">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-[12px] text-gray-500 leading-relaxed m-0">
                This document is chunked, embedded and indexed — every answer citing it links back
                to the exact passage.
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default">
              <button onClick={() => setSelected(null)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-gray-600 bg-surface-card border border-border-default hover:border-border-strong hover:bg-gray-50 transition-all">
                Close
              </button>
              <button
                onClick={() => router.push(`/chat?q=${encodeURIComponent(`Summarise the key points of the document "${selected.title ?? selected.name}" and what actions it implies`)}`)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-bold text-white bg-brand-600 border border-brand-700 hover:bg-brand-700 shadow-xs transition-all">
                Ask Iroko about this document →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
