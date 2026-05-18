"use client";

import { useState, useEffect, useCallback } from "react";
import AppShell from "@/components/layout/AppShell";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

// ─── Types ────────────────────────────────────────────────────────────────────

type ConnectorType = "onedrive" | "sharepoint" | "microsoft_teams" | "slack" | "servicenow"; // servicenow kept for API compatibility
type ConnectorStatus = "active" | "pending" | "error" | "disconnected" | "syncing";

interface Connector {
  id: string;
  connector_type: ConnectorType;
  display_name: string;
  status: ConnectorStatus;
  last_sync_at?: string;
  created_at: string;
  document_count?: number;
  extra_config?: Record<string, unknown>;
}

interface ConnectorsResponse {
  connectors?: Connector[];
  items?: Connector[];
}

// ─── Static connector metadata ────────────────────────────────────────────────

const CONNECTOR_TYPES: {
  type: ConnectorType;
  name: string;
  description: string;
  color: string;
  bg: string;
  icon: React.ReactNode;
}[] = [
  {
    type: "onedrive",
    name: "OneDrive",
    description: "Sync files and documents from Microsoft OneDrive",
    color: "#0078D4",
    bg: "#EBF4FF",
    icon: (
      // OneDrive logo — two overlapping clouds in Microsoft blue
      <svg width="22" height="16" viewBox="0 0 21 14" fill="none">
        <path d="M12.9 4.5A6.5 6.5 0 001.2 9.6L1 9.5A4 4 0 005 14h6.7L8.3 9.5A5.5 5.5 0 0112.9 4.5z" fill="#0364B8"/>
        <path d="M12.9 4.5A5 5 0 008.1 2a5 5 0 00-4.7 3.3 3.5 3.5 0 00.9 6.2L7.6 7A5.5 5.5 0 0112.9 4.5z" fill="#0078D4"/>
        <path d="M19.5 8.2a4.5 4.5 0 00-3.8-2.2 4.4 4.4 0 00-2.8 1l2.7 5h3.7a2.5 2.5 0 00.2-4.8z" fill="#1490DF"/>
        <path d="M5 14h14.5a2.5 2.5 0 000-5h-.2L15.6 12l-4.3-7.5A5.5 5.5 0 008 9.6L5 14z" fill="#28A8E8"/>
      </svg>
    ),
  },
  {
    type: "sharepoint",
    name: "SharePoint",
    description: "Connect to SharePoint sites and document libraries",
    color: "#038387",
    bg: "#E6F7F7",
    icon: (
      // SharePoint logo — two overlapping circles with S cutout
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <circle cx="9" cy="9" r="6.5" fill="#038387"/>
        <circle cx="14" cy="13" r="5.5" fill="#1BBBBB"/>
        <circle cx="14" cy="13" r="3.2" fill="white" fillOpacity="0.15"/>
        <path d="M7 8.5c0-.83.67-1.5 1.5-1.5h3c.55 0 1 .45 1 1s-.45 1-1 1H9c-.28 0-.5.22-.5.5s.22.5.5.5h2c.83 0 1.5.67 1.5 1.5S11.83 13 11 13H8c-.55 0-1-.45-1-1s.45-1 1-1h3c.28 0 .5-.22.5-.5s-.22-.5-.5-.5H9C8.17 10 7 9.33 7 8.5z" fill="white"/>
      </svg>
    ),
  },
  {
    type: "microsoft_teams",
    name: "Microsoft Teams",
    description: "Import conversations and files from Teams channels",
    color: "#5558AF",
    bg: "#EEEEF7",
    icon: (
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
        <rect x="2" y="8" width="12" height="11" rx="2.5" fill="#5558AF"/>
        <path d="M6 12h4M8 10v6" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
        <circle cx="16" cy="7" r="2.5" fill="#7B83EB"/>
        <path d="M12.5 10.5h5a1 1 0 011 1v4a1 1 0 01-1 1h-5" fill="#7B83EB"/>
        <path d="M12.5 10.5h5a1 1 0 011 1v4a1 1 0 01-1 1h-5" stroke="#5558AF" strokeWidth="0.5"/>
      </svg>
    ),
  },
  {
    type: "slack",
    name: "Slack",
    description: "Sync messages and files from Slack channels and workspaces",
    color: "#4A154B",
    bg: "#FDF0FF",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52z" fill="#E01E5A"/>
        <path d="M6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522z" fill="#E01E5A"/>
        <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834z" fill="#36C5F0"/>
        <path d="M8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521z" fill="#36C5F0"/>
        <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522z" fill="#2EB67D"/>
        <path d="M17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522z" fill="#2EB67D"/>
        <path d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522z" fill="#ECB22E"/>
        <path d="M15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523z" fill="#ECB22E"/>
      </svg>
    ),
  },
];

const STORAGE_KEY = "iroko_connector_oauth";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusBadge(status: ConnectorStatus) {
  const map: Record<ConnectorStatus, { label: string; cls: string }> = {
    active:       { label: "Active",       cls: "bg-success-50 text-success-700" },
    pending:      { label: "Pending",      cls: "bg-warning-50 text-warning-700" },
    syncing:      { label: "Syncing",      cls: "bg-brand-50 text-brand-700" },
    error:        { label: "Error",        cls: "bg-danger-50 text-danger-700" },
    disconnected: { label: "Disconnected", cls: "bg-gray-100 text-gray-500" },
  };
  const s = map[status] ?? map.disconnected;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${s.cls}`}>
      {s.label}
    </span>
  );
}

function formatRelative(iso?: string) {
  if (!iso) return "Never";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 2) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function connectorMeta(type: ConnectorType) {
  return CONNECTOR_TYPES.find((c) => c.type === type) ?? CONNECTOR_TYPES[0];
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<ConnectorType | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState<Connector | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchConnectors = useCallback(async () => {
    try {
      const res = await fetch("/api/connectors");
      if (!res.ok) { setConnectors([]); return; }
      const data: ConnectorsResponse = await res.json();
      const list = data.connectors ?? data.items ?? (Array.isArray(data) ? (data as Connector[]) : []);
      setConnectors(list);
    } catch {
      setConnectors([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchConnectors(); }, [fetchConnectors]);

  const handleConnect = async (type: ConnectorType, instanceUrl?: string) => {
    setConnecting(type);
    setError(null);
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const redirectUri = `${window.location.origin}/integrations/callback`;
      const params = new URLSearchParams({ connector_type: type, redirect_uri: redirectUri });
      if (instanceUrl) params.set("instance_url", instanceUrl);

      const res = await fetch(`/api/connectors/auth-url?${params.toString()}`);
      if (!res.ok) { setError("Failed to get authorization URL. Please try again."); return; }

      const data = await res.json() as { auth_url?: string; authorization_url?: string; url?: string };
      const authUrl = data.auth_url ?? data.authorization_url ?? data.url;
      if (!authUrl) { setError("Invalid response from server. Please try again."); return; }

      localStorage.setItem(STORAGE_KEY, JSON.stringify({ connector_type: type, redirect_uri: redirectUri }));
      window.location.href = authUrl;
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setConnecting(null);
    }
  };

  const handleSync = async (connector: Connector) => {
    setSyncing(connector.id);
    try {
      await fetch(`/api/connectors/${connector.id}/sync`, { method: "POST" });
      await fetchConnectors();
    } catch {
      // silent — connector list will reflect current state
    } finally {
      setSyncing(null);
    }
  };

  const handleDisconnect = async (connector: Connector) => {
    setDisconnecting(connector.id);
    setConfirmDisconnect(null);
    try {
      await fetch(`/api/connectors/${connector.id}`, { method: "DELETE" });
      setConnectors((prev) => prev.filter((c) => c.id !== connector.id));
    } catch {
      setError("Failed to disconnect. Please try again.");
    } finally {
      setDisconnecting(null);
    }
  };

  // ── Derived stats ──
  const total      = connectors.length;
  const active     = connectors.filter((c) => c.status === "active").length;
  const pending    = connectors.filter((c) => c.status === "pending" || c.status === "syncing").length;
  const errors     = connectors.filter((c) => c.status === "error").length;
  const totalDocs  = connectors.reduce((s, c) => s + (c.document_count ?? 0), 0);

  const stats = [
    { label: "Connected sources", value: total,                    accent: "#4A55D4" },
    { label: "Active",            value: active,                   accent: "#17B26A" },
    { label: "Pending",           value: pending,                  accent: "#F79009" },
    { label: "Documents ingested",value: totalDocs.toLocaleString(), accent: "#2E90FA" },
  ];

  const connectedTypes = new Set(connectors.map((c) => c.connector_type));

  return (
    <AppShell title="Integrations" subtitle="Connect data sources · sync documents · manage connectors">
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-danger-50 border border-danger-200 text-[13px] text-danger-700">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="shrink-0">
            <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.4"/>
            <path d="M7 4v3M7 9.5h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-danger-400 hover:text-danger-600">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        {stats.map((s) => (
          <div key={s.label} className="card relative overflow-hidden py-4.5 px-5">
            <div className="absolute top-0 inset-x-0 h-0.5" style={{ background: s.accent }} />
            <div className="text-[28px] font-bold text-gray-900 tracking-[-0.04em] leading-none mb-1.25">
              {loading ? <span className="inline-block w-8 h-7 bg-gray-100 rounded animate-pulse" /> : s.value}
            </div>
            <div className="text-[13px] font-medium text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Connected sources */}
      <div className="card">
        <div className="px-5 py-4 border-b border-border-default flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">Connected sources</h2>
            <p className="text-xs text-gray-400 mt-0.5">Manage your active integrations</p>
          </div>
        </div>

        {loading ? (
          <div className="px-5 py-10 flex justify-center text-brand-600">
            <LoadingSpinner size={20} />
          </div>
        ) : connectors.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <div className="size-10 rounded-full bg-gray-50 flex items-center justify-center mx-auto mb-3">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M9 2v5M9 11v5M2 9h5m6 0h3" stroke="#D1D5DB" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <p className="text-[13px] text-gray-400">No integrations connected yet</p>
            <p className="text-[12px] text-gray-300 mt-1">Connect a source below to start ingesting documents</p>
          </div>
        ) : (
          <div className="divide-y divide-border-default">
            {connectors.map((c) => {
              const meta = connectorMeta(c.connector_type);
              return (
                <div key={c.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors">
                  {/* icon */}
                  <div className="size-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: meta.bg }}>
                    {meta.icon}
                  </div>
                  {/* name + type */}
                  <div className="flex-1 min-w-0">
                    <div className="text-[13.5px] font-semibold text-gray-800 truncate">{c.display_name || meta.name}</div>
                    <div className="text-[11.5px] text-gray-400 mt-px">{meta.name} · {c.document_count != null ? `${c.document_count.toLocaleString()} docs` : "—"}</div>
                  </div>
                  {/* status */}
                  <div className="hidden md:block shrink-0">{statusBadge(c.status)}</div>
                  {/* last sync */}
                  <div className="hidden lg:block shrink-0 text-[12px] text-gray-400 w-20 text-right">
                    {formatRelative(c.last_sync_at)}
                  </div>
                  {/* actions */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => handleSync(c)}
                      disabled={syncing === c.id || c.status === "syncing"}
                      title="Sync now"
                      className="size-7 rounded-md flex items-center justify-center text-gray-400 hover:text-brand-600 hover:bg-brand-50 transition-colors disabled:opacity-40"
                    >
                      <svg width="13" height="13" viewBox="0 0 13 13" fill="none" className={syncing === c.id ? "animate-spin" : ""}>
                        <path d="M11 6.5A4.5 4.5 0 012.5 9M2 6.5A4.5 4.5 0 0110.5 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                        <path d="M10.5 1.5v2.5H8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                    <button
                      onClick={() => setConfirmDisconnect(c)}
                      disabled={disconnecting === c.id}
                      title="Disconnect"
                      className="size-7 rounded-md flex items-center justify-center text-gray-400 hover:text-danger-600 hover:bg-danger-50 transition-colors disabled:opacity-40"
                    >
                      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                        <path d="M2 2l9 9M11 2L2 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Available connectors */}
      <div>
        <div className="mb-3.5">
          <h2 className="text-[15px] font-semibold text-gray-900 tracking-[-0.01em]">Add a source</h2>
          <p className="text-xs text-gray-400 mt-0.5">OAuth-based — you'll be redirected to authorize access</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {CONNECTOR_TYPES.map((ct) => {
            const alreadyConnected = connectedTypes.has(ct.type);
            const isConnecting = connecting === ct.type;
            return (
              <div key={ct.type} className="card px-5 py-4.5 flex flex-col gap-3">
                <div className="flex items-start gap-3">
                  <div className="size-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: ct.bg }}>
                    {ct.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[13.5px] font-semibold text-gray-800">{ct.name}</span>
                      {alreadyConnected && (
                        <span className="text-[10px] font-bold px-1.5 py-px rounded-full bg-success-50 text-success-700">Connected</span>
                      )}
                    </div>
                    <p className="text-[12px] text-gray-400 mt-0.75 leading-normal">{ct.description}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleConnect(ct.type)}
                  disabled={isConnecting}
                  className={[
                    "w-full py-1.75 px-3 rounded-lg text-[12.5px] font-semibold transition-colors flex items-center justify-center gap-2",
                    alreadyConnected
                      ? "bg-gray-50 text-gray-500 border border-border-default hover:bg-gray-100 disabled:opacity-60"
                      : "btn-primary disabled:opacity-70",
                  ].join(" ")}
                >
                  {isConnecting && <LoadingSpinner size={13} />}
                  {isConnecting
                    ? "Redirecting…"
                    : alreadyConnected
                    ? "Connect another account"
                    : `Connect ${ct.name}`}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Disconnect confirm modal */}
      {confirmDisconnect && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setConfirmDisconnect(null)}>
          <div className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" />
          <div
            className="relative bg-white rounded-xl shadow-lg border border-border-default w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-[15px] font-semibold text-gray-900 mb-2">Disconnect integration?</h2>
            <p className="text-[13px] text-gray-500 leading-[1.6]">
              This will remove <strong>{confirmDisconnect.display_name || connectorMeta(confirmDisconnect.connector_type).name}</strong> and stop document syncing.
              Previously ingested documents will remain in your knowledge base.
            </p>
            <div className="flex gap-2 mt-5">
              <button
                className="flex-1 btn-secondary"
                onClick={() => setConfirmDisconnect(null)}
              >
                Cancel
              </button>
              <button
                className="flex-1 py-2 px-4 rounded-lg bg-danger-600 text-white text-[13px] font-semibold hover:bg-danger-700 transition-colors"
                onClick={() => handleDisconnect(confirmDisconnect)}
              >
                Disconnect
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
