/**
 * app/(auth)/reset-password/page.tsx
 *
 * Password reset completion page.
 *
 * The user arrives here from a link in their reset email, e.g.:
 *   /reset-password?token=<jwt_reset_token>
 *
 * API:  POST /api/auth/reset-password  (our Next.js proxy route)
 * Flow: read token from URL → user sets new password → redirect to /login
 *
 * UX rules:
 * - Show an error immediately if no token is present in the URL.
 * - Loading spinner on the submit button while request is in flight.
 * - Success / error messages auto-dismiss after 3 seconds.
 * - On success, redirect to /login after a short delay so the user sees
 *   the confirmation message.
 */

"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import StatusMessage from "@/components/ui/StatusMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

// ─── Inner form (needs Suspense because of useSearchParams) ───────────────────

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const token = searchParams.get("token");

  const [password, setPassword]   = useState("");
  const [confirm, setConfirm]     = useState("");
  const [loading, setLoading]     = useState(false);
  const [message, setMessage]     = useState<{ type: "success" | "error"; text: string } | null>(null);

  /** Show a status banner that auto-dismisses after 3 seconds */
  const showMessage = (type: "success" | "error", text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  // Guard: no token in the URL means the link is broken or already used
  useEffect(() => {
    if (!token) {
      setMessage({
        type: "error",
        text: "This reset link is invalid or has expired. Please request a new one.",
      });
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading || !token) return;

    if (!password || !confirm) {
      showMessage("error", "Please fill in both password fields.");
      return;
    }

    if (password.length < 8) {
      showMessage("error", "Password must be at least 8 characters.");
      return;
    }

    if (password !== confirm) {
      showMessage("error", "Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });

      const data = await res.json();

      if (!res.ok) {
        showMessage("error", data.error || "Failed to reset password. Please try again.");
        return;
      }

      showMessage("success", "Password reset successfully. Redirecting to sign in…");
      // Redirect to login after a short delay so the user can read the message
      setTimeout(() => router.push("/login"), 2000);
    } catch {
      showMessage("error", "Network error. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card p-9 rounded-2xl">
      {/* Icon */}
      <div className="size-12 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center mb-5">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none" className="text-brand-600">
          <rect x="6" y="10" width="10" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 10V7a3 3 0 1 1 6 0v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>

      <h1 className="text-[22px] font-bold text-gray-900 tracking-[-0.025em] mb-2 leading-[1.2]">
        Set a new password
      </h1>
      <p className="text-sm text-gray-400 leading-[1.6] mb-6">
        Choose a strong password with at least 8 characters.
      </p>

      {/* Status message */}
      {message && (
        <div className="mb-5">
          <StatusMessage type={message.type} text={message.text} />
        </div>
      )}

      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <div>
          <label className="label-base" htmlFor="new-password">New password</label>
          <input
            id="new-password"
            type="password"
            className="input-base"
            placeholder="At least 8 characters"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading || !token}
          />
        </div>

        <div>
          <label className="label-base" htmlFor="confirm-password">Confirm password</label>
          <input
            id="confirm-password"
            type="password"
            className="input-base"
            placeholder="Repeat your password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={loading || !token}
          />
        </div>

        <button
          type="submit"
          disabled={loading || !token}
          className="btn-primary w-full py-3 text-sm flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <LoadingSpinner size={15} />
              Resetting…
            </>
          ) : (
            "Reset password"
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
  );
}

// ─── Page wrapper ─────────────────────────────────────────────────────────────

export default function ResetPasswordPage() {
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

        {/* useSearchParams requires Suspense */}
        <Suspense fallback={<div className="card p-9 rounded-2xl text-sm text-gray-400">Loading…</div>}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
