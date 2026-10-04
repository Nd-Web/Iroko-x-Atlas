"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createConnector, type ConnectorType } from "@/lib/api";

type Status = "exchanging" | "success" | "error";

function CallbackHandler() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<Status>("exchanging");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state"); // "{user_id}:{connector_type}"
    const error = params.get("error");
    const errorDescription = params.get("error_description");

    if (error) {
      setStatus("error");
      setMessage(errorDescription ?? error);
      return;
    }

    if (!code || !state) {
      setStatus("error");
      setMessage("Missing code or state in callback URL.");
      return;
    }

    const connectorType = (state.split(":")[1] ?? "onedrive") as ConnectorType;
    const redirectUri = `${window.location.origin}/connectors/callback`;

    createConnector(code, connectorType, redirectUri)
      .then(() => {
        setStatus("success");
        setMessage(`${connectorType} connected successfully.`);
        setTimeout(() => router.push("/dashboard"), 1800);
      })
      .catch((err: Error) => {
        setStatus("error");
        setMessage(err.message ?? "Failed to complete connector setup.");
      });
  }, [params, router]);

  return (
    <>
      {status === "exchanging" && (
        <>
          <div className="w-8 h-8 border-2 border-[#FFCC00] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-white font-semibold text-lg">Connecting your drive…</p>
          <p className="text-zinc-400 text-sm mt-2">Exchanging authorisation token</p>
        </>
      )}

      {status === "success" && (
        <>
          <div className="text-4xl mb-4">✓</div>
          <p className="text-white font-semibold text-lg">Connected</p>
          <p className="text-zinc-400 text-sm mt-2">{message}</p>
          <p className="text-zinc-500 text-xs mt-4">Returning to dashboard…</p>
        </>
      )}

      {status === "error" && (
        <>
          <div className="text-4xl mb-4">✕</div>
          <p className="text-red-400 font-semibold text-lg">Connection failed</p>
          <p className="text-zinc-400 text-sm mt-2 break-words">{message}</p>
          <button
            onClick={() => router.push("/dashboard")}
            className="mt-6 bg-[#FFCC00] hover:bg-yellow-300 text-black font-semibold px-6 py-2.5 rounded-lg text-sm transition-colors"
          >
            Back to dashboard
          </button>
        </>
      )}
    </>
  );
}

export default function ConnectorCallbackPage() {
  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-10 w-full max-w-md text-center">
        <div className="w-14 h-14 rounded-xl bg-[#FFCC00] flex items-center justify-center font-black text-black text-2xl mx-auto mb-6">
          A
        </div>
        <Suspense
          fallback={
            <div className="w-8 h-8 border-2 border-[#FFCC00] border-t-transparent rounded-full animate-spin mx-auto" />
          }
        >
          <CallbackHandler />
        </Suspense>
      </div>
    </div>
  );
}
