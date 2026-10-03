"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";

type Evidence = {
  sha256: string;
  previous_id: string | null;
  review_status: string;
  issues: { page?: number; reasons: string[] }[];
  pages: { number: number | null; locator: string | null; method: string; text: string }[];
  job: { state: string; attempts: number; error: string | null } | null;
};

export default function DocumentEvidence({ id }: { id: string }) {
  const { user } = useAuth();
  const admin = user?.role === "admin" || user?.role === "superadmin";
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cache = useQueryClient();
  const query = useQuery<Evidence>({
    queryKey: ["document-evidence", id, user?.id],
    enabled: Boolean(user),
    queryFn: async () => {
      const response = await fetch(`/api/ingestion/documents/${id}`);
      if (!response.ok) throw new Error("Could not load source evidence. Please retry.");
      return response.json();
    },
    refetchInterval: (q) => ["queued", "running", "retry"].includes(q.state.data?.job?.state ?? "") ? 5000 : false,
  });
  async function act(action: "approve" | "reject" | "reprocess") {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/ingestion/documents/${id}/${action === "reprocess" ? action : "review"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: action, note }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail ?? data.error ?? "Action failed");
      }
      await Promise.all([query.refetch(), cache.invalidateQueries({ queryKey: ["documents"] })]);
    } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
    finally { setBusy(false); }
  }
  if (query.isPending) return <p className="text-sm text-gray-400">Loading source evidence…</p>;
  if (query.isError) return <button onClick={() => query.refetch()} className="text-sm text-red-400">Could not load evidence. Retry</button>;
  const data = query.data;
  return <section className="space-y-3 text-sm border-t border-border-default pt-4">
    <div className="flex items-center justify-between gap-3">
      <h4 className="font-semibold">Source evidence</h4>
      <a className="text-brand-500 underline" href={`/api/ingestion/documents/${id}/original`}>Download original</a>
    </div>
    <p className="text-gray-400">{data.job?.state.replaceAll("_", " ")} · {data.pages.length} extracted sections</p>
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
      <div className="flex gap-3">
        <button disabled={busy || note.trim().length < 5} onClick={() => act("approve")} className="text-brand-500 disabled:opacity-40">Approve for indexing</button>
        <button disabled={busy || note.trim().length < 5} onClick={() => act("reject")} className="text-red-400 disabled:opacity-40">Reject</button>
      </div>
    </div>}
    {admin && ["failed", "review_required", "rejected"].includes(data.job?.state ?? "") && <button disabled={busy} onClick={() => act("reprocess")} className="text-brand-500">Retry extraction</button>}
    {error && <p role="alert" className="text-red-400">{error}</p>}
  </section>;
}
