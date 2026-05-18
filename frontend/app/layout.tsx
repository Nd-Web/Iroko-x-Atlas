/**
 * app/layout.tsx
 *
 * Root layout — wraps every page with the AuthProvider so that all client
 * components can call useAuth() to access the current user.
 */

import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import SessionExpiredToast from "@/components/ui/SessionExpiredToast";
import { QueryProvider } from "@/providers/QueryProvider";

export const metadata: Metadata = {
  title: {
    default: "Iroko AI",
    template: "%s · Iroko AI",
  },
  description:
    "Enterprise document intelligence for MTN Nigeria — telecom-domain AI platform for workflow management and real-time analytics.",
  icons: {
    icon: "/icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <QueryProvider>
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
