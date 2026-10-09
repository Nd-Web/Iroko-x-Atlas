"use client";
/**
 * components/pages/DocumentsContent.tsx — Enterprise document library.
 * File grid/list, upload, status tracking, search and status filtering.
 */
import { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { useDocuments } from "@/app/(app)/documents/_hooks/useDocuments";
import { useUploadDocument } from "@/app/(app)/documents/_hooks/useUploadDocument";
import { useDeleteDocument } from "@/app/(app)/documents/_hooks/useDeleteDocument";
import { cn, formatBytes, formatRelativeTime, utcTimestamp } from "@/lib/utils";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Modal from "@/components/ui/Modal";
import { DOCUMENT_ROLES, roleHint } from "@/lib/compliance-graph-view";
import DocumentEvidence from "@/components/documents/DocumentEvidence";
import RegulatorySources from "@/components/documents/RegulatorySources";

interface Doc {
  id: string;
  name: string;
  title?: string;
  size: number;
  type: string;
  status: "indexed" | "indexing" | "error" | "review required" | "rejected" | "archived" | "superseded";
  pipeline?: boolean;
  /** What the uploader said this document is (compliance graph role). */
  role?: string;
  department?: string;
  tags?: string[];
  chunks?: number;
  error?: string;
  updated_at: string;
}

// Mirrors the backend upload allow-list and role check in routes/documents.py.
const UPLOAD_ACCEPT = ".pdf,.docx,.xlsx,.txt,.md,.csv";
const WRITE_ROLES = new Set(["superadmin", "admin", "analyst"]);
const PAGE_SIZE = 100;

function normaliseStatus(status: string): Doc["status"] {
  if (status === "review_required") return "review required";
  if (status === "rejected" || status === "archived" || status === "superseded") return status;
  if (status === "indexed" || status === "completed") return "indexed";
  if (status === "error" || status === "failed") return "error";
  return "indexing";
}

function statusClass(status: Doc["status"]) {
  switch (status) {
    case "indexed": return "bg-success-50 text-success-500";
    case "indexing": return "bg-info-50 text-info-500 animate-pulse";
    case "review required": return "bg-amber-50 text-amber-700";
    case "error":
    case "rejected": return "bg-[rgba(239,68,68,0.12)] text-[#F87171]";
    default: return "bg-gray-100 text-gray-500";
  }
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
  const { user } = useAuth();
  const canWrite = WRITE_ROLES.has(user?.role ?? "");
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [selectedSnapshot, setSelected] = useState<Doc | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, isPending, isError, error, refetch } = useDocuments({ page_size: PAGE_SIZE });
  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();
  const uploading = uploadMutation.isPending;

  const docs: Doc[] = useMemo(() => {
    if (!data?.documents) return [];
    return data.documents.map((doc) => ({
      id: doc.id,
      pipeline: !!doc.extra_metadata?.pipeline,
      role: doc.extra_metadata?.document_role,
      name: doc.filename ?? doc.title ?? "Untitled document",
      title: doc.title ?? undefined,
      size: doc.file_size ?? 0,
      type: doc.file_type ?? "",
      status: normaliseStatus(doc.status ?? "indexing"),
      department: doc.department ?? undefined,
      tags: doc.tags ?? undefined,
      chunks: doc.chunk_count ?? undefined,
      error: doc.error_message ?? undefined,
      // The backend list response has created_at only — updated_at may be absent.
      updated_at: utcTimestamp(doc.updated_at ?? doc.created_at ?? new Date().toISOString()),
    }));
  }, [data]);
  const selected = selectedSnapshot
    ? docs.find(doc => doc.id === selectedSnapshot.id) ?? selectedSnapshot
    : null;

  const openDoc = (doc: Doc) => { setConfirmRemove(false); setSelected(doc); };

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

  // Choosing a file first asks what it is (for the compliance graph) and whether
  // it replaces an earlier document, so new versions keep their history.
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploadRole, setUploadRole] = useState("");
  const [replaces, setReplaces] = useState("");
  const replaceable = useMemo(() => docs.filter(d => d.pipeline && d.status !== "archived" && d.status !== "rejected"), [docs]);

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploadRole(roleHint(file.name) ?? "");
    setReplaces("");
    setPendingFile(file);
  };

  const confirmUpload = async () => {
    const file = pendingFile;
    if (!file || !uploadRole) return;
    setPendingFile(null);
    const toastId = toast.loading(`Uploading ${file.name}…`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_role", uploadRole);
      if (replaces) formData.append("replaces_document_id", replaces);
      // onSuccess invalidates the ["documents"] query — the list refreshes itself.
      const saved = await uploadMutation.mutateAsync(formData);
      toast.success(`${file.name} saved · ${normaliseStatus(saved.status)}`, { id: toastId });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed. Please try again.", { id: toastId });
    }
  };

  const handleRemove = async (doc: Doc) => {
    const verb = doc.pipeline ? "archived" : "deleted";
    try {
      await deleteMutation.mutateAsync(doc.id);
      toast.success(`${doc.title ?? doc.name} ${verb}`);
      setSelected(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Document could not be ${verb}.`);
    } finally {
      setConfirmRemove(false);
    }
  };

  const statusChips = ["All", ...Array.from(new Set(docs.map(d => d.status)))];
  const activeFilter = statusChips.includes(filter) ? filter : "All";
  const needle = query.trim().toLowerCase();
  const filtered = docs.filter(d =>
    (activeFilter === "All" || d.status === activeFilter) &&
    (!needle || [d.name, d.title, d.department, ...(d.tags ?? [])].some(v => v?.toLowerCase().includes(needle)))
  );
  const total = data?.total ?? docs.length;

  return (
    <div className="space-y-6">
      <RegulatorySources />
      {/* Header / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Filter by name, department or tag"
            aria-label="Filter documents"
            className="w-full sm:w-64 px-3 py-1.5 rounded-lg text-[12.5px] bg-transparent border border-border-default text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-border-strong"
          />
          {statusChips.length > 2 && statusChips.map(c => (
            <button key={c} onClick={() => setFilter(c)}
              aria-pressed={activeFilter === c}
              className={cn("px-3 py-1.5 rounded-full text-[12px] font-semibold capitalize transition-all border",
                activeFilter === c ? "bg-brand-500 text-[#0A0A0B] border-brand-500" : "text-gray-500 border-border-default hover:border-border-strong")}>
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
          {canWrite && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept={UPLOAD_ACCEPT}
                className="hidden"
                onChange={handleFileSelected}
              />
              <Button variant="primary" className="gap-2" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
                <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 2v12M2 8h12"/></svg>
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            </>
          )}
        </div>
      </div>

      {!isPending && !isError && total > docs.length && (
        <p className="text-[12px] text-gray-400 m-0">Showing the {docs.length} most recent of {total} documents.</p>
      )}

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
            {canWrite
              ? "Upload a PDF, DOCX, XLSX, TXT, MD or CSV file to start building your knowledge base."
              : "Documents shared with your workspace will appear here."}
          </p>
          {canWrite && (
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="mt-2 px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-gray-500 border border-border-default hover:text-gray-900 hover:border-border-strong transition-all"
            >
              {uploading ? "Uploading…" : "Upload a document"}
            </button>
          )}
        </div>
      )}

      {/* No matches for the current search/filter */}
      {!isPending && !isError && docs.length > 0 && filtered.length === 0 && (
        <div className="rounded-2xl border border-border-default bg-surface-card p-8 text-center">
          <p className="text-[13px] text-gray-500 m-0">No documents match the current filter.</p>
          <button onClick={() => { setQuery(""); setFilter("All"); }} className="mt-2 text-[12px] font-semibold text-info-500 hover:underline">
            Clear filters
          </button>
        </div>
      )}

      {/* Grid View */}
      {!isPending && !isError && filtered.length > 0 && view === "grid" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(doc => (
            <Card key={doc.id} noPad className="hover:border-border-strong transition-colors">
              <button
                onClick={() => openDoc(doc)}
                aria-label={`View ${doc.title ?? doc.name}`}
                className="w-full p-4 text-left rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="w-10 h-12 rounded-lg bg-gray-50 border border-border-default flex items-center justify-center">
                    <FileGlyph name={doc.name} size={20} />
                  </div>
                  <div className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase", statusClass(doc.status))}>
                    {doc.status}
                  </div>
                </div>
                <h4 className="text-[13px] font-semibold text-gray-800 truncate mb-0.5" title={doc.title ?? doc.name}>{doc.title ?? doc.name}</h4>
                {doc.title && <p className="text-[11px] text-gray-400 font-mono truncate m-0 mb-1" title={doc.name}>{doc.name}</p>}
                {doc.role && (
                  <span className="mb-1 inline-block rounded-full badge-gray px-2 py-0.5 text-[10px]">
                    {DOCUMENT_ROLES.find(r => r.value === doc.role)?.label ?? doc.role}
                  </span>
                )}
                <div className="text-[11px] text-gray-400 flex justify-between gap-2">
                  <span>{doc.size ? formatBytes(doc.size) : "—"}</span>
                  <span className="truncate">{doc.department ?? doc.type.toUpperCase()}</span>
                </div>
                <div className="mt-4 pt-3 border-t border-border-default flex items-center justify-between">
                  <span className="text-[10px] text-gray-400">{formatRelativeTime(doc.updated_at)}</span>
                  <span className="text-[11px] font-bold text-info-500">View</span>
                </div>
              </button>
            </Card>
          ))}
        </div>
      )}

      {/* List View */}
      {!isPending && !isError && filtered.length > 0 && view === "list" && (
        <div className="rounded-2xl border border-border-default overflow-hidden bg-surface-card">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-border-default">
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">Name</th>
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider">Updated</th>
                <th className="px-5 py-3 text-[11px] font-bold text-gray-400 uppercase tracking-wider text-right">Size</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-default">
              {filtered.map(doc => (
                <tr key={doc.id} onClick={() => openDoc(doc)} className="hover:bg-gray-50 transition-colors group cursor-pointer">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3 min-w-0">
                      <FileGlyph name={doc.name} size={16} />
                      <button
                        onClick={e => { e.stopPropagation(); openDoc(doc); }}
                        className="text-[13px] text-gray-700 font-medium text-left truncate hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
                        title={doc.name}
                      >
                        {doc.title ?? doc.name}
                      </button>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap", statusClass(doc.status))}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-[12px] text-gray-400 whitespace-nowrap">{formatRelativeTime(doc.updated_at)}</td>
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
                  { label: "Department", value: selected.department ?? "—" },
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
                {selected.status === "indexed" ? "This document is available for answers. Open its evidence to inspect the extracted source." : "This document is not currently available for answers. Its processing or review status is shown above."}
              </p>
              {selected.error && (selected.status === "error" || selected.status === "rejected") && (
                <p role="alert" className="text-[12px] text-[#F87171] leading-relaxed m-0 break-words">{selected.error}</p>
              )}
              {selected.pipeline && <DocumentEvidence id={selected.id} />}
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2 px-5 py-4 border-t border-border-default">
              {canWrite && (
                confirmRemove ? (
                  <div className="mr-auto flex items-center gap-2">
                    <button
                      disabled={deleteMutation.isPending}
                      onClick={() => handleRemove(selected)}
                      className="px-3 py-2 rounded-xl text-[12.5px] font-bold text-[#F87171] border border-[rgba(239,68,68,0.35)] hover:bg-[rgba(239,68,68,0.08)] disabled:opacity-50 transition-all">
                      {deleteMutation.isPending ? "Working…" : selected.pipeline ? "Confirm archive" : "Confirm delete"}
                    </button>
                    <button onClick={() => setConfirmRemove(false)} className="text-[12px] text-gray-400 hover:text-gray-700">Cancel</button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmRemove(true)}
                    title={selected.pipeline ? "Removes it from the library; the original and audit history are kept" : "Permanently deletes this document"}
                    className="mr-auto px-3 py-2 rounded-xl text-[12.5px] font-semibold text-gray-400 hover:text-[#F87171] transition-all">
                    {selected.pipeline ? "Archive" : "Delete"}
                  </button>
                )
              )}
              <button onClick={() => setSelected(null)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-semibold text-gray-500 border border-border-default hover:text-gray-900 hover:border-border-strong transition-all">
                Close
              </button>
              <button
                disabled={selected.status !== "indexed"}
                onClick={() => router.push(`/chat?q=${encodeURIComponent(`Summarise the key points of the document "${selected.title ?? selected.name}" and what actions it implies`)}`)}
                className="px-3.5 py-2 rounded-xl text-[12.5px] font-bold text-[#0A0A0B] bg-brand-500 hover:bg-brand-400 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-brand-500 transition-all">
                Ask Iroko about this document →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload: what is this document? */}
      <Modal open={!!pendingFile} onClose={() => setPendingFile(null)} title="What is this document?" maxWidth="520px" footer={
        <div className="flex justify-end gap-2">
          <button className="btn-secondary" onClick={() => setPendingFile(null)}>Cancel</button>
          <button className="btn-primary" disabled={!uploadRole || uploading} onClick={confirmUpload}>Upload</button>
        </div>
      }>
        <div className="space-y-4">
          <p className="text-[13px] text-gray-600 truncate" title={pendingFile?.name}>{pendingFile?.name}</p>
          <fieldset className="space-y-2">
            <legend className="sr-only">Document type</legend>
            {DOCUMENT_ROLES.map(r => (
              <label key={r.value} className={cn("flex items-start gap-3 rounded-lg border px-3 py-2 cursor-pointer",
                uploadRole === r.value ? "border-brand-500" : "border-border-default hover:border-border-strong")}>
                <input type="radio" name="document_role" value={r.value} checked={uploadRole === r.value}
                  onChange={() => setUploadRole(r.value)} className="mt-1" />
                <span>
                  <span className="block text-[13px] text-gray-800">{r.label}</span>
                  <span className="block text-[11px] text-gray-500">{r.hint}</span>
                </span>
              </label>
            ))}
          </fieldset>
          {uploadRole && roleHint(pendingFile?.name) === uploadRole && (
            <p className="text-[11px] text-gray-500">Pre-selected from the file name. Change it if it is wrong; Iroko will also check the content.</p>
          )}
          {replaceable.length > 0 && (
            <label className="block text-[12px] text-gray-500">Replaces an existing document (optional)
              <select className="input-base mt-1 text-[13px]" value={replaces} onChange={e => setReplaces(e.target.value)}>
                <option value="">No — this is a new document</option>
                {replaceable.map(d => <option key={d.id} value={d.id}>{d.title ?? d.name}</option>)}
              </select>
              <span className="mt-1 block text-[11px]">A replacement becomes a new version: links and decisions carry over, and changed wording is flagged for review.</span>
            </label>
          )}
        </div>
      </Modal>
    </div>
  );
}
