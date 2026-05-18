/**
 * components/ui/SessionExpiredToast.tsx
 *
 * Full-screen overlay toast shown when the user's session expires mid-use.
 *
 * Behaviour:
 * - Appears as a fixed bottom-right toast (desktop) / bottom-center (mobile).
 * - Displays a 5-second countdown, then hard-navigates to /login.
 * - The user can also click "Sign in now" to redirect immediately.
 * - Rendered in app/layout.tsx so it covers every page.
 *
 * Trigger:
 * - Reads `sessionExpired` from AuthContext.
 * - Components that receive a 401 should call `triggerSessionExpiry()`.
 */

"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";

const COUNTDOWN_SECONDS = 5;

export default function SessionExpiredToast() {
  const { sessionExpired } = useAuth();
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);

  // Start the countdown as soon as the toast becomes visible
  useEffect(() => {
    if (!sessionExpired) return;

    // Reset countdown each time the toast shows
    setCountdown(COUNTDOWN_SECONDS);

    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          window.location.href = "/login";
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [sessionExpired]);

  if (!sessionExpired) return null;

  return (
    <>
      {/* Semi-transparent backdrop so the user knows the page is locked */}
      <div className="fixed inset-0 z-[9998] bg-black/10 backdrop-blur-[1px]" />

      {/* Toast card */}
      <div
        role="alertdialog"
        aria-live="assertive"
        className="fixed bottom-5 right-5 z-[9999] w-[calc(100vw-40px)] max-w-[360px] bg-white border border-border-default rounded-xl shadow-xl overflow-hidden"
      >
        {/* Animated progress bar — drains over COUNTDOWN_SECONDS */}
        <div className="h-[3px] bg-gray-100">
          <div
            className="h-full bg-warning-500 transition-none"
            style={{
              width: `${(countdown / COUNTDOWN_SECONDS) * 100}%`,
              transition: "width 1s linear",
            }}
          />
        </div>

        <div className="px-5 py-4 flex flex-col gap-3">
          {/* Header row */}
          <div className="flex items-start gap-3">
            {/* Warning icon */}
            <div className="size-9 rounded-lg bg-warning-50 border border-warning-100 flex items-center justify-center shrink-0 mt-[1px]">
              <svg width="17" height="17" viewBox="0 0 17 17" fill="none" className="text-warning-600">
                <path
                  d="M8.5 2L1.5 14h14L8.5 2Z"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinejoin="round"
                />
                <path
                  d="M8.5 7v3.5M8.5 12.5h.01"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                />
              </svg>
            </div>

            <div className="flex-1 min-w-0">
              <div className="text-[13.5px] font-semibold text-gray-900 leading-[1.3]">
                Your session has expired
              </div>
              <p className="text-[12.5px] text-gray-400 leading-[1.5] mt-[3px] m-0">
                You'll be redirected to the sign-in page in{" "}
                <span className="font-semibold text-warning-700">{countdown}s</span>.
              </p>
            </div>
          </div>

          {/* Action button */}
          <button
            onClick={() => { window.location.href = "/login"; }}
            className="btn-primary w-full py-2.5 text-[13px] font-semibold"
          >
            Sign in now
          </button>
        </div>
      </div>
    </>
  );
}
