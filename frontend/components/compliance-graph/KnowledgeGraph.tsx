"use client";
/**
 * The compliance knowledge graph page: requirements from regulations, your
 * controls and evidence, and how they connect.
 *
 * The URL carries the tab, filters and the open item (?tab=…&link=… or
 * ?requirement=…), so chat answers and tasks can link straight to the exact
 * relationship they rely on.
 */

import { useCallback, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import AppShell from "@/components/layout/AppShell";
import { downloadAuditPack, useOverview, type RequirementFilters } from "@/lib/compliance-graph";
import ChangesFeed from "./ChangesFeed";
import ControlsTab from "./ControlsTab";
import EvidencePanel, { type Selection } from "./EvidencePanel";
import Explorer from "./Explorer";
import Overview from "./Overview";
import ProfileDialog from "./ProfileDialog";
import RequirementsTable from "./RequirementsTable";
import ReviewQueue from "./ReviewQueue";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "requirements", label: "Requirements" },
  { key: "controls", label: "Controls" },
  { key: "explorer", label: "Explorer" },
  { key: "review", label: "Review" },
  { key: "changes", label: "Changes" },
] as const;
type TabKey = (typeof TABS)[number]["key"];
const SELECTION_KEYS = ["link", "requirement", "control", "document"] as const;
const FILTER_KEYS = ["q", "regulator", "document_id", "topic", "applicability", "coverage", "owner", "due_within"] as const;

export default function KnowledgeGraph() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const overview = useOverview();
  const [profileOpen, setProfileOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // All derived from the URL on each render (cheap; nothing to memoise).
  const tab: TabKey = (TABS.find((t) => t.key === params.get("tab"))?.key ?? "overview");
  let selection: Selection = null;
  for (const kind of SELECTION_KEYS) {
    const id = params.get(kind);
    if (id) { selection = { kind, id }; break; }
  }
  const filters: RequirementFilters = {};
  for (const key of FILTER_KEYS) {
    const value = params.get(key);
    if (!value) continue;
    if (key === "due_within") filters.due_within = Number(value) || undefined;
    else filters[key] = value;
  }
  const exploreType = params.get("explore_type");
  const exploreId = params.get("explore_id");
  const exploreStart = exploreType && exploreId ? { type: exploreType, id: exploreId } : null;

  const navigate = useCallback((changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [params, pathname, router]);

  const open = useCallback((s: Selection) => {
    const changes: Record<string, string | null> = Object.fromEntries(SELECTION_KEYS.map((k) => [k, null]));
    if (s) changes[s.kind] = s.id;
    navigate(changes);
  }, [navigate]);

  const goTab = useCallback((next: string, extra: Record<string, string> = {}) => {
    const changes: Record<string, string | null> = { tab: next === "overview" ? null : next };
    for (const key of FILTER_KEYS) changes[key] = extra[key] ?? null;
    for (const [key, value] of Object.entries(extra)) changes[key] = value;
    navigate(changes);
  }, [navigate]);

  const download = async () => {
    setDownloading(true);
    setDownloadError(null);
    try { await downloadAuditPack(); } catch (e) { setDownloadError(e instanceof Error ? e.message : "Download failed."); } finally { setDownloading(false); }
  };

  const reviewCount = overview.data?.totals.awaiting_review ?? 0;
  const changeCount = overview.data?.totals.open_changes ?? 0;
  const actions = (
    <div className="flex items-center gap-2">
      {/* Short labels on phones so both actions fit beside the menu button. */}
      <button className="btn-secondary text-[12px]" onClick={() => setProfileOpen(true)}>
        <span className="sm:hidden">Licence</span>
        <span className="hidden sm:inline">
          {overview.data?.profile.labels.length ? `Licence: ${overview.data.profile.labels.join(", ")}` : "Set licence"}
        </span>
      </button>
      <button className="btn-secondary text-[12px]" onClick={download} disabled={downloading}>
        {downloading ? "Preparing…" : <><span className="sm:hidden">Audit pack</span><span className="hidden sm:inline">Download audit pack</span></>}
      </button>
    </div>
  );

  return (
    <AppShell title="Knowledge Graph" subtitle="Requirements, your controls and evidence, and how they connect" actions={actions}>
      {downloadError && <p role="alert" className="text-[13px] text-danger-700">{downloadError}</p>}
      <nav className="-mx-1 flex gap-1 overflow-x-auto border-b border-border-default" role="tablist" aria-label="Knowledge graph sections">
        {TABS.map((t) => {
          const badge = t.key === "review" ? reviewCount : t.key === "changes" ? changeCount : 0;
          return (
            <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => goTab(t.key)}
              className={`whitespace-nowrap border-b-2 px-3 py-2 text-[13px] transition ${tab === t.key ? "border-brand-500 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-800"}`}>
              {t.label}
              {badge > 0 && <span className="ml-1.5 rounded-full bg-gray-100 px-1.5 text-[11px] text-gray-700">{badge}</span>}
            </button>
          );
        })}
      </nav>
      <div role="tabpanel" aria-label={TABS.find((t) => t.key === tab)?.label}>
        {tab === "overview" && <Overview onOpen={open} onTab={goTab} onProfile={() => setProfileOpen(true)} />}
        {tab === "requirements" && <RequirementsTable key={JSON.stringify(filters)} initial={filters} onOpen={open} />}
        {tab === "controls" && <ControlsTab onOpen={open} />}
        {tab === "explorer" && <Explorer start={exploreStart} onOpen={open} />}
        {tab === "review" && <ReviewQueue onOpen={open} />}
        {tab === "changes" && <ChangesFeed onOpen={open} />}
      </div>
      <EvidencePanel selection={selection} onClose={() => open(null)} onOpen={open} />
      <ProfileDialog open={profileOpen} onClose={() => setProfileOpen(false)} />
    </AppShell>
  );
}
