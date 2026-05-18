/**
 * app/settings/profile/page.tsx
 *
 * User profile and preferences page.
 *
 * API calls:
 * - GET  /api/auth/me         — hydrate the form on mount (via AuthContext)
 * - PATCH /api/auth/me        — save name / department changes
 * - POST  /api/auth/generate-key — rotate the user's API key
 *
 * UX rules:
 * - Form fields are pre-filled from the AuthContext user object.
 * - Loading spinner on each save/generate button while the request is in flight.
 * - Success / error messages auto-dismiss after 3 seconds.
 * - The generated API key is shown once inline — user must copy immediately.
 */

"use client";

import { useState, useEffect } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth, getInitials } from "@/context/AuthContext";
import StatusMessage from "@/components/ui/StatusMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();

  // Form fields
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [department, setDepartment] = useState("");

  // Save profile state
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // API key state
  const [generatingKey, setGeneratingKey] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [keyMessage, setKeyMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Pre-fill form from AuthContext user
  useEffect(() => {
    if (!user) return;
    const parts = user.full_name.split(" ");
    setFirstName(parts[0] ?? "");
    setLastName(parts.slice(1).join(" "));
    setDepartment(user.department ?? "");
  }, [user]);

  /** Show a save-form message that auto-dismisses after 3 seconds */
  const showSaveMessage = (type: "success" | "error", text: string) => {
    setSaveMessage({ type, text });
    setTimeout(() => setSaveMessage(null), 3000);
  };

  /** Show a key-generation message that auto-dismisses after 3 seconds */
  const showKeyMessage = (type: "success" | "error", text: string) => {
    setKeyMessage({ type, text });
    setTimeout(() => setKeyMessage(null), 3000);
  };

  /** Save profile — PATCH /api/auth/me */
  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (saving) return;

    const full_name = `${firstName.trim()} ${lastName.trim()}`.trim();
    if (!full_name) {
      showSaveMessage("error", "Please enter your full name.");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch("/api/auth/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name, department }),
      });

      const data = await res.json();

      if (!res.ok) {
        showSaveMessage(
          "error",
          data.error || "Failed to save changes. Please try again.",
        );
        return;
      }

      showSaveMessage("success", "Profile updated successfully.");
      // Refresh the AuthContext so Topbar/Sidebar reflect the new name
      await refreshUser();
    } catch {
      showSaveMessage("error", "Network error. Please check your connection.");
    } finally {
      setSaving(false);
    }
  };

  /** Rotate API key — POST /api/auth/generate-key */
  const handleGenerateKey = async () => {
    if (generatingKey) return;

    setGeneratingKey(true);
    setGeneratedKey(null);
    try {
      const res = await fetch("/api/auth/generate-key", { method: "POST" });
      const data = await res.json();

      if (!res.ok) {
        showKeyMessage("error", data.error || "Failed to generate API key.");
        return;
      }

      setGeneratedKey(data.key);
      showKeyMessage(
        "success",
        "New API key generated. Copy it now — it will not be shown again.",
      );
    } catch {
      showKeyMessage("error", "Network error. Please check your connection.");
    } finally {
      setGeneratingKey(false);
    }
  };

  const initials = user ? getInitials(user.full_name) : "?";

  return (
    <AppShell
      title="Profile & preferences"
      subtitle="Manage your account, language, and notification settings"
    >
      <div className="max-w-[620px] flex flex-col gap-5 mx-auto lg:mx-0">
        {/* Personal info */}
        <div className="card overflow-hidden">
          <div className="py-[18px] px-5 md:px-6 border-b border-border-default">
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">
              Personal information
            </h2>
            <p className="text-xs text-gray-400 mt-[3px]">
              Your name and contact details
            </p>
          </div>
          <form className="p-5 md:p-6" onSubmit={handleSave}>
            {/* Avatar row */}
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 mb-6 text-center sm:text-left">
              <div className="size-[56px] rounded-full bg-brand-600 flex items-center justify-center text-[18px] font-bold text-white shrink-0 ring-3 ring-brand-100">
                {initials}
              </div>
              <div className="min-w-0">
                <div className="text-[15px] font-semibold text-gray-900 mb-[2px]">
                  {user?.full_name ?? "Loading…"}
                </div>
                <div className="text-[12.5px] text-gray-400">
                  {user?.email ?? ""} · {user?.role ?? ""}
                </div>
              </div>
            </div>

            {/* Status message */}
            {saveMessage && (
              <div className="mb-4">
                <StatusMessage
                  type={saveMessage.type}
                  text={saveMessage.text}
                />
              </div>
            )}

            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label-base" htmlFor="first-name">
                    First name
                  </label>
                  <input
                    id="first-name"
                    className="input-base"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="label-base" htmlFor="last-name">
                    Last name
                  </label>
                  <input
                    id="last-name"
                    className="input-base"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    disabled={saving}
                  />
                </div>
              </div>
              <div>
                <label className="label-base" htmlFor="email">
                  Work email
                </label>
                <input
                  id="email"
                  className="input-base disabled:opacity-55 disabled:cursor-not-allowed disabled:bg-gray-50"
                  value={user?.email ?? ""}
                  disabled
                />
                <p className="text-xs text-gray-300 mt-[5px]">
                  Managed via Entra ID
                </p>
              </div>
              <div>
                <label className="label-base" htmlFor="dept">
                  Department
                </label>
                <input
                  id="dept"
                  className="input-base"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  disabled={saving}
                />
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 pt-5">
              <button
                type="submit"
                disabled={saving}
                className="btn-primary py-[10px] px-6 flex-1 sm:flex-none font-semibold flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {saving ? (
                  <>
                    <LoadingSpinner size={14} />
                    Saving…
                  </>
                ) : (
                  "Save changes"
                )}
              </button>
              <button
                type="button"
                className="btn-secondary py-[10px] px-6 flex-1 sm:flex-none"
                onClick={() => {
                  if (user) {
                    const parts = user.full_name.split(" ");
                    setFirstName(parts[0] ?? "");
                    setLastName(parts.slice(1).join(" "));
                    setDepartment(user.department ?? "");
                  }
                }}
                disabled={saving}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </AppShell>
  );
}
