"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";

type Source = { id: string; regulator: string; url: string; parser: string; enabled: boolean; interval_hours: number; max_documents: number; result: { status?: string; found?: number; accepted?: number; errors?: { detail: string }[] } };

export default function RegulatorySources() {
  const { user } = useAuth();
  const admin = user?.role === "admin" || user?.role === "superadmin";
  const [open, setOpen] = useState(false);
  const [regulator, setRegulator] = useState("CBN");
  const [url, setUrl] = useState("");
  const [parser, setParser] = useState("cbn_json");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const sources = useQuery<Source[]>({
    queryKey: ["regulatory-sources"], enabled: admin && open,
    queryFn: async () => {
      const res = await fetch("/api/ingestion/sources");
      if (!res.ok) throw new Error("Source collection is unavailable. Check that the document pipeline is configured.");
      return res.json();
    },
    refetchInterval: open ? 15000 : false,
  });
  if (!admin) return null;
  async function save(path: string, body: unknown, method = "POST") {
    setBusy(true); setError("");
    try {
      const res = await fetch(`/api/ingestion/sources${path}`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!res.ok) { const result = await res.json(); throw new Error(typeof result.detail === "string" ? result.detail : "Source could not be updated"); }
      await sources.refetch();
    } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); }
    finally { setBusy(false); }
  }
  return <section className="rounded-2xl border border-border-default bg-surface-card p-4">
    <button className="font-semibold text-sm w-full text-left" aria-expanded={open} onClick={() => setOpen(!open)}>Regulatory sources <span className="text-gray-400 font-normal ml-2">{open ? "Hide" : "Manage collection"}</span></button>
    {open && <div className="space-y-4 mt-4 text-sm">
      <p className="text-gray-400">Register an official listing page. Sources start paused; enable collection when you are ready. Download failures remain visible here.</p>
      {sources.isPending && <p>Loading sources…</p>}
      {sources.isError && <p role="alert" className="text-red-400">{sources.error.message}</p>}
      {sources.data?.map(s => <div key={s.id} className="border-t border-border-default pt-3 space-y-2">
        <p className="font-semibold">{s.regulator} · {s.enabled ? "Enabled" : "Paused"}</p>
        <a href={s.url} target="_blank" rel="noreferrer" className="text-brand-500 break-all">{s.url}</a>
        <p className="text-gray-400">{s.result.status ?? "Not collected yet"} · {s.result.found ?? 0} listed · {s.result.accepted ?? 0} accepted</p>
        {s.result.errors?.slice(0, 3).map((e, i) => <p key={i} className="text-amber-500">{e.detail}</p>)}
        <div className="flex gap-4">
          <button disabled={busy} className="text-brand-500" onClick={() => save(`/${s.id}`, { regulator: s.regulator, url: s.url, parser: s.parser, enabled: !s.enabled, interval_hours: s.interval_hours, max_documents: s.max_documents }, "PATCH")}>{s.enabled ? "Pause" : "Enable"}</button>
          <button disabled={busy || !s.enabled} className="text-brand-500 disabled:opacity-40" onClick={() => save(`/${s.id}/run`, {})}>Collect now</button>
        </div>
      </div>)}
      <form className="grid gap-3 border-t border-border-default pt-4" onSubmit={e => { e.preventDefault(); void save("", { regulator, url, parser, enabled: false }); }}>
        <label>Regulator<select value={regulator} onChange={e => { setRegulator(e.target.value); setParser(e.target.value === "CBN" ? "cbn_json" : "html_links"); }} className="block mt-1 w-full rounded-lg border border-border-default bg-surface-card p-2">{["CBN", "SEC", "NDIC", "NFIU", "NDPC", "FCCPC"].map(r => <option key={r}>{r}</option>)}</select></label>
        <label>Official listing URL<input type="url" required value={url} onChange={e => setUrl(e.target.value)} placeholder="https://…" className="block mt-1 w-full rounded-lg border border-border-default bg-transparent p-2" /></label>
        <label>Listing format<select value={parser} onChange={e => setParser(e.target.value)} className="block mt-1 w-full rounded-lg border border-border-default bg-surface-card p-2"><option value="html_links">Page with PDF or Office attachment links</option>{regulator === "CBN" && <option value="cbn_json">CBN circulars JSON catalogue</option>}</select></label>
        <button disabled={busy || sources.isError} className="justify-self-start rounded-lg px-4 py-2 bg-brand-500 text-black disabled:opacity-40">Register source</button>
      </form>
      {error && <p role="alert" className="text-red-400">{error}</p>}
    </div>}
  </section>;
}
