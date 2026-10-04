/**
 * app/(app)/layout.tsx
 *
 * Shared layout for every authenticated page. The route group adds no URL
 * segment; it exists so the sidebar/topbar mount once and persist across
 * navigation instead of remounting with each page.
 */

import PersistentShell from "@/components/layout/PersistentShell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <PersistentShell>{children}</PersistentShell>;
}
