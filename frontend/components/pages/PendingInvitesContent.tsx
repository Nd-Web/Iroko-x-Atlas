"use client";

import { useState, useEffect } from "react";
import StatusMessage from "@/components/ui/StatusMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import type { Invitation } from "@/lib/types";
import { useInvitations } from "@/app/user-management/_hooks/useInvitations";
import { useRevokeInvitation } from "@/app/user-management/_hooks/useRevokeInvitation";
import { useSendInvite } from "@/app/user-management/_hooks/useSendInvite";

type InviteStatus = "pending" | "accepted" | "expired";

const STATUS_STYLES: Record<InviteStatus, { color: string; bg: string; label: string }> = {
  pending:  { color: "var(--color-warning-700)", bg: "var(--color-warning-50)",  label: "Pending"  },
  accepted: { color: "var(--color-success-700)", bg: "var(--color-success-50)",  label: "Accepted" },
  expired:  { color: "var(--color-danger-700)",  bg: "var(--color-danger-50)",   label: "Expired"  },
};

const COL = "2fr 1.5fr 1fr 1fr 100px 130px";

function getStatus(inv: Invitation): InviteStatus {
  if (inv.used_at) return "accepted";
  if (new Date(inv.expires_at) < new Date()) return "expired";
  return "pending";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function PendingInvitesContent() {
  const { data, isLoading, isError, refetch } = useInvitations();
  const revoke = useRevokeInvitation();
  const sendInvite = useSendInvite();

  const [revokeTarget, setRevokeTarget] = useState<Invitation | null>(null);
  const [resentIds, setResentIds]   = useState<Set<string>>(new Set());
  const [sendingIds, setSendingIds] = useState<Set<string>>(new Set());

  const invitations = data?.invitations ?? [];

  useEffect(() => {
    if (!revokeTarget) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setRevokeTarget(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [revokeTarget]);

  const handleRevoke = () => {
    if (!revokeTarget) return;
    revoke.mutate(revokeTarget.id, {
      onSuccess: () => setRevokeTarget(null),
    });
  };

  const handleResend = async (inv: Invitation) => {
    if (sendingIds.has(inv.id)) return;
    setSendingIds((prev) => new Set(prev).add(inv.id));
    try {
      await sendInvite.mutateAsync({
        email: inv.email,
        role: inv.role,
        department: inv.department,
      });
      setResentIds((prev) => new Set(prev).add(inv.id));
      setTimeout(() => {
        setResentIds((prev) => { const n = new Set(prev); n.delete(inv.id); return n; });
      }, 2500);
    } catch {
      // Silently ignore — button returns to normal state
    } finally {
      setSendingIds((prev) => { const n = new Set(prev); n.delete(inv.id); return n; });
    }
  };

  if (isLoading) {
    return (
      <div className="card overflow-hidden">
        <div className="flex items-center justify-center py-16 gap-3 text-gray-400">
          <LoadingSpinner size={20} />
          <span className="text-sm">Loading invitations…</span>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm text-danger-700 mb-3">Failed to load invitations.</p>
        <button className="btn-secondary text-sm" onClick={() => refetch()}>Retry</button>
      </div>
    );
  }

  return (
    <>
      <div className="card overflow-hidden">
        <div
          className="grid py-[10px] px-5 bg-gray-50 border-b border-border-default gap-3"
          style={{ gridTemplateColumns: COL }}
        >
          {["Invitee", "Role", "Sent", "Expires", "Status", ""].map((h) => (
            <span key={h} className="text-[11px] font-semibold text-gray-400 uppercase tracking-[0.06em]">
              {h}
            </span>
          ))}
        </div>

        {invitations.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">
            No invitations found.
          </div>
        ) : (
          invitations.map((inv) => {
            const status    = getStatus(inv);
            const s         = STATUS_STYLES[status];
            const isResent  = resentIds.has(inv.id);
            const isSending = sendingIds.has(inv.id);

            return (
              <div
                key={inv.id}
                className="grid items-center py-[14px] px-5 gap-3 border-b border-border-default hover:bg-gray-50 transition-colors"
                style={{ gridTemplateColumns: COL }}
              >
                <div>
                  <div className="text-sm font-medium text-gray-800 truncate">{inv.email}</div>
                  <div className="text-xs text-gray-400">{inv.invited_by}</div>
                </div>
                <span className="text-[13px] text-gray-500 capitalize">{inv.role.replace(/_/g, " ")}</span>
                <div>
                  <div className="text-[13px] text-gray-600">{formatDate(inv.created_at)}</div>
                  <div className="text-xs text-gray-400">by {inv.invited_by.split(" ")[0]}</div>
                </div>
                <span className="text-[13px] text-gray-500">{formatDate(inv.expires_at)}</span>
                <span
                  className="text-[11px] font-semibold px-[10px] py-[2px] rounded-full w-fit"
                  style={{ color: s.color, background: s.bg }}
                >
                  {s.label}
                </span>
                <div className="flex gap-1.5 justify-end">
                  {status === "pending" && (
                    <>
                      <button
                        className={`btn-secondary py-1 px-[10px] text-xs flex items-center gap-1.5 ${isResent ? "text-success-700" : ""}`}
                        onClick={() => handleResend(inv)}
                        disabled={isSending}
                      >
                        {isSending ? <LoadingSpinner size={11} /> : isResent ? "Resent ✓" : "Resend"}
                      </button>
                      <button
                        className="btn-secondary py-1 px-[10px] text-xs text-danger-700"
                        onClick={() => setRevokeTarget(inv)}
                      >
                        Revoke
                      </button>
                    </>
                  )}
                  {status === "expired" && (
                    <button
                      className={`${isResent ? "btn-secondary text-success-700" : "btn-primary"} py-1 px-[10px] text-xs flex items-center gap-1.5`}
                      onClick={() => handleResend(inv)}
                      disabled={isSending}
                    >
                      {isSending ? <LoadingSpinner size={11} /> : isResent ? "Sent ✓" : "Resend"}
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {revokeTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-6"
          onClick={() => !revoke.isPending && setRevokeTarget(null)}
        >
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "400px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">Revoke invite</h2>
              <button
                onClick={() => !revoke.isPending && setRevokeTarget(null)}
                className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            </div>

            <div className="px-5 py-5 flex flex-col gap-4">
              <p className="text-[13px] text-gray-600 leading-[1.5] m-0">
                Are you sure you want to revoke the invite for{" "}
                <span className="font-semibold text-gray-900">{revokeTarget.email}</span>?
                This link will immediately be invalidated and can no longer be used.
              </p>
              {revoke.isError && (
                <StatusMessage
                  type="error"
                  text={(revoke.error as Error)?.message ?? "Failed to revoke invitation."}
                />
              )}
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button
                className="btn-secondary"
                onClick={() => setRevokeTarget(null)}
                disabled={revoke.isPending}
              >
                Cancel
              </button>
              <button
                className="bg-danger-600 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-danger-700 transition-colors flex items-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
                onClick={handleRevoke}
                disabled={revoke.isPending}
              >
                {revoke.isPending ? (
                  <>
                    <LoadingSpinner size={13} />
                    Revoking…
                  </>
                ) : (
                  "Revoke invite"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
