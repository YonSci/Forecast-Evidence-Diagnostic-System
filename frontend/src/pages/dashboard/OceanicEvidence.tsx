import { useEffect, useMemo, useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { getJson, assetUrl } from "../../api/client";
import type { SstProxyRow, MetaResponse, OverlayInfo, GridResponse } from "../../api/types";
import { Callout } from "../../components/ui/Callout";
import { StatTile } from "../../components/ui/StatTile";
import { ControlField } from "../../components/ui/ControlField";
import { GroupedBarChart } from "../../components/charts/GroupedBarChart";
import { DivergingBarChart } from "../../components/charts/DivergingBarChart";
import type { DivergingDatum } from "../../components/charts/DivergingBarChart";
import { MapFigure } from "../../components/ui/MapFigure";
import { AnomalyLeafletMap } from "../../components/maps/AnomalyLeafletMap";
import type { IndexBox } from "../../components/maps/AnomalyLeafletMap";
import { fmt, sign, titleCase } from "../../lib/format";

const GALLERY: [string, string][] = [
  ["sst_indian_ocean_jjas.png", "NMME tmpsfc SST-proxy anomaly — Indian Ocean (IOD boxes) — JJAS 2026"],
  ["sst_pacific_enso_jjas.png", "NMME tmpsfc SST-proxy anomaly — Pacific / Nino3.4 box — JJAS 2026"],
  ["enso_iod_proxy_chart.png", "NMME-derived Nino3.4 / IOD-West / IOD-East proxy indices by period"],
  ["dmi_proxy_chart.png", "NMME-derived DMI proxy by forecast period"],
];

// Standard NOAA CPC Nino boxes + the IOD boxes already used elsewhere in
// this project -- matches scripts/25_compute_expanded_sst_indices.py.
// Bounds are [[southLat, westLon], [northLat, eastLon]]. Nino4 straddles
// the antimeridian, so it's drawn as two rectangles.
const SST_INDEX_BOXES: IndexBox[] = [
  { name: "Niño 1+2", rects: [[[-10, -90], [0, -80]]] },
  { name: "Niño 3", rects: [[[-5, -150], [5, -90]]] },
  { name: "Niño 3.4", rects: [[[-5, -170], [5, -120]]] },
  {
    name: "Niño 4",
    rects: [
      [[-5, 160], [5, 180]],
      [[-5, -180], [5, -150]],
    ],
  },
  { name: "IOD West", rects: [[[-10, 50], [10, 70]]] },
  { name: "IOD East", rects: [[[-10, 90], [0, 110]]] },
];

const SST_INIT = "2026-05-08";

export function OceanicEvidence() {
  const { data: meta } = useFetch<MetaResponse>("/api/meta");
  const { data: sst } = useFetch<SstProxyRow[]>("/api/oceanic/sst-proxy");
  const jjas = sst?.find((r) => r.period === "JJAS");

  const initMeta = meta?.initializations.find((i) => i.key === SST_INIT);
  const [period, setPeriod] = useState("JJAS");
  const [overlay, setOverlay] = useState<OverlayInfo | null>(null);
  const [grid, setGrid] = useState<GridResponse | null>(null);

  useEffect(() => {
    if (!initMeta) return;
    getJson<OverlayInfo>("/api/oceanic/overlay", { init: SST_INIT, period })
      .then(setOverlay)
      .catch(() => setOverlay({ available: false }));
    getJson<GridResponse>("/api/oceanic/grid", { init: SST_INIT, period })
      .then(setGrid)
      .catch(() => setGrid(null));
  }, [period, initMeta]);

  const grouped = useMemo(
    () =>
      (sst ?? []).map((r) => ({
        label: r.period,
        nino34: r.nino34_anomaly,
        iod_west: r.iod_west_anomaly,
        iod_east: r.iod_east_anomaly,
      })),
    [sst]
  );

  const dmiData: DivergingDatum[] = useMemo(() => (sst ?? []).map((r) => ({ label: r.period, value: r.dmi_proxy })), [sst]);

  return (
    <div className="tabpanel">
      <div className="panel-head">
        <h2>Oceanic evidence</h2>
        <p className="sub">
          Model-based ocean-driver proxies built from the NMME tmpsfc anomaly field over standard index boxes. These are
          not official observed ENSO or IOD indices &mdash; treat them as an approximate read on the forecast ocean
          pattern, not a replacement for NOAA/BOM/JMA official product monitoring.
        </p>
      </div>

      <Callout tone="warn" title="Proxy, not an official index.">
        Ni&ntilde;o1+2, Ni&ntilde;o3, Ni&ntilde;o3.4, Ni&ntilde;o4, IOD-West, IOD-East, and DMI values here are area
        means of the NMME forecast temperature field over the standard Ni&ntilde;o / IOD index boxes &mdash; a
        convenient proxy, not the dedicated SST index products issued by NOAA, BOM, or JMA.
      </Callout>

      {jjas && (
        <div className="grid-4" style={{ margin: "22px 0" }}>
          <StatTile label="Nino3.4 proxy, JJAS" value={jjas.nino34_anomaly} unit="K" footLabel="El Nino-like" footTone="dry" />
          <StatTile label="IOD-West proxy, JJAS" value={jjas.iod_west_anomaly} unit="K" footLabel={jjas.iod_west_anomaly < 0 ? "Below normal" : "Above normal"} footTone="neutral" />
          <StatTile label="IOD-East proxy, JJAS" value={jjas.iod_east_anomaly} unit="K" footLabel={jjas.iod_east_anomaly < 0 ? "Below normal" : "Above normal"} footTone="neutral" />
          <StatTile label="DMI proxy, JJAS" value={jjas.dmi_proxy} unit="K" footLabel={titleCase(jjas.dmi_classification)} footTone="neutral" />
        </div>
      )}

      <div className="card-head" style={{ marginTop: 8 }}>
        <h3>Sea surface temperature map</h3>
        <span className="hint">NMME tmpsfc anomaly, ocean only &mdash; May 2026 init</span>
      </div>
      {initMeta && (
        <div className="control-bar" style={{ maxWidth: 260, marginBottom: 12 }}>
          <ControlField
            label="Forecast period"
            value={period}
            onChange={setPeriod}
            options={initMeta.periods.map((p) => [p, meta!.period_labels[p] ?? p])}
          />
        </div>
      )}
      <AnomalyLeafletMap
        overlay={overlay}
        grid={grid}
        region="global"
        indexBoxes={SST_INDEX_BOXES}
        legendGradient="linear-gradient(90deg, #08306b, #c6dbef, #f7f7f7, #fcbba1, #67000d)"
        emptyReason="No rendered SST map for this period in this build."
      />

      <div className="grid-2" style={{ marginTop: 22 }}>
        <div className="chart-card">
          <div className="card-head">
            <h3>Nino3.4 / IOD-West / IOD-East proxy by period</h3>
            <span className="hint">K, vs. model climatology</span>
          </div>
          <GroupedBarChart
            data={grouped}
            unit="K"
            series={[
              { key: "nino34", name: "Nino3.4", color: "var(--cat-1)" },
              { key: "iod_west", name: "IOD-West", color: "var(--cat-2)" },
              { key: "iod_east", name: "IOD-East", color: "var(--cat-3)" },
            ]}
          />
          <div className="legend">
            <div className="legend-item"><span className="legend-swatch" style={{ background: "var(--cat-1)" }} />Nino3.4 proxy</div>
            <div className="legend-item"><span className="legend-swatch" style={{ background: "var(--cat-2)" }} />IOD-West proxy</div>
            <div className="legend-item"><span className="legend-swatch" style={{ background: "var(--cat-3)" }} />IOD-East proxy</div>
          </div>
        </div>
        <div className="chart-card">
          <div className="card-head">
            <h3>DMI proxy (IOD-West &minus; IOD-East)</h3>
            <span className="hint">K</span>
          </div>
          <DivergingBarChart data={dmiData} unit="K" />
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 22 }}>
        <div className="card">
          <h3 style={{ fontSize: "0.95rem", marginBottom: 8 }}>El Nino-like ocean pattern</h3>
          <p style={{ fontSize: "0.87rem", color: "var(--ink-2)" }}>
            NMME&apos;s tmpsfc-based Nino3.4 proxy is classified el_nino_like across every 2026 forecast period. A warm
            eastern-Pacific pattern of this kind is one of the classic drivers associated with a dry-risk interpretation
            for parts of Ethiopia and the Greater Horn during Kiremt, though the exact regional response depends on
            season and the accompanying circulation state.
          </p>
        </div>
        <div className="card">
          <h3 style={{ fontSize: "0.95rem", marginBottom: 8 }}>Indian Ocean gradient</h3>
          <p style={{ fontSize: "0.87rem", color: "var(--ink-2)" }}>
            The DMI proxy stays neutral-to-weak early in the season, then strengthens toward a positive-IOD-like pattern
            by August/September. A positive west-minus-east SST gradient can alter moisture transport into the Horn of
            Africa &mdash; a signal worth tracking alongside the Pacific pattern rather than in isolation.
          </p>
        </div>
      </div>

      <div className="map-grid" style={{ marginTop: 22 }}>
        {GALLERY.map(([file, caption]) => (
          <MapFigure key={file} src={assetUrl(`/static/gallery/${file}`)} caption={caption} />
        ))}
      </div>

      <h3 style={{ margin: "30px 0 12px", fontSize: "1.05rem", fontFamily: "var(--sans)" }}>Full proxy-index readout</h3>
      <div className="table-scroll">
        <table className="data-table" style={{ minWidth: 920 }}>
          <thead>
            <tr>
              <th>Period</th>
              <th>Nino1+2 (K)</th>
              <th>Nino3 (K)</th>
              <th>Nino3.4 (K)</th>
              <th>Nino4 (K)</th>
              <th>IOD-West (K)</th>
              <th>IOD-East (K)</th>
              <th>DMI (K)</th>
              <th>Classification</th>
            </tr>
          </thead>
          <tbody>
            {(sst ?? []).map((r) => (
              <tr key={r.period}>
                <td className="diag">{r.period}</td>
                <td className="num">{r.nino1_2_anomaly != null ? `${sign(r.nino1_2_anomaly)}${fmt(r.nino1_2_anomaly, 2)}` : "—"}</td>
                <td className="num">{r.nino3_anomaly != null ? `${sign(r.nino3_anomaly)}${fmt(r.nino3_anomaly, 2)}` : "—"}</td>
                <td className="num">{sign(r.nino34_anomaly)}{fmt(r.nino34_anomaly, 2)}</td>
                <td className="num">{r.nino4_anomaly != null ? `${sign(r.nino4_anomaly)}${fmt(r.nino4_anomaly, 2)}` : "—"}</td>
                <td className="num">{sign(r.iod_west_anomaly)}{fmt(r.iod_west_anomaly, 2)}</td>
                <td className="num">{sign(r.iod_east_anomaly)}{fmt(r.iod_east_anomaly, 2)}</td>
                <td className="num">{sign(r.dmi_proxy)}{fmt(r.dmi_proxy, 2)}</td>
                <td>
                  <span className="pill pill-dry pill-sm" style={{ marginRight: 4 }}>{titleCase(r.nino34_classification)}</span>
                  <span className="pill pill-outline pill-sm">{titleCase(r.dmi_classification)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
