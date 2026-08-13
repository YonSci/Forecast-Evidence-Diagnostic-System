import { useMemo } from "react";
import { useFetch } from "../../hooks/useFetch";
import { assetUrl } from "../../api/client";
import type { TejRow, Cfsv2Row } from "../../api/types";
import { Callout } from "../../components/ui/Callout";
import { Pill, directionTone } from "../../components/ui/Pill";
import { MagnitudeBarChart } from "../../components/charts/MagnitudeBarChart";
import { DivergingBarChart } from "../../components/charts/DivergingBarChart";
import type { DivergingDatum } from "../../components/charts/DivergingBarChart";
import { MapFigure } from "../../components/ui/MapFigure";
import { fmt } from "../../lib/format";

const CARD_META: Record<string, [string, string]> = {
  div200: ["200 hPa divergence", "Upper-level divergence/convergence over Ethiopia"],
  mfc850: ["850 hPa moisture-flux convergence", "Low-level moisture convergence over Ethiopia"],
  omega500: ["500 hPa omega", "Mid-level vertical motion"],
  omega700: ["700 hPa omega", "Lower-mid vertical motion"],
  tej_strength: ["TEJ strength (CFSv2)", "Tropical Easterly Jet proxy, −u200"],
};

const GALLERY_MAP: [string, string][] = [
  ["z200_greater_horn_jjas.png", "NMME 200 hPa geopotential height anomaly — Greater Horn — JJAS 2026"],
  ["tej_climatology_jjas.png", "ERA5 climatology: 200 hPa wind speed/direction, TEJ core outlined — JJAS"],
  ["moisture_flux_mfc_jjas.png", "ERA5 climatology: 850 hPa moisture flux and convergence — Greater Horn — JJAS"],
  ["omega500_jjas.png", "ERA5 climatology: 500 hPa omega — Greater Horn — JJAS"],
  ["divergence200_jjas.png", "ERA5 climatology: 200 hPa divergence — Greater Horn — JJAS"],
];

export function AtmosphericEvidence() {
  const { data: tej } = useFetch<TejRow[]>("/api/atmospheric/tej-climatology");
  const { data: cfsv2 } = useFetch<Cfsv2Row[]>("/api/atmospheric/cfsv2", { domain: "ethiopia" });

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

      <h3 style={{ margin: "30px 0 14px", fontSize: "1.05rem", fontFamily: "var(--sans)" }}>
        Circulation diagnostic maps &mdash; JJAS 2026 / climatology
      </h3>
      <div className="map-grid">
        {GALLERY_MAP.map(([file, caption]) => (
          <MapFigure key={file} src={assetUrl(`/static/gallery/${file}`)} caption={caption} />
        ))}
      </div>
    </div>
  );
}
