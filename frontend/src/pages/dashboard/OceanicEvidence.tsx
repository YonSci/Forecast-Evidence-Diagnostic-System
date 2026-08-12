import { useEffect, useMemo, useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { getJson } from "../../api/client";
import type { SstProxyRow, MetaResponse, OverlayInfo, GridResponse } from "../../api/types";
import { Callout } from "../../components/ui/Callout";
import { StatTile } from "../../components/ui/StatTile";
import { Pill } from "../../components/ui/Pill";
import type { PillTone } from "../../components/ui/Pill";
import { ControlField } from "../../components/ui/ControlField";
import { GroupedBarChart } from "../../components/charts/GroupedBarChart";
import { DivergingBarChart } from "../../components/charts/DivergingBarChart";
import type { DivergingDatum } from "../../components/charts/DivergingBarChart";
import { MultiLineChart } from "../../components/charts/MultiLineChart";
import { AnomalyLeafletMap } from "../../components/maps/AnomalyLeafletMap";
import type { IndexBox } from "../../components/maps/AnomalyLeafletMap";
import { fmt, sign, titleCase } from "../../lib/format";

// Standard NOAA CPC Nino boxes + the IOD boxes already used elsewhere in
// this project -- matches scripts/25_compute_expanded_sst_indices.py.
// Bounds are [[southLat, westLon], [northLat, eastLon]], expressed in the
// same 0-360 (Pacific-centered) longitude frame the SST raster renders in
// (see scripts/26) -- the map's initial view spans lon 0-360, so a box
// given in signed -180..180 form (e.g. Nino3.4 as -170 to -120) would
// render off-screen to the left of that view. In this frame Nino4 no
// longer needs to be split across the antimeridian either.
const SST_INDEX_BOXES: IndexBox[] = [
  { name: "Niño 1+2", rects: [[[-10, 270], [0, 280]]] },
  { name: "Niño 3", rects: [[[-5, 210], [5, 270]]] },
  { name: "Niño 3.4", rects: [[[-5, 190], [5, 240]]] },
  { name: "Niño 4", rects: [[[-5, 160], [5, 210]]] },
  { name: "IOD West", rects: [[[-10, 50], [10, 70]]] },
  { name: "IOD East", rects: [[[-10, 90], [0, 110]]] },
];

const SST_INIT = "2026-05-08";
const MONTHLY_PERIODS = ["Jun", "Jul", "Aug", "Sep"];

// Same +/-0.5degC threshold the backend uses for the Nino3.4 proxy
// (scripts/05_compute_dynamic_diagnostics.py::classify_value), applied to
// the other Nino boxes too since they share the same tmpsfc-anomaly
// methodology and aren't classified server-side.
function classifyNinoBox(value: number | null): string | null {
  if (value == null) return null;
  if (value >= 0.5) return "el_nino_like";
  if (value <= -0.5) return "la_nina_like";
  return "neutral_or_weak";
}

function ninoTone(cls: string): PillTone {
  if (cls === "el_nino_like") return "dry";
  if (cls === "la_nina_like") return "wet";
  return "outline";
}

// IOD-West/IOD-East don't have an official combined threshold (only their
// difference, the DMI, does) -- fall back to a sign-only read, matching the
// convention already used for these two boxes in the stat tiles above.
function classifyIodBox(value: number | null): string | null {
  if (value == null) return null;
  return value < 0 ? "below_normal" : "above_normal";
}

function dmiTone(cls: string): PillTone {
  if (cls === "positive_iod_like") return "dry";
  if (cls === "negative_iod_like") return "wet";
  return "outline";
}

function NumCell({ value, cls, tone }: { value: number | null; cls: string | null; tone: PillTone }) {
  return (
    <td className="num">
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
        <span>{value != null ? `${sign(value)}${fmt(value, 2)}` : "—"}</span>
        {cls && (
          <Pill tone={tone} small>
            {titleCase(cls)}
          </Pill>
        )}
      </div>
    </td>
  );
}

export function OceanicEvidence() {
  const { data: meta } = useFetch<MetaResponse>("/api/meta");
  const { data: sst } = useFetch<SstProxyRow[]>("/api/oceanic/sst-proxy");

  const initMeta = meta?.initializations.find((i) => i.key === SST_INIT);
  const [period, setPeriod] = useState("JJAS");
  const [overlay, setOverlay] = useState<OverlayInfo | null>(null);
  const [grid, setGrid] = useState<GridResponse | null>(null);

  const selected = sst?.find((r) => r.period === period);
  const periodLabel = meta?.period_labels[period] ?? period;

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

  const monthlyTimeseries = useMemo(
    () =>
      (sst ?? [])
        .filter((r) => MONTHLY_PERIODS.includes(r.period))
        .sort((a, b) => MONTHLY_PERIODS.indexOf(a.period) - MONTHLY_PERIODS.indexOf(b.period))
        .map((r) => ({
          label: r.period,
          nino1_2: r.nino1_2_anomaly,
          nino3: r.nino3_anomaly,
          nino34: r.nino34_anomaly,
          nino4: r.nino4_anomaly,
          iod_west: r.iod_west_anomaly,
          iod_east: r.iod_east_anomaly,
        })),
    [sst]
  );

  return (
    <div className="tabpanel">
      <div className="panel-head">
        <h2>Oceanic evidence</h2>
        <p className="sub" style={{ maxWidth: "none" }}>
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

      {initMeta && (
        <div className="control-bar" style={{ maxWidth: 260, margin: "22px 0 0" }}>
          <ControlField
            label="Forecast period"
            value={period}
            onChange={setPeriod}
            options={initMeta.periods.map((p) => [p, meta!.period_labels[p] ?? p])}
          />
        </div>
      )}

      {selected && (
        <div className="grid-4" style={{ margin: "16px 0 22px" }}>
          <StatTile
            label={`Nino3.4 proxy, ${periodLabel}`}
            value={selected.nino34_anomaly}
            unit="°C"
            footLabel={titleCase(selected.nino34_classification)}
            footTone={ninoTone(selected.nino34_classification)}
          />
          <StatTile
            label={`IOD-West proxy, ${periodLabel}`}
            value={selected.iod_west_anomaly}
            unit="°C"
            footLabel={selected.iod_west_anomaly < 0 ? "Below normal" : "Above normal"}
            footTone="neutral"
          />
          <StatTile
            label={`IOD-East proxy, ${periodLabel}`}
            value={selected.iod_east_anomaly}
            unit="°C"
            footLabel={selected.iod_east_anomaly < 0 ? "Below normal" : "Above normal"}
            footTone="neutral"
          />
          <StatTile
            label={`DMI proxy, ${periodLabel}`}
            value={selected.dmi_proxy}
            unit="°C"
            footLabel={titleCase(selected.dmi_classification)}
            footTone={dmiTone(selected.dmi_classification)}
          />
        </div>
      )}

      <div className="card-head" style={{ marginTop: 8 }}>
        <h3>Sea surface temperature map</h3>
        <span className="hint">NMME tmpsfc anomaly, ocean only &mdash; May 2026 init</span>
      </div>
      {initMeta && (
        <p className="hint" style={{ marginBottom: 12 }}>
          Uses the forecast period selected above.
        </p>
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
            <span className="hint">&deg;C, vs. model climatology</span>
          </div>
          <GroupedBarChart
            data={grouped}
            unit="°C"
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
            <span className="hint">&deg;C</span>
          </div>
          <DivergingBarChart data={dmiData} unit="°C" />
        </div>
      </div>

      

      <h3 style={{ margin: "30px 0 12px", fontSize: "1.05rem", fontFamily: "var(--sans)" }}>Full proxy-index readout</h3>
      <div className="table-scroll">
        <table className="data-table" style={{ minWidth: 920 }}>
          <thead>
            <tr>
              <th>Period</th>
              <th>Nino1+2 (&deg;C)</th>
              <th>Nino3 (&deg;C)</th>
              <th>Nino3.4 (&deg;C)</th>
              <th>Nino4 (&deg;C)</th>
              <th>IOD-West (&deg;C)</th>
              <th>IOD-East (&deg;C)</th>
              <th>DMI (&deg;C)</th>
            </tr>
          </thead>
          <tbody>
            {(sst ?? []).map((r) => (
              <tr key={r.period}>
                <td className="diag">{r.period}</td>
                <NumCell value={r.nino1_2_anomaly} cls={classifyNinoBox(r.nino1_2_anomaly)} tone={ninoTone(classifyNinoBox(r.nino1_2_anomaly) ?? "")} />
                <NumCell value={r.nino3_anomaly} cls={classifyNinoBox(r.nino3_anomaly)} tone={ninoTone(classifyNinoBox(r.nino3_anomaly) ?? "")} />
                <NumCell value={r.nino34_anomaly} cls={r.nino34_classification} tone={ninoTone(r.nino34_classification)} />
                <NumCell value={r.nino4_anomaly} cls={classifyNinoBox(r.nino4_anomaly)} tone={ninoTone(classifyNinoBox(r.nino4_anomaly) ?? "")} />
                <NumCell value={r.iod_west_anomaly} cls={classifyIodBox(r.iod_west_anomaly)} tone="outline" />
                <NumCell value={r.iod_east_anomaly} cls={classifyIodBox(r.iod_east_anomaly)} tone="outline" />
                <NumCell value={r.dmi_proxy} cls={r.dmi_classification} tone={dmiTone(r.dmi_classification)} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="chart-card" style={{ marginTop: 22 }}>
        <div className="card-head">
          <h3>Index values by month</h3>
          <span className="hint">&deg;C &mdash; June through September 2026</span>
        </div>
        <MultiLineChart
          data={monthlyTimeseries}
          unit="°C"
          series={[
            { key: "nino1_2", name: "Nino1+2", color: "var(--cat-1)" },
            { key: "nino3", name: "Nino3", color: "var(--cat-2)" },
            { key: "nino34", name: "Nino3.4", color: "var(--cat-3)" },
            { key: "nino4", name: "Nino4", color: "var(--cat-4)" },
            { key: "iod_west", name: "IOD-West", color: "var(--cat-5)" },
            { key: "iod_east", name: "IOD-East", color: "var(--cat-6)" },
          ]}
        />
      </div>
    </div>
  );
}
