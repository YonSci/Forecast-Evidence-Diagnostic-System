import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { useFetch } from "../../hooks/useFetch";
import { getJson, assetUrl } from "../../api/client";
import type { TejRow, Cfsv2Row, OverlayInfo, GridResponse, CirculationVariable } from "../../api/types";
import { Callout } from "../../components/ui/Callout";
import { Pill, directionTone } from "../../components/ui/Pill";
import { ControlField } from "../../components/ui/ControlField";
import { useLightbox } from "../../components/ui/Lightbox";
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
const CIVIDIS = "linear-gradient(90deg, #00204d, #00336f, #39486b, #575d6d, #707173, #8a8779, #a69d75, #c4b56c, #e4cf5b, #ffea46)";

// A circulation-consistency check, not just a list of diagnostics: is
// the jet where/how strong the forecast implies, does its exit-region
// divergence favor ascent, is that ascent actually happening, is
// moisture both being supplied and accumulating to support it, and is
// the low-level jet that delivers that moisture actually present. Every
// entry is ERA5 1991-2020 climatology -- none is an "anomaly": there's
// no per-2026 forecast grid for any of them to diff against, so what's
// shown is the raw climatological field itself. The period dropdown
// switches the climatological month/season, not a forecast lead time --
// see scripts/27_generate_atmospheric_leaflet_overlays.py, whose fixed
// discrete color levels these legendGradient/unit/vmin/vmax values must
// stay in sync with.
// Not every entry covers every period: the six TEJ fields come from a
// JJAS-only ERA5 download (scripts/02) and the two low-level-jet fields
// from an all-months one (scripts/29-31). Availability is read per
// variable from the API, never assumed here.
// defaultScope: the wind fields default to "large" (the jets span
// continents, so the wide South-Asia-to-Africa view is the informative
// one); the moisture and ascent fields default to "regional" (the
// Ethiopia-focused view is the locally relevant signal). Either can be
// toggled to the other scope in the UI -- both are always generated.
const CIRCULATION_MAPS: {
  key: string;
  title: string;
  blurb: string;
  unit: string;
  legendTitle: string;
  legendGradient: string;
  legendNote?: string;
  defaultScope: "large" | "regional";
  /** Whether a climatology-vs-2026-target comparison figure exists. False
   * for the low-level-jet fields: the CFSv2 extraction only carries 200
   * and 850 hPa, so there is no sub-600-hPa stack on the forecast side to
   * run the same column search against. */
  hasComparison?: boolean;
  /** Whether this map carries a traced Somali jet core. Declared here
   * rather than inferred from the response: the API serializes jet_core
   * on every overlay, so a null there means "no jet core concept applies"
   * for the TEJ fields but "no jet this period" for the two low-level
   * ones, and only this flag distinguishes them. */
  hasJetCore?: boolean;
}[] = [
  {
    key: "u200",
    title: "200-hPa Zonal Wind",
    blurb: "Primary indicator of TEJ strength.",
    unit: "m s⁻¹",
    legendTitle: "u₂₀₀",
    legendGradient: RDBU,
    legendNote: "Easterly (−)  ·  Westerly (+)",
    defaultScope: "large",
  },
  {
    key: "u200_vectors",
    title: "200-hPa Wind Vectors",
    blurb: "Shows the actual circulation and jet orientation — arrows are direction, shading is speed.",
    unit: "m s⁻¹",
    legendTitle: "Wind speed",
    legendGradient: JET,
    defaultScope: "large",
  },
  {
    key: "divergence200",
    title: "200-hPa Divergence",
    blurb: "Positive divergence can indicate favorable upper-level outflow.",
    unit: "s⁻¹",
    legendTitle: "Divergence",
    legendGradient: RDBU,
    legendNote: "Convergence (−)  ·  Divergence (+)",
    defaultScope: "regional",
  },
  {
    key: "omega500",
    title: "500-hPa Vertical Velocity (ω₅₀₀)",
    blurb: "Forced ascent (negative) or subsidence (positive) beneath the jet.",
    unit: "Pa s⁻¹",
    legendTitle: "ω₅₀₀",
    legendGradient: RDBU,
    legendNote: "Ascent (−)  ·  Subsidence (+)",
    defaultScope: "regional",
  },
  {
    key: "qflux850",
    title: "850-hPa Moisture Flux (qV₈₅₀)",
    blurb: "Tells whether moisture is actually being supplied — arrows show transport direction.",
    unit: "kg kg⁻¹ m s⁻¹",
    legendTitle: "Moisture flux",
    legendGradient: YLGNBU,
    defaultScope: "regional",
  },
  {
    key: "mfc850",
    title: "850-hPa Moisture-Flux Convergence",
    blurb: "Helps diagnose low-level moisture accumulation.",
    unit: "kg kg⁻¹ s⁻¹",
    legendTitle: "MFC",
    legendGradient: BRBG,
    legendNote: "Divergence (−)  ·  Convergence (+)",
    defaultScope: "regional",
  },
  {
    key: "llj_speed",
    title: "Low-Level Jet Speed (Somali jet)",
    blurb:
      "Strongest wind anywhere below 600 hPa, so the jet is caught wherever in the column it sits. The white-cased line traces the climatological core pathway; the dot marks the core itself.",
    unit: "m s⁻¹",
    legendTitle: "Max wind below 600 hPa",
    legendGradient: YLGNBU,
    defaultScope: "large",
    hasComparison: false,
    hasJetCore: true,
  },
  {
    key: "llj_level",
    title: "Low-Level Jet Core Height",
    blurb:
      "The pressure at which that maximum occurs — how high the jet core rides. Drawn only where the wind reaches 8 m s⁻¹, so what remains is the real jets rather than a map of the terrain underneath.",
    unit: "hPa",
    legendTitle: "Core pressure",
    legendGradient: CIVIDIS,
    legendNote: "Lower hPa = core rides higher",
    defaultScope: "large",
    hasComparison: false,
    hasJetCore: true,
  },
];

const SCOPE_LABELS: Record<"large" | "regional", string> = {
  large: "Large-scale",
  regional: "Ethiopia focus",
};

// All twelve calendar months plus the two season aggregates. Which of
// these each map actually has is not uniform and is NOT hardcoded here:
// the six TEJ fields come from a JJAS-only ERA5 download while the two
// low-level-jet fields cover the whole year, so every card carries its
// own `periods` from /api/atmospheric/circulation-variables (read from
// the rendered overlay index) and cards that lack the selected period
// are hidden rather than shown as an empty panel.
const CIRC_PERIODS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  "JJA", "JJAS",
];
const CIRC_PERIOD_LABELS: Record<string, string> = {
  Jan: "January",
  Feb: "February",
  Mar: "March",
  Apr: "April",
  May: "May",
  Jun: "June",
  Jul: "July",
  Aug: "August",
  Sep: "September",
  Oct: "October",
  Nov: "November",
  Dec: "December",
  JJA: "JJA",
  JJAS: "JJAS",
};

function CirculationMapCard({
  variableKey,
  title,
  blurb,
  legendTitle,
  legendGradient,
  legendNote,
  period,
  periodLabel,
  defaultScope,
  hasComparison = true,
  hasJetCore = false,
}: {
  variableKey: string;
  title: string;
  blurb: string;
  legendTitle: string;
  legendGradient: string;
  legendNote?: string;
  period: string;
  periodLabel: string;
  defaultScope: "large" | "regional";
  hasComparison?: boolean;
  hasJetCore?: boolean;
}) {
  const [overlay, setOverlay] = useState<OverlayInfo | null>(null);
  const [grid, setGrid] = useState<GridResponse | null>(null);
  const [scope, setScope] = useState<"large" | "regional">(defaultScope);
  const openLightbox = useLightbox();

  useEffect(() => {
    getJson<OverlayInfo>("/api/atmospheric/overlay", { variable: variableKey, scope, period })
      .then(setOverlay)
      .catch(() => setOverlay({ available: false }));
    getJson<GridResponse>("/api/atmospheric/grid", { variable: variableKey, scope, period })
      .then(setGrid)
      .catch(() => setGrid(null));
  }, [variableKey, scope, period]);

  const publicationUrl = assetUrl(`/static/atmos_publication/${variableKey}/${variableKey}_${period}.png`);
  const comparisonUrl = assetUrl(
    `/static/atmos_publication_comparison/${variableKey}/${variableKey}_${period}_comparison.png`
  );
  const linkStyle: CSSProperties = {
    background: "none", border: "none", padding: 0, font: "inherit", fontSize: "0.78rem",
    color: "var(--accent)", cursor: "pointer", textDecoration: "underline",
  };

  return (
    <div className="chart-card">
      <div className="card-head">
        <h3>
          {periodLabel} {title}
        </h3>
        <span className="hint">ERA5 &middot; Reference climatology 1991&ndash;2020</span>
      </div>
      <div className="scope-toggle" style={{ marginBottom: 12 }}>
        {(["large", "regional"] as const).map((s) => (
          <button
            key={s}
            type="button"
            className={s === scope ? "active" : undefined}
            onClick={() => setScope(s)}
          >
            {SCOPE_LABELS[s]}
          </button>
        ))}
      </div>
      <p style={{ fontSize: "0.84rem", color: "var(--ink-2)", marginTop: -8, marginBottom: 12 }}>{blurb}</p>
      <AnomalyLeafletMap
        overlay={overlay}
        grid={grid}
        legendGradient={legendGradient}
        legendTitle={legendTitle}
        legendNote={legendNote}
        emptyReason="No rendered map for this period in this build."
      />
      {hasJetCore && overlay?.available && (
        <p style={{ fontSize: "0.78rem", color: "var(--ink-2)", marginTop: 10, marginBottom: 0 }}>
          {overlay.jet_core ? (
            <>
              <strong>Jet core:</strong> {fmt(overlay.jet_core.speed_ms, 1)} m s⁻¹ at{" "}
              {fmt(Math.abs(overlay.jet_core.lon), 2)}°{overlay.jet_core.lon < 0 ? "W" : "E"},{" "}
              {fmt(Math.abs(overlay.jet_core.lat), 2)}°{overlay.jet_core.lat < 0 ? "S" : "N"},{" "}
              {fmt(overlay.jet_core.level_hpa, 0)} hPa
              {overlay.jet_core.crosses_equator
                ? " — pathway crosses the equator."
                : " — pathway does not reach the equator this month."}
            </>
          ) : (
            <>
              <strong>No low-level jet this period.</strong> No cross-equatorial southerly core below 600 hPa
              reaches the {"≥"}12 m s⁻¹ threshold, so no pathway is drawn.
            </>
          )}
        </p>
      )}
      <div style={{ display: "flex", gap: 16, marginTop: 10 }}>
        <button
          type="button"
          style={linkStyle}
          onClick={() =>
            openLightbox({
              src: publicationUrl,
              caption: `${periodLabel} ${title} — publication figure (ERA5 1991–2020 climatology, lat/lon labeled, dual-panel).`,
            })
          }
        >
          View publication figure
        </button>
        {hasComparison && (
          <button
            type="button"
            style={linkStyle}
            onClick={() =>
              openLightbox({
                src: comparisonUrl,
                caption: `${periodLabel} ${title} — ERA5 climatology vs. CFSv2 2026 target (qualitative comparison, not an anomaly).`,
              })
            }
          >
            View vs. 2026 target
          </button>
        )}
      </div>
      <p style={{ fontSize: "0.72rem", color: "var(--muted)", marginTop: 8 }}>
        Data: ERA5 &middot; Reference: 1991&ndash;2020 &middot; Aggregation: {periodLabel} mean &middot; Resolution:
        0.25&deg; &middot; Domain: {SCOPE_LABELS[scope]} &middot; Variable: {title}
      </p>
    </div>
  );
}

export function AtmosphericEvidence() {
  const { data: tej } = useFetch<TejRow[]>("/api/atmospheric/tej-climatology");
  const { data: cfsv2 } = useFetch<Cfsv2Row[]>("/api/atmospheric/cfsv2", { domain: "ethiopia" });
  const { data: circVars } = useFetch<CirculationVariable[]>("/api/atmospheric/circulation-variables");
  const [circPeriod, setCircPeriod] = useState("JJAS");

  // Each map is shown only for the periods it was actually rendered for.
  // Until the registry loads nothing is filtered out, so the cards do not
  // pop in and out on first paint; a card that slips through anyway still
  // falls back to its own "no rendered map" placeholder.
  const visibleMaps = useMemo(() => {
    const periodsByKey = new Map((circVars ?? []).map((v) => [v.key, v.periods]));
    return CIRCULATION_MAPS.filter((m) => {
      const periods = periodsByKey.get(m.key);
      return !periods || periods.includes(circPeriod);
    });
  }, [circVars, circPeriod]);

  const hiddenCount = CIRCULATION_MAPS.length - visibleMaps.length;

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
          <MagnitudeBarChart data={tejChartData} unit="m s⁻¹" />
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
        <h3 style={{ fontSize: "1.05rem", fontFamily: "var(--sans)" }}>Circulation consistency check</h3>
        <span className="hint">Upper jet &amp; outflow &rarr; ascent &rarr; moisture supply &amp; accumulation &rarr; the low-level jet that delivers it</span>
      </div>
      <p className="sub" style={{ marginTop: -8, marginBottom: 16, maxWidth: "none" }}>
        Where the jet sits, its entrance/exit structure, upper-level divergence, forced ascent, and whether moisture is
        actually being supplied and accumulating at low levels all have to line up for a dry- or wet-risk signal to be
        dynamically consistent, not just a single-diagnostic coincidence &mdash; these read together, not in isolation.
        The last two close the chain at the bottom: the Somali jet is the cross-equatorial low-level flow that carries
        the moisture the four fields above account for, located here by searching every ERA5 level below 600 hPa rather
        than a single fixed surface.
      </p>
      <div className="control-bar" style={{ maxWidth: 260, margin: "0 0 16px" }}>
        <ControlField
          label="Period"
          value={circPeriod}
          onChange={setCircPeriod}
          options={CIRC_PERIODS.map((p) => [p, CIRC_PERIOD_LABELS[p]])}
        />
      </div>
      {hiddenCount > 0 && (
        <p style={{ fontSize: "0.78rem", color: "var(--muted)", marginTop: -8, marginBottom: 16 }}>
          Showing {visibleMaps.length} of {CIRCULATION_MAPS.length} maps for {CIRC_PERIOD_LABELS[circPeriod]}. The
          six TEJ-consistency fields are generated from a JJAS-only ERA5 archive and exist for June&ndash;September,
          JJA and JJAS only; the two low-level-jet fields cover all twelve months.
        </p>
      )}

      {visibleMaps.map((m) => (
        <div key={m.key} style={{ marginBottom: 22 }}>
          <CirculationMapCard
            variableKey={m.key}
            title={m.title}
            blurb={m.blurb}
            legendTitle={m.legendTitle}
            legendGradient={m.legendGradient}
            legendNote={m.legendNote}
            period={circPeriod}
            periodLabel={CIRC_PERIOD_LABELS[circPeriod]}
            defaultScope={m.defaultScope}
            hasComparison={m.hasComparison}
            hasJetCore={m.hasJetCore}
          />
        </div>
      ))}
    </div>
  );
}
