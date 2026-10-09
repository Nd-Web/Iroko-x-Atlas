/**
 * app/(app)/layout.tsx
 *
 * Shared layout for every authenticated page. The route group adds no URL
 * segment; it exists so the sidebar/topbar mount once and persist across
 * navigation instead of remounting with each page.
 */

import PersistentShell from "@/components/layout/PersistentShell";
import AppProviders from "@/providers/AppProviders";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppProviders><PersistentShell>{children}</PersistentShell></AppProviders>;
}
