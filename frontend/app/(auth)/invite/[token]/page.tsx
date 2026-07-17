/**
 * app/(auth)/invite/[token]/page.tsx
 *
 * Invite acceptance page — handles the path-parameter URL format that
 * the backend includes in invitation emails:
 *
 *   https://iroko-frontend.azurewebsites.net/invite/<token>
 *
 * Flow:
 * 1. `token` is extracted from the URL path (params.token).
 * 2. On mount, validate via GET /api/auth/invite/[token].
 *    Pre-fill email, role, department, and invited_by from the response.
 * 3. User enters their name and password.
 * 4. On submit, call POST /api/auth/accept-invite.
 *    Success → server sets httpOnly cookie → redirect to /dashboard.
 *
 * UX rules:
 * - Full-page spinner while validating the token.
 * - Clear error state if the token is invalid or expired.
 * - Loading spinner on the submit button while the accept request is in flight.
 * - Error / success messages auto-dismiss after 3 seconds.
 */

"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import StatusMessage from "@/components/ui/StatusMessage";
import Spinner from "@/components/ui/Spinner";
import { useAuth } from "@/context/AuthContext";
import type { InviteTokenPayload } from "@/lib/types";

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function InviteTokenPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  // In Next.js 16 dynamic routes, params is a Promise
  const { token } = use(params);

  const router = useRouter();
  const { refreshUser } = useAuth();

  // Token validation state
  const [tokenLoading, setTokenLoading] = useState(true);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [invite, setInvite] = useState<InviteTokenPayload | null>(null);

  // Form state
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [language, setLanguage] = useState("en");

  // Submission state
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  /** Validate the invite token as soon as the page mounts */
  useEffect(() => {
    if (!token) {
      setTokenError(
        "No invitation token found. Please use the link from your email.",
      );
      setTokenLoading(false);
      return;
    }

    (async () => {
      try {
        const res = await fetch(`/api/auth/invite/${token}`);
        const data = await res.json();

        if (!res.ok) {
          setTokenError(
            data.error || "This invitation link is invalid or has expired.",
          );
        } else {
          setInvite(data as InviteTokenPayload);
        }
      } catch {
        setTokenError("Network error. Could not validate your invitation.");
      } finally {
        setTokenLoading(false);
      }
    })();
  }, [token]);

  /** Show a status banner that auto-dismisses after 3 seconds */
  const showMessage = (type: "success" | "error", text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading || !invite) return;

    if (!firstName || !lastName) {
      showMessage("error", "Please enter your first and last name.");
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
      const res = await fetch("/api/auth/accept-invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          full_name: `${firstName.trim()} ${lastName.trim()}`,
          password,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        showMessage(
          "error",
          data.error || "Registration failed. Please try again.",
        );
        return;
      }

      // Hydrate AuthContext with the newly registered user
      await refreshUser();
      router.push("/dashboard");
    } catch {
      showMessage("error", "Network error. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  // ── Loading: validating token ──
  if (tokenLoading) {
    return (
      <div className="min-h-screen bg-surface-page flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <Spinner size={28} />
          <span className="text-sm">Validating invitation…</span>
        </div>
      </div>
    );
  }

  // ── Error: invalid / expired token ──
  if (tokenError) {
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
            Invitation invalid
          </h2>
          <p className="text-sm text-gray-400 leading-relaxed mb-6">
            {tokenError}
          </p>
          <a
            href="mailto:admin@iroko.ai"
            className="btn-primary py-2.5 px-5 text-sm no-underline"
          >
            Contact admin
          </a>
        </div>
      </div>
    );
  }

  // ── Main form ──
  return (
    <div className="flex min-h-screen font-sans bg-surface-page">
      {/* Left brand panel — desktop only */}
      <div className="hidden lg:flex w-[440px] shrink-0 bg-surface-card border-r border-border-default flex-col p-12 relative overflow-hidden">
        {/* Logo */}
        <div className="relative flex items-center gap-3">
          <div className="size-10 bg-brand-500 rounded-[10px] flex items-center justify-center shadow-[0_0_0_1px_rgba(255,255,255,0.12),0_4px_12px_rgba(255,203,5,0.2)] shrink-0">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <path
                d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z"
                stroke="#0A0A0B"
                strokeWidth="1.5"
                strokeLinejoin="round"
                fill="none"
              />
              <circle cx="11" cy="10.5" r="2.25" fill="#0A0A0B" />
            </svg>
          </div>
          <div>
            <div className="text-[17px] font-bold text-gray-900 tracking-[-0.01em] leading-[1.2]">
              Iroko AI
            </div>
            <div className="text-[11px] text-gray-400 leading-none">
              Fintech RegIntel
            </div>
          </div>
        </div>

        {/* Headline */}
        <div className="relative flex-1 flex flex-col justify-center">
          <h2 className="text-[29px] font-bold text-gray-900 tracking-[-0.035em] leading-tight mb-4">
            You've been invited to{" "}
            <span className="text-brand-500">Iroko AI.</span>
          </h2>
          <p className="text-sm text-gray-500 leading-[1.7] max-w-[330px]">
            Set up your account below to start using enterprise regulatory
            intelligence built for African fintechs.
          </p>

          {/* Access summary card — populated from the validated token */}
          {invite && (
            <div className="mt-11 bg-gray-50 border border-border-default rounded-xl p-5">
              <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-[0.07em] mb-3">
                Your access
              </div>
              {[
                { label: "Role", value: invite.role },
                { label: "Department", value: invite.department },
                { label: "Invited by", value: invite.invited_by },
              ].map((row) => (
                <div
                  key={row.label}
                  className="flex justify-between items-center pb-2 mb-2 border-b border-border-default last:border-b-0 last:mb-0 last:pb-0"
                >
                  <span className="text-xs text-gray-400">{row.label}</span>
                  <span className="text-xs font-semibold text-gray-800">
                    {row.value}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-12 overflow-y-auto bg-surface-page">
        <div className="w-full max-w-[400px] p-2 md:p-0 rounded-2xl">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="size-9 bg-brand-500 rounded-lg flex items-center justify-center shadow-md">
              <svg width="18" height="18" viewBox="0 0 22 22" fill="none">
                <path
                  d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z"
                  stroke="#0A0A0B"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                  fill="none"
                />
                <circle cx="11" cy="10.5" r="2.25" fill="#0A0A0B" />
              </svg>
            </div>
            <div>
              <div className="text-base font-bold text-gray-900 leading-none">
                Iroko AI
              </div>
              <div className="text-[10px] text-gray-400 mt-0.5">
                Fintech RegIntel
              </div>
            </div>
          </div>

          <div className="mb-8">
            <h1 className="text-xl md:text-2xl font-bold text-gray-900 tracking-tight mb-2 leading-tight">
              Set up your account
            </h1>
            <p className="text-sm text-gray-400 leading-relaxed">
              Create a password to complete your invitation and get access to
              Iroko AI.
            </p>
          </div>

          {/* Status message */}
          {message && (
            <div className="mb-4">
              <StatusMessage type={message.type} text={message.text} />
            </div>
          )}

          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label-base" htmlFor="first-name">
                  First name
                </label>
                <input
                  id="first-name"
                  type="text"
                  className="input-base"
                  placeholder="Adaeze"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  disabled={loading}
                />
              </div>
              <div>
                <label className="label-base" htmlFor="last-name">
                  Last name
                </label>
                <input
                  id="last-name"
                  type="text"
                  className="input-base"
                  placeholder="Okonkwo"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  disabled={loading}
                />
              </div>
            </div>

            {/* Email pre-filled from token — user cannot edit their own invite email */}
            <div>
              <label className="label-base" htmlFor="invite-email">
                Work email
              </label>
              <input
                id="invite-email"
                type="email"
                className="input-base opacity-55 cursor-not-allowed bg-gray-50"
                value={invite?.email ?? ""}
                disabled
              />
            </div>

            <div>
              <label className="label-base" htmlFor="new-password">
                Create password
              </label>
              <input
                id="new-password"
                type="password"
                className="input-base"
                placeholder="At least 8 characters"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>

            <div>
              <label className="label-base" htmlFor="confirm-password">
                Confirm password
              </label>
              <input
                id="confirm-password"
                type="password"
                className="input-base"
                placeholder="Repeat your password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 mt-1 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Spinner size={15} />
                  Creating account…
                </>
              ) : (
                "Accept invitation & sign in"
              )}
            </button>
          </form>

          <p className="mt-6 text-xs text-gray-300 text-center leading-relaxed">
            By accepting, you agree to Iroko AI's{" "}
            <a href="#" className="text-brand-600 no-underline font-medium">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="#" className="text-brand-600 no-underline font-medium">
              Privacy Policy
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
