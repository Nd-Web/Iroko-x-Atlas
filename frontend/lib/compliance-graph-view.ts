/**
 * lib/compliance-graph-view.ts
 *
 * Pure presentation helpers for the compliance knowledge graph: no React, no
 * fetch, so they are unit-tested with node:test (tests/compliance-graph.test.cjs).
 *
 * Wording rule: a gap is "Not established in Iroko's records", never a
 * compliance verdict, and gaps are never shown in alarm (danger) colours.
 */

export type Tone = "success" | "warning" | "info" | "gray" | "danger";

export interface StatusLike {
  basis?: string | null;
  review_status?: string | null;
}

/** How a relationship's state is shown: stated, suggested, confirmed, re-review or rejected. */
export function statusTone(status: StatusLike | null | undefined): Tone {
  const review = status?.review_status;
  if (review === "confirmed") return "success";
  if (review === "needs_re_review") return "warning";
  if (review === "rejected") return "danger";
  if (status?.basis === "stated") return "info";
  return "gray";
}

export function statusShortLabel(status: StatusLike | null | undefined): string {
  const review = status?.review_status;
  if (review === "confirmed") return "Confirmed";
  if (review === "needs_re_review") return "Needs re-review";
  if (review === "rejected") return "Rejected";
  if (status?.basis === "stated") return "Stated in source";
  if (status?.basis === "manual") return "Entered by a person";
  return "Suggested by Iroko";
}

export const COVERAGE_ORDER = [
  "needs_re_review",
  "no_control_linked",
  "control_suggested",
  "control_confirmed_no_evidence",
  "evidence_suggested",
  "evidence_out_of_date",
  "evidence_on_record",
  "not_applicable",
] as const;

export const COVERAGE_SHORT: Record<string, string> = {
  not_applicable: "Not applicable",
  no_control_linked: "No control linked",
  control_suggested: "Control suggested",
  control_confirmed_no_evidence: "No evidence yet",
  evidence_suggested: "Evidence suggested",
  evidence_on_record: "Evidence on record",
  evidence_out_of_date: "Evidence out of date",
  needs_re_review: "Needs re-review",
};

export function coverageTone(state: string | null | undefined): Tone {
  switch (state) {
    case "evidence_on_record": return "success";
    case "evidence_out_of_date":
    case "needs_re_review": return "warning";
    case "control_suggested":
    case "evidence_suggested":
    case "control_confirmed_no_evidence": return "info";
    default: return "gray"; // "no control linked" is a gap in records, not an alarm
  }
}

export const APPLICABILITY_SHORT: Record<string, string> = {
  applies: "Applies (stated)",
  applies_confirmed: "Applies (confirmed)",
  applies_decided: "Applies (your decision)",
  likely: "Likely applies",
  not_addressed: "Not addressed to you",
  not_applicable: "Not applicable (your decision)",
  undetermined: "Not established",
  no_profile: "Set your licence",
};

export function applicabilityTone(state: string | null | undefined): Tone {
  if (state === "applies" || state === "applies_confirmed" || state === "applies_decided") return "success";
  if (state === "likely") return "info";
  return "gray";
}

export const TONE_CLASS: Record<Tone, string> = {
  success: "badge-success",
  warning: "badge-warning",
  info: "badge-info",
  gray: "badge-gray",
  danger: "badge-danger",
};

const VERDICT_WORDING = /\bnon[-\s]?complian(?:t|ce)\b|\bnot\s+(?:fully\s+)?compliant\b|\b(?:is|are|fully|partially)\s+compliant\b|\bin\s+breach\b/i;

/** True when Iroko-written text would state a compliance verdict (it never should). */
export function hasVerdictWording(text: string | null | undefined): boolean {
  return !!text && VERDICT_WORDING.test(text);
}

// ─── Document roles ──────────────────────────────────────────────────────────

export const DOCUMENT_ROLES: { value: string; label: string; hint: string }[] = [
  { value: "regulation", label: "Regulation or guidance", hint: "A circular, guideline, framework or Act from a regulator" },
  { value: "policy", label: "Our policy", hint: "Your institution's own policy or framework" },
  { value: "procedure", label: "Our procedure", hint: "Your step-by-step procedure or manual" },
  { value: "evidence_record", label: "Evidence record", hint: "A register, log, report, minutes or attestation showing something was done" },
  { value: "other", label: "Other", hint: "Anything else" },
];

const ROLE_HINTS: [string, RegExp][] = [
  ["evidence_record", /\b(register|log|minutes|attendance|report|attestation|certificate|acknowledg\w*|receipt|sign[-\s]?off|checklist|evidence)\b/i],
  ["procedure", /\b(procedures?|manual|process|playbook|sop|standard operating)\b/i],
  ["policy", /\b(policy|policies|framework|charter|code of conduct)\b/i],
  ["regulation", /\b(circular|guidelines?|regulations?|act \d{4}|letter to all|directive|cbn|nfiu|ndic|ndpc|exposure draft)\b/i],
];

/** A first guess from the file name, the same rules the server uses; the uploader confirms it. */
export function roleHint(name: string | null | undefined): string | null {
  const text = (name ?? "").replace(/[_.-]+/g, " ");
  for (const [role, pattern] of ROLE_HINTS) if (pattern.test(text)) return role;
  return null;
}

// ─── Explorer lanes ──────────────────────────────────────────────────────────

export interface LaneNode { id: string; lane: number; label: string; }
export interface LaneEdge { id: string; from: string; to: string; }
export interface PlacedNode<N extends LaneNode = LaneNode> { node: N; lane: number; row: number; }

/**
 * Deterministic lane layout: nodes keep their lane (instrument → requirement →
 * control → evidence); rows are ordered by label, then by the average row of
 * their neighbours in the adjacent lane (two sweeps), which keeps connectors
 * short. The same input always yields the same picture.
 */
export function laneLayout<N extends LaneNode>(nodes: N[], edges: LaneEdge[], lanes = 4): PlacedNode<N>[] {
  const byLane: N[][] = Array.from({ length: lanes }, () => []);
  for (const node of nodes) byLane[Math.max(0, Math.min(lanes - 1, node.lane))].push(node);
  for (const lane of byLane) lane.sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  const neighbours = new Map<string, string[]>();
  for (const e of edges) {
    if (!neighbours.has(e.from)) neighbours.set(e.from, []);
    if (!neighbours.has(e.to)) neighbours.set(e.to, []);
    neighbours.get(e.from)!.push(e.to);
    neighbours.get(e.to)!.push(e.from);
  }
  const rowOf = () => {
    const rows = new Map<string, number>();
    byLane.forEach((lane) => lane.forEach((n, i) => rows.set(n.id, i)));
    return rows;
  };
  const sweep = (order: number[], reference: (lane: number) => number) => {
    for (const laneIndex of order) {
      const rows = rowOf();
      const ref = reference(laneIndex);
      if (ref < 0 || ref >= lanes) continue;
      const refIds = new Set(byLane[ref].map((n) => n.id));
      const score = (n: N) => {
        const linked = (neighbours.get(n.id) ?? []).filter((id) => refIds.has(id)).map((id) => rows.get(id) ?? 0);
        return linked.length ? linked.reduce((a, b) => a + b, 0) / linked.length : rows.get(n.id) ?? 0;
      };
      byLane[laneIndex].sort((a, b) => score(a) - score(b) || a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
    }
  };
  sweep([1, 2, 3], (lane) => lane - 1);
  sweep([2, 1, 0], (lane) => lane + 1);
  const placed: PlacedNode<N>[] = [];
  byLane.forEach((lane, laneIndex) => lane.forEach((node, row) => placed.push({ node, lane: laneIndex, row })));
  return placed;
}

export interface Geometry { laneWidth: number; cardWidth: number; rowHeight: number; cardHeight: number; top: number; }

/** Bezier path between two placed cards (right edge → left edge; same-lane edges arc on the left). */
export function connectorPath(a: PlacedNode, b: PlacedNode, g: Geometry): string {
  const ay = g.top + a.row * g.rowHeight + g.cardHeight / 2;
  const by = g.top + b.row * g.rowHeight + g.cardHeight / 2;
  if (a.lane === b.lane) {
    const x = a.lane * g.laneWidth + 4;
    const bulge = Math.min(48, 16 + Math.abs(a.row - b.row) * 8);
    return `M ${x} ${ay} C ${x - bulge} ${ay}, ${x - bulge} ${by}, ${x} ${by}`;
  }
  const [left, right] = a.lane < b.lane ? [a, b] : [b, a];
  const ly = left === a ? ay : by;
  const ry = right === a ? ay : by;
  const x1 = left.lane * g.laneWidth + g.cardWidth;
  const x2 = right.lane * g.laneWidth;
  const mid = (x1 + x2) / 2;
  return `M ${x1} ${ly} C ${mid} ${ly}, ${mid} ${ry}, ${x2} ${ry}`;
}

export const EDGE_STYLE: Record<string, { dash?: string; className: string; label: string }> = {
  confirmed: { className: "text-success-500", label: "Confirmed" },
  stated: { className: "text-info-500", label: "Stated in source" },
  suggested: { dash: "6 5", className: "text-gray-400", label: "Suggested by Iroko" },
  re_review: { dash: "2 4", className: "text-warning-500", label: "Needs re-review" },
  contains: { className: "text-gray-300", label: "Contains" },
};
