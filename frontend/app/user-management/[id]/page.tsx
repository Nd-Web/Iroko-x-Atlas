"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useState, useEffect } from "react";
import AppShell from "@/components/layout/AppShell";
import { useUser } from "../_hooks/useUser";
import { useUpdateUser } from "../_hooks/useUpdateUser";
import { useActivateUser } from "../_hooks/useActivateUser";
import { useDeactivateUser } from "../_hooks/useDeactivateUser";

const ROLES = ["superadmin", "admin", "analyst", "viewer"];

export default function EditUserPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.id as string;

  const { data: user, isLoading, isError } = useUser(userId);
  const updateUser = useUpdateUser(userId);
  const activateUser = useActivateUser();
  const deactivateUser = useDeactivateUser();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [department, setDepartment] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [role, setRole] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!user) return;
    const parts = user.full_name?.split(" ") ?? [];
    setFirstName(parts[0] ?? "");
    setLastName(parts.slice(1).join(" "));
    setDepartment(user.department ?? "");
    setOrganisation(user.organisation ?? "");
    setRole(user.role ?? "");
    setIsActive(user.is_active);
  }, [user]);

  const initials = user
    ? user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()
    : "";

  const handleSave = async () => {
    setSaveError(null);
    setSaveSuccess(false);

    const profileChanged =
      `${firstName} ${lastName}`.trim() !== user?.full_name ||
      department !== user?.department ||
      organisation !== user?.organisation ||
      role !== user?.role;

    const statusChanged = isActive !== user?.is_active;

    try {
      if (profileChanged) {
        await updateUser.mutateAsync({
          full_name: `${firstName} ${lastName}`.trim(),
          department,
          organisation,
          role,
        });
      }

      if (statusChanged) {
        if (isActive) {
          await activateUser.mutateAsync(userId);
        } else {
          await deactivateUser.mutateAsync(userId);
        }
      }

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError((err as Error)?.message ?? "Failed to save changes.");
    }
  };

  const isSaving =
    updateUser.isPending || activateUser.isPending || deactivateUser.isPending;

  if (isLoading) {
    return (
      <AppShell title="Edit user" subtitle="Loading…">
        <div className="max-w-[640px] flex flex-col gap-5 mx-auto lg:mx-0">
          {[1, 2].map((i) => (
            <div key={i} className="card px-5 md:px-6 py-5 flex flex-col gap-4">
              <div className="h-4 w-32 bg-gray-100 animate-pulse rounded" />
              <div className="grid grid-cols-2 gap-4">
                {[1, 2, 3, 4].map((j) => (
                  <div key={j} className="flex flex-col gap-2">
                    <div className="h-3 w-16 bg-gray-100 animate-pulse rounded" />
                    <div className="h-9 bg-gray-100 animate-pulse rounded-lg" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </AppShell>
    );
  }

  if (isError || !user) {
    return (
      <AppShell title="User not found" subtitle="The requested user could not be found">
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="size-14 rounded-full bg-gray-100 flex items-center justify-center text-gray-400">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M4 20a8 8 0 0 1 16 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <p className="text-[15px] text-gray-500">User not found</p>
          <Link href="/user-management" className="btn-secondary py-2 px-4 text-sm no-underline">
            ← Back to user management
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Edit user" subtitle={user.email}>
      <div className="max-w-[640px] flex flex-col gap-5 mx-auto lg:mx-0">

        {/* User info card */}
        <div className="card px-5 md:px-6 py-5 flex flex-col gap-5">
          {/* Avatar row */}
          <div className="flex items-center gap-3 pb-4 border-b border-border-default">
            <div className="size-10 md:size-12 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[14px] md:text-[16px] font-bold shrink-0">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="text-[14px] md:text-[15px] font-semibold text-gray-900 truncate">{user.full_name}</div>
              <div className="text-[12px] md:text-[13px] text-gray-400 truncate">{user.email}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label-base">First name</label>
              <input
                className="input-base"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div>
              <label className="label-base">Last name</label>
              <input
                className="input-base"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label-base">Work email</label>
              <input className="input-base" value={user.email} disabled />
            </div>
            <div>
              <label className="label-base">Role</label>
              <select
                className="input-base appearance-none cursor-pointer"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
                {/* Show current role if it's not in the predefined list */}
                {role && !ROLES.includes(role) && (
                  <option value={role}>{role}</option>
                )}
              </select>
            </div>
            <div>
              <label className="label-base">Organisation</label>
              <input
                className="input-base"
                value={organisation}
                onChange={(e) => setOrganisation(e.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="label-base">Department</label>
              <input
                className="input-base"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Access & permissions card */}
        <div className="card px-5 md:px-6 py-5 flex flex-col gap-4">
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Account status</h2>
          <div>
            <label className="label-base">Access</label>
            <select
              className="input-base appearance-none cursor-pointer"
              value={isActive ? "active" : "suspended"}
              onChange={(e) => setIsActive(e.target.value === "active")}
            >
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
            </select>
            <p className="text-[11.5px] text-gray-400 mt-1.5">
              Suspending a user blocks login immediately. Activating restores access.
            </p>
          </div>

          <div className="text-[12px] text-gray-400">
            <span className="font-medium text-gray-500">Member since: </span>
            {new Date(user.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
          </div>
          {user.last_login && (
            <div className="text-[12px] text-gray-400">
              <span className="font-medium text-gray-500">Last login: </span>
              {new Date(user.last_login).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
            </div>
          )}
        </div>

        {/* Error / success feedback */}
        {saveError && (
          <p className="text-[13px] text-danger-600 px-1">{saveError}</p>
        )}
        {saveSuccess && (
          <p className="text-[13px] text-success-600 px-1">Changes saved successfully.</p>
        )}

        {/* Footer actions */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <Link href="/user-management" className="flex items-center gap-1.5 text-[13px] font-medium text-brand-600 no-underline hover:text-brand-700">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Back to user management
          </Link>
          <div className="flex gap-2 w-full sm:w-auto">
            <button
              onClick={() => router.push("/user-management")}
              className="btn-secondary flex-1 sm:flex-none py-2 px-4 text-sm"
              disabled={isSaving}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="btn-primary flex-1 sm:flex-none py-2 px-4 text-sm font-semibold disabled:opacity-60"
            >
              {isSaving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
