"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import Topbar from "@/components/layout/Topbar";

interface AppShellProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export default function AppShell({ children, title, subtitle, actions }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  // Close sidebar when route changes on mobile
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  return (
    /*
     * h-screen + overflow-hidden on the outer shell locks the entire layout
     * to the viewport. The content column (right of the fixed sidebar) fills
     * the remaining space with its own overflow-y-auto so normal pages still
     * scroll when their content exceeds the visible area. The chat page
     * controls its own internal scroll and never triggers this outer scroll.
     */
    <div className="flex h-screen overflow-hidden bg-surface-page">
      {/* Mobile Sidebar Overlay */}
      <div
        className={`sidebar-overlay lg:hidden ${sidebarOpen ? 'active' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Content column — lg:pl-[240px] offsets the fixed sidebar */}
      <div className="flex flex-col flex-1 min-w-0 lg:pl-[240px] overflow-hidden">
        <Topbar
          title={title}
          subtitle={subtitle}
          actions={actions}
          onMenuClick={() => setSidebarOpen(true)}
        />

        {/* overflow-y-auto lets normal pages scroll; chat page fills this exactly via flex-1 min-h-0 */}
        <main className="flex-1 p-4 md:p-6 lg:p-7 flex flex-col gap-6 max-w-[1600px] mx-auto w-full overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
