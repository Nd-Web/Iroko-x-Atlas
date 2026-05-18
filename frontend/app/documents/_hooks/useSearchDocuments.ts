"use client";

import { useQuery } from "@tanstack/react-query";
import { documentsService } from "@/services/documents.service";
import type { DocumentSearchRequest } from "@/lib/types";

type Options = DocumentSearchRequest & { enabled?: boolean };

export function useSearchDocuments({ enabled = true, ...params }: Options) {
  return useQuery({
    queryKey: ["documents", "search", params],
    queryFn: () => documentsService.searchDocuments(params),
    staleTime: 60_000,
    enabled: enabled && params.q.length > 0,
  });
}
