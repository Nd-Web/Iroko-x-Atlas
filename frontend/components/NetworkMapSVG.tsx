"use client";

import { useState, useRef, useEffect } from "react";
import type { HeatmapRegion } from "@/components/LeafletMap";

// ─── Inline TopoJSON decoder ──────────────────────────────────────────────────
// Parses the Natural Earth world-atlas format without any npm package.
// Only Nigeria (ISO 3166-1 numeric = 566) is extracted.

interface RawTopo {
  transform: { scale: [number, number]; translate: [number, number] };
  arcs: number[][][];
  objects: {
    countries: {
      geometries: Array<{
        id: string | number;
        type: "Polygon" | "MultiPolygon";
        arcs: number[][][] | number[][][][];
      }>;
    };
  };
}

type LonLat = [number, number];

function decodeLonLats(topo: RawTopo): LonLat[][] {
  const [sx, sy] = topo.transform.scale;
  const [tx, ty] = topo.transform.translate;

  // Decode one arc (delta-compressed integers → lon/lat floats)
  function arc(i: number): LonLat[] {
    const reversed = i < 0;
    const raw = topo.arcs[reversed ? ~i : i];
    let x = 0, y = 0;
    const pts: LonLat[] = raw.map(([dx, dy]) => {
      x += dx;
      y += dy;
      return [x * sx + tx, y * sy + ty];
    });
    if (reversed) pts.reverse();
    return pts.slice(0, -1); // drop closing duplicate
  }

  function ring(indices: number[]): LonLat[] {
    return indices.flatMap(arc);
  }

  const nigeria = topo.objects.countries.geometries.find(
    (g) => String(g.id) === "566"
  );
  if (!nigeria) return [];

  // Normalise both Polygon and MultiPolygon to a flat list of rings
  const polys: number[][][] =
  nigeria.type === "Polygon"
    ? [nigeria.arcs as unknown as number[][]]
    : (nigeria.arcs as unknown as number[][][][]).flat();

  return polys.flat().map(ring);
}

// ─── Web Mercator → SVG viewport ─────────────────────────────────────────────
// Fixed viewport: a tile of Nigeria that leaves a small border on each side.

const SVG_W = 700;
const SVG_H = 420;
const MIN_LON = 1.8;
const MAX_LON = 15.6;
const MIN_LAT = 3.2;
const MAX_LAT = 14.8;

function mercY(latDeg: number): number {
  const r = (latDeg * Math.PI) / 180;
  return Math.log(Math.tan(Math.PI / 4 + r / 2));
}
const MERC_MIN = mercY(MIN_LAT);
const MERC_MAX = mercY(MAX_LAT);

function project([lon, lat]: LonLat): [number, number] {
  const x = ((lon - MIN_LON) / (MAX_LON - MIN_LON)) * SVG_W;
  const y = ((MERC_MAX - mercY(lat)) / (MERC_MAX - MERC_MIN)) * SVG_H;
  return [x, y];
}

function ringsToPath(rings: LonLat[][]): string {
  return rings
    .map(
      (ring) =>
        "M " +
        ring.map((pt) => project(pt).map((n) => n.toFixed(2)).join(",")).join(" L ") +
        " Z"
    )
    .join(" ");
}

// ─── Component ────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  operational: "#16A34A",
  degraded:    "#D97706",
  down:        "#DC2626",
};

interface Props {
  regions: HeatmapRegion[];
}

export default function NetworkMapSVG({ regions }: Props) {
  const [nigeriaPath, setNigeriaPath] = useState<string>("");
  const [hovered, setHovered]         = useState<HeatmapRegion | null>(null);
  const [mouse, setMouse]             = useState({ x: 0, y: 0 });
  const svgRef                        = useRef<SVGSVGElement>(null);

  // Fetch world-atlas TopoJSON once; no npm package needed
  useEffect(() => {
    fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json")
      .then((r) => r.json())
      .then((topo: RawTopo) => {
        const rings = decodeLonLats(topo);
        if (rings.length) setNigeriaPath(ringsToPath(rings));
      })
      .catch(() => {/* map still renders markers without the outline */});
  }, []);

  function onMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (rect) setMouse({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }

  const op  = regions.filter((r) => r.status === "operational").length;
  const deg = regions.filter((r) => r.status === "degraded").length;
  const dn  = regions.filter((r) => r.status === "down").length;

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-zinc-200 bg-[#D6E8F5] mt-3">
      {/* Title badge */}
      <div className="absolute top-2.5 left-3 z-10 pointer-events-none">
        <span className="text-[11px] font-bold text-zinc-700 bg-white/85 rounded-md px-2 py-0.5 backdrop-blur-sm">
          MTN Nigeria · Network Status
        </span>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        style={{ width: "100%", height: "auto", display: "block" }}
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHovered(null)}
      >
        {/* Ocean / background */}
        <rect width={SVG_W} height={SVG_H} fill="#D6E8F5" />

        {/* Land surrounding Nigeria (rough bounding box fill so neighbours are visible) */}
        <rect width={SVG_W} height={SVG_H} fill="#E8EEF4" />

        {/* Nigeria country fill — rendered once world-atlas loads */}
        {nigeriaPath && (
          <path
            d={nigeriaPath}
            fill="#C6D9ED"
            stroke="#5A8FC8"
            strokeWidth={1.2}
            strokeLinejoin="round"
          />
        )}

        {/* Region markers */}
        {regions.map((r) => {
          const [cx, cy] = project([r.longitude, r.latitude]);
          const color  = STATUS_COLOR[r.status] ?? "#16A34A";
          const radius = Math.max(9, Math.min(22, r.site_count * 2.2));

          return (
            <g
              key={r.region}
              onMouseEnter={() => setHovered(r)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: "pointer" }}
            >
              {/* White halo */}
              <circle cx={cx} cy={cy} r={radius + 3} fill="white" fillOpacity={0.65} />

              {/* Status circle */}
              <circle
                cx={cx} cy={cy} r={radius}
                fill={color} fillOpacity={0.88}
                stroke="white" strokeWidth={2}
              />

              {/* Region label (text outline via paintOrder so it's readable over the map) */}
              <text
                x={cx} y={cy - radius - 6}
                textAnchor="middle"
                style={{
                  fontSize:       9,
                  fontWeight:     700,
                  fill:           "#1A202C",
                  fontFamily:     "system-ui, sans-serif",
                  paintOrder:     "stroke",
                  stroke:         "white",
                  strokeWidth:    3,
                  strokeLinejoin: "round",
                  pointerEvents:  "none",
                } as React.CSSProperties}
              >
                {r.region}
              </text>

              {/* Availability % below (only when site is degraded or down) */}
              {r.availability_pct < 99 && (
                <text
                  x={cx} y={cy + radius + 14}
                  textAnchor="middle"
                  style={{
                    fontSize:      8,
                    fontWeight:    600,
                    fill:          r.status === "down" ? "#DC2626" : "#D97706",
                    fontFamily:    "system-ui, sans-serif",
                    pointerEvents: "none",
                  }}
                >
                  {r.availability_pct}%
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Hover tooltip */}
      {hovered && (
        <div
          className="absolute z-20 bg-white border border-zinc-200 rounded-xl shadow-xl px-3 py-2.5 text-xs pointer-events-none min-w-[170px]"
          style={{
            left: Math.min(mouse.x + 14, 520),
            top:  Math.max(mouse.y - 90, 36),
          }}
        >
          <p className="font-bold text-zinc-900 text-sm mb-1.5">{hovered.region}</p>
          <div className="space-y-1">
            <p className="text-zinc-500">
              Status:{" "}
              <strong style={{ color: STATUS_COLOR[hovered.status] }}>
                {hovered.status.charAt(0).toUpperCase() + hovered.status.slice(1)}
              </strong>
            </p>
            <p className="text-zinc-500">
              Availability: <strong className="text-zinc-800">{hovered.availability_pct}%</strong>
            </p>
            <p className="text-zinc-500">
              Sites: <strong className="text-zinc-800">{hovered.site_count}</strong>
              {" · "}Operational:{" "}
              <strong className="text-green-700">{hovered.operational}</strong>
            </p>
            {hovered.degraded > 0 && (
              <p className="text-amber-600 font-medium">Degraded: {hovered.degraded}</p>
            )}
            {hovered.down > 0 && (
              <p className="text-red-600 font-medium">Down: {hovered.down}</p>
            )}
            {hovered.active_incidents > 0 && (
              <p className="text-red-500 font-semibold border-t border-zinc-100 pt-1 mt-1">
                {hovered.critical_incidents > 0 ? "⚠ " : ""}
                {hovered.active_incidents} active incident
                {hovered.active_incidents !== 1 ? "s" : ""}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-2.5 right-2.5 flex items-center gap-3 bg-white/85 backdrop-blur-sm rounded-lg px-2.5 py-1.5 text-[10px] text-zinc-600 border border-white/60 pointer-events-none">
        {(
          [
            ["Operational", "#16A34A", op],
            ["Degraded",    "#D97706", deg],
            ["Down",        "#DC2626", dn],
          ] as [string, string, number][]
        ).map(([label, color, count]) => (
          <span key={label} className="flex items-center gap-1">
            <span
              style={{
                background:   color,
                width:        8,
                height:       8,
                borderRadius: "50%",
                display:      "inline-block",
                flexShrink:   0,
              }}
            />
            {label} ({count})
          </span>
        ))}
      </div>
    </div>
  );
}
