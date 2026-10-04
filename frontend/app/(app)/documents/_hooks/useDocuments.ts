"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import { documentsService, type DocumentListParams } from "@/services/documents.service";

type Options = DocumentListParams & { enabled?: boolean };

export function useDocuments({ enabled = true, ...params }: Options = {}) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["documents", "list", user?.id, params],
    queryFn: () => documentsService.listDocuments(params),
    staleTime: 30_000,
    refetchInterval: (query) => query.state.data?.documents.some(
      doc => ["pending", "processing"].includes(doc.status)
    ) ? 5000 : false,
    enabled: enabled && Boolean(user),
  });
}
