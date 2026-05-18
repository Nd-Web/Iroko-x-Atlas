"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import AppShell from "@/components/layout/AppShell";

const STORAGE_KEY = "iroko_connector_oauth";

function CallbackHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [message, setMessage] = useState("Completing connector setup…");

  useEffect(() => {
    const code = searchParams.get("code");

    if (!code) {
      setMessage("No authorization code found.");
      return;
    }

    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setMessage("Missing connector context. Please retry the connection.");
      return;
    }

    const payload = JSON.parse(stored) as {
      connector_type: string;
      redirect_uri: string;
      site_id?: string;
      display_name?: string;
      extra_config?: Record<string, unknown>;
    };

    const submit = async () => {
      try {
        const res = await fetch("/api/connectors", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            connector_type: payload.connector_type,
            auth_code: code,
            redirect_uri: payload.redirect_uri,
            site_id: payload.site_id,
            display_name: payload.display_name,
            extra_config: payload.extra_config,
          }),
        });

        if (!res.ok) {
          setMessage("Failed to create connector. Please try again.");
          return;
        }

        localStorage.removeItem(STORAGE_KEY);
        router.replace("/integrations");
      } catch {
        setMessage("Network error. Please try again.");
      }
    };

    void submit();
  }, [searchParams, router]);

  return <div className="card p-6 text-[13px] text-gray-500">{message}</div>;
}

export default function IntegrationsCallbackPage() {
  return (
    <AppShell title="Integrations" subtitle="Completing OAuth flow">
      <Suspense fallback={<div className="card p-6 text-[13px] text-gray-500">Loading…</div>}>
        <CallbackHandler />
      </Suspense>
    </AppShell>
  );
}
