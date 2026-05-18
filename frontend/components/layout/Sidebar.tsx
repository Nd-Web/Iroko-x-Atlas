"use client";
/**
 * components/layout/Sidebar.tsx — Premium dark sidebar redesign.
 * Collapsed icon-only state with tooltips, nav groups, Live pulse badge.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth, getInitials, formatRole } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

interface SidebarProps { open?: boolean; onClose?: () => void; }

// ── Icons ─────────────────────────────────────────────────────────────────────
const Icon = {
  dashboard: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/></svg>,
  chat: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5C4.41 1.5 1.5 3.96 1.5 7c0 1.22.45 2.35 1.21 3.27L1.5 13.5l3.5-1.05A7.3 7.3 0 0 0 8 12.5c3.59 0 6.5-2.46 6.5-5.5S11.59 1.5 8 1.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>,
  insights: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5a4.5 4.5 0 0 1 3.18 7.68L12 13.5H4l.82-4.32A4.5 4.5 0 0 1 8 1.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M6 13.5V15h4v-1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  search: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5"/><path d="M14 14l-3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  alerts: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5L14 4.5V8C14 11 11.5 13.6 8 14.5C4.5 13.6 2 11 2 8V4.5L8 1.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M8 6v2.5M8 10h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  network: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 13v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M5.5 13h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M4.5 8a4.5 4.5 0 0 1 7 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M2 5.5a8.5 8.5 0 0 1 12 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="8" cy="11" r="1" fill="currentColor"/></svg>,
  graph: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/><circle cx="3" cy="4" r="1.5" stroke="currentColor" strokeWidth="1.5"/><circle cx="13" cy="4" r="1.5" stroke="currentColor" strokeWidth="1.5"/><circle cx="13" cy="12" r="1.5" stroke="currentColor" strokeWidth="1.5"/><circle cx="3" cy="12" r="1.5" stroke="currentColor" strokeWidth="1.5"/><path d="M4.5 4.5L6.5 6.5M11.5 4.5L9.5 6.5M11.5 11.5L9.5 9.5M4.5 11.5L6.5 9.5" stroke="currentColor" strokeWidth="1.2"/></svg>,
  docs: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M9.5 1.5H4A1.5 1.5 0 0 0 2.5 3v10A1.5 1.5 0 0 0 4 14.5h8a1.5 1.5 0 0 0 1.5-1.5V6l-4-4.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M9.5 1.5V6H13.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M5.5 9h5M5.5 11.5h3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  connectors: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2.5 8h3M10.5 8h3M8 2.5v3M8 10.5v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/></svg>,
  compliance: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1.5L13.5 4v5.5C13.5 12.5 11 14.5 8 15.5c-3-1-5.5-3-5.5-6V4L8 1.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  audit: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2.5" y="1.5" width="11" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><path d="M5 6h6M5 8.5h6M5 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  users: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="5.5" r="2.5" stroke="currentColor" strokeWidth="1.5"/><path d="M1.5 14.5a5 5 0 0 1 10 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M12.5 7.5v4M10.5 9.5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  settings: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/><path d="M8 1v1.5m0 11V15M1 8h1.5m11 0H15M2.93 2.93l1.06 1.06m8 8 1.07 1.07M2.93 13.07l1.06-1.06m8-8 1.07-1.07" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>,
  logout: <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10.5 5.5V3.5A1 1 0 0 0 9.5 2.5H3.5A1 1 0 0 0 2.5 3.5v9a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/><path d="M6.5 8h7M11.5 5.5 14 8l-2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>,
};

const NAV = [
  {
    group: "Intelligence",
    items: [
      { label: "Dashboard",    href: "/dashboard",           icon: Icon.dashboard },
      { label: "Chat",         href: "/chat",                icon: Icon.chat },
      { label: "Insights",     href: "/insights",            icon: Icon.insights },
      { label: "Search",       href: "/search",              icon: Icon.search },
    ],
  },
  {
    group: "Operations",
    items: [
      { label: "Alerts",       href: "/agents/noc",          icon: Icon.alerts,   badge: "Live" },
      { label: "Network Intel",href: "/network-intelligence",icon: Icon.network,  badge: "Live" },
      { label: "Knowledge Graph",href:"/knowledge-graph",    icon: Icon.graph },
    ],
  },
  {
    group: "Data",
    items: [
      { label: "Documents",    href: "/documents",           icon: Icon.docs },
      { label: "Connectors",   href: "/connectors",          icon: Icon.connectors },
    ],
  },
  {
    group: "Compliance",
    items: [
      { label: "Compliance",   href: "/compliance",          icon: Icon.compliance },
      { label: "Audit Trail",  href: "/audit-trail",         icon: Icon.audit },
    ],
  },
  {
    group: "Admin",
    items: [
      { label: "User Mgmt",    href: "/user-management",     icon: Icon.users },
      { label: "Settings",     href: "/settings/profile",    icon: Icon.settings },
    ],
  },
];

export default function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);

  const w = collapsed ? 64 : 240;

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-white/[0.06] overflow-y-auto overflow-x-hidden sidebar-transition",
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
      )}
      style={{ width: w, background: "#080B14", minHeight: "100vh" }}
    >
      {/* Logo */}
      <div className={cn("flex items-center gap-3 py-4 border-b border-white/[0.06] shrink-0",
        collapsed ? "justify-center px-4" : "px-4")}>
        <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-[0_0_20px_rgba(59,123,246,0.4)]"
          style={{ background: "linear-gradient(135deg, #3B7BF6, #8B5CF6)" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 1.5L13 4.5V10.5L8 13.5L3 10.5V4.5L8 1.5Z" stroke="white" strokeWidth="1.4" strokeLinejoin="round"/>
            <circle cx="8" cy="7.5" r="1.75" fill="white"/>
          </svg>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="text-[13px] font-bold text-white tracking-tight leading-tight">Iroko AI</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[10px] text-[#6B7280]">MTN Nigeria</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold text-[#3B7BF6] bg-[#3B7BF6]/10 border border-[#3B7BF6]/20">Enterprise</span>
            </div>
          </div>
        )}
        <button onClick={() => setCollapsed(!collapsed)}
          className="ml-auto hidden lg:flex w-6 h-6 rounded-md items-center justify-center text-[#6B7280] hover:text-white hover:bg-white/5 transition-colors shrink-0"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d={collapsed ? "M4 2l4 4-4 4" : "M8 2L4 6l4 4"} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {/* Nav */}
      <div className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {NAV.map(({ group, items }) => (
          <div key={group} className="mb-1">
            {!collapsed && (
              <span className="block text-[9.5px] font-bold text-[#374151] uppercase tracking-[0.1em] px-2 mb-1 mt-3 first:mt-0">{group}</span>
            )}
            {items.map(({ label, href, icon, badge }) => {
              const active = isActive(href);
              return (
                <div key={href} className="relative group">
                  <Link href={href}
                    className={cn(
                      "flex items-center gap-2.5 px-2 py-2 rounded-lg text-[13px] font-medium transition-all duration-150 no-underline relative overflow-hidden",
                      collapsed ? "justify-center" : "",
                      active
                        ? "text-white bg-[#3B7BF6]/15 border-l-2 border-[#3B7BF6] pl-[6px]"
                        : "text-[#6B7280] hover:text-[#E5E7EB] hover:bg-white/[0.04]",
                    )}>
                    <span className={cn("shrink-0", active ? "text-[#3B7BF6]" : "")}>{icon}</span>
                    {!collapsed && <span className="truncate">{label}</span>}
                    {!collapsed && badge === "Live" && (
                      <span className="ml-auto flex items-center gap-1 text-[9px] font-bold text-emerald-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-live 2s ease infinite" }} />
                        Live
                      </span>
                    )}
                  </Link>
                  {/* Collapsed tooltip */}
                  {collapsed && (
                    <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center z-50">
                      <div className="bg-[#1a1d27] border border-white/10 text-[#E5E7EB] text-xs font-medium px-2.5 py-1.5 rounded-lg shadow-xl whitespace-nowrap">
                        {label}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* User footer */}
      <div className={cn("border-t border-white/[0.06] p-3 shrink-0 flex items-center gap-2.5", collapsed ? "justify-center" : "")}>
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#3B7BF6] to-[#8B5CF6] flex items-center justify-center text-[11px] font-bold text-white shrink-0">
          {user ? getInitials(user.full_name) : "?"}
        </div>
        {!collapsed && (
          <>
            <div className="flex-1 min-w-0">
              <div className="text-[12px] font-semibold text-[#E5E7EB] truncate">{user?.full_name ?? "Loading…"}</div>
              <div className="text-[10px] text-[#6B7280]">{user ? formatRole(user.role) : ""}</div>
            </div>
            <button onClick={() => logout()} title="Sign out"
              className="w-7 h-7 rounded-lg flex items-center justify-center text-[#6B7280] hover:text-red-400 hover:bg-red-400/10 transition-all duration-150 shrink-0">
              {Icon.logout}
            </button>
          </>
        )}
      </div>
      <style>{`@keyframes pulse-live{0%,100%{opacity:.4}50%{opacity:1}}`}</style>
    </aside>
  );
}
