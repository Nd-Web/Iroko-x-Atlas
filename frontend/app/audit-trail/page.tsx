import AuditTrailContent from "@/components/pages/AuditTrailContent";
import AppShell from "@/components/layout/AppShell";

export const metadata = { title: "Audit Trail" };

export default function AuditTrailPage() {
  return (
    <AppShell title="Audit trail" subtitle="Powered by Atlas · Cryptographically-chained · NDPA-grade">
      <AuditTrailContent />
    </AppShell>
  );
}
