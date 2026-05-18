/**
 * app/(auth)/forgot-password/page.tsx
 *
 * Password reset request page.
 *
 * API:  POST /api/auth/forgot-password  (our Next.js proxy route)
 * Flow: user submits email → AtlasCore sends reset link → show success message
 *
 * AtlasCore always returns 200 regardless of whether the email exists,
 * to prevent email enumeration attacks. We surface the same success message
 * in both cases.
 *
 * UX rules:
 * - Loading spinner on button while request is in flight.
 * - Success / error messages auto-dismiss after 3 seconds.
 */

"use client";

import { useState } from "react";
import Link from "next/link";
import StatusMessage from "@/components/ui/StatusMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

export default function ForgotPasswordPage() {
  const [email, setEmail]   = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  /** Show a status banner that automatically clears after 3 seconds */
  const showMessage = (type: "success" | "error", text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;

    if (!email) {
      showMessage("error", "Please enter your work email address.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      const data = await res.json();

      if (!res.ok) {
        showMessage("error", data.error || "Something went wrong. Please try again.");
        return;
      }

      showMessage(
        "success",
        "If this email is registered, a reset link has been sent. Check your inbox."
      );
      setEmail(""); // Clear the field after success
    } catch {
      showMessage("error", "Network error. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-page flex items-center justify-center p-6">
      <div className="w-full max-w-[420px]">
        {/* Logo */}
        <div className="flex items-center gap-3 justify-center mb-12">
          <div className="size-10 bg-[#4A55D4] rounded-[10px] flex items-center justify-center shadow-[0_4px_12px_rgba(74,85,212,0.3)] shrink-0">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <path d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round" fill="none" />
              <circle cx="11" cy="10.5" r="2.25" fill="white" />
            </svg>
          </div>
          <div>
            <div className="text-[17px] font-bold text-gray-900 tracking-[-0.01em] leading-[1.2]">Iroko AI</div>
            <div className="text-[11px] text-gray-400 leading-none">MTN Nigeria</div>
          </div>
        </div>

        {/* Card */}
        <div className="card p-9 rounded-2xl">
          {/* Icon */}
          <div className="size-12 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center mb-5">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="text-brand-600">
              <rect x="2" y="6" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M2 9l9 5 9-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>

          <h1 className="text-[22px] font-bold text-gray-900 tracking-[-0.025em] mb-2 leading-[1.2]">
            Reset your password
          </h1>
          <p className="text-sm text-gray-400 leading-[1.6] mb-6">
            Enter your work email and we'll send a reset link if the account exists in our system.
          </p>

          {/* Status message */}
          {message && (
            <div className="mb-5">
              <StatusMessage type={message.type} text={message.text} />
            </div>
          )}

          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div>
              <label className="label-base" htmlFor="reset-email">Work email</label>
              <input
                id="reset-email"
                type="email"
                className="input-base"
                placeholder="you@mtn.ng"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 text-sm flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <LoadingSpinner size={15} />
                  Sending…
                </>
              ) : (
                "Send reset link"
              )}
            </button>
          </form>

          <div className="text-center mt-6">
            <Link
              href="/login"
              className="text-[13px] text-brand-600 no-underline font-medium inline-flex items-center gap-1.5"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
