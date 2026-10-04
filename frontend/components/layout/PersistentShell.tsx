"use client";

/**
 * components/layout/PersistentShell.tsx
 *
 * The authenticated app frame (sidebar + topbar), mounted ONCE by
 * app/(app)/layout.tsx so it survives client-side navigation. Previously
 * every page rendered its own AppShell, which remounted the whole frame on
 * each click and made navigation flicker.
 *
 * Pages still render <AppShell title=… actions=…>; inside this shell AppShell
 * only publishes its title/subtitle here and portals its actions into the
 * topbar slot, then renders the page's <main>.
 */

import { createContext, useContext, useState } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import Topbar from "@/components/layout/Topbar";

interface ShellHeader {
  title: string;
  subtitle?: string;
}

interface ShellContextValue {
  setHeader: (header: ShellHeader) => void;
  actionsSlot: HTMLDivElement | null;
}

const ShellContext = createContext<ShellContextValue | null>(null);

/** Returns the persistent shell, or null when rendered outside it. */
export function useShell() {
  return useContext(ShellContext);
}

export default function PersistentShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // The mobile sidebar is open for the path it was opened on, so it closes
  // automatically when the route changes.
  const [openOnPath, setOpenOnPath] = useState<string | null>(null);
  const sidebarOpen = openOnPath === pathname;
  const setSidebarOpen = (open: boolean) => setOpenOnPath(open ? pathname : null);
  const [header, setHeader] = useState<ShellHeader>({ title: "" });
  const [actionsSlot, setActionsSlot] = useState<HTMLDivElement | null>(null);

  return (
    <ShellContext.Provider value={{ setHeader, actionsSlot }}>
      {/*
       * h-screen + overflow-hidden on the outer shell locks the entire layout
       * to the viewport. Each page's <main> (rendered by AppShell) owns the
       * scroll inside the content column.
       */}
      <div className="flex h-screen overflow-hidden bg-surface-page">
        {/* Keyboard users can jump straight past the sidebar/topbar */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-2 focus:rounded-lg focus:bg-surface-card focus:text-brand-700 focus:shadow-md focus:text-sm focus:font-semibold"
        >
          Skip to main content
        </a>

        {/* Mobile Sidebar Overlay */}
        <div
          className={`sidebar-overlay lg:hidden ${sidebarOpen ? "active" : ""}`}
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />

        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        {/* Content column — lg:pl-[240px] offsets the fixed sidebar */}
        <div className="flex flex-col flex-1 min-w-0 lg:pl-[240px] overflow-hidden">
          <Topbar
            title={header.title}
            subtitle={header.subtitle}
            actionsSlotRef={setActionsSlot}
            onMenuClick={() => setSidebarOpen(true)}
          />
          {children}
        </div>
      </div>
    </ShellContext.Provider>
  );
}
