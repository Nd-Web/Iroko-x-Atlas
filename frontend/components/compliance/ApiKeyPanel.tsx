"use client";

import { useEffect, useState } from "react";

export default function ApiKeyPanel() {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load any existing key from the session user (same-origin proxy, cookie auth).
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/auth/me");
        if (!res.ok) return;
        const user = await res.json();
        if (user?.api_key) setApiKey(user.api_key as string);
      } catch {
        // Non-critical — the user can still generate a key.
      }
    })();
  }, []);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    try {
      // Same-origin Next.js proxy forwards the httpOnly cookie as a Bearer token.
      const res = await fetch("/api/auth/generate-key", { method: "POST" });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data: { api_key: string } = await res.json();
      setApiKey(data.api_key);
      setVisible(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate key");
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy() {
    if (!apiKey) return;
    await navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const masked = apiKey
    ? `${apiKey.slice(0, 12)}${"•".repeat(Math.max(0, apiKey.length - 16))}${apiKey.slice(-4)}`
    : null;

  return (
    <div className="card overflow-hidden">
      <div className="flex justify-between items-center px-5 py-4 border-b border-border-default">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 tracking-[-0.01em]">
            Compliance API key
          </h2>
          <p className="text-[11.5px] text-gray-400 mt-[2px]">
            Use with{" "}
            <code className="bg-gray-100 px-1 rounded text-[11px]">
              POST /api/v1/compliance/check
            </code>
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="btn-secondary py-[5px] px-3 text-xs disabled:opacity-50"
        >
          {loading ? "Generating…" : apiKey ? "Regenerate" : "Generate key"}
        </button>
      </div>

      <div className="px-5 py-4">
        {error && (
          <p className="text-xs text-danger-700 mb-3">{error}</p>
        )}

        {apiKey ? (
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-gray-50 border border-border-default rounded-md px-3 py-2 text-[12.5px] font-mono text-gray-700 truncate select-all">
              {visible ? apiKey : masked}
            </code>
            <button
              onClick={() => setVisible((v) => !v)}
              title={visible ? "Hide" : "Show"}
              className="btn-secondary p-2 shrink-0"
            >
              {visible ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
              )}
            </button>
            <button
              onClick={handleCopy}
              title="Copy"
              className="btn-secondary p-2 shrink-0"
            >
              {copied ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
              )}
            </button>
          </div>
        ) : (
          <p className="text-xs text-gray-400">
            No API key yet. Click <span className="font-semibold text-gray-600">Generate key</span> to create one.
          </p>
        )}

        {apiKey && (
          <p className="text-[11.5px] text-gray-400 mt-3">
            Pass as{" "}
            <code className="bg-gray-100 px-1 rounded text-[11px]">Authorization: Bearer &lt;key&gt;</code>.
            {" "}Regenerating immediately invalidates the old key.
          </p>
        )}
      </div>
    </div>
  );
}
