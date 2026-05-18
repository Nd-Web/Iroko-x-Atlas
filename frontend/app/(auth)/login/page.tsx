/**
 * app/(auth)/login/page.tsx
 *
 * Sign-in page for Iroko AI.
 *
 * API:  POST /api/auth/login  (our Next.js proxy route)
 * Flow: submit credentials → set httpOnly cookie → redirect to /dashboard
 *
 * UX rules:
 * - Loading spinner on the submit button while the request is in flight.
 * - Error message is shown inline and auto-dismisses after 3 seconds.
 * - SSO button is a placeholder — wired to the same loading/error pattern.
 */

"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import StatusMessage from "@/components/ui/StatusMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { useAuth } from "@/context/AuthContext";

// ─── Brand panel (desktop left column) ────────────────────────────────────────

const BrandPanel = () => (
  <div className="hidden lg:flex w-[440px] shrink-0 bg-[#0C111D] flex-col p-12 relative overflow-hidden">
    <div
      className="absolute inset-0 pointer-events-none"
      style={{
        background:
          "radial-gradient(ellipse at 0% 60%, rgba(97,114,243,0.22) 0%, transparent 65%), radial-gradient(ellipse at 95% 5%, rgba(97,114,243,0.1) 0%, transparent 55%)",
      }}
    />

    {/* Logo */}
    <div className="relative flex items-center gap-3">
      <div className="size-10 bg-[#4A55D4] rounded-[10px] flex items-center justify-center shadow-[0_0_0_1px_rgba(255,255,255,0.12),0_4px_12px_rgba(74,85,212,0.4)] shrink-0">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <path
            d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z"
            stroke="white"
            strokeWidth="1.5"
            strokeLinejoin="round"
            fill="none"
          />
          <circle cx="11" cy="10.5" r="2.25" fill="white" />
        </svg>
      </div>
      <div>
        <div className="text-[17px] font-bold text-white tracking-[-0.01em] leading-[1.2]">
          Iroko AI
        </div>
        <div className="text-[11px] text-white/40 leading-none">
          MTN Nigeria
        </div>
      </div>
    </div>

    {/* Headline */}
    <div className="relative flex-1 flex flex-col justify-center">
      <h2 className="text-[29px] font-bold text-white tracking-[-0.035em] leading-[1.25] mb-4">
        Enterprise intelligence.{" "}
        <span className="text-[#818CF8]">Cite-first answers.</span>
      </h2>
      <p className="text-sm text-white/50 leading-[1.7] mb-11 max-w-[330px]">
        Purpose-built for MTN Nigeria — multilingual AI that grounds every
        answer in your verified document corpus and logs every interaction for
        regulatory audit.
      </p>

      <div className="flex flex-col gap-[22px]">
        {[
          {
            title: "Cite-first AI answers",
            desc: "Every response backed by verifiable document evidence",
          },
          {
            title: "Audit-grade compliance logging",
            desc: "Cryptographically chained records for NCC and NDPA",
          },
          {
            title: "Multilingual by design",
            desc: "English, Pidgin, Yoruba, Hausa, and Igbo",
          },
        ].map((f) => (
          <div key={f.title} className="flex items-start gap-3">
            <div className="size-5 rounded-full bg-[rgba(97,114,243,0.18)] border border-[rgba(97,114,243,0.4)] flex items-center justify-center shrink-0 mt-[2px]">
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path
                  d="M2 5l2 2 4-4"
                  stroke="#818CF8"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div>
              <div className="text-[13px] font-semibold text-white/[0.88] mb-[2px]">
                {f.title}
              </div>
              <div className="text-xs text-white/[0.38] leading-[1.55]">
                {f.desc}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LoginPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  /** Show a status message that automatically clears after 3 seconds */
  const showMessage = (type: "success" | "error", text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return;

    if (!email || !password) {
      showMessage("error", "Please enter your email and password.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        showMessage("error", data.error || "Login failed. Please try again.");
        return;
      }

      // Hydrate the AuthContext with the freshly authenticated user
      await refreshUser();
      router.push("/dashboard");
    } catch {
      showMessage("error", "Network error. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen font-sans bg-white md:bg-surface-page lg:bg-white">
      <BrandPanel />

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-[380px] bg-white p-2 md:p-0 rounded-2xl">
          <div className="mb-8 md:mb-9">
            {/* Mobile Logo */}
            <div className="lg:hidden flex items-center gap-2.5 mb-8">
              <div className="size-9 bg-[#4A55D4] rounded-lg flex items-center justify-center shadow-md">
                <svg width="18" height="18" viewBox="0 0 22 22" fill="none">
                  <path
                    d="M11 2.5L17.5 6.5V14.5L11 18.5L4.5 14.5V6.5L11 2.5Z"
                    stroke="white"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                    fill="none"
                  />
                  <circle cx="11" cy="10.5" r="2.25" fill="white" />
                </svg>
              </div>
              <div>
                <div className="text-base font-bold text-gray-900 leading-none">
                  Iroko AI
                </div>
                <div className="text-[10px] text-gray-400 mt-0.5">
                  MTN Nigeria
                </div>
              </div>
            </div>

            <h1 className="text-xl md:text-2xl font-bold text-gray-900 tracking-[-0.025em] mb-2 leading-[1.2]">
              Welcome back
            </h1>
            <p className="text-sm text-gray-400 leading-[1.6]">
              Iroko AI is invite-only. Contact your administrator if you need
              access.
            </p>
          </div>

          {/* Status message */}
          {message && (
            <div className="mb-4">
              <StatusMessage type={message.type} text={message.text} />
            </div>
          )}

          <form
            className="flex flex-col gap-4 md:gap-[18px]"
            onSubmit={handleSubmit}
          >
            <div>
              <label className="label-base" htmlFor="email">
                Work email
              </label>
              <input
                id="email"
                type="email"
                className="input-base"
                placeholder="you@mtn.ng"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="label-base m-0" htmlFor="password">
                  Password
                </label>
                <Link
                  href="/forgot-password"
                  className="text-[13px] text-brand-600 no-underline font-medium"
                >
                  Forgot password?
                </Link>
              </div>
              {/* suppressHydrationWarning: password managers inject UI here before React hydrates */}
              <div className="relative" suppressHydrationWarning>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  className="input-base pr-10"
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  suppressHydrationWarning
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? (
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 mt-1 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <LoadingSpinner size={15} />
                  Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          <p className="mt-7 text-xs text-gray-300 text-center leading-[1.6]">
            Access is by invitation only.{" "}
            <a
              href="mailto:iroko-admin@mtn.ng"
              className="text-brand-600 no-underline font-medium"
            >
              Request access
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
