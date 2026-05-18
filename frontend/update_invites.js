const fs = require('fs');

const pendingInvitesCode = `"use client";

import { useState, useEffect } from "react";

const INVITES = [
  {
    id: "i1",
    email: "emeka.obi@mtn.ng",
    name: "Emeka Obi",
    role: "NOC Engineer",
    sentBy: "Adaeze Okonkwo",
    sentAt: "Today, 09:14",
    expires: "May 9, 2026",
    status: "pending",
  },
  {
    id: "i2",
    email: "ngozi.eze@mtn.ng",
    name: "Ngozi Eze",
    role: "Field Engineer",
    sentBy: "Adaeze Okonkwo",
    sentAt: "Yesterday",
    expires: "May 8, 2026",
    status: "pending",
  },
  {
    id: "i3",
    email: "james.taiwo@mtn.ng",
    name: "James Taiwo",
    role: "Finance Analyst",
    sentBy: "Adaeze Okonkwo",
    sentAt: "Apr 28, 2026",
    expires: "May 5, 2026",
    status: "expired",
  },
  {
    id: "i4",
    email: "sarah.ibrahim@mtn.ng",
    name: "Sarah Ibrahim",
    role: "Compliance Officer",
    sentBy: "Adaeze Okonkwo",
    sentAt: "Apr 25, 2026",
    expires: "May 2, 2026",
    status: "accepted",
  },
  {
    id: "i5",
    email: "david.nwachukwu@mtn.ng",
    name: "David Nwachukwu",
    role: "Care Agent",
    sentBy: "Adaeze Okonkwo",
    sentAt: "Apr 22, 2026",
    expires: "Apr 29, 2026",
    status: "revoked",
  },
];

const STATUS = {
  pending: { color: "var(--color-warning-700)", bg: "var(--color-warning-50)", label: "Pending" },
  accepted: { color: "var(--color-success-700)", bg: "var(--color-success-50)", label: "Accepted" },
  expired: { color: "var(--color-danger-700)", bg: "var(--color-danger-50)", label: "Expired" },
  revoked: { color: "var(--color-gray-500)", bg: "var(--color-gray-100)", label: "Revoked" },
};

const COL = "2fr 1.5fr 1fr 1fr 100px 130px";

export default function PendingInvitesContent() {
  const [revokeTarget, setRevokeTarget] = useState<typeof INVITES[0] | null>(null);
  const [resentIds, setResentIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!revokeTarget) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setRevokeTarget(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [revokeTarget]);

  return (
    <>
      <div className="card overflow-hidden">
        <div
          className="grid py-[10px] px-5 bg-gray-50 border-b border-border-default gap-3"
          style={{ gridTemplateColumns: COL }}
        >
          {["Invitee", "Role", "Sent", "Expires", "Status", ""].map((h) => (
            <span
              key={h}
              className="text-[11px] font-semibold text-gray-400 uppercase tracking-[0.06em]"
            >
              {h}
            </span>
          ))}
        </div>

        {INVITES.map((inv) => {
          const s = STATUS[inv.status as keyof typeof STATUS];
          const isResent = resentIds.has(inv.id);
          
          return (
            <div
              key={inv.id}
              className="grid items-center py-[14px] px-5 gap-3 border-b border-border-default hover:bg-gray-50 transition-colors"
              style={{ gridTemplateColumns: COL }}
            >
              <div>
                <div className="text-sm font-medium text-gray-800">{inv.name}</div>
                <div className="text-xs text-gray-400">{inv.email}</div>
              </div>
              <span className="text-[13px] text-gray-500">{inv.role}</span>
              <div>
                <div className="text-[13px] text-gray-600">{inv.sentAt}</div>
                <div className="text-xs text-gray-400">by {inv.sentBy.split(" ")[0]}</div>
              </div>
              <span className="text-[13px] text-gray-500">{inv.expires}</span>
              <span
                className="text-[11px] font-semibold px-[10px] py-[2px] rounded-full w-fit"
                style={{ color: s.color, background: s.bg }}
              >
                {s.label}
              </span>
              <div className="flex gap-1.5 justify-end">
                {inv.status === "pending" && (
                  <>
                    <button 
                      className={\`btn-secondary py-1 px-[10px] text-xs \${isResent ? "text-success-700" : ""}\`}
                      onClick={() => {
                        setResentIds(prev => new Set(prev).add(inv.id));
                        setTimeout(() => {
                          setResentIds(prev => {
                            const next = new Set(prev);
                            next.delete(inv.id);
                            return next;
                          });
                        }, 2500);
                      }}
                    >
                      {isResent ? "Resent ✓" : "Resend"}
                    </button>
                    <button 
                      className="btn-secondary py-1 px-[10px] text-xs text-danger-700"
                      onClick={() => setRevokeTarget(inv)}
                    >
                      Revoke
                    </button>
                  </>
                )}
                {inv.status === "expired" && (
                  <button 
                    className={\`\${isResent ? "btn-secondary text-success-700" : "btn-primary"} py-1 px-[10px] text-xs\`}
                    onClick={() => {
                      setResentIds(prev => new Set(prev).add(inv.id));
                      setTimeout(() => {
                        setResentIds(prev => {
                          const next = new Set(prev);
                          next.delete(inv.id);
                          return next;
                        });
                      }, 2500);
                    }}
                  >
                    {isResent ? "Sent ✓" : "Resend"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {revokeTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setRevokeTarget(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "400px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">Revoke invite</h2>
              <button onClick={() => setRevokeTarget(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="px-5 py-5">
              <p className="text-[13px] text-gray-600 leading-[1.5] m-0">
                Are you sure you want to revoke the invite for <span className="font-semibold text-gray-900">{revokeTarget.email}</span>? This link will immediately invalidate and no longer work.
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setRevokeTarget(null)}>Cancel</button>
              <button 
                className="bg-danger-600 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-danger-700 transition-colors"
                onClick={() => setRevokeTarget(null)}
              >
                Revoke invite
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
`;

fs.writeFileSync("components/pages/PendingInvitesContent.tsx", pendingInvitesCode);
