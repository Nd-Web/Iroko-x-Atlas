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
    default: "Iroko AI · MFB & Fintech Regulatory Compliance (CBN/SEC)",
    template: "%s · Iroko AI",
  },
  description:
    "Iroko AI turns your microfinance bank or fintech's scattered documents into real-time CBN/SEC/NDPA compliance answers and insight — five AI agents that ingest, understand and analyse regulatory documents, with plain-language Q&A, AML/CFT monitoring and live workflow analytics. Also available configured for general enterprise document intelligence.",
  keywords: [
    // Primary cluster — fintech/regulatory compliance
    "CBN compliance software",
    "SEC Nigeria compliance",
    "fintech regulatory compliance Nigeria",
    "microfinance bank compliance",
    "AML CFT monitoring",
    // Secondary cluster — enterprise document intelligence (retained)
    "enterprise document intelligence",
    "AI workflow analytics",
    "real-time document insights",
    "multi-agent AI Nigeria",
    "enterprise AI document search",
  ],
  openGraph: {
    type: "website",
    siteName: "Iroko AI",
    title: "Iroko AI · MFB & Fintech Regulatory Compliance",
    description:
      "Turn scattered regulatory documents into real-time CBN/SEC/NDPA compliance answers. Five AI agents ingest, understand and analyse your microfinance bank's documents — with cited answers and live compliance analytics.",
    url: "https://irokoai.site",
  },
  twitter: {
    card: "summary",
    title: "Iroko AI · MFB & Fintech Regulatory Compliance",
    description:
      "Turn scattered regulatory documents into real-time CBN/SEC/NDPA compliance answers. Five AI agents ingest, understand and analyse your microfinance bank's documents — with cited answers and live compliance analytics.",
  },
  icons: {
    icon: "/icon.png",
  },
};

// Organization structured data — MFB/fintech compliance leads; general
// enterprise document intelligence is listed as an additional offering.
const ORG_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Iroko AI",
  url: "https://irokoai.site",
  description:
    "Iroko AI is a regulatory compliance and document intelligence platform for Nigerian microfinance banks and fintechs. Five AI agents ingest, understand and analyse regulatory documents, answering staff questions in plain language with cited CBN/SEC/NDPA evidence.",
  makesOffer: [
    {
      "@type": "Offer",
      itemOffered: {
        "@type": "Service",
        name: "MFB & fintech regulatory compliance (CBN/SEC)",
        description:
          "Regulatory monitoring, filings, AML/CFT & KYC checks, and audit-grade logging for Nigerian microfinance banks and fintechs.",
      },
    },
    {
      "@type": "Offer",
      itemOffered: {
        "@type": "Service",
        name: "Enterprise document intelligence & workflow analytics",
        description:
          "Document ingestion, understanding, real-time analytics and contextual Q&A for large organisations.",
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
                background: "#1A1A1F",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "#EBEBEF",
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
