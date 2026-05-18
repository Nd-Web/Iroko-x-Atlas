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

// ─── Static notification data (replace with API call when available) ──────────

const NOTIFICATIONS = [
  {
    id: 1,
    type: "incident",
    title: "INC-4821 critical",
    desc: "Ikeja cluster 4G fault — SLA at risk. ₦27.3M exposure.",
    time: "2m ago",
    read: false,
  },
  {
    id: 2,
    type: "compliance",
    title: "DPIA approval pending",
    desc: "MoMo Analytics Pipeline v2 awaiting DPO sign-off.",
    time: "18m ago",
    read: false,
  },
  {
    id: 3,
    type: "system",
    title: "Audit log verified",
    desc: "1,284 entries cryptographically chained. Evidence Act compliant.",
    time: "1h ago",
    read: true,
  },
  {
    id: 4,
    type: "info",
    title: "Sync complete",
    desc: "Lagos Fibre Phase 3 bundle synced. 62 MB ready for offline use.",
    time: "3h ago",
    read: true,
  },
];

const NOTIF_COLORS: Record<string, { bg: string; color: string }> = {
  incident: { bg: "bg-danger-50", color: "text-danger-600" },
  compliance: { bg: "bg-warning-50", color: "text-warning-600" },
  system: { bg: "bg-success-50", color: "text-success-600" },
  info: { bg: "bg-brand-50", color: "text-brand-600" },
};

function NotifIcon({ type }: { type: string }) {
  if (type === "incident")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path
          d="M1 11.5L5 6 7 8.5l3-4.5 3.5 7.5H1Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
      </svg>
    );
  if (type === "compliance")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path
          d="M7 1 2 3.5V7C2 9.8 4.2 12.4 7 13c2.8-.6 5-3.2 5-6V3.5L7 1Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
      </svg>
    );
  if (type === "system")
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3" />
        <path
          d="M5 7l1.5 1.5L9.5 5"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3" />
      <path
        d="M7 6.5V10M7 4.5h.01"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function Topbar({
  title,
  subtitle,
  actions,
  onMenuClick,
}: TopbarProps) {
  const { user, logout } = useAuth();

  const [notifOpen, setNotifOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);

  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  // Close dropdowns when the user clicks outside of them
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node))
        setNotifOpen(false);
      if (userRef.current && !userRef.current.contains(e.target as Node))
        setUserOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const unreadCount = NOTIFICATIONS.filter((n) => !n.read).length;

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
      className="bg-white border-b border-border-default flex items-center justify-between px-4 md:px-6 sticky top-0 z-30 shrink-0 gap-4"
      style={{ height: "var(--topbar-height)" }}
    >
      <div className="flex items-center gap-3 min-w-0">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuClick}
          className="lg:hidden p-1.5 -ml-1.5 text-gray-400 hover:text-gray-600 transition-colors cursor-pointer"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
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

        {/* Notification bell */}
        {/* <div ref={notifRef} className="relative">
          <button
            onClick={() => { setNotifOpen((v) => !v); setUserOpen(false); }}
            className="relative size-[34px] border border-border-default rounded-md bg-transparent flex items-center justify-center cursor-pointer text-gray-400 transition-colors shrink-0 hover:bg-gray-50 hover:text-gray-600"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 1.5a4.5 4.5 0 0 1 4.5 4.5v2.5L14 11H2l1.5-2.5V6A4.5 4.5 0 0 1 8 1.5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
              <path d="M6.5 12a1.5 1.5 0 0 0 3 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 size-1.5 bg-danger-500 rounded-full border-[1.5px] border-white" />
            )}
          </button>

          {notifOpen && (
            <div className="absolute top-[calc(100%+6px)] right-0 w-[280px] sm:w-[340px] bg-white border border-border-default rounded-xl shadow-lg z-50 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-border-default">
                <span className="text-[13px] font-semibold text-gray-900">Notifications</span>
                <button className="text-[12px] font-medium text-brand-600 hover:text-brand-700">Mark all read</button>
              </div>
              <div className="flex flex-col">
                {NOTIFICATIONS.map((n) => {
                  const c = NOTIF_COLORS[n.type];
                  return (
                    <div
                      key={n.id}
                      className={`flex gap-3 px-4 py-3 border-b border-border-default last:border-b-0 hover:bg-gray-50 transition-colors cursor-pointer ${!n.read ? "bg-brand-50/30" : ""}`}
                    >
                      <div className={`size-7 rounded-lg flex items-center justify-center shrink-0 mt-[1px] ${c.bg} ${c.color}`}>
                        <NotifIcon type={n.type} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-[13px] font-semibold text-gray-800 leading-[1.3] truncate">{n.title}</span>
                          <span className="text-[11px] text-gray-300 shrink-0 mt-[1px]">{n.time}</span>
                        </div>
                        <p className="text-[11.5px] text-gray-400 leading-[1.4] mt-[1px] m-0 line-clamp-2">{n.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="px-4 py-2.5 border-t border-border-default text-center">
                <button className="text-[12.5px] font-semibold text-brand-600 hover:text-brand-700">View all notifications</button>
              </div>
            </div>
          )}
        </div> */}

        {/* User chip */}
        <div ref={userRef} className="relative">
          <button
            onClick={() => {
              setUserOpen((v) => !v);
              setNotifOpen(false);
            }}
            className="flex items-center gap-2 px-[6px] py-[6px] md:px-[10px] md:py-2 border border-border-default rounded-full bg-transparent cursor-pointer transition-colors shrink-0 hover:bg-gray-50"
          >
            <div className="size-[24px] md:size-[26px] rounded-full bg-brand-600 flex items-center justify-center text-[9px] md:text-[10px] font-bold text-white tracking-[0.02em] shrink-0">
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
            <div className="absolute top-[calc(100%+6px)] right-0 w-[200px] bg-white border border-border-default rounded-xl shadow-lg z-50 overflow-hidden py-1.5">
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
