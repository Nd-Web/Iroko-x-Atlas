import PendingInvitesContent from "@/components/pages/PendingInvitesContent";
import AppShell from "@/components/layout/AppShell";
import Link from "next/link";

export const metadata = { title: "Pending invites" };

export default function PendingInvitesPage() {
  return (
    <AppShell
      title="Pending invites"
      subtitle="Track all sent, accepted, and expired invitations"
      actions={
        <Link
          href="/user-management/invite"
          className="btn-primary"
          style={{ padding: "8px 14px", fontSize: "13px" }}
        >
          + New invite
        </Link>
      }
    >
      <PendingInvitesContent />
    </AppShell>
  );
}
