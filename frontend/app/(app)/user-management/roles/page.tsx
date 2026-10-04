import RolesContent from "@/components/pages/RolesContent";
import AppShell from "@/components/layout/AppShell";

export const metadata = { title: "Roles & Permissions" };

export default function RolesPage() {
  return (
    <AppShell title="Roles & permissions" subtitle="Define ABAC attribute claims and document classification access per role">
      <RolesContent />
    </AppShell>
  );
}
