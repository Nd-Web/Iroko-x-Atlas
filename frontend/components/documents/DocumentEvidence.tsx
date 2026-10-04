"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";

type Evidence = {
  sha256: string;
  previous_id: string | null;
  review_status: string;
  shared_regulatory: boolean;
  shareable: boolean;
  provenance: { regulator?: string; source_url?: string; reference_number?: string; published_date?: string };
  issues: { page?: number; reasons: string[] }[];
  pages: { number: number | null; locator: string | null; method: string; text: string }[];
  job: { state: string; attempts: number; error: string | null } | null;
};

const JOB_STATE: Record<string, string> = {
  queued: "Queued for processing", running: "Processing", retry: "Retrying after an error", done: "Processed",
  review_required: "Needs review", failed: "Failed", rejected: "Rejected", superseded: "Superseded by a newer version",
  cancelled: "Cancelled",
};

async function detail(response: Response, fallback: string) {
  const data = await response.json().catch(() => ({}));
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  return typeof data.error === "string" ? data.error : fallback;
}

export default function DocumentEvidence({ id }: { id: string }) {
  const { user } = useAuth();
  const admin = user?.role === "admin" || user?.role === "superadmin";
  const platformAdmin = user?.role === "superadmin";
  const [note, setNote] = useState("");
  const [publishedDate, setPublishedDate] = useState("");
  const [shareNote, setShareNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cache = useQueryClient();
  const query = useQuery<Evidence>({
    queryKey: ["document-evidence", id, user?.id],
    enabled: Boolean(user),
    queryFn: async () => {
      const response = await fetch(`/api/ingestion/documents/${id}`);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === "string" ? data.detail : data.error;
        throw new Error(detail ?? "Could not load source evidence. Please retry.");
      }
      return response.json();
    },
    // A disabled pipeline (503) or missing record (404) will not fix itself on retry.
    retry: (count, err) => count < 2 && !/not enabled|not found/i.test(err.message),
    refetchInterval: (q) => ["queued", "running", "retry"].includes(q.state.data?.job?.state ?? "") ? 5000 : false,
  });
  async function act(action: "approve" | "reject" | "reprocess") {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/ingestion/documents/${id}/${action === "reprocess" ? action : "review"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: action, note, ...(action === "approve" && publishedDate ? { published_date: publishedDate } : {}) }),
      });
      if (!response.ok) throw new Error(await detail(response, "Action failed"));
      await Promise.all([query.refetch(), cache.invalidateQueries({ queryKey: ["documents"] })]);
    } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
    finally { setBusy(false); }
  }
  async function share(shared: boolean) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/ingestion/documents/${id}/sharing`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shared_regulatory: shared, note: shareNote }),
      });
      if (!response.ok) throw new Error(await detail(response, "Sharing could not be changed"));
      setShareNote("");
      await query.refetch();
    } catch (e) { setError(e instanceof Error ? e.message : "Sharing could not be changed"); }
    finally { setBusy(false); }
  }
  if (query.isPending) return <p className="text-sm text-gray-400">Loading source evidence…</p>;
  if (query.isError) return <section className="space-y-2 text-sm border-t border-border-default pt-4">
    <div className="flex items-center justify-between gap-3">
      <h4 className="font-semibold">Source evidence</h4>
      <a className="text-brand-500 underline" href={`/api/ingestion/documents/${id}/original`}>Download original</a>
    </div>
    <p role="alert" className="text-amber-500">{query.error.message}</p>
    <button onClick={() => query.refetch()} disabled={query.isFetching} className="text-brand-500 disabled:opacity-40">{query.isFetching ? "Retrying…" : "Retry"}</button>
  </section>;
  const data = query.data;
  return <section className="space-y-3 text-sm border-t border-border-default pt-4">
    <div className="flex items-center justify-between gap-3">
      <h4 className="font-semibold">Source evidence</h4>
      <a className="text-brand-500 underline" href={`/api/ingestion/documents/${id}/original`}>Download original</a>
    </div>
    <p className="text-gray-400">{data.job ? JOB_STATE[data.job.state] ?? data.job.state.replaceAll("_", " ") : "Not queued"} · {data.pages.length} extracted sections</p>
    {data.job?.error && ["failed", "retry"].includes(data.job.state) && <p role="alert" className="text-amber-500 break-words">
      {data.job.state === "retry" ? `Attempt ${data.job.attempts} failed; retrying automatically. ` : ""}{data.job.error}
    </p>}
    {data.provenance?.regulator && data.provenance.source_url && <p className="text-gray-400 break-words">
      {data.provenance.regulator}{data.provenance.reference_number ? ` · ${data.provenance.reference_number}` : ""}
      {data.provenance.published_date ? ` · published ${data.provenance.published_date}` : ""} ·{" "}
      <a href={data.provenance.source_url} target="_blank" rel="noreferrer" className="text-brand-500 underline">official source</a>
    </p>}
    {data.previous_id && <p className="text-gray-400">This file is a new version. Earlier evidence is retained.</p>}
    {data.issues.length > 0 && <ul className="space-y-1 text-amber-500" aria-label="Extraction issues">
      {data.issues.map((issue, i) => <li key={i}>{issue.page ? `Page ${issue.page}: ` : ""}{issue.reasons.map(r => r.replaceAll("_", " ")).join(", ")}</li>)}
    </ul>}
    <details><summary className="cursor-pointer text-gray-400">Inspect extracted text and file checksum</summary>
      <p className="break-all font-mono text-xs py-2">SHA-256: {data.sha256}</p>
      <div className="max-h-64 overflow-auto space-y-4">
        {data.pages.map((p, i) => <div key={i}><p className="font-semibold">{p.number ? `Page ${p.number}` : p.locator} · {p.method}</p><pre className="whitespace-pre-wrap text-xs text-gray-400">{p.text}</pre></div>)}
      </div>
    </details>
    {admin && data.review_status === "required" && <div className="space-y-2">
      <label className="block" htmlFor="review-note">Review note</label>
      <textarea id="review-note" value={note} onChange={e => setNote(e.target.value)} maxLength={2000} className="w-full rounded-lg bg-transparent border border-border-default p-2" placeholder="Record what you checked against the original" />
      {data.issues.some(i => i.reasons.includes("publication_date_missing")) && <label className="block text-gray-400">
        Publication date, as printed on the document (optional)
        <input type="date" value={publishedDate} onChange={e => setPublishedDate(e.target.value)}
          className="block mt-1 rounded-lg bg-transparent border border-border-default p-2 text-gray-700" />
      </label>}
      <div className="flex gap-3">
        <button disabled={busy || note.trim().length < 5} onClick={() => act("approve")} className="text-brand-500 disabled:opacity-40">Approve for indexing</button>
        <button disabled={busy || note.trim().length < 5} onClick={() => act("reject")} className="text-red-400 disabled:opacity-40">Reject</button>
      </div>
    </div>}
    {admin && ["failed", "review_required", "rejected"].includes(data.job?.state ?? "") && <button disabled={busy} onClick={() => act("reprocess")} className="text-brand-500">Retry extraction</button>}
    {platformAdmin && (data.shareable || data.shared_regulatory) && <div className="space-y-2 border-t border-border-default pt-3">
      <p className="m-0">{data.shared_regulatory
        ? "Shared with all workspaces as public regulatory evidence."
        : "Private to your workspace. Official regulator documents can be shared with every workspace."}</p>
      <label className="block text-gray-400" htmlFor="share-note">Sharing note (recorded in the audit log)</label>
      <textarea id="share-note" value={shareNote} onChange={e => setShareNote(e.target.value)} maxLength={2000}
        className="w-full rounded-lg bg-transparent border border-border-default p-2"
        placeholder={data.shared_regulatory ? "Why this document should no longer be shared" : "What you checked: title, reference, date and pages match the official file"} />
      <button disabled={busy || shareNote.trim().length < 10} onClick={() => share(!data.shared_regulatory)}
        className={data.shared_regulatory ? "text-red-400 disabled:opacity-40" : "text-brand-500 disabled:opacity-40"}>
        {data.shared_regulatory ? "Stop sharing" : "Share with all workspaces"}
      </button>
    </div>}
    {error && <p role="alert" className="text-red-400">{error}</p>}
  </section>;
}
