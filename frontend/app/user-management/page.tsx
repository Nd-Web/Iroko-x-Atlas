import UserManagementContent from "@/components/pages/UserManagementContent";
import AppShell from "@/components/layout/AppShell";
import Link from "next/link";
import { PendingInvitesBadge } from "@/components/ui/PendingInvitesBadge";

export const metadata = { title: "User management" };

export default function UserManagementPage() {
  const actions = (
    <div className="flex gap-2">
      <Link
        href="/user-management/invites"
        className="btn-secondary"
        style={{ padding: "8px 14px", fontSize: "13px" }}
      >
        Pending invites
        <PendingInvitesBadge />
      </Link>
      <Link
        href="/user-management/invite"
        className="btn-primary"
        style={{ padding: "8px 14px", fontSize: "13px" }}
      >
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
          <path d="M7.5 2v11M2 7.5h11" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        Invite user
      </Link>
    </div>
  );

  return (
    <AppShell title="User management" subtitle="Invite-only access · Super admin controls" actions={actions}>
      <UserManagementContent />
    </AppShell>
  );
}
