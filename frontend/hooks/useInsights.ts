/**
 * hooks/useInsights.ts
 *
 * Migrated to @tanstack/react-query.
 * - Automatic background refetching every 60s (refetchInterval)
 * - Deduplication: multiple components sharing this hook hit the network once
 * - Stale-while-revalidate built-in
 * - No manual setInterval / clearInterval needed
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

export interface Insight {
  id: string;
  title: string;
  summary: string;
  severity: "critical" | "warning" | "info";
  alert_type: string;
  status: string;
  created_at: string;
}

interface AlertsResponse {
  alerts: Insight[];
  total: number;
  critical_count: number;
  warning_count: number;
}

export interface UseInsightsReturn {
  insights: Insight[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useInsights(): UseInsightsReturn {
  const { data, isLoading, error, refetch } = useQuery<AlertsResponse>({
    queryKey: ["insights"],
    queryFn: () => apiFetch<AlertsResponse>("/api/alerts?status=all&limit=50"),
    refetchInterval: 60_000,       // poll every 60s
    staleTime: 30_000,             // treat data as fresh for 30s
    refetchOnWindowFocus: true,    // refresh when user returns to tab
  });

  return {
    insights: data?.alerts ?? [],
    isLoading,
    error: error ? (error instanceof Error ? error.message : "Failed to fetch insights.") : null,
    refetch,
  };
}

export default useInsights;
