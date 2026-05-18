"use client";

import { useQuery } from "@tanstack/react-query";
import { invitationsService } from "@/services/invitations.service";

export function useValidateInviteToken(token: string) {
  return useQuery({
    queryKey: ["invite", "validate", token],
    queryFn: () => invitationsService.validateToken(token),
    enabled: Boolean(token),
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}
