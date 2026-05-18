"use client";

import { useEffect, useState } from "react";
import type { ActivityFeedResponse, ActivityItem } from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function getInitials(name: string): string {
  return (name ?? "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join("");
}

function relativeTime(dateStr: string): string {
  const ms   = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1)  return "just now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}

function deriveStatus(item: ActivityItem): { label: string; cls: string } {
  const a = (item.action ?? "").toLowerCase();
  const r = (item.resource ?? "").toLowerCase();

  if (a.includes("logged in") || a.includes("login"))       return { label: "Login",        cls: "badge-info"    };
  if (a.includes("uploaded"))                                return { label: "Uploaded",      cls: "badge-info"    };
  if (a.includes("deleted"))                                 return { label: "Deleted",       cls: "badge-danger"  };
  if (a.includes("acknowledged"))                            return { label: "Acknowledged",  cls: "badge-success" };
  if (a.includes("resolved"))                                return { label: "Resolved",      cls: "badge-success" };
  if (a.includes("published"))                               return { label: "Published",     cls: "badge-success" };
  if (a.includes("invited"))                                 return { label: "Invited",       cls: "badge-info"    };
  if (a.includes("escalat"))                                 return { label: "Escalated",     cls: "badge-danger"  };
  if (a.includes("review"))                                  return { label: "Review",        cls: "badge-warning" };
  if (r.startsWith("alerts"))                                return { label: "Alert",         cls: "badge-warning" };
  if (r.startsWith("documents"))                             return { label: "Document",      cls: "badge-info"    };
  if (r.startsWith("auth"))                                  return { label: "Auth",          cls: "badge-info"    };
  return { label: "Activity", cls: "badge-info" };
}

// ── Row ───────────────────────────────────────────────────────────────────────

function ActivityRow({ item }: { item: ActivityItem }) {
  const { label, cls } = deriveStatus(item);
  const initials = getInitials(item.user_name);
  const time     = item.timestamp ? relativeTime(item.timestamp) : "";

  // Build a subtitle from details when useful
  let sub = item.action;
  if (item.details?.contract)   sub = item.details.contract;
  else if (item.details?.filename) sub = item.details.filename;

  return (
    <div className="flex items-center gap-[10px] py-[11px] border-b border-border-default last:border-0">
      <div className="size-[30px] rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[10.5px] font-bold shrink-0 tracking-[0.02em]">
        {initials}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-semibold text-gray-800 leading-[1.2] mb-0.5 truncate">{item.user_name}</div>
        <div className="text-[11.5px] text-gray-400 truncate">{sub}</div>
      </div>
      <div className="flex flex-col items-end gap-1 shrink-0">
        <span className={`badge ${cls} text-[10px] py-0.5`}>{label}</span>
        <span className="text-[11px] text-gray-300">{time}</span>
      </div>
    </div>
  );
}

// ── Static fallback ───────────────────────────────────────────────────────────

const FALLBACK: ActivityItem[] = [
  { id: "1", user_name: "Adaeze O.",     user_email: "", action: "published report",     resource: "documents", details: {}, timestamp: new Date(Date.now() - 8  * 60000).toISOString() },
  { id: "2", user_name: "Kenechukwu M.", user_email: "", action: "review compliance",    resource: "documents", details: {}, timestamp: new Date(Date.now() - 25 * 60000).toISOString() },
  { id: "3", user_name: "Ruth Taiwo",    user_email: "", action: "escalated field case", resource: "alerts",    details: {}, timestamp: new Date(Date.now() - 60 * 60000).toISOString() },
  { id: "4", user_name: "Seyi Omoregie", user_email: "", action: "uploaded contract dataset", resource: "documents", details: {}, timestamp: new Date(Date.now() - 120 * 60000).toISOString() },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ActivityFeed() {
  const [items, setItems] = useState<ActivityItem[] | null>(null);

  useEffect(() => {
    fetch("/api/analytics/activity?limit=5")
      .then((r) => r.json())
      .then((data: ActivityFeedResponse) => {
        if (Array.isArray(data?.activities)) setItems(data.activities);
      })
      .catch(() => {});
  }, []);

  const list = items ?? FALLBACK;

  return (
    <div className="flex flex-col">
      {list.map((item) => (
        <ActivityRow key={item.id} item={item} />
      ))}
    </div>
  );
}
