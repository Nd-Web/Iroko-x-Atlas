/**
 * context/AuthContext.tsx
 *
 * Client-side authentication state for Iroko AI.
 *
 * Session expiry detection:
 * - On mount, fetch /api/auth/me to hydrate user state.
 * - A polling interval checks the session every 5 minutes.
 * - If the server returns 401 while the user was previously active,
 *   `sessionExpired` is set to true, which triggers the SessionExpiredToast
 *   rendered in the root layout.
 * - Components that get a 401 from direct API calls should call
 *   `triggerSessionExpiry()` to surface the same toast.
 */

"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import type { User } from "@/lib/types";

// How often to silently re-validate the session (milliseconds)
const SESSION_POLL_INTERVAL = 5 * 60 * 1000; // 5 minutes

// ─── Context shape ────────────────────────────────────────────────────────────

interface AuthContextValue {
  /** The currently authenticated user, or null if not logged in. */
  user: User | null;
  /** True while the initial /api/auth/me request is in flight. */
  userLoading: boolean;
  /**
   * True when the session has expired mid-use.
   * The SessionExpiredToast component reads this to show its overlay.
   */
  sessionExpired: boolean;
  /**
   * Re-fetch the current user from the server.
   * Call this after a successful login or profile update.
   */
  refreshUser: () => Promise<void>;
  /**
   * Manually trigger the "session expired" toast.
   * Call this in any component that receives a 401 from a direct API call.
   */
  triggerSessionExpiry: () => void;
  /**
   * Clear the server-side cookie and redirect to /login.
   * Also clears local user state immediately for instant UI feedback.
   */
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]               = useState<User | null>(null);
  const [userLoading, setUserLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Track whether the user was previously authenticated so we can distinguish
  // "never logged in" (no toast) from "session expired mid-use" (show toast).
  const wasAuthenticated = useRef(false);

  /** Show the session-expired toast and clear local user state */
  const triggerSessionExpiry = useCallback(() => {
    setUser(null);
    setSessionExpired(true);
  }, []);

  /**
   * Fetch the authenticated user from our proxy API.
   * Silently sets sessionExpired if the token has expired mid-session.
   */
  const refreshUser = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/me", { cache: "no-store" });
      if (res.ok) {
        const data: User = await res.json();
        setUser(data);
        wasAuthenticated.current = true;
      } else if (res.status === 401 || res.status === 403) {
        setUser(null);
        wasAuthenticated.current = false;

        // Public auth routes never need a redirect on 401 — the user
        // is supposed to be unauthenticated there.
        const publicRoutes = ["/login", "/forgot-password", "/reset-password", "/invite"];
        const isPublic = publicRoutes.some((r) =>
          window.location.pathname.startsWith(r)
        );

        // On any protected page, a 401 means the cookie is present but the
        // JWT is invalid or expired on the backend. We must DELETE the cookie
        // first — otherwise proxy.ts sees the cookie and redirects /login back
        // to /dashboard, creating an infinite loop.
        if (!isPublic) {
          try { await fetch("/api/auth/logout", { method: "DELETE" }); } catch { /* noop */ }
          window.location.href = "/login";
        }
      }
    } catch {
      setUser(null);
    }
  }, []);

  /** Initial hydration on mount */
  useEffect(() => {
    refreshUser().finally(() => setUserLoading(false));
  }, [refreshUser]);

  /**
   * Periodic session validation — polls every 5 minutes while the tab is open.
   * This catches token expiry between user interactions.
   */
  useEffect(() => {
    const interval = setInterval(() => {
      // Only poll if the user is currently authenticated
      if (wasAuthenticated.current) {
        refreshUser();
      }
    }, SESSION_POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [refreshUser]);

  /** Delete the server-side cookie then redirect to login */
  const logout = useCallback(async () => {
    // Immediately clear UI state before the network request returns
    setUser(null);
    wasAuthenticated.current = false;
    try {
      await fetch("/api/auth/logout", { method: "DELETE" });
    } catch {
      // Navigate away even if the request fails
    }
    window.location.href = "/login";
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        userLoading,
        sessionExpired,
        refreshUser,
        triggerSessionExpiry,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Access the current auth state from any client component.
 * Must be used inside an <AuthProvider>.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Returns initials from a full name (e.g. "Adaeze Okonkwo" → "AO").
 * Exported so Topbar/Sidebar can use it without re-importing AuthContext.
 */
export function getInitials(fullName: string): string {
  return fullName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join("");
}

/**
 * Returns a display-friendly role label (e.g. "superadmin" → "Super Admin").
 */
export function formatRole(role: string): string {
  return role
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
