/**
 * hooks/useSearch.ts
 *
 * React hook for debounced document search.
 *
 * - Manages query string, results array, loading and error states.
 * - Debounces search calls by 300ms to avoid hammering the backend.
 * - Calls POST /api/documents/search via the client-side api helper.
 */

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import type { DocumentSearchResult, DocumentSearchResponse } from "@/lib/types";

// ── Types ────────────────────────────────────────────────────────────────────

export interface UseSearchReturn {
  query: string;
  results: DocumentSearchResult[];
  isSearching: boolean;
  error: string | null;
  search: (q: string) => void;
  setQuery: (q: string) => void;
}

// ── Constants ────────────────────────────────────────────────────────────────

const DEBOUNCE_MS = 300;

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useSearch(initialQuery = ""): UseSearchReturn {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<DocumentSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  /**
   * Execute the search after the debounce window.
   * Cancels any in-flight request before starting a new one.
   */
  const executeSearch = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) {
      setResults([]);
      setIsSearching(false);
      return;
    }

    // Cancel previous in-flight request
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setIsSearching(true);
    setError(null);

    try {
      const data = await apiFetch<DocumentSearchResponse>(
        "/api/documents/search",
        {
          method: "POST",
          body: JSON.stringify({ q: trimmed, top: 20 }),
          signal: abortRef.current.signal,
        },
      );
      setResults(data.results ?? []);
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") return;
      const message =
        err instanceof Error ? err.message : "Search failed.";
      setError(message);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  /**
   * Public search function — debounces by 300ms.
   */
  const search = useCallback(
    (q: string) => {
      setQuery(q);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => executeSearch(q), DEBOUNCE_MS);
    },
    [executeSearch],
  );

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      abortRef.current?.abort();
    };
  }, []);

  // If initialQuery was provided, trigger an immediate search
  useEffect(() => {
    if (initialQuery.trim()) {
      executeSearch(initialQuery);
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { query, results, isSearching, error, search, setQuery };
}

export default useSearch;
