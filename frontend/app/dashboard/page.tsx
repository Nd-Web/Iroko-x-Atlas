"use client";
/**
 * app/dashboard/page.tsx
 * 
 * Replaced with Iroko AI Web Intelligence Dashboard.
 * WebIntelDashboard manages its own layout/header/tabs.
 * We still render Sidebar + Topbar via the manual shell below
 * to avoid AppShell's padded <main> conflicting with WebIntelDashboard's
 * own px-8 header and tab layout.
 */

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import Topbar from "@/components/layout/Topbar";
import WebIntelDashboard from "@/components/WebIntelDashboard";

export default function DashboardPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  return (
    <div className="flex h-screen overflow-hidden bg-surface-page">
      {/* Mobile sidebar overlay */}
      <div
        className={`sidebar-overlay lg:hidden ${sidebarOpen ? "active" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content column */}
      <div className="flex flex-col flex-1 min-w-0 lg:pl-[240px] overflow-hidden">
        <Topbar
          title="Web Intelligence"
          subtitle="Live signals · Document &amp; ops intelligence · Audit trail"
          onMenuClick={() => setSidebarOpen(true)}
        />

        {/* WebIntelDashboard controls its own scroll and padding */}
        <div className="flex-1 overflow-y-auto">
          <WebIntelDashboard />
        </div>
      </div>
    </div>
  );
}