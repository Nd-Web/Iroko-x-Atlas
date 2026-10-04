"use client";

import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { formatRelativeTime, utcTimestamp } from "@/lib/utils";

type ListedItem = {
  title: string; source_url: string; published_date?: string; reference_number?: string | null;
  catalogue_size?: number; importable?: boolean;
};
type Source = {
  id: string; regulator: string; url: string; parser: string; enabled: boolean;
  interval_hours: number; max_documents: number; last_run: string | null;
  job: { state: string; attempts: number; error: string | null; available_at: string } | null;
  result: {
    status?: string; found?: number; accepted?: number; attempted?: number; blocked?: boolean;
    skipped_recent_failures?: number; failing_links?: number; missing?: ListedItem[]; missing_total?: number;
    errors?: { url?: string; error?: string; detail: string }[];
  };
};

const REGULATORS = ["CBN", "SEC", "NDIC", "NFIU", "NDPC", "FCCPC"];
const BATCH_SIZES = [5, 10, 20, 50, 100];
const SCHEDULES = [
  { hours: 0, label: "Manual only" }, { hours: 6, label: "Every 6 hours" }, { hours: 12, label: "Every 12 hours" },
  { hours: 24, label: "Daily" }, { hours: 168, label: "Weekly" },
];
// Official listing pages checked on 4 Oct 2026: each served attachments to the
// collector's identified client. CBN lists circulars but challenges file downloads.
const SUGGESTED = [
  { regulator: "CBN", url: "https://www.cbn.gov.ng/api/GetAllCirculars", parser: "cbn_json", label: "CBN — all circulars (catalogue)" },
  { regulator: "SEC", url: "https://sec.gov.ng/our-mandate/regulation/rules-and-regulations/", parser: "html_links", label: "SEC — rules and regulations" },
  { regulator: "SEC", url: "https://sec.gov.ng/our-mandate/regulation/guidelines/", parser: "html_links", label: "SEC — guidelines" },
  { regulator: "FCCPC", url: "https://fccpc.gov.ng/resources-library/regulations/", parser: "html_links", label: "FCCPC — regulations" },
  { regulator: "FCCPC", url: "https://fccpc.gov.ng/resources-library/guidelines/", parser: "html_links", label: "FCCPC — guidelines" },
  { regulator: "NDIC", url: "https://ndic.gov.ng/publications", parser: "html_links", label: "NDIC — publications" },
  { regulator: "NDPC", url: "https://ndpc.gov.ng/", parser: "html_links", label: "NDPC — documents linked from the homepage" },
];
const STATUS_TEXT: Record<string, string> = {
  succeeded: "Succeeded", partial: "Some downloads failed", blocked: "Blocked by the site's browser check",
  suspect: "No documents found — the page layout may have changed", failed: "Listing could not be read", running: "Running",
};
function statusText(r: Source["result"]) {
  // Runs before October 2026 also used "suspect" for a high download failure rate.
  if (r.status === "suspect" && r.found) return "Many downloads failed";
  return STATUS_TEXT[r.status ?? ""] ?? r.status ?? "Unknown";
}
// A queued job older than this means no worker is running against this database.
const STALE_QUEUE_MS = 10 * 60 * 1000;

async function errorMessage(res: Response, fallback: string) {
  const data = await res.json().catch(() => ({}));
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  return typeof data.error === "string" ? data.error : fallback;
}

export default function RegulatorySources() {
  const { user } = useAuth();
  const admin = user?.role === "superadmin";
  const [open, setOpen] = useState(false);
  const [regulator, setRegulator] = useState("CBN");
  const [url, setUrl] = useState("");
  const [parser, setParser] = useState("cbn_json");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const sources = useQuery<Source[]>({
    queryKey: ["regulatory-sources", user?.id], enabled: admin && open,
    queryFn: async () => {
      const res = await fetch("/api/ingestion/sources");
      if (!res.ok) throw new Error(await errorMessage(res, "Source collection is unavailable. Check that the document pipeline is configured."));
      return res.json();
    },
    refetchInterval: (q) => !open ? false
      : q.state.data?.some(s => ["queued", "running", "retry"].includes(s.job?.state ?? "")) ? 5000 : 15000,
  });
  if (!admin) return null;

  async function save(path: string, body: unknown, method = "POST") {
    setBusy(true); setError("");
    try {
      const res = await fetch(`/api/ingestion/sources${path}`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!res.ok) throw new Error(await errorMessage(res, "Source could not be updated"));
      await sources.refetch();
      return true;
    } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); return false; }
    finally { setBusy(false); }
  }
  const update = (s: Source, change: Partial<Pick<Source, "enabled" | "interval_hours" | "max_documents">>) =>
    save(`/${s.id}`, {
      regulator: s.regulator, url: s.url, parser: s.parser, enabled: s.enabled,
      interval_hours: s.interval_hours, max_documents: s.max_documents, ...change,
    }, "PATCH");

  const registered = new Set(sources.data?.map(s => s.url));
  const suggestions = SUGGESTED.filter(s => !registered.has(s.url));
  const enabledCount = sources.data?.filter(s => s.enabled).length ?? 0;

  return <section className="rounded-2xl border border-border-default bg-surface-card p-4">
    <button className="font-semibold text-sm w-full text-left" aria-expanded={open} onClick={() => setOpen(!open)}>
      Regulatory sources <span className="text-gray-400 font-normal ml-2">
        {open ? "Hide" : sources.data ? `${sources.data.length} sources · ${enabledCount} enabled · Manage collection` : "Manage collection"}
      </span>
    </button>
    {open && <div className="space-y-4 mt-4 text-sm">
      <p className="text-gray-400 m-0">
        Iroko collects files from official regulator pages, identifies itself, honours robots.txt and never bypasses a site&apos;s
        access checks. New sources start paused. Collected documents stay private to your workspace until you share them.
      </p>
      {sources.isPending && <p className="m-0">Loading sources…</p>}
      {sources.isError && <p role="alert" className="text-red-400 m-0">{sources.error.message}</p>}
      {sources.data?.length === 0 && <p className="text-gray-400 m-0">No sources registered yet. Add a suggested source below.</p>}
      {sources.data?.map(s => <SourceCard key={s.id} source={s} fetchedAt={sources.dataUpdatedAt} busy={busy} onUpdate={change => update(s, change)}
        onRun={() => save(`/${s.id}/run`, {})} onImported={() => sources.refetch()} />)}

      {suggestions.length > 0 && sources.isSuccess && <div className="border-t border-border-default pt-4 space-y-2">
        <p className="font-semibold m-0">Suggested official sources</p>
        <ul className="space-y-1.5 m-0 p-0 list-none">
          {suggestions.map(s => <li key={s.url} className="flex items-center justify-between gap-3">
            <span className="min-w-0"><span className="text-gray-700">{s.label}</span>
              <span className="block text-[11px] text-gray-400 truncate">{s.url}</span></span>
            <button disabled={busy} className="shrink-0 text-brand-500 disabled:opacity-40"
              onClick={() => save("", { regulator: s.regulator, url: s.url, parser: s.parser, enabled: false })}>Add</button>
          </li>)}
        </ul>
      </div>}

      <form className="grid gap-3 border-t border-border-default pt-4" onSubmit={async e => {
        e.preventDefault();
        if (await save("", { regulator, url, parser, enabled: false })) setUrl("");
      }}>
        <p className="font-semibold m-0">Register another official page</p>
        <label>Regulator<select value={regulator} onChange={e => { setRegulator(e.target.value); setParser(e.target.value === "CBN" ? "cbn_json" : "html_links"); }} className="block mt-1 w-full rounded-lg border border-border-default bg-surface-card p-2">{REGULATORS.map(r => <option key={r}>{r}</option>)}</select></label>
        <label>Official listing URL<input type="url" required value={url} onChange={e => setUrl(e.target.value)} placeholder="https://…" className="block mt-1 w-full rounded-lg border border-border-default bg-transparent p-2" /></label>
        <label>Listing format<select value={parser} onChange={e => setParser(e.target.value)} className="block mt-1 w-full rounded-lg border border-border-default bg-surface-card p-2"><option value="html_links">Page with PDF or Office attachment links</option>{regulator === "CBN" && <option value="cbn_json">CBN circulars JSON catalogue</option>}</select></label>
        <button disabled={busy || sources.isError} className="justify-self-start rounded-lg px-4 py-2 bg-brand-500 text-black disabled:opacity-40">Register source</button>
      </form>
      {error && <p role="alert" className="text-red-400 m-0">{error}</p>}
    </div>}
  </section>;
}

function SourceCard({ source: s, fetchedAt, busy, onUpdate, onRun, onImported }: {
  source: Source; fetchedAt: number; busy: boolean;
  onUpdate: (change: Partial<Pick<Source, "enabled" | "interval_hours" | "max_documents">>) => void;
  onRun: () => void; onImported: () => void;
}) {
  const [showMissing, setShowMissing] = useState(false);
  const r = s.result ?? {};
  const state = s.job?.state;
  const active = state === "queued" || state === "running" || state === "retry";
  const stale = state === "queued" && fetchedAt - new Date(utcTimestamp(s.job!.available_at)).getTime() > STALE_QUEUE_MS;
  const missing = r.missing ?? [];
  const schedules = SCHEDULES.some(o => o.hours === s.interval_hours) ? SCHEDULES : [...SCHEDULES, { hours: s.interval_hours, label: `Every ${s.interval_hours} hours` }];
  const sizes = BATCH_SIZES.includes(s.max_documents) ? BATCH_SIZES : [...BATCH_SIZES, s.max_documents].sort((a, b) => a - b);

  return <div className="border-t border-border-default pt-3 space-y-2">
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-semibold">{s.regulator}</span>
      <span className={s.enabled ? "text-success-500 text-[12px]" : "text-gray-400 text-[12px]"}>
        {s.enabled ? (s.interval_hours ? `Enabled · ${schedules.find(o => o.hours === s.interval_hours)?.label}` : "Enabled · manual") : "Paused"}
      </span>
    </div>
    <a href={s.url} target="_blank" rel="noreferrer" className="text-brand-500 break-all">{s.url}</a>

    <p className="text-gray-400 m-0" aria-live="polite">
      {state === "queued" && "Queued — waiting for the document worker."}
      {state === "running" && "Collecting now…"}
      {state === "retry" && `Retrying after an error${s.job?.error ? `: ${s.job.error}` : ""}`}
      {!active && (s.last_run
        ? <>Last run {formatRelativeTime(utcTimestamp(s.last_run))}: {statusText(r)} · {r.found ?? 0} listed · {r.accepted ?? 0} collected
          {r.missing_total ? ` · ${r.missing_total} not yet collected` : ""}</>
        : "Not collected yet.")}
    </p>
    {stale && <p className="text-amber-500 m-0">
      No worker has picked this up in over 10 minutes. Start the document worker (run.bat starts one locally, or deploy the scheduled worker).
    </p>}
    {!active && r.blocked && <p className="text-amber-500 m-0">
      This site blocks automated downloads with a browser check, and Iroko will not bypass it. Open each file&apos;s official link,
      download it in your browser, then import it from the list below.
    </p>}
    {!active && !r.blocked && r.errors?.slice(0, 3).map((e, i) => <p key={i} className="text-amber-500 m-0 break-words">{e.detail}</p>)}
    {!active && !!r.skipped_recent_failures && <p className="text-gray-400 m-0">
      {r.skipped_recent_failures} broken link{r.skipped_recent_failures === 1 ? "" : "s"} skipped; they are retried with increasing delays.
    </p>}

    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <button disabled={busy} className="text-brand-500 disabled:opacity-40" onClick={() => onUpdate({ enabled: !s.enabled })}>{s.enabled ? "Pause" : "Enable"}</button>
      <button disabled={busy || !s.enabled || active} className="text-brand-500 disabled:opacity-40" onClick={onRun}
        title={s.enabled ? undefined : "Enable the source first"}>{active ? "Collecting…" : "Collect now"}</button>
      <label className="text-gray-400 flex items-center gap-1.5">Batch
        <select disabled={busy} value={s.max_documents} onChange={e => onUpdate({ max_documents: Number(e.target.value) })}
          className="rounded-md border border-border-default bg-surface-card px-1.5 py-1 text-gray-700">
          {sizes.map(n => <option key={n} value={n}>{n} files</option>)}
        </select>
      </label>
      <label className="text-gray-400 flex items-center gap-1.5">Schedule
        <select disabled={busy} value={s.interval_hours} onChange={e => onUpdate({ interval_hours: Number(e.target.value) })}
          className="rounded-md border border-border-default bg-surface-card px-1.5 py-1 text-gray-700">
          {schedules.map(o => <option key={o.hours} value={o.hours}>{o.label}</option>)}
        </select>
      </label>
    </div>

    {missing.length > 0 && <div>
      <button className="text-gray-500 hover:text-gray-800" aria-expanded={showMissing} onClick={() => setShowMissing(!showMissing)}>
        {showMissing ? "Hide" : "Show"} documents not yet collected ({r.missing_total ?? missing.length}{(r.missing_total ?? 0) > missing.length ? `, newest ${missing.length} listed` : ""})
      </button>
      {showMissing && <ul className="mt-2 space-y-2 m-0 p-0 list-none">
        {missing.map(item => <MissingItem key={item.source_url} sourceId={s.id} item={item} onImported={onImported} />)}
      </ul>}
    </div>}
  </div>;
}

function MissingItem({ sourceId, item, onImported }: { sourceId: string; item: ListedItem; onImported: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const cache = useQueryClient();
  async function upload(file: File) {
    setUploading(true);
    const toastId = toast.loading(`Importing ${item.title}…`);
    try {
      const form = new FormData();
      form.append("source_url", item.source_url);
      form.append("file", file);
      const res = await fetch(`/api/ingestion/sources/${encodeURIComponent(sourceId)}/import`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await errorMessage(res, "Import failed. Please try again."));
      toast.success(`${item.title} imported · processing`, { id: toastId });
      await Promise.all([cache.invalidateQueries({ queryKey: ["documents"] }), onImported()]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Import failed. Please try again.", { id: toastId });
    } finally { setUploading(false); }
  }
  const ext = item.source_url.split("?")[0].split(".").pop()?.toLowerCase() ?? "";
  return <li className="rounded-lg border border-border-default p-2.5 flex flex-wrap items-center justify-between gap-2">
    <div className="min-w-0">
      <p className="text-gray-700 m-0 break-words">{item.title}</p>
      <p className="text-[11px] text-gray-400 m-0">
        {[item.published_date, item.reference_number, item.catalogue_size ? `${item.catalogue_size.toLocaleString()} bytes` : null].filter(Boolean).join(" · ")}
      </p>
    </div>
    <div className="flex items-center gap-3 shrink-0">
      <a href={item.source_url} target="_blank" rel="noreferrer" className="text-brand-500">Official link</a>
      {item.importable === false
        ? <span className="text-[11px] text-gray-400">.{ext} files are not supported</span>
        : <>
          <input ref={input} type="file" accept={`.${ext}`} className="hidden"
            onChange={e => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void upload(f); }} />
          <button disabled={uploading} onClick={() => input.current?.click()} className="text-brand-500 disabled:opacity-40">
            {uploading ? "Importing…" : "Import file"}
          </button>
        </>}
    </div>
  </li>;
}
