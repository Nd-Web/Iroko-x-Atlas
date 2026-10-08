"use client";

/**
 * The bank's particulars — entered once, shared by the whole team, printed on
 * every return's letterhead.
 */

import { useState } from "react";
import { toast } from "sonner";
import FieldInput from "@/components/compliance/returns/FieldInput";
import { api, type ReturnField, type Values } from "@/lib/returns";

export default function ProfileForm({
  fields, licenceCategories, initial, onSaved, compact,
}: {
  fields: ReturnField[];
  licenceCategories: Record<string, string>;
  initial: Values;
  onSaved: (missing: string[]) => void;
  compact?: boolean;
}) {
  const [profile, setProfile] = useState<Values>(initial);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      const res = await api.saveProfile(profile);
      if (res.missing.length) toast.warning(`Still needed: ${res.missing.join(", ")}`);
      else toast.success("Bank details saved for your team");
      onSaved(res.missing);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="flex flex-col gap-4">
      {!compact && (
        <p className="text-[13px] text-gray-500 m-0 leading-[1.6]">
          These appear on the letterhead of every return. Enter them once — everyone in your team uses the same details.
        </p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {fields.map((f) => (
          <div key={f.key} className={f.type === "textarea" ? "md:col-span-2" : ""}>
            <FieldInput field={f} value={profile[f.key]} onChange={(v) => setProfile((p) => ({ ...p, [f.key]: v }))}
              optionLabels={f.key === "licence_category" ? licenceCategories : undefined} />
          </div>
        ))}
      </div>
      <button className="btn-primary self-start" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save bank details"}</button>
    </div>
  );
}
