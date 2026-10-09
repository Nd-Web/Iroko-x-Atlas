"use client";
/** Licence categories: which requirements are addressed to this workspace depends on them. */

import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { useCategories, useGraphActions, useProfile } from "@/lib/compliance-graph";

const SECTORS: Record<string, string> = { mfb: "Microfinance banks", payments: "Payments and fintech", banks: "Banks" };

export default function ProfileDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const profile = useProfile();
  const categories = useCategories();
  const actions = useGraphActions();
  // Edits start from the saved profile; null means "not edited since opening".
  const [edited, setEdited] = useState<string[] | null>(null);
  const chosen = edited ?? profile.data?.category_codes ?? [];
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const close = () => { setEdited(null); setError(null); onClose(); };
  const toggle = (code: string) => setEdited(chosen.includes(code) ? chosen.filter((x) => x !== code) : [...chosen, code]);
  const save = async () => {
    setBusy(true);
    setError(null);
    try { await actions.setProfile(chosen); close(); } catch (e) { setError(e instanceof Error ? e.message : "Not saved."); } finally { setBusy(false); }
  };
  const bySector: Record<string, { code: string; label: string }[]> = {};
  for (const c of categories.data?.declarable ?? []) (bySector[c.sector] ??= []).push(c);
  const canEdit = profile.data?.can_edit ?? false;
  return (
    <Modal open={open} onClose={close} title="Your licence categories" maxWidth="560px" footer={
      <div className="flex justify-end gap-2">
        <button className="btn-secondary" onClick={close}>Close</button>
        {canEdit && <button className="btn-primary" disabled={busy || chosen.length === 0} onClick={save}>Save</button>}
      </div>
    }>
      <div className="space-y-4">
        <p className="text-[13px] text-gray-500">
          Iroko shows a requirement as applying to you only when the regulator addressed it to one of these licences.
          {profile.data?.basis === "from_filing_profile" && " The current choice comes from your filing profile — please confirm it."}
        </p>
        {Object.entries(bySector).map(([sector, items]) => (
          <fieldset key={sector} className="space-y-2">
            <legend className="text-[12px] font-semibold text-gray-700">{SECTORS[sector] ?? sector}</legend>
            {items.map((c) => (
              <label key={c.code} className="flex items-center gap-2 text-[13px] text-gray-800">
                <input type="checkbox" disabled={!canEdit} checked={chosen.includes(c.code)} onChange={() => toggle(c.code)} />
                {c.label}
              </label>
            ))}
          </fieldset>
        ))}
        {!canEdit && <p className="text-[12px] text-gray-500">Only an admin of your workspace can change this.</p>}
        {error && <p role="alert" className="text-[12px] text-danger-700">{error}</p>}
      </div>
    </Modal>
  );
}
