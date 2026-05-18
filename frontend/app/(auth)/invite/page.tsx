/**
 * app/(auth)/invite/page.tsx
 *
 * Redirect handler for the legacy query-string invite URL format:
 *   /invite?token=<token>
 *
 * AtlasCore sends email links as /invite/<token> (path parameter), which is
 * handled by app/(auth)/invite/[token]/page.tsx.
 *
 * This page exists as a fallback — if someone arrives with ?token=xxx in the
 * query string, they are immediately redirected to the canonical path-based URL.
 * If there is no token at all, we show an error.
 */

"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

function InviteRedirector() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");

  useEffect(() => {
    if (token) {
      // Redirect to the canonical path-based invite URL
      router.replace(`/invite/${token}`);
    }
    // If no token, stay on this page and show the error below
  }, [token, router]);

  // If there's a token, we're redirecting — show a brief spinner
  if (token) {
    return (
      <div className="min-h-screen bg-surface-page flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <LoadingSpinner size={24} />
          <span className="text-sm">Redirecting…</span>
        </div>
      </div>
    );
  }

  // No token in query string at all
  return (
    <div className="min-h-screen bg-surface-page flex items-center justify-center p-6">
      <div className="w-full max-w-[400px] text-center">
        <div className="size-14 mx-auto bg-danger-50 border border-danger-100 rounded-full flex items-center justify-center mb-4">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            className="text-danger-600"
          >
            <circle
              cx="12"
              cy="12"
              r="9"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <path
              d="M12 8v5M12 16h.01"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <h2 className="text-lg font-bold text-gray-900 mb-2">
          No invitation found
        </h2>
        <p className="text-sm text-gray-400 leading-relaxed mb-6">
          This link appears to be incomplete. Please use the full link from your
          invitation email, or contact your administrator.
        </p>
        <a
          href="mailto:iroko-admin@mtn.ng"
          className="btn-primary py-2.5 px-5 text-sm no-underline"
        >
          Contact admin
        </a>
      </div>
    </div>
  );
}

export default function InvitePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-surface-page flex items-center justify-center">
          <LoadingSpinner size={24} />
        </div>
      }
    >
      <InviteRedirector />
    </Suspense>
  );
}
