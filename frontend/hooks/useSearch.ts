/**
 * hooks/useSearch.ts
 *
 * Migrated to @tanstack/react-query + use-debounce.
 * - use-debounce replaces manual setTimeout/clearTimeout
 * - React Query handles loading/error state, caching, and deduplication
 * - Results for the same query are served from cache instantly
 */

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDebounce } from "use-debounce";
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

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useSearch(initialQuery = ""): UseSearchReturn {
  const [query, setQuery] = useState(initialQuery);

  // Debounce the query string — fires 300ms after the user stops typing
  const [debouncedQuery] = useDebounce(query, 300);

  const { data, isFetching, error } = useQuery<DocumentSearchResponse>({
    queryKey: ["document-search", debouncedQuery],
    queryFn: () =>
      apiFetch<DocumentSearchResponse>("/api/documents/search", {
        method: "POST",
        body: JSON.stringify({ q: debouncedQuery.trim(), top: 20 }),
      }),
    // Only run the query when there's something to search
    enabled: debouncedQuery.trim().length > 0,
    // Cache results per query — same query typed again returns instantly
    staleTime: 1000 * 60 * 2,
  });

  const search = (q: string) => setQuery(q);

  return {
    query,
    results: data?.results ?? [],
    isSearching: isFetching,
    error: error ? (error instanceof Error ? error.message : "Search failed.") : null,
    search,
    setQuery,
  };
}

export default useSearch;
