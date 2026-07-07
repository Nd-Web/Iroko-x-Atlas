/**
 * app/request-demo/layout.tsx
 *
 * Server layout providing per-page metadata for the client-rendered
 * /request-demo form page (client components cannot export metadata).
 */

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Request a demo",
  description:
    "Book a live walkthrough of Iroko AI — enterprise document intelligence and real-time workflow analytics for large organisations, plus the fintech/MFB compliance configuration.",
};

export default function RequestDemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
