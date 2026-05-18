"use client";

import { useState } from "react";
import AppShell from "@/components/layout/AppShell";
import Link from "next/link";
import { useRouter } from "next/navigation";
import StatusMessage from "@/components/ui/StatusMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { useSendInvite } from "../_hooks/useSendInvite";

export default function InviteUserPage() {
  const router = useRouter();
  const sendInvite = useSendInvite();

  const [email, setEmail]           = useState("");
  const [role, setRole]             = useState("");
  const [department, setDepartment] = useState("Network Operations");
  const [personalMessage, setPersonalMessage] = useState("");
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email) {
      sendInvite.reset();
      return;
    }

    if (!role) return;

    try {
      await sendInvite.mutateAsync({
        email,
        role,
        department,
        personal_message: personalMessage || undefined,
      });
      setSuccessMsg(`Invitation sent to ${email} successfully.`);
      setTimeout(() => router.push("/user-management/invites"), 1500);
    } catch {
      // error surfaced via sendInvite.error
    }
  };

  return (
    <AppShell title="Invite user" subtitle="New users can only access Iroko AI via invitation">
      <div className="max-w-[600px] mx-auto lg:mx-0">
        <div className="card p-5 md:p-8">
          <h2 className="text-base font-semibold text-gray-900 mb-1">Send invitation</h2>
          <p className="text-[13px] text-gray-400 mb-6">
            The user will receive an email with a secure one-time invite link.
          </p>

          {successMsg && (
            <div className="mb-5">
              <StatusMessage type="success" text={successMsg} />
            </div>
          )}
          {sendInvite.isError && (
            <div className="mb-5">
              <StatusMessage
                type="error"
                text={(sendInvite.error as Error)?.message ?? "Failed to send invitation. Please try again."}
              />
            </div>
          )}

          <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
            <div>
              <label className="label-base" htmlFor="inv-email">Work email address</label>
              <input
                id="inv-email"
                type="email"
                className="input-base"
                placeholder="firstname.lastname@mtn.ng"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={sendInvite.isPending}
              />
              <p className="text-xs text-gray-300 mt-1.5">Must be an mtn.ng email address.</p>
            </div>

            <div>
              <label className="label-base" htmlFor="inv-role">Role</label>
              <select
                id="inv-role"
                className="input-base appearance-none cursor-pointer"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={sendInvite.isPending}
              >
                <option value="">Select a role…</option>
                <option value="superadmin">Super Admin</option>
                <option value="admin">Admin</option>
                <option value="noc_engineer">NOC Engineer</option>
                <option value="compliance_officer">Compliance Officer</option>
                <option value="dpo">DPO</option>
                <option value="procurement_manager">Procurement Manager</option>
                <option value="field_engineer">Field Engineer</option>
                <option value="care_agent">Care Agent</option>
                <option value="finance_analyst">Finance Analyst</option>
                <option value="viewer">Read Only</option>
              </select>
            </div>

            <div>
              <label className="label-base" htmlFor="inv-dept">Department</label>
              <select
                id="inv-dept"
                className="input-base appearance-none cursor-pointer"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                disabled={sendInvite.isPending}
              >
                <option>Network Operations</option>
                <option>Regulatory Affairs</option>
                <option>Legal & Compliance</option>
                <option>Procurement</option>
                <option>Network Rollout</option>
                <option>Customer Care</option>
                <option>Finance</option>
                <option>IT & Systems</option>
              </select>
            </div>

            <div>
              <label className="label-base" htmlFor="inv-msg">Personal message (optional)</label>
              <textarea
                id="inv-msg"
                className="input-base resize-y"
                rows={3}
                placeholder="e.g. Welcome to Iroko AI…"
                value={personalMessage}
                onChange={(e) => setPersonalMessage(e.target.value)}
                disabled={sendInvite.isPending}
              />
            </div>

            <div className="flex flex-col sm:flex-row gap-3 pt-1">
              <button
                type="submit"
                disabled={sendInvite.isPending}
                className="btn-primary flex-1 py-3 font-semibold order-1 sm:order-none flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {sendInvite.isPending ? (
                  <>
                    <LoadingSpinner size={15} />
                    Sending…
                  </>
                ) : (
                  "Send invitation"
                )}
              </button>
              <Link href="/user-management" className="btn-secondary py-3 px-5 text-center no-underline">
                Cancel
              </Link>
            </div>
          </form>
        </div>
      </div>
    </AppShell>
  );
}
