"use client";

import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export interface HeatmapRegion {
  region: string;
  latitude: number;
  longitude: number;
  site_count: number;
  operational: number;
  degraded: number;
  down: number;
  availability_pct: number;
  active_incidents: number;
  critical_incidents: number;
  status: "operational" | "degraded" | "down";
  subscribers: number;
}

const STATUS_COLOR: Record<string, string> = {
  operational: "#16A34A",
  degraded:    "#D97706",
  down:        "#DC2626",
};

const STATUS_LABEL: Record<string, string> = {
  operational: "Operational",
  degraded:    "Degraded",
  down:        "Down",
};

interface Props {
  regions: HeatmapRegion[];
}

export default function LeafletMap({ regions }: Props) {
  return (
    <MapContainer
      center={[9.0, 8.0]}
      zoom={6}
      style={{ height: "100%", width: "100%", borderRadius: "0 0 1rem 1rem" }}
      scrollWheelZoom={false}
      attributionControl={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {regions.map((r) => {
        const color  = STATUS_COLOR[r.status] ?? "#16A34A";
        const radius = Math.max(10, Math.min(28, r.site_count * 2.5));

        return (
          <CircleMarker
            key={r.region}
            center={[r.latitude, r.longitude]}
            radius={radius}
            pathOptions={{
              color:       color,
              fillColor:   color,
              fillOpacity: 0.82,
              weight:      2.5,
              opacity:     1,
            }}
          >
            <Tooltip direction="top" offset={[0, -radius - 4]} permanent={false}>
              <div style={{ minWidth: 140 }}>
                <p style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{r.region}</p>
                <p style={{ fontSize: 11, color: "#555", marginBottom: 2 }}>
                  Status: <strong style={{ color }}>{STATUS_LABEL[r.status]}</strong>
                </p>
                <p style={{ fontSize: 11, color: "#555", marginBottom: 2 }}>
                  Availability: <strong>{r.availability_pct}%</strong>
                </p>
                <p style={{ fontSize: 11, color: "#555", marginBottom: 2 }}>
                  Sites: {r.site_count} &nbsp;·&nbsp; Operational: {r.operational}
                  {r.degraded > 0 && <> &nbsp;·&nbsp; Degraded: {r.degraded}</>}
                  {r.down > 0    && <> &nbsp;·&nbsp; Down: {r.down}</>}
                </p>
                {r.active_incidents > 0 && (
                  <p style={{ fontSize: 11, color: "#DC2626", fontWeight: 600 }}>
                    {r.critical_incidents > 0 ? "⚠ " : ""}
                    {r.active_incidents} active incident{r.active_incidents !== 1 ? "s" : ""}
                  </p>
                )}
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}