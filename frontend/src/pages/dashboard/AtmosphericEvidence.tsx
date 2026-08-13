import { useEffect, useMemo, useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import { getJson } from "../../api/client";
import type { TejRow, Cfsv2Row, OverlayInfo, GridResponse } from "../../api/types";
import { Callout } from "../../components/ui/Callout";
import { Pill, directionTone } from "../../components/ui/Pill";
import { ControlField } from "../../components/ui/ControlField";
import { MagnitudeBarChart } from "../../components/charts/MagnitudeBarChart";
import { DivergingBarChart } from "../../components/charts/DivergingBarChart";
import type { DivergingDatum } from "../../components/charts/DivergingBarChart";
import { AnomalyLeafletMap } from "../../components/maps/AnomalyLeafletMap";
import { fmt } from "../../lib/format";

const CARD_META: Record<string, [string, string]> = {
  div200: ["200 hPa divergence", "Upper-level divergence/convergence over Ethiopia"],
  mfc850: ["850 hPa moisture-flux convergence", "Low-level moisture convergence over Ethiopia"],
  omega500: ["500 hPa omega", "Mid-level vertical motion"],
  omega700: ["700 hPa omega", "Lower-mid vertical motion"],
  tej_strength: ["TEJ strength (CFSv2)", "Tropical Easterly Jet proxy, −u200"],
};

const RDBU = "linear-gradient(90deg, #08306b, #c6dbef, #f7f7f7, #fcbba1, #67000d)";
const JET = "linear-gradient(90deg, #00007f, #0000ff, #00ffff, #7fff7f, #ffff00, #ff7f00, #7f0000)";
const YLGNBU = "linear-gradient(90deg, #ffffd9, #edf8b1, #c7e9b4, #7fcdbb, #41b6c4, #1d91c0, #225ea8, #253494, #081d58)";
const BRBG = "linear-gradient(90deg, #543005, #bf812d, #f6e8c3, #f5f5f5, #c7eae5, #35978f, #003c30)";

// A TEJ dynamical-consistency check, not just a list of diagnostics: is
// the jet where/how strong the forecast implies, does its exit-region
// divergence favor ascent, is that ascent actually happening, and is
// moisture both being supplied and accumulating to support it. Every
// entry is ERA5 1991-2020 climatology (no per-2026-forecast gridded
// product exists yet for any of these six), so the period dropdown
// switches the climatological month/season, not a forecast lead time --
// see scripts/27_generate_atmospheric_leaflet_overlays.py.
const CIRCULATION_MAPS: { key: string; title: string; blurb: string; unit: string; legendGradient: string }[] = [
  {
    key: "u200",
    title: "200 hPa zonal wind",
    blurb: "Primary indicator of TEJ strength.",
    unit: "m/s",
    legendGradient: RDBU,
  },
  {
    key: "u200_vectors",
    title: "200 hPa wind vectors",
    blurb: "Shows the actual circulation and jet orientation.",
    unit: "m/s",
    legendGradient: JET,
  },
  {
    key: "divergence200",
    title: "200 hPa divergence",
    blurb: "Positive divergence can indicate favorable upper-level outflow.",
    unit: "s⁻¹",
    legendGradient: RDBU,
  },
  {
    key: "omega500",
    title: "Vertical velocity (ω500)",
    blurb: "Forced ascent (negative) or subsidence (positive) beneath the jet.",
    unit: "Pa/s",
    legendGradient: RDBU,
  },
  {
    key: "qflux850",
    title: "850 hPa moisture flux (qV850)",
    blurb: "Tells whether moisture is actually being supplied.",
    unit: "kg/kg·m/s",
    legendGradient: YLGNBU,
  },
  {
    key: "mfc850",
    title: "850 hPa moisture-flux convergence",
    blurb: "Helps diagnose low-level moisture accumulation.",
    unit: "kg/kg/s",
    legendGradient: BRBG,
  },
];

const CIRC_PERIODS = ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"];
const CIRC_PERIOD_LABELS: Record<string, string> = {
  Jun: "June",
  Jul: "July",
  Aug: "August",
  Sep: "September",
  JJA: "JJA",
  JJAS: "JJAS",
};

function CirculationMapCard({
  variableKey,
  title,
  blurb,
  unit,
  legendGradient,
  period,
}: {
  variableKey: string;
  title: string;
  blurb: string;
  unit: string;
  legendGradient: string;
  period: string;
}) {
  const [overlay, setOverlay] = useState<OverlayInfo | null>(null);
  const [grid, setGrid] = useState<GridResponse | null>(null);

  useEffect(() => {
    getJson<OverlayInfo>("/api/atmospheric/overlay", { variable: variableKey, period })
      .then(setOverlay)
      .catch(() => setOverlay({ available: false }));
    getJson<GridResponse>("/api/atmospheric/grid", { variable: variableKey, period })
      .then(setGrid)
      .catch(() => setGrid(null));
  }, [variableKey, period]);

  return (
    <div className="chart-card">
      <div className="card-head">
        <h3>{title}</h3>
        <span className="hint">ERA5 climatology, 1991–2020 &middot; {unit}</span>
      </div>
      <p style={{ fontSize: "0.84rem", color: "var(--ink-2)", marginTop: -8, marginBottom: 12 }}>{blurb}</p>
      <AnomalyLeafletMap
        overlay={overlay}
        grid={grid}
        legendGradient={legendGradient}
        emptyReason="No rendered map for this period in this build."
      />
    </div>
  );
}

export function AtmosphericEvidence() {
  const { data: tej } = useFetch<TejRow[]>("/api/atmospheric/tej-climatology");
  const { data: cfsv2 } = useFetch<Cfsv2Row[]>("/api/atmospheric/cfsv2", { domain: "ethiopia" });
  const [circPeriod, setCircPeriod] = useState("JJAS");

  const tejChartData = useMemo(
    () => (tej ?? []).map((r) => ({ label: r.period.slice(0, 3), value: r.value })),
    [tej]
  );

  const jjasCards = useMemo(() => {
    if (!cfsv2) return [];
    return Object.keys(CARD_META)
      .map((key) => cfsv2.find((r) => r.period === "JJAS_2026" && r.diagnostic === key))
      .filter((r): r is Cfsv2Row => !!r);
  }, [cfsv2]);

  const periodScoreData: DivergingDatum[] = useMemo(() => {
    if (!cfsv2) return [];
    const periods = ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"];
    // approximate weighted score per period from raw dry/wet-support classification counts
    return periods.map((p) => {
      const rows = cfsv2.filter((r) => r.period === `${p}_2026`);
      const score = rows.reduce((sum, r) => {
        if (r.classification === "convergence") return sum + 0.5;
        if (r.classification === "rising_motion_tendency" || r.classification === "moisture_convergence") return sum - 0.5;
        return sum;
      }, 0);
      return { label: p, value: score };
    });
  }, [cfsv2]);

  return (
    <div className="tabpanel">
      <div className="panel-head">
        <h2>Atmospheric evidence</h2>
        <p className="sub">
          Tests whether the circulation is dynamically consistent with the rainfall signal &mdash; distinct from the
          anomaly evidence. ERA5 fields (1991&ndash;2020) describe the normal Kiremt circulation background; CFSv2
          NOMADS fields are a June-2026-initialized raw operational forecast, not yet converted to an anomaly, so they
          carry lower confidence weight.
        </p>
      </div>

      <Callout>
        The Anomaly Evidence tab shows what the forecast says will happen. This tab tests whether the physical
        mechanisms that would have to be in place &mdash; jet strength, moisture convergence, rising motion, upper-level
        divergence &mdash; are actually pointing the same direction.
      </Callout>

      <div className="grid-3" style={{ margin: "22px 0" }}>
        {jjasCards.map((r) => {
          const meta = CARD_META[r.diagnostic];
          const evTone = r.classification === "convergence" ? directionTone("supports_dry_kiremt") : r.classification.includes("rising") || r.classification.includes("moisture") ? directionTone("supports_wet_or_reduces_dry_risk") : directionTone(null);
          return (
            <div className="card" key={r.diagnostic}>
              <div className="card-head">
                <h3>{meta[0]}</h3>
                <Pill tone={evTone.tone}>{evTone.label}</Pill>
              </div>
              <div style={{ fontFamily: "var(--mono)", fontSize: "1.35rem", fontWeight: 600, marginBottom: 6 }}>
                {fmt(r.value, Math.abs(r.value) < 0.01 ? 6 : 3)} {r.units}
              </div>
              <p style={{ fontSize: "0.84rem", color: "var(--ink-2)" }}>{meta[1]}</p>
              <p style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{r.description}</p>
            </div>
          );
        })}
      </div>

      <div className="grid-2">
        <div className="chart-card">
          <div className="card-head">
            <h3>ERA5 TEJ strength climatology (1991&ndash;2020)</h3>
            <span className="hint">m s&#8315;&sup1;</span>
          </div>
          <MagnitudeBarChart data={tejChartData} unit="m/s" />
          <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginTop: 8 }}>
            Climatological baseline only &mdash; describes the normal jet, not the 2026 anomaly.
          </p>
        </div>
        <div className="chart-card">
          <div className="card-head">
            <h3>CFSv2 weighted evidence score by period</h3>
            <span className="hint">Ethiopia, raw dynamics</span>
          </div>
          <DivergingBarChart data={periodScoreData} unit="score" dryIsPositive />
        </div>
      </div>

      <div className="card-head" style={{ marginTop: 30 }}>
        <h3 style={{ fontSize: "1.05rem", fontFamily: "var(--sans)" }}>TEJ dynamical-consistency check</h3>
        <span className="hint">Jet strength &amp; structure &rarr; upper divergence &rarr; ascent &rarr; moisture supply &amp; accumulation</span>
      </div>
      <p className="sub" style={{ marginTop: -8, marginBottom: 16, maxWidth: "none" }}>
        Where the jet sits, its entrance/exit structure, upper-level divergence, forced ascent, and whether moisture is
        actually being supplied and accumulating at low levels all have to line up for a dry- or wet-risk signal to be
        dynamically consistent, not just a single-diagnostic coincidence &mdash; these six read together, not in isolation.
      </p>
      <div className="control-bar" style={{ maxWidth: 260, margin: "0 0 16px" }}>
        <ControlField
          label="Period"
          value={circPeriod}
          onChange={setCircPeriod}
          options={CIRC_PERIODS.map((p) => [p, CIRC_PERIOD_LABELS[p]])}
        />
      </div>

      {CIRCULATION_MAPS.map((m) => (
        <div key={m.key} style={{ marginBottom: 22 }}>
          <CirculationMapCard
            variableKey={m.key}
            title={m.title}
            blurb={m.blurb}
            unit={m.unit}
            legendGradient={m.legendGradient}
            period={circPeriod}
          />
        </div>
      ))}
    </div>
  );
}
