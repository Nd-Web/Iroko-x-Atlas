"use client";
/**
 * app/knowledge-graph/page.tsx — SVG force-directed knowledge graph.
 */
import { useState, useCallback } from "react";
import AppShell from "@/components/layout/AppShell";
import { cn } from "@/lib/utils";

interface Node { id: string; label: string; type: string; x: number; y: number; connections: string[]; }
interface Edge { from: string; to: string; label?: string; }

const NODE_COLORS: Record<string, string> = {
  contract: "#3B7BF6", vendor: "#8B5CF6", sla: "#10B981",
  alert: "#EF4444", document: "#F59E0B", regulation: "#EC4899",
};

const NODES: Node[] = [
  { id: "n1",  label: "IHS Nigeria",              type: "vendor",     x: 220, y: 160, connections: ["n2","n3","n5"] },
  { id: "n2",  label: "Tower Lease 2024",         type: "contract",   x: 100, y: 90,  connections: ["n1","n4","n6"] },
  { id: "n3",  label: "SLA — 99.5% Uptime",       type: "sla",        x: 320, y: 80,  connections: ["n1","n7"] },
  { id: "n4",  label: "Article 9.3 Credit",       type: "document",   x: 60,  y: 200, connections: ["n2","n7"] },
  { id: "n5",  label: "Ikeja Cluster Alert",      type: "alert",      x: 200, y: 280, connections: ["n1","n3","n8"] },
  { id: "n6",  label: "NCA 2003 s.73",            type: "regulation", x: 120, y: 320, connections: ["n2","n9"] },
  { id: "n7",  label: "SLA Breach — 4 events",   type: "alert",      x: 400, y: 180, connections: ["n3","n5"] },
  { id: "n8",  label: "Ericsson RAN SLA",         type: "sla",        x: 340, y: 300, connections: ["n5","n9"] },
  { id: "n9",  label: "NCC QoS Report Q4",        type: "document",   x: 480, y: 260, connections: ["n6","n8"] },
  { id: "n10", label: "Huawei Core Contract",     type: "contract",   x: 460, y: 110, connections: ["n3","n9"] },
];

const EDGES: Edge[] = [
  { from: "n1", to: "n2", label: "leases" },
  { from: "n1", to: "n3", label: "governed by" },
  { from: "n1", to: "n5", label: "triggered" },
  { from: "n2", to: "n4", label: "contains" },
  { from: "n2", to: "n6", label: "subject to" },
  { from: "n3", to: "n7", label: "breach of" },
  { from: "n4", to: "n7", label: "applies to" },
  { from: "n5", to: "n3", label: "violates" },
  { from: "n5", to: "n8", label: "also violates" },
  { from: "n6", to: "n9", label: "referenced in" },
  { from: "n8", to: "n9", label: "cited in" },
  { from: "n10", to: "n3", label: "references" },
  { from: "n10", to: "n9", label: "appears in" },
];

function getNode(id: string) { return NODES.find(n => n.id === id); }

function GraphLegend() {
  return (
    <div className="absolute top-4 right-4 rounded-xl px-4 py-3 space-y-2" style={{ background: "rgba(8,11,20,0.85)", border: "1px solid rgba(255,255,255,0.08)", backdropFilter: "blur(8px)" }}>
      <div className="text-[9.5px] font-bold text-[#6B7280] uppercase tracking-wider mb-2">Node Types</div>
      {Object.entries(NODE_COLORS).map(([type, color]) => (
        <div key={type} className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ background: color }} />
          <span className="text-[10px] text-[#9CA3AF] capitalize">{type}</span>
        </div>
      ))}
    </div>
  );
}

export default function KnowledgeGraphPage() {
  const [selected, setSelected] = useState<Node | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const isHighlighted = useCallback((nodeId: string) => {
    if (!selected) return true;
    return nodeId === selected.id || selected.connections.includes(nodeId);
  }, [selected]);

  const isEdgeHighlighted = useCallback((edge: Edge) => {
    if (!selected) return true;
    return edge.from === selected.id || edge.to === selected.id;
  }, [selected]);

  return (
    <AppShell title="Knowledge Graph" subtitle="Semantic relationships between documents, contracts and alerts">
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* Graph canvas */}
        <div className="xl:col-span-3 relative rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "#080B14", minHeight: 520 }}>
          <svg viewBox="0 0 560 400" className="w-full h-full" style={{ minHeight: 480 }}>
            <defs>
              <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 Z" fill="rgba(255,255,255,0.15)" />
              </marker>
              {Object.entries(NODE_COLORS).map(([type, color]) => (
                <radialGradient key={type} id={`grad-${type}`} cx="35%" cy="35%">
                  <stop offset="0%" stopColor={color} stopOpacity="0.9" />
                  <stop offset="100%" stopColor={color} stopOpacity="0.5" />
                </radialGradient>
              ))}
            </defs>

            {/* Grid background */}
            <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
              <path d="M30 0L0 0 0 30" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
            </pattern>
            <rect width="560" height="400" fill="url(#grid)" />

            {/* Edges */}
            {EDGES.map((edge, i) => {
              const from = getNode(edge.from);
              const to = getNode(edge.to);
              if (!from || !to) return null;
              const highlighted = isEdgeHighlighted(edge);
              const mx = (from.x + to.x) / 2;
              const my = (from.y + to.y) / 2;
              return (
                <g key={i}>
                  <line
                    x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                    stroke={highlighted ? "rgba(59,123,246,0.25)" : "rgba(255,255,255,0.04)"}
                    strokeWidth={highlighted ? 1.5 : 0.8}
                    markerEnd="url(#arrow)"
                    style={{ transition: "all 0.3s ease" }}
                  />
                  {highlighted && edge.label && (
                    <text x={mx} y={my - 4} textAnchor="middle" fontSize="7" fill="rgba(155,171,255,0.6)" fontStyle="italic">{edge.label}</text>
                  )}
                </g>
              );
            })}

            {/* Nodes */}
            {NODES.map(node => {
              const col = NODE_COLORS[node.type] ?? "#6B7280";
              const lit = isHighlighted(node.id);
              const hov = hovered === node.id;
              const sel = selected?.id === node.id;
              const r = sel ? 22 : hov ? 18 : 15;
              return (
                <g key={node.id} style={{ cursor: "pointer" }}
                  onClick={() => setSelected(selected?.id === node.id ? null : node)}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}>
                  {/* Glow */}
                  {(sel || hov) && <circle cx={node.x} cy={node.y} r={r + 10} fill={col} opacity="0.1" />}
                  {/* Ring */}
                  <circle cx={node.x} cy={node.y} r={r} fill={`url(#grad-${node.type})`}
                    opacity={lit ? 1 : 0.2} stroke={sel ? col : "rgba(255,255,255,0.15)"}
                    strokeWidth={sel ? 2 : 0.8}
                    style={{ filter: sel ? `drop-shadow(0 0 8px ${col}80)` : "none", transition: "all 0.25s ease" }} />
                  {/* Label */}
                  <text x={node.x} y={node.y + r + 12} textAnchor="middle" fontSize="7.5"
                    fill={lit ? "#E5E7EB" : "#4B5563"} fontWeight="600" style={{ transition: "fill 0.3s" }}>
                    {node.label.length > 18 ? node.label.slice(0, 17) + "…" : node.label}
                  </text>
                </g>
              );
            })}
          </svg>
          <GraphLegend />
          {!selected && (
            <div className="absolute bottom-4 left-4 text-[10px] text-[#4B5563]">Click a node to explore relationships</div>
          )}
        </div>

        {/* Detail panel */}
        <div className="rounded-2xl border border-white/[0.06] p-5 flex flex-col gap-4" style={{ background: "#0F1320" }}>
          {selected ? (
            <>
              <div>
                <div className="w-10 h-10 rounded-xl mb-3 flex items-center justify-center" style={{ background: `${NODE_COLORS[selected.type]}20` }}>
                  <div className="w-4 h-4 rounded-full" style={{ background: NODE_COLORS[selected.type] }} />
                </div>
                <div className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: NODE_COLORS[selected.type] }}>{selected.type}</div>
                <h3 className="text-[14px] font-bold text-[#E5E7EB] leading-snug">{selected.label}</h3>
              </div>

              <div>
                <div className="text-[10px] text-[#6B7280] uppercase tracking-wider font-bold mb-2">Connected Nodes ({selected.connections.length})</div>
                <div className="space-y-1.5">
                  {selected.connections.map(id => {
                    const n = getNode(id);
                    if (!n) return null;
                    const c = NODE_COLORS[n.type] ?? "#6B7280";
                    return (
                      <button key={id} onClick={() => setSelected(n)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left hover:bg-white/[0.04] transition-colors">
                        <div className="w-3 h-3 rounded-full shrink-0" style={{ background: c }} />
                        <span className="text-[11px] text-[#D1D5DB] truncate">{n.label}</span>
                        <span className="text-[9px] capitalize text-[#6B7280] ml-auto">{n.type}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <button onClick={() => setSelected(null)}
                className="mt-auto text-[11px] text-[#6B7280] hover:text-[#E5E7EB] transition-colors text-left">
                ← Clear selection
              </button>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-8">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)" }}>
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="#8B5CF6" strokeWidth="1.5">
                  <circle cx="11" cy="11" r="3"/><circle cx="4" cy="5" r="2"/><circle cx="18" cy="5" r="2"/>
                  <circle cx="18" cy="17" r="2"/><circle cx="4" cy="17" r="2"/>
                  <path d="M6 6l3.5 3.5M16 6l-3.5 3.5M16 16l-3.5-3.5M6 16l3.5-3.5"/>
                </svg>
              </div>
              <p className="text-[12px] font-semibold text-[#E5E7EB]">Knowledge Graph</p>
              <p className="text-[11px] text-[#6B7280] leading-relaxed">Click any node to explore its relationships, connected contracts and alerts.</p>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
