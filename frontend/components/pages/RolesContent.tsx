"use client";

import { useState, useEffect } from "react";

const COL = "160px 1fr 130px 150px 80px";

const ROLES = [
  { name: "Super Admin", agents: "All", maxClass: "Restricted", users: 1 },
  { name: "Admin", agents: "All", maxClass: "Confidential", users: 2 },
  { name: "NOC Engineer", agents: "NOC, Contracts", maxClass: "Internal", users: 2 },
  { name: "Compliance Officer", agents: "Compliance, Contracts", maxClass: "Restricted", users: 1 },
  { name: "DPO", agents: "Compliance", maxClass: "Restricted", users: 1 },
  { name: "Field Engineer", agents: "Field, NOC", maxClass: "Internal", users: 2 },
  { name: "Care Agent", agents: "Care", maxClass: "Internal", users: 3 },
  { name: "Finance Analyst", agents: "Contracts", maxClass: "Confidential", users: 1 },
  { name: "Read Only", agents: "NOC, Care (read-only)", maxClass: "Public", users: 0 },
];

export default function RolesContent() {
  const [roleModal, setRoleModal] = useState<{ mode: "create" | "visit", role?: typeof ROLES[0] } | null>(null);

  useEffect(() => {
    if (!roleModal) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setRoleModal(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [roleModal]);

  return (
    <>
      <div className="card overflow-hidden">
        <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
          <h2 className="text-[15px] font-semibold text-gray-800">Role definitions</h2>
          <button 
            className="btn-secondary py-[7px] px-3 text-[13px]"
            onClick={() => setRoleModal({ mode: "create" })}
          >
            + New role
          </button>
        </div>
        <div
          className="grid py-[10px] px-5 bg-gray-50 border-b border-border-default gap-3"
          style={{ gridTemplateColumns: COL }}
        >
          {["Role", "Agent access", "Max classification", "Users", ""].map((h) => (
            <span
              key={h}
              className="text-[11px] font-semibold text-gray-400 uppercase tracking-[0.06em]"
            >
              {h}
            </span>
          ))}
        </div>
        {ROLES.map((role) => (
          <div
            key={role.name}
            className="grid items-center py-[13px] px-5 gap-3 border-b border-border-default cursor-pointer hover:bg-gray-50 transition-colors"
            style={{ gridTemplateColumns: COL }}
          >
            <span className="text-[13px] font-semibold text-gray-700">{role.name}</span>
            <span className="text-xs text-gray-500">{role.agents}</span>
            <span
              className={`text-[11px] font-semibold px-2 py-[2px] rounded-full w-fit ${
                role.maxClass === "Restricted"
                  ? "text-danger-700 bg-danger-50"
                  : role.maxClass === "Confidential"
                  ? "text-warning-700 bg-warning-50"
                  : role.maxClass === "Internal"
                  ? "text-info-700 bg-info-50"
                  : "text-success-700 bg-success-50"
              }`}
            >
              {role.maxClass}
            </span>
            <span className="text-[13px] text-gray-400">
              {role.users} {role.users === 1 ? "user" : "users"}
            </span>
            <button 
              className="btn-secondary py-1 px-[10px] text-xs"
              onClick={(e) => { e.stopPropagation(); setRoleModal({ mode: "visit", role }); }}
            >
              Edit
            </button>
          </div>
        ))}
      </div>

      {roleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" onClick={() => setRoleModal(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default flex flex-col w-full max-h-[88vh] overflow-hidden"
            style={{ maxWidth: "560px" }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default shrink-0">
              <h2 className="text-sm font-semibold text-gray-900">
                {roleModal.mode === "create" ? "Create new role" : `Edit ${roleModal.role?.name}`}
              </h2>
              <button onClick={() => setRoleModal(null)} className="size-7 flex items-center justify-center rounded-md hover:bg-gray-100 text-gray-400">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-4">
              <div>
                <label className="label-base block mb-1.5">Role name</label>
                <input type="text" className="input-base w-full" defaultValue={roleModal.role?.name || ""} placeholder="e.g. Support Manager" />
              </div>
              
              <div>
                <label className="label-base block mb-1.5">Max data classification access</label>
                <select className="input-base w-full" defaultValue={roleModal.role?.maxClass || "Internal"}>
                  <option value="Restricted">Restricted</option>
                  <option value="Confidential">Confidential</option>
                  <option value="Internal">Internal</option>
                  <option value="Public">Public</option>
                </select>
                <p className="text-[11px] text-gray-400 mt-1.5">Highest level of sensitive data this role can access.</p>
              </div>
              
              <div className="pt-2 border-t border-border-default mt-2">
                <label className="label-base block mb-3">Agent Access</label>
                <div className="grid grid-cols-2 gap-3">
                  {["NOC", "Contracts", "Compliance", "Field", "Care"].map(ag => (
                    <label key={ag} className="flex items-center gap-2 text-sm text-gray-700">
                      <input 
                        type="checkbox" 
                        defaultChecked={roleModal.mode === "visit" ? roleModal.role?.agents.includes("All") || roleModal.role?.agents.includes(ag) : false} 
                        className="rounded border-gray-300 text-brand-600 focus:ring-brand-500" 
                      />
                      {ag} Agent
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border-default shrink-0">
              <button className="btn-secondary" onClick={() => setRoleModal(null)}>Cancel</button>
              <button 
                className="btn-primary"
                onClick={() => setRoleModal(null)}
              >
                {roleModal.mode === "create" ? "Create role" : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
