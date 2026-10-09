"use client";

import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import SessionExpiredToast from "@/components/ui/SessionExpiredToast";
import { QueryProvider } from "./QueryProvider";

/** App-only state: marketing and booking don't need a session or query cache. */
export default function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <Toaster position="bottom-right" toastOptions={{ style: {
        background: "#1A1A1F",
        border: "1px solid rgba(255,255,255,0.08)",
        color: "#EBEBEF",
      } }} />
      <AuthProvider>
        {children}
        <SessionExpiredToast />
      </AuthProvider>
    </QueryProvider>
  );
}
