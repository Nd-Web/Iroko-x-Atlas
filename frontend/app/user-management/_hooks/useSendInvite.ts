"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { invitationsService } from "@/services/invitations.service";
import type { InviteRequest } from "@/lib/types";

export function useSendInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: InviteRequest) => invitationsService.sendInvite(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invitations"] });
    },
  });
}
