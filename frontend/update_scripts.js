const fs = require('fs');

const userManagementCode = `"use client";

import Link from "next/link";
import { useState, useEffect } from "react";

const USERS = [
  { id: "u1", name: "Adaeze Okonkwo",  email: "adaeze.okonkwo@mtn.ng",  role: "Super Admin",         dept: "Network Operations", region: "Lagos", status: "active",    lastActive: "Just now"   },
  { id: "u2", name: "Tunde Adeyemi",   email: "tunde.adeyemi@mtn.ng",   role: "Compliance Officer",  dept: "Regulatory Affairs", region: "Lagos", status: "active",    lastActive: "2 hr ago"   },
  { id: "u3", name: "Ifeoma Chukwu",   email: "ifeoma.chukwu@mtn.ng",   role: "DPO",                 dept: "Legal & Compliance", region: "Abuja", status: "active",    lastActive: "Yesterday"  },
  { id: "u4", name: "Chidi Eze",       email: "chidi.eze@mtn.ng",       role: "Procurement Manager", dept: "Procurement",        region: "Lagos", status: "active",    lastActive: "3 days ago" },
  { id: "u5", name: "Musa Garba",      email: "musa.garba@mtn.ng",      role: "Field Engineer",      dept: "Network Rollout",    region: "Kano",  status: "active",    lastActive: "1 hr ago"   },
  { id: "u6", name: "Bukola Adesanya", email: "bukola.adesanya@mtn.ng", role: "Care Agent",          dept: "Customer Care",      region: "Lagos", status: "active",    lastActive: "4 hr ago"   },
  { id: "u7", name: "Emeka Obi",       email: "emeka.obi@mtn.ng",       role: "NOC Engineer",        dept: "Network Operations", region: "Lagos", status: "invited",   lastActive: "Never"      },
  { id: "u8", name: "Fatima Bello",    email: "fatima.bello@mtn.ng",    role: "Finance Analyst",     dept: "Finance",            region: "Abuja", status: "suspended", lastActive: "2 weeks ago" },
];

const ROLE_COLORS: Record<string, { bg: string; color: string }> = {
  "Super Admin":         { bg: "var(--color-danger-50)",  color: "var(--color-danger-700)"  },
  "Compliance Officer":  { bg: "var(--color-success-50)", color: "var(--color-success-700)" },
  "DPO":                 { bg: "var(--color-success-50)", color: "var(--color-success-700)" },
  "Procurement Manager": { bg: "var(--color-warning-50)", color: "var(--color-warning-700)" },
  "Field Engineer":      { bg: "var(--color-info-50)",    color: "var(--color-info-700)"    },
  "Care Agent":          { bg: "var(--color-info-50)",    color: "var(--color-info-700)"    },
  "NOC Engineer":        { bg: "var(--color-brand-50)",   color: "var(--color-brand-700)"   },
  "Finance Analyst":     { bg: "var(--color-gray-100)",   color: "var(--color-gray-600)"    },
};

const STATUS: Record<string, { dot: string; label: string }> = {
  active:    { dot: "var(--color-success-500)", label: "Active"    },
  invited:   { dot: "var(--color-warning-500)", label: "Invited"   },
  suspended: { dot: "var(--color-gray-300)",    label: "Suspended" },
};

const STATS = [
  { label: "Total users",     value: "8", sub: "across all roles",     accent: "#4A55D4" },
  { label: "Active",          value: "6", sub: "currently enabled",    accent: "#17B26A" },
  { label: "Pending invites", value: "3", sub: "awaiting acceptance",  accent: "#F79009" },
  { label: "Suspended",       value: "1", sub: "access revoked",       accent: "#F04438" },
];

const COL = "2fr 1.4fr 1.4fr 90px 130px 110px";

export default function UserManagementContent() {
  const [suspendTarget, setSuspendTarget] = useState<typeof USERS[0] | null>(null);

  useEffect(() => {
    if (!suspendTarget) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setSuspendTarget(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [suspendTarget]);

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-4 gap-[14px]">
        {STATS.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-[18px] px-5">
            <div className="absolute top-0 inset-x-0 h-[2px] opacity-70" style={{ background: s.accent }} />
            <div className="text-[28px] font-bold text-gray-900 tracking-[-0.04em] leading-none mb-[5px]">{s.value}</div>
            <div className="text-[13px] font-medium text-gray-500 mb-[2px]">{s.label}</div>
            <div className="text-[11.5px] text-gray-300">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* User table */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-[14px] border-b border-border-default">
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">All users</h2>
          <div className="flex gap-2">
            <div className="relative">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="absolute left-[10px] top-1/2 -translate-y-1/2 text-gray-300 pointer-events-none">
                <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.4" />
                <path d="M11 11l-2.5-2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
              <input type="text" placeholder="Search users…" className="input-base w-[210px] py-[7px] pr-3 pl-[30px]" />
            </div>
            <select className="input-base w-auto py-[7px] px-3 appearance-none">
              <option>All roles</option>
              <option>Super Admin</option>
              <option>NOC Engineer</option>
              <option>Compliance Officer</option>
              <option>Field Engineer</option>
            </select>
          </div>
        </div>

        <div className="grid py-[9px] px-5 bg-gray-50 border-b border-border-default gap-3" style={{ gridTemplateColumns: COL }}>
          {["User", "Role", "Department", "Region", "Status", ""].map((h) => (
            <span key={h} className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.055em]">{h}</span>
          ))}
        </div>

        {USERS.map((user) => {
          const roleStyle = ROLE_COLORS[user.role] || { bg: "var(--color-gray-100)", color: "var(--color-gray-600)" };
          const st = STATUS[user.status as keyof typeof STATUS];
          const initials = user.name.split(" ").map((n) => n[0]).join("").slice(0, 2);
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
                <div>
                  <div className="text-[13.5px] font-medium text-gray-800 leading-[1.2]">{user.name}</div>
                  <div className="text-[11.5px] text-gray-400">{user.email}</div>
                </div>
              </div>

              <span className="text-[11.5px] font-semibold px-2 py-[2px] rounded-full w-fit" style={{ color: roleStyle.color, background: roleStyle.bg }}>
                {user.role}
              </span>

              <span className="text-[13px] text-gray-500">{user.dept}</span>
              <span className="text-[13px] text-gray-500">{user.region}</span>

              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: st.dot }} />
                <div>
                  <span className="text-[12.5px] text-gray-600">{st.label}</span>
                  {user.status === "active" && (
                    <div className="text-[11px] text-gray-300">{user.lastActive}</div>
                  )}
                </div>
              </div>

              <div className="flex gap-1.5 justify-end">
                <Link href={\`/user-management/\${user.id}\`} className="btn-secondary py-1 px-[10px] text-xs no-underline" onClick={(e) => e.stopPropagation()}>
                  Edit
                </Link>
                {user.status === "active" && (
                  <button className="btn-secondary py-1 px-[10px] text-xs text-danger-600 border-danger-100" onClick={(e) => { e.stopPropagation(); setSuspendTarget(user); }}>
                    Suspend
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {suspendTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setSuspendTarget(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "440px" }}
            onClick={e => e.stopPropagation()}
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
                <div>
                  <h3 className="text-[14px] font-semibold text-gray-900 leading-tight">{suspendTarget.name}</h3>
                  <p className="text-[12px] text-gray-500 mt-0.5">{suspendTarget.email}</p>
                </div>
              </div>
              
              <p className="text-[13px] text-gray-600 leading-[1.5] m-0">
                This will immediately revoke {suspendTarget.name.split(" ")[0]}'s access to Iroko AI. They will not be able to log in until their account is reactivated. All active sessions will be terminated.
              </p>
              
              <div>
                <label className="label-base block mb-1.5">Reason for suspension (optional)</label>
                <textarea 
                  className="input-base w-full h-[80px] resize-none" 
                  placeholder="e.g. Employee offboarding, compliance investigation..." 
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setSuspendTarget(null)}>Cancel</button>
              <button 
                className="bg-danger-600 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-danger-700 transition-colors"
                onClick={() => setSuspendTarget(null)}
              >
                Suspend account
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
`;

fs.writeFileSync("components/pages/UserManagementContent.tsx", userManagementCode);
