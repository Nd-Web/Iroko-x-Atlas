"use client";
/** Controls: what your organisation does, who owns it, what it addresses and its latest evidence. */

import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { useControls, useGraphActions, usePeople } from "@/lib/compliance-graph";
import type { Selection } from "./EvidencePanel";
import { Empty, ErrorBox, Loading, StatusChip, formatDate } from "./ui";

const FREQUENCIES = ["daily", "weekly", "monthly", "quarterly", "semiannual", "annual", "event", "once"];

export default function ControlsTab({ onOpen }: { onOpen: (s: Selection) => void }) {
  const [showRetired, setShowRetired] = useState(false);
  const [adding, setAdding] = useState(false);
  const { data, isLoading, error, refetch } = useControls(showRetired);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-gray-500">Controls come from your uploaded policies and procedures, or you can add them yourself.</p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-[12px] text-gray-500">
            <input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)} /> Show retired
          </label>
          <button className="btn-primary text-[12px]" onClick={() => setAdding(true)}>Add control</button>
        </div>
      </div>
      {isLoading ? <Loading label="Loading controls" /> : error ? <ErrorBox error={error} onRetry={() => refetch()} /> : !data?.items.length ? (
        <Empty title="No controls yet">Upload a policy or procedure on the Documents page and choose “Our policy or procedure”. Iroko will find the controls in it for you to confirm.</Empty>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border-default">
          <table className="table-base min-w-[820px]">
            <thead>
              <tr><th>Control</th><th>Status</th><th>Owner</th><th>Frequency</th><th>Requirements</th><th>Latest evidence</th></tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id} className="cursor-pointer" onClick={() => onOpen({ kind: "control", id: c.id })}>
                  <td className="max-w-[360px]">
                    <button className="text-left" onClick={(e) => { e.stopPropagation(); onOpen({ kind: "control", id: c.id }); }}>
                      <span className="text-[13px] text-gray-800">{c.name}</span>
                    </button>
                    <span className="block text-[11px] text-gray-500">{c.document?.title ?? "Entered manually"}{c.status === "retired" ? " · retired" : ""}</span>
                  </td>
                  <td><StatusChip status={c.review} /></td>
                  <td className="text-[12px] text-gray-600">{c.owner.name || c.owner.team || <span className="text-gray-400">—</span>}</td>
                  <td className="text-[12px] text-gray-600">{c.frequency ?? <span className="text-gray-400">—</span>}</td>
                  <td className="text-[12px] text-gray-600">{c.requirements_confirmed} confirmed{c.requirements_suggested ? ` · ${c.requirements_suggested} suggested` : ""}</td>
                  <td className="text-[12px] text-gray-600">{c.latest_evidence ? formatDate(c.latest_evidence) : <span className="text-gray-400">None linked</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AddControl open={adding} onClose={() => setAdding(false)} onCreated={(id) => { setAdding(false); onOpen({ kind: "control", id }); }} />
    </div>
  );
}

function AddControl({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (id: string) => void }) {
  const actions = useGraphActions();
  const people = usePeople();
  const [form, setForm] = useState({ name: "", summary: "", frequency: "", owner_user_id: "", owner_team: "", evidence_expected: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const update = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v));
      const created = await actions.createControl(body);
      setForm({ name: "", summary: "", frequency: "", owner_user_id: "", owner_team: "", evidence_expected: "" });
      onCreated(created.control.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The control could not be saved.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="Add a control" footer={
      <div className="flex justify-end gap-2">
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={busy || form.name.trim().length < 2} onClick={submit}>Save control</button>
      </div>
    }>
      <div className="space-y-3">
        <label className="label-base">Name<input className="input-base mt-1" value={form.name} onChange={update("name")} placeholder="e.g. Daily sanctions screening" /></label>
        <label className="label-base">What is done<textarea className="input-base mt-1 min-h-[72px]" value={form.summary} onChange={update("summary")} /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="label-base">How often
            <select className="input-base mt-1" value={form.frequency} onChange={update("frequency")}>
              <option value="">Not stated</option>
              {FREQUENCIES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label className="label-base">Owner
            <select className="input-base mt-1" value={form.owner_user_id} onChange={update("owner_user_id")}>
              <option value="">No owner</option>
              {people.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        </div>
        <label className="label-base">Team<input className="input-base mt-1" value={form.owner_team} onChange={update("owner_team")} /></label>
        <label className="label-base">Record it produces<input className="input-base mt-1" value={form.evidence_expected} onChange={update("evidence_expected")} placeholder="e.g. Screening log" /></label>
        <p className="text-[12px] text-gray-500">Admins&apos; controls are confirmed straight away; analysts&apos; controls wait for an admin.</p>
        {error && <p role="alert" className="text-[12px] text-danger-700">{error}</p>}
      </div>
    </Modal>
  );
}
