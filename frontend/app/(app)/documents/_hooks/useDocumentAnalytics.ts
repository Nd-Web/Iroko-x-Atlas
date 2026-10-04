"use client";

import { useQuery } from "@tanstack/react-query";
import { documentsService } from "@/services/documents.service";

export function useDocumentAnalytics(days?: number) {
  return useQuery({
    queryKey: ["documents", "analytics", days],
    queryFn: () => documentsService.getAnalytics(days),
    staleTime: 60_000,
  });
}
