"use client";
/**
 * Explorer: start from an instrument, requirement, control or record and see
 * its immediate connections in lanes — Instruments → Requirements → Your
 * controls → Your evidence. Cards are buttons; connectors are drawn in an SVG
 * layer underneath and differ by line style as well as colour.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useGraphSearch, useNeighbourhood, type GraphEdge, type GraphNode } from "@/lib/compliance-graph";
import { EDGE_STYLE, connectorPath, laneLayout, type Geometry } from "@/lib/compliance-graph-view";
import type { Selection } from "./EvidencePanel";
import { Empty, ErrorBox, Loading } from "./ui";

interface Props {
  start: { type: string; id: string } | null;
  onOpen: (s: Selection) => void;
}

const ROW = 76;
const CARD = 60;
const TOP = 36;

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

function open(node: GraphNode, onOpen: Props["onOpen"]) {
  if (node.type === "requirement") onOpen({ kind: "requirement", id: node.key });
  else if (node.type === "control") onOpen({ kind: "control", id: node.key });
  else if (node.type === "instrument" || node.type === "evidence") onOpen({ kind: "document", id: node.key });
}

export default function Explorer({ start, onOpen }: Props) {
  // The user's pick applies until the URL names a different starting point.
  const startKey = start ? `${start.type}:${start.id}` : "";
  const [picked, setPicked] = useState<{ under: string; focus: { type: string; id: string } } | null>(null);
  const focus = picked && picked.under === startKey ? picked.focus : start;
  const setFocus = (next: { type: string; id: string }) => setPicked({ under: startKey, focus: next });
  const [q, setQ] = useState("");
  const [depth, setDepth] = useState(1);
  const [suggested, setSuggested] = useState(true);
  const search = useGraphSearch(q);
  const hood = useNeighbourhood(focus?.type ?? null, focus?.id ?? null, depth, suggested);
  const [ref, width] = useWidth<HTMLDivElement>();

  const placed = useMemo(() => hood.data ? laneLayout(hood.data.nodes, hood.data.edges) : [], [hood.data]);
  const byId = useMemo(() => new Map(placed.map((p) => [p.node.id, p])), [placed]);
  const rows = placed.reduce((m, p) => Math.max(m, p.row + 1), 0);
  const laneWidth = width / 4;
  const geometry: Geometry = { laneWidth, cardWidth: Math.max(80, laneWidth - 28), rowHeight: ROW, cardHeight: CARD, top: TOP };
  const narrow = width > 0 && width < 720;

  const results = search.data;
  const choices = results ? [
    ...results.instruments.map((x) => ({ type: "document", id: x.id, label: x.title, hint: x.reference || "Instrument" })),
    ...results.requirements.map((x) => ({ type: "requirement", id: x.lineage_id, label: x.summary || x.quote.slice(0, 120), hint: "Requirement" })),
    ...results.controls.map((x) => ({ type: "control", id: x.id, label: x.name, hint: "Your control" })),
    ...results.evidence.map((x) => ({ type: "document", id: x.id, label: x.title, hint: "Your record" })),
  ].slice(0, 12) : [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <input className="input-base max-w-md flex-1" placeholder="Find an instrument, requirement, control or record" value={q}
          onChange={(e) => setQ(e.target.value)} aria-label="Find something to explore" />
        <label className="flex items-center gap-2 text-[12px] text-gray-500">
          <input type="checkbox" checked={suggested} onChange={(e) => setSuggested(e.target.checked)} /> Show suggestions
        </label>
        <label className="flex items-center gap-2 text-[12px] text-gray-500">
          Depth
          <select className="input-base w-auto py-1 text-[12px]" value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            <option value={1}>1 step</option>
            <option value={2}>2 steps</option>
          </select>
        </label>
      </div>
      {q.trim().length >= 2 && (
        <ul className="grid gap-2 md:grid-cols-2" aria-label="Search results">
          {choices.length === 0 && !search.isLoading && <li className="text-[13px] text-gray-500">Nothing found.</li>}
          {choices.map((c) => (
            <li key={`${c.type}:${c.id}`}>
              <button className="w-full rounded-lg border border-border-default px-3 py-2 text-left hover:border-border-strong hover:bg-gray-50"
                onClick={() => { setFocus({ type: c.type, id: c.id }); setQ(""); }}>
                <span className="line-clamp-1 text-[13px] text-gray-800">{c.label}</span>
                <span className="text-[11px] text-gray-500">{c.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <Legend />
      <div ref={ref} className="w-full">
        {!focus ? (
          <Empty title="Choose where to start">Search above, or open the Explorer from a requirement, control or document.</Empty>
        ) : hood.isLoading ? <Loading label="Loading connections" /> : hood.error ? (
          <ErrorBox error={hood.error} onRetry={() => hood.refetch()} />
        ) : !hood.data?.nodes.length ? (
          <Empty title="Nothing connected yet" />
        ) : narrow ? (
          <StackedLanes nodes={hood.data.nodes} edges={hood.data.edges} lanes={hood.data.lanes} focus={hood.data.focus}
            onOpen={onOpen} onFocus={(n) => setFocus({ type: n.type === "instrument" || n.type === "evidence" ? "document" : n.type, id: n.key })} />
        ) : width > 0 && (
          <div className="relative" style={{ height: TOP + rows * ROW }}>
            {hood.data.lanes.map((lane, i) => (
              <p key={lane} className="absolute text-[11px] font-semibold uppercase tracking-wide text-gray-400" style={{ left: i * laneWidth, top: 0 }}>{lane}</p>
            ))}
            <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
              {hood.data.edges.map((edge) => {
                const a = byId.get(edge.from);
                const b = byId.get(edge.to);
                if (!a || !b) return null;
                const style = EDGE_STYLE[edge.style] ?? EDGE_STYLE.suggested;
                return (
                  <path key={edge.id} d={connectorPath(a, b, geometry)} fill="none" stroke="currentColor"
                    strokeWidth={edge.style === "contains" ? 1 : 1.6} strokeDasharray={style.dash}
                    className={`${style.className} ${edge.style === "contains" ? "opacity-50" : "opacity-90"}`} />
                );
              })}
            </svg>
            {placed.map(({ node, lane, row }) => (
              <div key={node.id} className="absolute" style={{ left: lane * laneWidth, top: TOP + row * ROW, width: geometry.cardWidth, height: CARD }}>
                <button onClick={() => open(node, onOpen)}
                  className={`flex h-full w-full flex-col justify-center rounded-lg border px-3 text-left transition hover:border-border-strong ${node.id === hood.data!.focus ? "border-brand-500 bg-brand-50" : "border-border-default bg-surface-card"}`}>
                  <span className="line-clamp-2 text-[12px] leading-snug text-gray-800">{node.label}</span>
                  {(node.sublabel || node.awaiting_publication) && (
                    <span className="truncate text-[10px] text-gray-500">{node.awaiting_publication ? "Newer version awaiting publication" : node.sublabel}</span>
                  )}
                </button>
                {node.id !== hood.data!.focus && (node.type !== "act" && node.type !== "reference") && (
                  <button className="absolute -right-1 -top-2 rounded-full border border-border-default bg-surface-card px-1.5 text-[10px] text-gray-500 hover:text-gray-900"
                    title="Explore from here" aria-label={`Explore from ${node.label}`}
                    onClick={() => setFocus({ type: node.type === "instrument" || node.type === "evidence" ? "document" : node.type, id: node.key })}>
                    ⤢
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      {hood.data?.truncated && <p className="text-[12px] text-gray-500">Showing the first 80 connected items. Explore from a narrower starting point to see more.</p>}
      {hood.data && (
        <EdgeList edges={hood.data.edges.filter((e) => e.style !== "contains")} nodes={hood.data.nodes} onOpen={onOpen} />
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-4 text-[11px] text-gray-500" aria-label="Line styles">
      {(["confirmed", "stated", "suggested", "re_review"] as const).map((key) => (
        <span key={key} className="flex items-center gap-1.5">
          <svg width="28" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" stroke="currentColor" strokeWidth="1.6"
            strokeDasharray={EDGE_STYLE[key].dash} className={EDGE_STYLE[key].className} /></svg>
          {EDGE_STYLE[key].label}
        </span>
      ))}
    </div>
  );
}

/** Relationships as a list: every connector is also reachable by keyboard and screen reader. */
function EdgeList({ edges, nodes, onOpen }: { edges: GraphEdge[]; nodes: GraphNode[]; onOpen: Props["onOpen"] }) {
  if (!edges.length) return null;
  const label = new Map(nodes.map((n) => [n.id, n.label]));
  return (
    <details className="rounded-xl border border-border-default p-3">
      <summary className="cursor-pointer text-[12px] text-gray-600">Relationships shown ({edges.length})</summary>
      <ul className="mt-2 space-y-1">
        {edges.map((e) => (
          <li key={e.id}>
            <button className="text-left text-[12px] text-gray-700 hover:text-gray-900" onClick={() => onOpen({ kind: "link", id: e.id })}>
              {label.get(e.from)} <span className="text-gray-500">{e.label}</span> {label.get(e.to)} — {EDGE_STYLE[e.style]?.label ?? e.style}
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}

function StackedLanes({ nodes, edges, lanes, focus, onOpen, onFocus }: {
  nodes: GraphNode[]; edges: GraphEdge[]; lanes: string[]; focus: string; onOpen: Props["onOpen"]; onFocus: (n: GraphNode) => void;
}) {
  return (
    <div className="space-y-4">
      {lanes.map((lane, i) => {
        const inLane = nodes.filter((n) => n.lane === i);
        if (!inLane.length) return null;
        return (
          <section key={lane}>
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">{lane}</h3>
            <ul className="space-y-2">
              {inLane.map((n) => (
                <li key={n.id} className={`rounded-lg border p-3 ${n.id === focus ? "border-brand-500" : "border-border-default"}`}>
                  <button className="text-left text-[13px] text-gray-800" onClick={() => open(n, onOpen)}>{n.label}</button>
                  <ul className="mt-1 space-y-0.5">
                    {edges.filter((e) => (e.from === n.id || e.to === n.id) && e.style !== "contains").map((e) => (
                      <li key={e.id}>
                        <button className="text-left text-[11px] text-gray-500 hover:text-gray-800" onClick={() => onOpen({ kind: "link", id: e.id })}>
                          {e.label} · {EDGE_STYLE[e.style]?.label ?? e.style}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {n.id !== focus && <button className="mt-1 text-[11px] text-gray-500 underline" onClick={() => onFocus(n)}>Explore from here</button>}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
