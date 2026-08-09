import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, ImageOverlay, LayersControl, useMap } from "react-leaflet";
import L from "leaflet";
import type { LatLngBoundsExpression, LeafletMouseEvent } from "leaflet";
import type { OverlayInfo, GridResponse } from "../../api/types";
import { assetUrl } from "../../api/client";
import { fmt } from "../../lib/format";

const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const CARTO_ATTR = `${OSM_ATTR} &copy; <a href="https://carto.com/attributions">CARTO</a>`;
const ESRI_ATTR = "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS user community";

const BASEMAPS: { name: string; url: string; attribution: string; checked?: boolean }[] = [
  { name: "Light", url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", attribution: CARTO_ATTR, checked: true },
  { name: "Dark", url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", attribution: CARTO_ATTR },
  { name: "Streets", url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: OSM_ATTR },
  {
    name: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
  },
  {
    name: "Terrain",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
  },
];

function FitBounds({ bounds, extraZoom = 0 }: { bounds: LatLngBoundsExpression; extraZoom?: number }) {
  const map = useMap();
  useEffect(() => {
    // animate:false -- this fires on every region/period/init switch, and an
    // in-flight animated fitBounds getting interrupted by the next one (e.g.
    // overlay data arriving mid-transition) left Leaflet's zoom animation in
    // an inconsistent state, settling on the wrong zoom/center (reproduced:
    // selecting Global then Greater Horn left the map stuck at zoom 0).
    // A synchronous jump has no such race and is appropriate for a
    // programmatic region switch anyway.
    map.fitBounds(bounds, { animate: false });
    if (extraZoom) {
      // fitBounds picks the tightest zoom where BOTH dimensions still fit,
      // constrained by whichever axis is closer to the container's aspect
      // ratio -- any zoom past that starts cropping that same axis. For a
      // country-sized region (Ethiopia, Greater Horn, Africa) that axis is
      // real content (the region's own north/south extent), so nudging
      // zoom there crops the region itself. "Global" is the one case where
      // that constrained axis is latitude near the poles, which is fine to
      // crop -- so only Global gets a boost to shrink its large left/right
      // basemap padding.
      map.setZoom(map.getZoom() + extraZoom, { animate: false });
    }
  }, [map, JSON.stringify(bounds), extraZoom]);
  return null;
}

function nearestIndex(sortedOrUnsorted: number[], target: number): number {
  let bestIdx = 0;
  let bestDist = Infinity;
  for (let i = 0; i < sortedOrUnsorted.length; i++) {
    const dist = Math.abs(sortedOrUnsorted[i] - target);
    if (dist < bestDist) {
      bestDist = dist;
      bestIdx = i;
    }
  }
  return bestIdx;
}

/** Exact-value hover tooltip driven by the raw grid backing the overlay
 * image (not the image's pixel colors), so the number shown is the real
 * anomaly at the nearest grid cell rather than a decoded/approximated one. */
function GridHoverTooltip({ grid }: { grid: GridResponse | null }) {
  const map = useMap();
  const tooltipRef = useRef<L.Tooltip | null>(null);

  useEffect(() => {
    if (!tooltipRef.current) {
      tooltipRef.current = L.tooltip({ direction: "top", sticky: true, opacity: 0.95 });
    }
    const tooltip = tooltipRef.current;

    if (!grid || grid.lats.length === 0 || grid.lons.length === 0) {
      map.closeTooltip(tooltip);
      return;
    }

    const latMin = Math.min(...grid.lats);
    const latMax = Math.max(...grid.lats);
    const lonMin = Math.min(...grid.lons);
    const lonMax = Math.max(...grid.lons);

    function onMove(e: LeafletMouseEvent) {
      const { lat } = e.latlng;
      // Panning a world-wrapping map can push lng outside [-180,180]; fold back in.
      const lon = ((((e.latlng.lng + 180) % 360) + 360) % 360) - 180;

      if (lat < latMin || lat > latMax || lon < lonMin || lon > lonMax) {
        map.closeTooltip(tooltip);
        return;
      }

      const i = nearestIndex(grid!.lats, lat);
      const j = nearestIndex(grid!.lons, lon);
      const value = grid!.values[i]?.[j];
      if (value == null) {
        map.closeTooltip(tooltip);
        return;
      }

      tooltip.setContent(
        `<strong>${value > 0 ? "+" : ""}${value.toFixed(1)} ${grid!.unit}</strong>` +
          `<br/><span style="opacity:.7">${grid!.lats[i].toFixed(1)}°, ${grid!.lons[j].toFixed(1)}°</span>`,
      );
      tooltip.setLatLng(e.latlng);
      if (!map.hasLayer(tooltip)) tooltip.addTo(map);
    }

    function onLeave() {
      map.closeTooltip(tooltip);
    }

    map.on("mousemove", onMove);
    map.on("mouseout", onLeave);
    return () => {
      map.off("mousemove", onMove);
      map.off("mouseout", onLeave);
      map.closeTooltip(tooltip);
    };
  }, [map, grid]);

  return null;
}

export function AnomalyLeafletMap({
  overlay,
  grid,
  region,
  emptyReason,
}: {
  overlay: OverlayInfo | null;
  grid?: GridResponse | null;
  region?: string;
  emptyReason?: string;
}) {
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
        <MapContainer
          bounds={bounds}
          style={{ height: "100%", width: "100%" }}
          scrollWheelZoom={true}
          zoomSnap={0.1}
          zoomDelta={0.5}
        >
          <LayersControl position="topright">
            {BASEMAPS.map((b) => (
              <LayersControl.BaseLayer key={b.name} name={b.name} checked={b.checked}>
                <TileLayer url={b.url} attribution={b.attribution} />
              </LayersControl.BaseLayer>
            ))}
          </LayersControl>
          <ImageOverlay url={assetUrl(overlay.url!)} bounds={bounds} opacity={0.82} />
          <FitBounds bounds={bounds} extraZoom={region === "global" ? 0.6 : 0} />
          <GridHoverTooltip grid={grid ?? null} />
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
