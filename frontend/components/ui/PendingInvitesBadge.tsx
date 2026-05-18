"use client";

import { useInvitations } from "@/app/user-management/_hooks/useInvitations";
import type { Invitation } from "@/lib/types";

function isPending(inv: Invitation): boolean {
  return !inv.used_at && new Date(inv.expires_at) >= new Date();
}

export function PendingInvitesBadge() {
  const { data } = useInvitations();
  const count = (data?.invitations ?? []).filter(isPending).length;
  if (!count) return null;
  return (
    <span className="bg-warning-500 text-white rounded-full text-[11px] font-bold px-1.5 py-px ml-1">
      {count}
    </span>
  );
}
