import { useEffect, useMemo, useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { getJson } from "../../api/client";
import type { MetaResponse, AnomalySeriesResponse, AnomalyTableRow, OverlayInfo, GridResponse } from "../../api/types";
import { ControlField } from "../../components/ui/ControlField";
import { StatTile } from "../../components/ui/StatTile";
import { Callout } from "../../components/ui/Callout";
import { AnomalyLeafletMap } from "../../components/maps/AnomalyLeafletMap";
import { DivergingBarChart } from "../../components/charts/DivergingBarChart";
import type { DivergingDatum } from "../../components/charts/DivergingBarChart";
import { fmt, sign } from "../../lib/format";

export function AnomalyEvidence() {
  const { data: meta } = useFetch<MetaResponse>("/api/meta");

  const [init, setInit] = useState("2026-05-08");
  const [variable, setVariable] = useState<"prate" | "tmpsfc">("prate");
  const [region, setRegion] = useState("ethiopia");
  const [period, setPeriod] = useState("JJAS");
  const [tableRegion, setTableRegion] = useState<string>("current");
  const [overlay, setOverlay] = useState<OverlayInfo | null>(null);
  const [grid, setGrid] = useState<GridResponse | null>(null);
  const [tableRows, setTableRows] = useState<AnomalyTableRow[] | null>(null);

  const initMeta = meta?.initializations.find((i) => i.key === init);
  const regionMeta = meta?.regions.find((r) => r.key === region);

  // Keep the selected period valid whenever the initialization changes.
  useEffect(() => {
    if (initMeta && !initMeta.periods.includes(period)) {
      setPeriod(initMeta.periods[initMeta.periods.length - 1]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [init, initMeta?.periods.join(",")]);

  const { data: series } = useFetch<AnomalySeriesResponse>(meta ? "/api/anomaly" : null, { init, region, variable });

  useEffect(() => {
    if (!initMeta || !period) return;
    getJson<OverlayInfo>("/api/anomaly/overlay", { init, region, period, variable })
      .then(setOverlay)
      .catch(() => setOverlay({ available: false }));
  }, [init, region, period, variable, initMeta]);

  // Exact-value hover tooltips need the raw grid backing the overlay image;
  // only available for rainfall (prate), same restriction as the overlay.
  useEffect(() => {
    if (!initMeta || !period || variable !== "prate") {
      setGrid(null);
      return;
    }
    getJson<GridResponse>("/api/anomaly/grid", { init, region, period, variable })
      .then(setGrid)
      .catch(() => setGrid(null));
  }, [init, region, period, variable, initMeta]);

  const resolvedTableRegion = tableRegion === "current" ? region : tableRegion === "all" ? "all" : tableRegion;
  useEffect(() => {
    if (!meta) return;
    getJson<AnomalyTableRow[]>("/api/anomaly/table", { init, region: resolvedTableRegion })
      .then(setTableRows)
      .catch(() => setTableRows(null));
  }, [init, resolvedTableRegion, meta]);

  const reading = series?.readings.find((r) => r.period === period);

  const chartData: DivergingDatum[] = useMemo(() => {
    if (!series) return [];
    return series.readings.map((r) => ({
      label: r.period,
      value: variable === "prate" ? r.prate_mm_day : r.tmpsfc_anomaly_k,
    }));
  }, [series, variable]);

  if (!meta || !initMeta || !regionMeta) {
    return (
      <div className="tabpanel">
        <div className="panel-head">
          <h2>Anomaly evidence</h2>
          <p className="sub">Loading…</p>
        </div>
      </div>
    );
  }

  const periodLabel = meta.period_labels[period] ?? period;
  const isPrate = variable === "prate";

  const dryLean = isPrate ? (reading?.prate_mm_day ?? 0) < -0.0005 : false;
  const wetLean = isPrate ? (reading?.prate_mm_day ?? 0) > 0.0005 : false;
  const prateFootLabel = dryLean ? "Below normal (dry-leaning)" : wetLean ? "Above normal (wet-leaning)" : "Near normal";
  const prateFootTone = dryLean ? "dry" : wetLean ? "wet" : "neutral";

  const regionChipOptions: [string, string][] = [
    ["current", `Selected (${regionMeta.label})`],
    ["all", "All regions"],
    ...meta.regions.map((r): [string, string] => [r.key, r.label]),
  ];

  return (
    <div className="tabpanel">
      <div className="panel-head">
        <h2>Anomaly evidence</h2>
        <p className="sub">
          Direct signal from the CPC NMME real-time ensemble-mean anomaly product. An anomaly here is the model&apos;s
          forecast for a given month or season compared with that same model&apos;s own climatology for the same lead
          time and season &mdash; not compared with a different observational normal.
        </p>
      </div>

      <Callout>
        Negative precipitation anomaly = below-normal rainfall for that lead time (dry-leaning). Positive = above-normal
        (wet-leaning). Positive surface-temperature anomaly = warmer than the model&apos;s own normal.
      </Callout>

      <div className="control-bar">
        <ControlField label="Forecast period" value={period} onChange={setPeriod} options={initMeta.periods.map((p) => [p, meta.period_labels[p] ?? p])} />
        <ControlField label="Variable" value={variable} onChange={(v) => setVariable(v as "prate" | "tmpsfc")} options={Object.entries(meta.variables)} />
        <ControlField label="Geographic region" value={region} onChange={setRegion} options={meta.regions.map((r) => [r.key, r.label])} />
        <ControlField label="Initialization" value={init} onChange={setInit} options={meta.initializations.map((i) => [i.key, i.label])} />
      </div>
      <p style={{ fontSize: "0.78rem", color: "var(--muted)", margin: "8px 0 12px" }}>
        Three initialization cycles are loaded in this build — CPC NMME ENSMEAN, 2026-05-08, 2026-06-08, and 2026-07-08 00Z.
      </p>
      {init !== "2026-05-08" && (
        <Callout tone="warn" title={`${initMeta.short_label} coverage is narrower.`}>
          {initMeta.note}
        </Callout>
      )}

      <div style={{ marginBottom: 26 }}>
        <AnomalyLeafletMap
          overlay={overlay}
          grid={grid}
          region={region}
          emptyReason={`No rendered map for ${meta.variables[variable]} · ${regionMeta.label} · ${periodLabel} in this build.`}
        />
      </div>

      <div className="grid-4" style={{ marginBottom: 22 }}>
        {isPrate ? (
          <>
            <StatTile label={`Rainfall rate, ${periodLabel}`} value={reading?.prate_mm_day ?? null} unit="mm/day" footLabel={prateFootLabel} footTone={prateFootTone} />
            <StatTile label={`Rainfall total, ${periodLabel}`} value={reading?.prate_total ?? null} unit={reading?.prate_total_unit ?? ""} footLabel={prateFootLabel} footTone={prateFootTone} />
            <StatTile label="Region" value={null} footLabel={regionMeta.label} footTone="outline" />
            <StatTile label="Classification" value={null} footLabel={init === "2026-05-08" ? "See Integrated Evidence Matrix" : "Not in evidence matrix (non-May init)"} footTone="outline" />
          </>
        ) : (
          <>
            <StatTile
              label={`Surface temperature anomaly, ${periodLabel}`}
              value={reading?.tmpsfc_anomaly_k ?? null}
              unit="K"
              footLabel={(reading?.tmpsfc_anomaly_k ?? 0) < 0 ? "Cooler than normal" : "Warmer than normal"}
              footTone="neutral"
            />
            <StatTile label="Region" value={null} footLabel={regionMeta.label} footTone="outline" />
            <StatTile label="Role in scoring" value={null} footLabel="Context only — not independently scored" footTone="neutral" />
            <StatTile label="Initialization" value={null} footLabel={initMeta.short_label} footTone="outline" />
          </>
        )}
      </div>

      {reading && (
        <p style={{ fontSize: "0.92rem", color: "var(--ink-2)", margin: "-6px 0 26px", maxWidth: "70ch" }}>
          {isPrate
            ? `NMME indicates ${dryLean ? "below-normal (dry-leaning)" : wetLean ? "above-normal (wet-leaning)" : "near-normal"} rainfall over ${regionMeta.label} for ${periodLabel}: ${sign(reading.prate_total)}${fmt(reading.prate_total, 1)} ${reading.prate_total_unit} (${sign(reading.prate_mm_day)}${fmt(reading.prate_mm_day, 3)} mm/day), relative to the model's own climatology for this lead time.`
            : `NMME's surface-temperature field runs ${(reading.tmpsfc_anomaly_k ?? 0) < 0 ? "cooler" : "warmer"} than its own climatology over ${regionMeta.label} for ${periodLabel}: ${sign(reading.tmpsfc_anomaly_k)}${fmt(reading.tmpsfc_anomaly_k, 2)} K. This is retained as circulation context and is not independently scored in the evidence matrix.`}
        </p>
      )}

      <div className="chart-card">
        <div className="card-head">
          <h3>{isPrate ? "Rainfall-rate anomaly across forecast periods" : "Surface-temperature anomaly across forecast periods"}</h3>
          <span className="hint">
            {regionMeta.label} · {initMeta.short_label} · click a bar to change period
          </span>
        </div>
        <DivergingBarChart data={chartData} unit={isPrate ? "mm/day" : "K"} highlightLabel={period} onBarClick={setPeriod} />
        <div className="legend">
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: "var(--wet)" }} />
            {isPrate ? "Above-normal (wet-leaning)" : "Warmer than normal"}
          </div>
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: "var(--dry)" }} />
            {isPrate ? "Below-normal (dry-leaning)" : "Cooler than normal"}
          </div>
        </div>
      </div>

      <h3 style={{ margin: "38px 0 12px", fontSize: "1.05rem", fontFamily: "var(--sans)" }}>
        Full {meta.variables[variable].toLowerCase()} anomaly readout — {initMeta.short_label}
      </h3>
      <div className="table-toolbar" style={{ marginBottom: 12 }}>
        <div className="chip-toggle">
          {regionChipOptions.map(([val, lab]) => (
            <button key={val} className={tableRegion === val ? "on" : ""} onClick={() => setTableRegion(val)}>
              {lab}
            </button>
          ))}
        </div>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Region</th>
              <th>Period</th>
              {isPrate ? (
                <>
                  <th>mm/day</th>
                  <th>Total</th>
                  <th>Reading</th>
                </>
              ) : (
                <>
                  <th>Anomaly (K)</th>
                  <th>Reading</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {(tableRows ?? []).map((r) => {
              const isCurrent = r.region === region && r.period === period;
              const rowDry = (r.prate_mm_day ?? 0) < -0.0005;
              return (
                <tr key={`${r.region}-${r.period}`} style={isCurrent ? { background: "var(--accent-soft)" } : undefined}>
                  <td className="diag">{r.region_label}</td>
                  <td>{r.period_label}</td>
                  {isPrate ? (
                    <>
                      <td className="num">{sign(r.prate_mm_day)}{fmt(r.prate_mm_day, 3)}</td>
                      <td className="num">{sign(r.prate_total)}{fmt(r.prate_total, 1)} {r.prate_total_unit}</td>
                      <td>
                        <span className={`pill pill-sm pill-${rowDry ? "dry" : "wet"}`}>{rowDry ? "Below normal" : "Above normal"}</span>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="num">{sign(r.tmpsfc_anomaly_k)}{fmt(r.tmpsfc_anomaly_k, 3)}</td>
                      <td>
                        <span className="pill pill-sm pill-neutral">{(r.tmpsfc_anomaly_k ?? 0) < 0 ? "Cooler" : "Warmer"}</span>
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
