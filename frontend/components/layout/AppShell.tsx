"use client";

import { useLayoutEffect } from "react";
import { createPortal } from "react-dom";
import PersistentShell, { useShell } from "@/components/layout/PersistentShell";

interface AppShellProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  /** Drop the default padding/max-width — for pages that lay out their own content area. */
  bare?: boolean;
}

/**
 * Per-page frame content. The sidebar/topbar live in PersistentShell
 * (mounted once by app/(app)/layout.tsx); this sets the topbar's title and
 * actions for the current page and renders its scrollable <main>.
 */
export default function AppShell(props: AppShellProps) {
  const shell = useShell();
  const { children, title, subtitle, actions, bare } = props;
  const setHeader = shell?.setHeader;

  useLayoutEffect(() => {
    setHeader?.({ title, subtitle });
  }, [setHeader, title, subtitle]);

  // Rendered outside the (app) route group — provide a shell of its own.
  if (!shell) {
    return (
      <PersistentShell>
        <AppShell {...props} />
      </PersistentShell>
    );
  }

  return (
    <>
      {actions && shell.actionsSlot && createPortal(actions, shell.actionsSlot)}
      {/* overflow-y-auto lets normal pages scroll; chat page fills this exactly via flex-1 min-h-0 */}
      <main
        id="main-content"
        className={
          bare
            ? "flex-1 min-h-0 overflow-y-auto"
            : "flex-1 p-4 md:p-6 lg:p-7 flex flex-col gap-6 max-w-[1600px] mx-auto w-full overflow-y-auto"
        }
      >
        {children}
      </main>
    </>
  );
}
