"use client";

import Link from "next/link";
import { useState, useEffect, useMemo } from "react";
import { useUsers } from "@/app/user-management/_hooks/useUsers";
import { useDeactivateUser } from "@/app/user-management/_hooks/useDeactivateUser";
import { useInvitations } from "@/app/user-management/_hooks/useInvitations";
import type { User } from "@/lib/types";

const ROLE_COLORS: Record<string, { bg: string; color: string }> = {
  superadmin:  { bg: "var(--color-danger-50)",  color: "var(--color-danger-700)"  },
  admin:       { bg: "var(--color-warning-50)", color: "var(--color-warning-700)" },
  analyst:     { bg: "var(--color-success-50)", color: "var(--color-success-700)" },
  viewer:      { bg: "var(--color-info-50)",    color: "var(--color-info-700)"    },
};

function roleStyle(role: string) {
  return ROLE_COLORS[role.toLowerCase()] ?? { bg: "var(--color-gray-100)", color: "var(--color-gray-600)" };
}

const COL = "2fr 1.4fr 1.4fr 1fr 130px 110px";

export default function UserManagementContent() {
  const { data, isLoading, isError } = useUsers();
  const { data: invitationsData, isLoading: invitesLoading } = useInvitations();
  const deactivate = useDeactivateUser();

  const [suspendTarget, setSuspendTarget] = useState<User | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("All roles");

  useEffect(() => {
    if (!suspendTarget) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setSuspendTarget(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [suspendTarget]);

  // Handle both User[] and { users: User[], total: number } shapes defensively
  const users: User[] = Array.isArray(data) ? data : (data?.users ?? []);
  const totalCount = Array.isArray(data) ? data.length : (data?.total ?? users.length);
  const activeCount = users.filter((u) => u.is_active).length;
  const suspendedCount = users.filter((u) => !u.is_active).length;
  const pendingCount = (invitationsData?.invitations ?? []).filter(
    (inv) => !inv.used_at && new Date(inv.expires_at) >= new Date()
  ).length;

  const STATS = [
    { label: "Total users",     value: isLoading ? null : String(totalCount),                      sub: "across all roles",    accent: "#4A55D4" },
    { label: "Active",          value: isLoading ? null : String(activeCount),                     sub: "currently enabled",   accent: "#17B26A" },
    { label: "Pending invites", value: invitesLoading ? null : String(pendingCount),               sub: "awaiting acceptance", accent: "#F79009" },
    { label: "Suspended",       value: isLoading ? null : String(suspendedCount),                  sub: "access revoked",      accent: "#F04438" },
  ];

  const uniqueRoles = useMemo(
    () => Array.from(new Set(users.map((u) => u.role).filter(Boolean))),
    [users]
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return users.filter((u) => {
      const matchesSearch =
        !q ||
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        u.department?.toLowerCase().includes(q) ||
        u.organisation?.toLowerCase().includes(q);
      const matchesRole = roleFilter === "All roles" || u.role === roleFilter;
      return matchesSearch && matchesRole;
    });
  }, [users, search, roleFilter]);

  const handleSuspendConfirm = () => {
    if (!suspendTarget) return;
    deactivate.mutate(suspendTarget.id, {
      onSuccess: () => setSuspendTarget(null),
    });
  };

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[14px]">
        {STATS.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-[18px] px-5">
            <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            {s.value === null ? (
              <div className="h-8 w-10 bg-gray-100 animate-pulse rounded mb-[5px]" />
            ) : (
              <div className="text-[28px] font-bold text-gray-900 tracking-[-0.04em] leading-none mb-[5px]">{s.value}</div>
            )}
            <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{s.label}</div>
            <div className="text-[11.5px] text-gray-400">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* User table */}
      <div className="card overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between px-4 md:px-5 py-[14px] border-b border-border-default gap-3">
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">All users</h2>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="absolute left-[10px] top-1/2 -translate-y-1/2 text-gray-300 pointer-events-none">
                <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.4" />
                <path d="M11 11l-2.5-2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
              <input
                type="text"
                placeholder="Search users…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input-base w-full sm:w-[200px] py-[7px] pr-3 pl-[30px]"
              />
            </div>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="input-base w-full sm:w-auto py-[7px] px-3 appearance-none cursor-pointer"
            >
              <option>All roles</option>
              {uniqueRoles.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <div className="min-w-[900px]">
            <div className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3" style={{ gridTemplateColumns: COL }}>
              {["User", "Role", "Department", "Organisation", "Status", ""].map((h) => (
                <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
              ))}
            </div>

            {isError && (
              <div className="px-5 py-10 text-center text-[13px] text-danger-600">
                Failed to load users. Please refresh the page.
              </div>
            )}

            {isLoading && Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="grid items-center py-[13px] px-5 gap-3 border-b border-border-default" style={{ gridTemplateColumns: COL }}>
                <div className="flex items-center gap-[10px]">
                  <div className="size-8 rounded-full bg-gray-100 animate-pulse shrink-0" />
                  <div className="flex flex-col gap-1.5">
                    <div className="h-3 w-28 bg-gray-100 animate-pulse rounded" />
                    <div className="h-2.5 w-36 bg-gray-100 animate-pulse rounded" />
                  </div>
                </div>
                {[1, 2, 3, 4].map((k) => (
                  <div key={k} className="h-3 w-20 bg-gray-100 animate-pulse rounded" />
                ))}
                <div />
              </div>
            ))}

            {!isLoading && !isError && filtered.map((user) => {
              const rs = roleStyle(user.role);
              const initials = user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
              const statusDot = user.is_active ? "var(--color-success-500)" : "var(--color-gray-300)";
              const statusLabel = user.is_active ? "Active" : "Suspended";
              const lastSeen = user.last_login
                ? new Date(user.last_login).toLocaleDateString()
                : "Never";

              return (
                <div
                  key={user.id}
                  className="grid items-center py-[13px] px-5 gap-3 border-b border-border-default cursor-pointer hover:bg-gray-50 transition-colors"
                  style={{ gridTemplateColumns: COL }}
                >
                  <div className="flex items-center gap-[10px]">
                    <div className="size-8 rounded-full bg-brand-100 flex items-center justify-center text-[11.5px] font-bold text-brand-700 shrink-0">
                      {initials}
                    </div>
                    <div className="min-w-0">
                      <div className="text-[13.5px] font-medium text-gray-800 leading-[1.2] truncate">{user.full_name}</div>
                      <div className="text-[11.5px] text-gray-400 truncate">{user.email}</div>
                    </div>
                  </div>

                  <span className="text-[11.5px] font-semibold px-2 py-[2px] rounded-full w-fit" style={{ color: rs.color, background: rs.bg }}>
                    {user.role}
                  </span>

                  <span className="text-[13px] text-gray-500 truncate">{user.department || "—"}</span>
                  <span className="text-[13px] text-gray-500 truncate">{user.organisation || "—"}</span>

                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: statusDot }} />
                    <div>
                      <span className="text-[12.5px] text-gray-600">{statusLabel}</span>
                      {user.is_active && (
                        <div className="text-[11px] text-gray-300">{lastSeen}</div>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-1.5 justify-end">
                    <Link
                      href={`/user-management/${user.id}`}
                      className="btn-secondary py-1 px-[10px] text-xs no-underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Edit
                    </Link>
                    {user.is_active && (
                      <button
                        className="btn-secondary py-1 px-[10px] text-xs text-danger-600 border-danger-100"
                        onClick={(e) => { e.stopPropagation(); setSuspendTarget(user); }}
                      >
                        Suspend
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {!isLoading && !isError && filtered.length === 0 && (
              <div className="px-5 py-10 text-center text-[13px] text-gray-400">
                No users match your search.
              </div>
            )}
          </div>
        </div>
      </div>

      {suspendTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6" onClick={() => setSuspendTarget(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "440px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">Suspend user</h2>
              <button onClick={() => setSuspendTarget(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <div className="size-11 rounded-lg bg-danger-50 flex items-center justify-center text-danger-600 shrink-0">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M10 2l8 14H2l8-14z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M10 7v4m0 3h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <div className="min-w-0">
                  <h3 className="text-[14px] font-semibold text-gray-900 leading-tight truncate">{suspendTarget.full_name}</h3>
                  <p className="text-[12px] text-gray-500 mt-0.5 truncate">{suspendTarget.email}</p>
                </div>
              </div>

              <p className="text-[13px] text-gray-600 leading-[1.5] m-0">
                This will immediately revoke {suspendTarget.full_name.split(" ")[0]}&apos;s access to Iroko AI. They will not be able to log in until their account is reactivated.
              </p>

              {deactivate.isError && (
                <p className="text-[12px] text-danger-600">
                  {(deactivate.error as Error)?.message ?? "Failed to suspend user. Please try again."}
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setSuspendTarget(null)} disabled={deactivate.isPending}>
                Cancel
              </button>
              <button
                className="bg-danger-600 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-danger-700 transition-colors disabled:opacity-60"
                onClick={handleSuspendConfirm}
                disabled={deactivate.isPending}
              >
                {deactivate.isPending ? "Suspending…" : "Suspend account"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
