import { useFetch } from "../../hooks/useFetch";
import type { DomainBox, WeightRow } from "../../api/types";
import { titleCase } from "../../lib/format";

export function Methodology() {
  const { data: domains } = useFetch<DomainBox[]>("/api/methodology/domains");
  const { data: weights } = useFetch<WeightRow[]>("/api/methodology/weights");
  const { data: limitations } = useFetch<string[]>("/api/methodology/limitations");

  return (
    <div className="tabpanel">
      <div className="panel-head">
        <h2>Methodology and data sources</h2>
        <p className="sub">How the evidence in this dashboard is built, weighted, and limited.</p>
      </div>

      <div className="methodology-body">
        <h3>Forecast anomaly product</h3>
        <p>
          This system is built on the CPC NMME real-time ensemble-mean anomaly product across three cycles:{" "}
          <code className="mono" style={{ background: "var(--surface-3)", padding: "2px 6px", borderRadius: 4 }}>
            realtime_anom/ENSMEAN/2026050800, 2026060800, 2026070800
          </code>
        </p>
        <dl className="def-list">
          <dt>Initialization</dt>
          <dd>May, June, and July 2026 (each 8th of the month, 00Z cycle)</dd>
          <dt>Product type</dt>
          <dd>Real-time ensemble-mean anomaly</dd>
          <dt>Aggregation</dt>
          <dd>Ensemble mean across contributing NMME models (CanESM5, CFSv2, GEM5.2-NEMO, NASA GEOS5v2, NCAR CCSM4, NCAR CESM1)</dd>
          <dt>Variables used</dt>
          <dd>
            <code className="mono">prate</code> (precipitation-rate anomaly), <code className="mono">tmpsfc</code>{" "}
            (surface temperature anomaly, used as an SST proxy)
          </dd>
        </dl>
        <p>
          <b>What &ldquo;anomaly&rdquo; means here:</b> the model&apos;s forecast for a given lead time and season,
          compared with that same model&apos;s own climatological normal for the same lead and season &mdash; not a
          comparison against an independent observational dataset.
        </p>

        <h3>Why each initialization covers fewer months</h3>
        <p>
          NMME real-time anomaly products skip the partially-elapsed initialization month itself and start forecasting
          at the next full calendar month. Verified directly against each cycle&apos;s target-month coordinate: May-init
          starts at June, June-init starts at July, July-init starts at August. Each successive cycle therefore covers a
          narrower window within the Kiremt/JJAS season.
        </p>

        <h3>Atmospheric diagnostics</h3>
        <p>Two complementary streams feed the Atmospheric Evidence tab:</p>
        <ul>
          <li>
            <b>ERA5 climatology (1991&ndash;2020):</b> u/v wind at 200 and 850 hPa, specific humidity at 850 hPa, omega
            at 500/700 hPa, and 200 hPa divergence. These describe the normal Kiremt circulation background &mdash;
            informational context, not a 2026 forecast anomaly (weight 0.0).
          </li>
          <li>
            <b>CFSv2 NOMADS (June 2026 initialization):</b> the same diagnostics from raw operational forecast fields.
            Not yet bias-corrected into an anomaly and initialized a month after the base NMME product, so treated as
            lower-confidence evidence (weight 0.5, or 0.25 for context-only fields).
          </li>
        </ul>

        <h3>Evidence scoring &amp; weighting</h3>
        <p>
          Every diagnostic is classified, assigned a raw score (+1 dry-supporting, &minus;1 wet-supporting, 0
          neutral/context), multiplied by an evidence-type weight, and summed by period:
        </p>
        <table className="source-table">
          <thead>
            <tr>
              <th>Evidence type</th>
              <th>Weight</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {(weights ?? []).map((w) => (
              <tr key={w.evidence_type}>
                <td>{w.evidence_type}</td>
                <td className="mono">{w.weight.toFixed(2)}</td>
                <td>{w.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3>Spatial domains</h3>
        <p>Area means use a cosine-latitude weighting. Key domains (lon min, lon max, lat min, lat max, degrees):</p>
        <table className="domain-table">
          <thead>
            <tr>
              <th>Domain</th>
              <th>Bounding box</th>
            </tr>
          </thead>
          <tbody>
            {(domains ?? []).map((d) => (
              <tr key={d.name}>
                <td>{titleCase(d.name)}</td>
                <td className="box">[{d.box.join(", ")}]</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3>Limitations</h3>
        <ul>
          {(limitations ?? []).map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
