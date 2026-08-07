import { useEffect } from "react";
import { MapContainer, TileLayer, ImageOverlay, useMap } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import type { OverlayInfo } from "../../api/types";
import { assetUrl } from "../../api/client";
import { fmt } from "../../lib/format";

function FitBounds({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(bounds, { animate: true, duration: 0.4 });
  }, [map, JSON.stringify(bounds)]);
  return null;
}

export function AnomalyLeafletMap({ overlay, emptyReason }: { overlay: OverlayInfo | null; emptyReason?: string }) {
  if (!overlay || !overlay.available || !overlay.bounds) {
    return (
      <div className="card map-empty-card">
        <p>{emptyReason ?? "No rendered map for this combination in this build."}</p>
        <p>
          The statistics on this page are computed directly from the underlying NMME anomaly grid, cosine-latitude-weighted
          over this region&apos;s bounding box — only the map overlay is missing for this exact combination.
        </p>
      </div>
    );
  }

  const bounds = overlay.bounds as LatLngBoundsExpression;

  return (
    <div className="leaflet-map-card">
      <div className="leaflet-map-wrap">
        <MapContainer bounds={bounds} style={{ height: "100%", width: "100%" }} scrollWheelZoom={true}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          <ImageOverlay url={assetUrl(overlay.url!)} bounds={bounds} opacity={0.82} />
          <FitBounds bounds={bounds} />
        </MapContainer>
        {overlay.vmin != null && overlay.vmax != null && (
          <div className="leaflet-legend">
            <div>Anomaly ({overlay.unit})</div>
            <div className="bar" style={{ background: "linear-gradient(90deg, var(--dry), #f5f1ea, var(--wet))" }} />
            <div className="ends">
              <span>{fmt(overlay.vmin, 0)}</span>
              <span>{fmt(overlay.vmax, 0)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
