import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, ImageOverlay, GeoJSON, Rectangle, Tooltip, LayersControl, Pane, useMap } from "react-leaflet";
import L from "leaflet";
import type { LatLngBoundsExpression, LeafletMouseEvent } from "leaflet";
import type { OverlayInfo, GridResponse } from "../../api/types";
import { assetUrl } from "../../api/client";
import { fmt } from "../../lib/format";

// A named reference box that may need more than one rectangle (e.g. Nino4
// straddles the antimeridian at 180deg, which Leaflet can't express as a
// single lon-wrapping rectangle).
export interface IndexBox {
  name: string;
  rects: LatLngBoundsExpression[];
}

const INDEX_BOX_STYLE: L.PathOptions = { color: "#1f2430", weight: 1.5, fill: false, dashArray: "4 3" };

function IndexBoxesOverlay({ boxes }: { boxes: IndexBox[] }) {
  if (boxes.length === 0) return null;
  return (
    <LayersControl.Overlay name="Index boxes" checked>
      {/* Above the country-borders pane (450) so box outlines/labels never
          get hidden behind them. */}
      <Pane name="index-boxes-pane" style={{ zIndex: 460 }}>
        <>
          {boxes.map((box) =>
            box.rects.map((rect, i) => (
              <Rectangle key={`${box.name}-${i}`} bounds={rect} pathOptions={INDEX_BOX_STYLE}>
                <Tooltip permanent direction="center" className="index-box-label" opacity={0.9}>
                  {box.name}
                </Tooltip>
              </Rectangle>
            )),
          )}
        </>
      </Pane>
    </LayersControl.Overlay>
  );
}

// Static reference layer (Natural Earth 50m, simplified) -- fetched once
// and reused across every map instance/page, since it never changes.
let countryBordersPromise: Promise<GeoJSON.FeatureCollection> | null = null;
function loadCountryBorders(): Promise<GeoJSON.FeatureCollection> {
  if (!countryBordersPromise) {
    countryBordersPromise = fetch("/country_borders.geojson").then((r) => r.json());
  }
  return countryBordersPromise;
}

const BORDER_STYLE: L.PathOptions = { color: "#5b6270", weight: 1, opacity: 0.85, fill: false };
const EMPTY_FEATURE_COLLECTION: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function CountryBordersOverlay() {
  // LayersControl only picks up an overlay it sees on its first render, so
  // <LayersControl.Overlay> and its <GeoJSON> child must be mounted from the
  // start (react-leaflet's GeoJSON also doesn't react to a changed `data`
  // prop after mount) -- start empty and populate the layer imperatively
  // via the ref once the fetch resolves.
  const geoJsonRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadCountryBorders().then((d) => {
      if (cancelled || !geoJsonRef.current) return;
      geoJsonRef.current.clearLayers();
      geoJsonRef.current.addData(d);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <LayersControl.Overlay name="Country borders" checked>
      {/* Own pane (z-index above the default overlayPane's 400) so the
          borders reliably paint above the anomaly ImageOverlay regardless
          of which mounts first -- more robust than relying on JSX order. */}
      <Pane name="country-borders-pane" style={{ zIndex: 450 }}>
        <GeoJSON ref={geoJsonRef} data={EMPTY_FEATURE_COLLECTION} style={BORDER_STYLE} interactive={false} />
      </Pane>
    </LayersControl.Overlay>
  );
}

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

function FitBounds({ bounds, cover = false }: { bounds: LatLngBoundsExpression; cover?: boolean }) {
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
    if (cover) {
      // fitBounds ("contain") picks the tightest zoom where BOTH dimensions
      // still fit, constrained by whichever axis is closer to the
      // container's aspect ratio -- the other axis is then under-filled,
      // leaving blank map canvas as padding. For a country-sized region
      // (Ethiopia, Greater Horn, Africa) that constrained axis is real
      // content (the region's own north/south extent), so cropping it would
      // crop the region itself -- not used there. "Global" is the one case
      // where the under-filled axis is left/right basemap padding (the
      // constrained axis is latitude near the poles, which is fine to
      // crop), so compute the exact extra zoom needed to fill it too.
      const zoom = map.getZoom();
      const b = L.latLngBounds(bounds);
      const nePx = map.project(b.getNorthEast(), zoom);
      const swPx = map.project(b.getSouthWest(), zoom);
      const boundsPx = { x: Math.abs(nePx.x - swPx.x), y: Math.abs(nePx.y - swPx.y) };
      const mapPx = map.getSize();
      const scale = Math.max(mapPx.x / boundsPx.x, mapPx.y / boundsPx.y);
      if (scale > 1.001) {
        map.setZoom(zoom + Math.log2(scale), { animate: false });
      }
    }
  }, [map, JSON.stringify(bounds), cover]);
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
      // Panning a world-wrapping map can push lng outside the grid's own
      // longitude range; fold back into [lonMin, lonMin+360) -- works for
      // both -180..180 (rainfall) and 0..360 Pacific-centered (SST) grids.
      const lon = (((e.latlng.lng - lonMin) % 360) + 360) % 360 + lonMin;

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
  indexBoxes = [],
  legendGradient = "linear-gradient(90deg, var(--dry), #f5f1ea, var(--wet))",
}: {
  overlay: OverlayInfo | null;
  grid?: GridResponse | null;
  region?: string;
  emptyReason?: string;
  /** Toggleable reference boxes drawn on top of the map (e.g. Nino3.4/IOD
   * index regions on the Oceanic Evidence SST map). Omit for none. */
  indexBoxes?: IndexBox[];
  /** CSS gradient for the legend bar -- defaults to the rainfall dry/wet
   * scheme; pass a blue-red gradient for temperature/SST overlays. */
  legendGradient?: string;
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
            <CountryBordersOverlay />
            <IndexBoxesOverlay boxes={indexBoxes} />
          </LayersControl>
          <ImageOverlay url={assetUrl(overlay.url!)} bounds={bounds} opacity={0.82} />
          <FitBounds bounds={bounds} cover={region === "global"} />
          <GridHoverTooltip grid={grid ?? null} />
        </MapContainer>
        {overlay.vmin != null && overlay.vmax != null && (
          <div className="leaflet-legend">
            <div>Anomaly ({overlay.unit})</div>
            <div className="bar" style={{ background: legendGradient }} />
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
