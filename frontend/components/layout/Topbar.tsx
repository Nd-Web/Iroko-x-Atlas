/**
 * components/layout/Topbar.tsx
 *
 * Sticky top navigation bar shown on every authenticated page.
 *
 * Reads the current user from AuthContext so the user chip shows real data.
 * The sign-out item calls logout() from AuthContext, which deletes the
 * server-side cookie before redirecting to /login.
 */

"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useAuth, getInitials, formatRole } from "@/context/AuthContext";

interface TopbarProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  onMenuClick?: () => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function Topbar({
  title,
  subtitle,
  actions,
  onMenuClick,
}: TopbarProps) {
  const { user, logout } = useAuth();

  const [userOpen, setUserOpen] = useState(false);

  const userRef = useRef<HTMLDivElement>(null);

  // Close the dropdown when the user clicks outside of it
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (userRef.current && !userRef.current.contains(e.target as Node))
        setUserOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Derive display values from the current user (fall back to placeholders during loading)
  const displayName = user
    ? user.full_name.split(" ")[0] +
      " " +
      user.full_name.split(" ")[1]?.[0] +
      "."
    : "…";
  const displayRole = user ? formatRole(user.role) : "";
  const initials = user ? getInitials(user.full_name) : "?";
  const fullName = user?.full_name ?? "";

  return (
    <header
      className="bg-sidebar-bg border-b border-border-default flex items-center justify-between px-4 md:px-6 sticky top-0 z-30 shrink-0 gap-4"
      style={{ height: "var(--topbar-height)" }}
    >
      <div className="flex items-center gap-3 min-w-0">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuClick}
          aria-label="Open navigation menu"
          className="lg:hidden p-1.5 -ml-1.5 text-gray-400 hover:text-gray-600 transition-colors cursor-pointer"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M3 5h14M3 10h14M3 15h14"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>

        {/* Page title */}
        <div className="min-w-0">
          <h1 className="text-[14px] md:text-[15px] font-semibold text-gray-900 tracking-[-0.015em] leading-[1.2] truncate">
            {title}
          </h1>
          {subtitle && (
            <p className="hidden sm:block text-xs text-gray-400 leading-none mt-[3px] truncate">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-1.5 md:gap-2.5 shrink-0">
        <div className="flex items-center gap-2">{actions}</div>

        {/* User chip */}
        <div ref={userRef} className="relative">
          <button
            onClick={() => {
              setUserOpen((v) => !v);

            }}
            aria-label="Open user menu"
            aria-haspopup="menu"
            aria-expanded={userOpen}
            className="flex items-center gap-2 px-[6px] py-[6px] md:px-[10px] md:py-2 border border-border-default rounded-full bg-transparent cursor-pointer transition-colors shrink-0 hover:bg-gray-50"
          >
            <div className="size-[24px] md:size-[26px] rounded-full bg-brand-600 flex items-center justify-center text-[9px] md:text-[10px] font-bold text-[#0A0A0B] tracking-[0.02em] shrink-0">
              {initials}
            </div>
            <div className="hidden sm:block text-left">
              <div className="text-[13px] font-semibold text-gray-800 leading-[1.2]">
                {displayName}
              </div>
              <div className="text-[10.5px] text-gray-400 leading-none">
                {displayRole}
              </div>
            </div>
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              className="text-gray-300 ml-0.5"
            >
              <path
                d="M2.5 4.5l3.5 3 3.5-3"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          {userOpen && (
            <div className="absolute top-[calc(100%+6px)] right-0 w-[200px] bg-surface-card border border-border-default rounded-xl shadow-lg z-50 overflow-hidden py-1.5">
              <div className="px-3.5 py-2.5 border-b border-border-default mb-1">
                <div className="text-[13px] font-semibold text-gray-800 leading-[1.2] truncate">
                  {fullName || "Loading…"}
                </div>
                <div className="text-[11px] text-gray-400 mt-[1px]">
                  {displayRole}
                </div>
              </div>
              <Link
                href="/settings/profile"
                onClick={() => setUserOpen(false)}
                className="flex items-center gap-2.5 px-3.5 py-2 text-[13px] text-gray-600 hover:bg-gray-50 transition-colors no-underline"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  className="text-gray-400"
                >
                  <circle
                    cx="7"
                    cy="5"
                    r="2.5"
                    stroke="currentColor"
                    strokeWidth="1.3"
                  />
                  <path
                    d="M2 12.5a5 5 0 0 1 10 0"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinecap="round"
                  />
                </svg>
                Profile settings
              </Link>
              <Link
                href="/settings/system"
                onClick={() => setUserOpen(false)}
                className="flex items-center gap-2.5 px-3.5 py-2 text-[13px] text-gray-600 hover:bg-gray-50 transition-colors no-underline"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  className="text-gray-400"
                >
                  <circle
                    cx="7"
                    cy="7"
                    r="2"
                    stroke="currentColor"
                    strokeWidth="1.3"
                  />
                  <path
                    d="M7 1v1.5m0 9V13M1 7h1.5m9 0H13M2.5 2.5l1 1m6 6 1 1M2.5 11.5l1-1m6-6 1-1"
                    stroke="currentColor"
                    strokeWidth="1.2"
                    strokeLinecap="round"
                  />
                </svg>
                System settings
              </Link>
              <div className="border-t border-border-default mt-1 pt-1">
                {/* Sign out calls the auth context logout which clears the cookie */}
                <button
                  onClick={() => {
                    setUserOpen(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-2.5 px-3.5 py-2 text-[13px] text-danger-600 hover:bg-danger-50 transition-colors"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path
                      d="M9.5 4.5V3A1 1 0 0 0 8.5 2H3A1 1 0 0 0 2 3v8a1 1 0 0 0 1 1h5.5a1 1 0 0 0 1-1V9.5"
                      stroke="currentColor"
                      strokeWidth="1.3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M6 7h6M10 5l2 2-2 2"
                      stroke="currentColor"
                      strokeWidth="1.3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Sign out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
