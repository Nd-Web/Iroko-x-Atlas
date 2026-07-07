/**
 * app/demo/layout.tsx
 *
 * Server layout providing per-page metadata for the client-rendered
 * /demo pitch-deck page (client components cannot export metadata).
 */

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Product demo",
  description:
    "Walk through Iroko AI — five AI agents that turn scattered enterprise documents into real-time answers and workflow analytics, including the fintech/MFB compliance configuration and pricing.",
};

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
