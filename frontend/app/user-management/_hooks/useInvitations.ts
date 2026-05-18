"use client";

import { useQuery } from "@tanstack/react-query";
import { invitationsService } from "@/services/invitations.service";

export function useInvitations() {
  return useQuery({
    queryKey: ["invitations"],
    queryFn: invitationsService.listInvitations,
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}
