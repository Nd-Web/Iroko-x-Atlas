"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import type { HeatmapRegion } from "@/components/LeafletMap";

// Leaflet touches `window` at import time — must be client-only
const LeafletMap = dynamic(() => import("./LeafletMap"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-zinc-400 text-sm">
      <div className="flex flex-col items-center gap-2">
        <div className="w-6 h-6 border-2 border-zinc-300 border-t-zinc-600 rounded-full animate-spin" />
        Loading map…
      </div>
    </div>
  ),
});

const STATUS_DOT: Record<string, string> = {
  operational: "bg-green-500",
  degraded:    "bg-amber-500",
  down:        "bg-red-500",
};

export default function NigeriaNetworkMap() {
  const [regions, setRegions]   = useState<HeatmapRegion[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    apiFetch<{ regions: HeatmapRegion[]; total_regions: number }>("/api/network/heatmap")
      .then((data) => {
        setRegions(data.regions);
        setLastUpdated(new Date());
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const operational = regions.filter((r) => r.status === "operational").length;
  const degraded    = regions.filter((r) => r.status === "degraded").length;
  const down        = regions.filter((r) => r.status === "down").length;
  const totalSites  = regions.reduce((s, r) => s + r.site_count, 0);

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between flex-shrink-0">
        <div>
          <h3 className="font-semibold text-zinc-900">Network Status Map — Nigeria</h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            {totalSites > 0
              ? `${totalSites} sites across ${regions.length} regions`
              : "Live network heatmap"}
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Legend */}
          <div className="hidden sm:flex items-center gap-3 text-xs text-zinc-600">
            {[["operational", "Operational"], ["degraded", "Degraded"], ["down", "Down"]].map(
              ([key, label]) => (
                <span key={key} className="flex items-center gap-1.5">
                  <span className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[key]}`} />
                  {label}
                </span>
              )
            )}
          </div>

          {/* Status counters */}
          {regions.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              {operational > 0 && (
                <span className="bg-green-50 text-green-700 border border-green-200 rounded-full px-2 py-0.5 font-medium">
                  {operational} OK
                </span>
              )}
              {degraded > 0 && (
                <span className="bg-amber-50 text-amber-700 border border-amber-200 rounded-full px-2 py-0.5 font-medium">
                  {degraded} Degraded
                </span>
              )}
              {down > 0 && (
                <span className="bg-red-50 text-red-700 border border-red-200 rounded-full px-2 py-0.5 font-medium">
                  {down} Down
                </span>
              )}
            </div>
          )}

          <button
            onClick={load}
            disabled={loading}
            className="text-xs text-zinc-400 hover:text-zinc-700 transition-colors disabled:opacity-50"
            title="Refresh"
          >
            {loading ? "…" : "↻"}
          </button>
        </div>
      </div>

      {/* Map area */}
      <div className="relative flex-1" style={{ minHeight: 420 }}>
        {error ? (
          <div className="absolute inset-0 flex items-center justify-center text-red-500 text-sm p-6 text-center">
            <div>
              <p className="font-medium">Failed to load map data</p>
              <p className="text-xs text-zinc-400 mt-1">{error}</p>
              <button
                onClick={load}
                className="mt-3 text-xs text-zinc-500 underline hover:text-zinc-700"
              >
                Try again
              </button>
            </div>
          </div>
        ) : (
          <LeafletMap regions={regions} />
        )}
      </div>

      {/* Footer */}
      {lastUpdated && (
        <div className="px-5 py-2 border-t border-zinc-100 text-xs text-zinc-400 flex-shrink-0">
          Updated {lastUpdated.toLocaleTimeString()} · hover a circle for details
        </div>
      )}
    </div>
  );
}