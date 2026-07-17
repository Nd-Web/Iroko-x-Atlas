"use client";
/**
 * app/knowledge-graph/page.tsx — LIVE knowledge graph.
 *
 * Data comes exclusively from GET /api/graph (documents, extracted entities,
 * contracts, alerts, workflow tasks from the real corpus). Layout is a small
 * deterministic force simulation computed client-side. Loading / error /
 * empty states are rendered honestly — no mock fallbacks.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { apiFetch } from "@/lib/api";

interface ApiNode { id: string; label: string; type: string; meta: Record<string, unknown>; }
interface ApiEdge { from: string; to: string; label?: string; }
interface GraphData {
  nodes: ApiNode[];
  edges: ApiEdge[];
  stats: { node_count: number; edge_count: number; by_type: Record<string, number>; documents_scanned: number };
}
interface LaidNode extends ApiNode { x: number; y: number; connections: string[]; }

const NODE_COLORS: Record<string, string> = {
  document: "#818CF8", vendor: "#FB923C", regulator: "#F472B6",
  regulation: "#A78BFA", location: "#38BDF8", contract: "#60A5FA",
  alert: "#F87171", task: "#34D399",
};
const NODE_LABELS: Record<string, string> = {
  document: "Document", vendor: "Vendor", regulator: "Regulator",
  regulation: "Regulation", location: "Location", contract: "Contract",
  alert: "Alert", task: "Action Task",
};

const W = 560, H = 440;

/** Small deterministic force layout — repulsion + edge springs + centering. */
function layoutGraph(nodes: ApiNode[], edges: ApiEdge[]): LaidNode[] {
  const n = nodes.length;
  if (n === 0) return [];
  const idx = new Map(nodes.map((nd, i) => [nd.id, i]));
  // Seeded circular init (deterministic — no Math.random)
  const xs = new Array(n).fill(0).map((_, i) => W / 2 + (W / 3) * Math.cos((2 * Math.PI * i) / n + (i % 5) * 0.35));
  const ys = new Array(n).fill(0).map((_, i) => H / 2 + (H / 3) * Math.sin((2 * Math.PI * i) / n + (i % 7) * 0.22));

  const links = edges
    .filter(e => idx.has(e.from) && idx.has(e.to))
    .map(e => [idx.get(e.from)!, idx.get(e.to)!] as [number, number]);

  const ITER = 160, REPULSE = 5200, SPRING = 0.015, SPRING_LEN = 90, CENTER = 0.012;
  for (let it = 0; it < ITER; it++) {
    const fx = new Array(n).fill(0), fy = new Array(n).fill(0);
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = xs[i] - xs[j], dy = ys[i] - ys[j];
        let d2 = dx * dx + dy * dy;
        if (d2 < 1) { d2 = 1; dx = 0.5; dy = 0.5; }
        const f = REPULSE / d2;
        const d = Math.sqrt(d2);
        fx[i] += (dx / d) * f; fy[i] += (dy / d) * f;
        fx[j] -= (dx / d) * f; fy[j] -= (dy / d) * f;
      }
    }
    for (const [a, b] of links) {
      const dx = xs[b] - xs[a], dy = ys[b] - ys[a];
      const d = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const f = SPRING * (d - SPRING_LEN);
      fx[a] += (dx / d) * f; fy[a] += (dy / d) * f;
      fx[b] -= (dx / d) * f; fy[b] -= (dy / d) * f;
    }
    const cool = 1 - it / ITER;
    for (let i = 0; i < n; i++) {
      fx[i] += (W / 2 - xs[i]) * CENTER;
      fy[i] += (H / 2 - ys[i]) * CENTER;
      xs[i] = Math.min(W - 30, Math.max(30, xs[i] + fx[i] * 0.02 * cool));
      ys[i] = Math.min(H - 34, Math.max(26, ys[i] + fy[i] * 0.02 * cool));
    }
  }

  const conns = new Map<string, string[]>();
  for (const e of edges) {
    if (!idx.has(e.from) || !idx.has(e.to)) continue;
    conns.set(e.from, [...(conns.get(e.from) ?? []), e.to]);
    conns.set(e.to, [...(conns.get(e.to) ?? []), e.from]);
  }
  return nodes.map((nd, i) => ({ ...nd, x: xs[i], y: ys[i], connections: conns.get(nd.id) ?? [] }));
}

function GraphLegend({ byType }: { byType: Record<string, number> }) {
  return (
    <div className="absolute top-4 right-4 rounded-xl px-4 py-3 space-y-2" style={{ background: "rgba(26,26,31,0.9)", border: "1px solid rgba(255,255,255,0.08)", backdropFilter: "blur(8px)" }}>
      <div className="text-[9.5px] font-bold text-gray-400 uppercase tracking-wider mb-2">Node Types</div>
      {Object.entries(NODE_COLORS).filter(([t]) => (byType[t] ?? 0) > 0).map(([type, color]) => (
        <div key={type} className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ background: color }} />
          <span className="text-[10px] text-gray-500">{NODE_LABELS[type] ?? type} · {byType[type]}</span>
        </div>
      ))}
    </div>
  );
}

export default function KnowledgeGraphPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<LaidNode | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const g = await apiFetch<GraphData>("/api/graph");
      setData(g);
    } catch (e) {
      setError((e as Error).message ?? "Failed to load knowledge graph");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const nodes = useMemo(() => layoutGraph(data?.nodes ?? [], data?.edges ?? []), [data]);
  const nodeById = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes]);
  const edges = data?.edges ?? [];

  const isHighlighted = useCallback((nodeId: string) => {
    if (!selected) return true;
    return nodeId === selected.id || selected.connections.includes(nodeId);
  }, [selected]);

  const isEdgeHighlighted = useCallback((edge: ApiEdge) => {
    if (!selected) return true;
    return edge.from === selected.id || edge.to === selected.id;
  }, [selected]);

  return (
    <AppShell title="Knowledge Graph" subtitle="Live semantic relationships across your documents, entities, alerts and action tasks">
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* Graph canvas */}
        <div className="xl:col-span-3 relative rounded-2xl border border-border-default overflow-hidden" style={{ background: "#0A0A0B", minHeight: 520 }}>
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-[12px] text-gray-400">Building live graph from your corpus…</div>
          )}
          {error && !loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
              <div className="text-[12px] text-[#EF4444]">{error}</div>
              <button onClick={() => void load()} className="text-[11px] font-semibold px-3 py-1.5 rounded-lg text-brand-500 border border-brand-200 hover:bg-brand-50">Retry</button>
            </div>
          )}
          {!loading && !error && nodes.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
              <div className="text-[13px] text-gray-500 font-semibold">No graph data yet</div>
              <div className="text-[11px] text-gray-400 max-w-xs text-center">Upload documents or run a Watchdog sweep — nodes appear as soon as the corpus has content.</div>
            </div>
          )}
          {!loading && !error && nodes.length > 0 && (
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full" style={{ minHeight: 480 }}>
              <defs>
                <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L6,3 Z" fill="rgba(255,255,255,0.15)" />
                </marker>
              </defs>
              <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                <path d="M30 0L0 0 0 30" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
              </pattern>
              <rect width={W} height={H} fill="url(#grid)" />

              {edges.map((edge, i) => {
                const from = nodeById.get(edge.from);
                const to = nodeById.get(edge.to);
                if (!from || !to) return null;
                const highlighted = isEdgeHighlighted(edge);
                const mx = (from.x + to.x) / 2, my = (from.y + to.y) / 2;
                return (
                  <g key={i}>
                    <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                      stroke={highlighted ? "rgba(255,203,5,0.3)" : "rgba(255,255,255,0.04)"}
                      strokeWidth={highlighted ? 1.5 : 0.8}
                      markerEnd="url(#arrow)" style={{ transition: "all 0.3s ease" }} />
                    {selected && highlighted && edge.label && (
                      <text x={mx} y={my - 4} textAnchor="middle" fontSize="7" fill="rgba(184,184,193,0.75)" fontStyle="italic">{edge.label}</text>
                    )}
                  </g>
                );
              })}

              {nodes.map(node => {
                const col = NODE_COLORS[node.type] ?? "#7A7A85";
                const lit = isHighlighted(node.id);
                const hov = hovered === node.id;
                const sel = selected?.id === node.id;
                const base = node.type === "document" ? 15 : node.type === "task" || node.type === "alert" ? 13 : 11;
                const r = sel ? base + 7 : hov ? base + 3 : base;
                return (
                  <g key={node.id} style={{ cursor: "pointer" }}
                    onClick={() => setSelected(sel ? null : node)}
                    onMouseEnter={() => setHovered(node.id)}
                    onMouseLeave={() => setHovered(null)}>
                    {(sel || hov) && <circle cx={node.x} cy={node.y} r={r + 10} fill={col} opacity="0.1" />}
                    <circle cx={node.x} cy={node.y} r={r} fill={col}
                      opacity={lit ? 1 : 0.2} stroke={sel ? col : "rgba(255,255,255,0.15)"}
                      strokeWidth={sel ? 2 : 0.8}
                      style={{ filter: sel ? `drop-shadow(0 0 8px ${col}80)` : "none", transition: "all 0.25s ease" }} />
                    <text x={node.x} y={node.y + r + 11} textAnchor="middle" fontSize="7.5"
                      fill={lit ? "#EBEBEF" : "#4A4A54"} fontWeight="600" style={{ transition: "fill 0.3s" }}>
                      {node.label.length > 20 ? node.label.slice(0, 19) + "…" : node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
          {data && <GraphLegend byType={data.stats.by_type} />}
          {!selected && !loading && nodes.length > 0 && (
            <div className="absolute bottom-4 left-4 text-[10px] text-gray-300">
              {data?.stats.node_count} nodes · {data?.stats.edge_count} relationships · built live from {data?.stats.documents_scanned} documents — click a node to explore
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className="rounded-2xl border border-border-default p-5 flex flex-col gap-4" style={{ background: "#131316" }}>
          {selected ? (
            <>
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
                  style={{ color: NODE_COLORS[selected.type], background: `${NODE_COLORS[selected.type]}15`, border: `1px solid ${NODE_COLORS[selected.type]}30` }}>
                  {NODE_LABELS[selected.type] ?? selected.type}
                </span>
                <h3 className="text-[15px] font-semibold text-gray-800 mt-3 leading-snug">{selected.label}</h3>
              </div>
              {Object.entries(selected.meta ?? {}).filter(([, v]) => v !== null && v !== "" && v !== undefined).map(([k, v]) => (
                <div key={k} className="flex items-start justify-between gap-3 text-[11.5px]">
                  <span className="text-gray-400 capitalize">{k.replace(/_/g, " ")}</span>
                  <span className="text-gray-500 text-right break-all">{String(v).slice(0, 60)}</span>
                </div>
              ))}
              <div>
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">
                  Connected ({selected.connections.length})
                </div>
                <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                  {selected.connections.map(cid => {
                    const c = nodeById.get(cid);
                    if (!c) return null;
                    return (
                      <button key={cid} onClick={() => setSelected(c)}
                        className="w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-white/[0.04] transition-colors">
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: NODE_COLORS[c.type] ?? "#7A7A85" }} />
                        <span className="text-[11px] text-gray-500 truncate">{c.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <button onClick={() => setSelected(null)}
                className="mt-auto text-[11px] font-semibold px-3 py-2 rounded-lg text-gray-400 border border-white/[0.08] hover:bg-white/[0.04] transition-all">
                Clear selection
              </button>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
              <div className="text-[13px] font-semibold text-gray-500">Live corpus graph</div>
              <p className="text-[11px] text-gray-400 leading-relaxed">
                Nodes are built in real time from your indexed documents, the entities they mention,
                active alerts, and the action tasks they generated. Select any node to trace its relationships.
              </p>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
