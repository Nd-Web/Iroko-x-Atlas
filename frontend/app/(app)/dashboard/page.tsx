"use client";
/**
 * app/(app)/dashboard/page.tsx
 *
 * Iroko AI Web Intelligence Dashboard.
 * WebIntelDashboard manages its own header/tabs and padding, so the shell's
 * <main> is rendered bare (no default padding).
 */

import AppShell from "@/components/layout/AppShell";
import WebIntelDashboard from "@/components/WebIntelDashboard";

export default function DashboardPage() {
  return (
    <AppShell
      title="Web Intelligence"
      subtitle="Live signals · Document & ops intelligence · Audit trail"
      bare
    >
      <WebIntelDashboard />
    </AppShell>
  );
}
