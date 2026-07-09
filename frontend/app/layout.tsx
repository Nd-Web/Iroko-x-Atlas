/**
 * app/layout.tsx
 *
 * Root layout — wraps every page with the AuthProvider so that all client
 * components can call useAuth() to access the current user.
 */

import type { Metadata } from "next";
import { DM_Sans, DM_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import SessionExpiredToast from "@/components/ui/SessionExpiredToast";
import { QueryProvider } from "@/providers/QueryProvider";
import { Toaster } from "sonner";

// Self-hosted via next/font — no runtime request to fonts.googleapis.com,
// zero layout shift (size-adjusted fallbacks generated at build time).
const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-dm-sans",
  display: "swap",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-dm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://irokoai.site"),
  title: {
    default: "Iroko AI · Enterprise Document Intelligence & Real-Time Workflow Analytics",
    template: "%s · Iroko AI",
  },
  description:
    "Iroko AI turns your organisation's scattered documents into real-time answers and insight — five AI agents that ingest, understand and analyse enterprise documents, with plain-language Q&A and live workflow analytics. Also available configured for fintech/MFB regulatory compliance (CBN/SEC).",
  keywords: [
    // Primary cluster — enterprise document intelligence
    "enterprise document intelligence",
    "AI workflow analytics",
    "real-time document insights",
    "multi-agent AI Nigeria",
    "enterprise AI document search",
    // Secondary cluster — fintech/regulatory compliance (retained)
    "CBN compliance software",
    "SEC Nigeria compliance",
    "fintech regulatory compliance Nigeria",
    "microfinance bank compliance",
    "AML CFT monitoring",
  ],
  openGraph: {
    type: "website",
    siteName: "Iroko AI",
    title: "Iroko AI · Enterprise Document Intelligence",
    description:
      "Turn scattered documents into real-time answers. Five AI agents ingest, understand and analyse your organisation's documents — with cited answers and live workflow analytics.",
    url: "https://irokoai.site",
  },
  twitter: {
    card: "summary",
    title: "Iroko AI · Enterprise Document Intelligence",
    description:
      "Turn scattered documents into real-time answers. Five AI agents ingest, understand and analyse your organisation's documents — with cited answers and live workflow analytics.",
  },
  icons: {
    icon: "/icon.png",
  },
};

// Organization structured data — document intelligence leads; compliance is
// listed as an additional offering (not the primary description).
const ORG_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Iroko AI",
  url: "https://irokoai.site",
  description:
    "Iroko AI is an enterprise document intelligence and real-time workflow analytics platform. Five AI agents ingest, understand and analyse an organisation's documents, answering staff questions in plain language with cited evidence.",
  makesOffer: [
    {
      "@type": "Offer",
      itemOffered: {
        "@type": "Service",
        name: "Enterprise document intelligence & workflow analytics",
        description:
          "Document ingestion, understanding, real-time analytics and contextual Q&A for large organisations.",
      },
    },
    {
      "@type": "Offer",
      itemOffered: {
        "@type": "Service",
        name: "Fintech & MFB regulatory compliance (CBN/SEC)",
        description:
          "The compliance configuration of the engine for Nigerian microfinance banks and fintechs — regulatory monitoring, filings and audit-grade logging.",
      },
    },
  ],
  award: [
    "4th place of 200+ teams — TeKnowledge × Microsoft Agentic AI Hackathon Finale",
    "Best Student Award — YPIT Artificial Future Hackathon",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`${dmSans.variable} ${dmMono.variable}`}>
      <body suppressHydrationWarning>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_JSON_LD) }}
        />
        <QueryProvider>
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: "var(--color-surface-card)",
                border: "1px solid var(--color-border-default)",
                color: "var(--color-gray-700)",
                boxShadow: "var(--shadow-md)",
              },
            }}
          />
          {/* AuthProvider fetches /api/auth/me on mount and makes the user
            object available to every client component via useAuth() */}
          <AuthProvider>
            {children}
            {/* Shown globally whenever the user's session expires mid-use */}
            <SessionExpiredToast />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
