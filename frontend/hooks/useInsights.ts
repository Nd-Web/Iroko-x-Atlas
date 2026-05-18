/**
 * hooks/useInsights.ts
 *
 * React hook for fetching insights / active alerts from the backend.
 *
 * - Fetches GET /api/alerts on mount and every 60 seconds.
 * - Returns { insights, isLoading, error, refetch }.
 * - On error sets error state without throwing.
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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

// ── Polling interval ─────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 60_000; // 60 seconds

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useInsights(): UseInsightsReturn {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchInsights = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await apiFetch<AlertsResponse>("/api/alerts?status=all&limit=50");
      setInsights(data.alerts ?? []);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to fetch insights.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    fetchInsights();

    intervalRef.current = setInterval(fetchInsights, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchInsights]);

  const refetch = useCallback(() => {
    fetchInsights();
  }, [fetchInsights]);

  return { insights, isLoading, error, refetch };
}

export default useInsights;
