"use client";

import { useMutation } from "@tanstack/react-query";
import { invitationsService } from "@/services/invitations.service";
import type { AcceptInviteRequest } from "@/lib/types";

export function useAcceptInvite() {
  return useMutation({
    mutationFn: (body: AcceptInviteRequest) => invitationsService.acceptInvite(body),
  });
}
