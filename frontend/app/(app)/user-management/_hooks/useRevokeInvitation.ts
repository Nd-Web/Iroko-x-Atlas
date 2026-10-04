"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { invitationsService } from "@/services/invitations.service";

export function useRevokeInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: string) => invitationsService.revokeInvitation(inviteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invitations"] });
    },
  });
}
