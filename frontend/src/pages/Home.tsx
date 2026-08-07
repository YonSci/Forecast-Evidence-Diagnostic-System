import { Link } from "react-router-dom";
import { useFetch } from "../hooks/useFetch";
import type { EvidenceSummaryRow } from "../api/types";
import { titleCase } from "../lib/format";

function HeroBands() {
  return (
    <svg className="hero-bands" viewBox="0 0 1200 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="bandA" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.16" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="bandB" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--wet)" stopOpacity="0.14" />
          <stop offset="100%" stopColor="var(--wet)" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="bandC" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--dry)" stopOpacity="0.13" />
          <stop offset="100%" stopColor="var(--dry)" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <g strokeWidth="1.4" fill="none">
        <path d="M -50 90 C 150 40, 350 140, 550 85 S 950 40, 1250 95" stroke="url(#bandA)" />
        <path d="M -50 130 C 180 190, 340 70, 560 135 S 940 190, 1250 140" stroke="url(#bandA)" />
        <path d="M -50 170 C 160 120, 380 210, 600 160 S 980 120, 1250 175" stroke="url(#bandA)" />
        <path d="M -50 260 C 170 320, 360 220, 580 275 S 960 330, 1250 265" stroke="url(#bandB)" />
        <path d="M -50 300 C 190 240, 350 340, 570 295 S 930 240, 1250 305" stroke="url(#bandB)" />
        <path d="M -50 340 C 150 400, 380 300, 600 355 S 970 400, 1250 345" stroke="url(#bandB)" />
        <path d="M -50 430 C 160 380, 340 470, 560 420 S 950 380, 1250 435" stroke="url(#bandC)" />
        <path d="M -50 470 C 190 520, 360 430, 580 475 S 930 520, 1250 465" stroke="url(#bandC)" />
      </g>
    </svg>
  );
}

export function Home() {
  const { data: summary } = useFetch<EvidenceSummaryRow[]>("/api/evidence/summary");
  const jjas = summary?.find((r) => r.period === "JJAS");

  return (
    <div>
      <div className="hero">
        <HeroBands />
        <div className="wrap hero-inner">
          <div className="eyebrow">
            <span className="dot" />
            Kiremt / JJAS 2026 &middot; Ethiopia &amp; the Greater Horn of Africa
          </div>
          <h1>Forecast Evidence and Diagnostic System</h1>
          <p className="lede">
            A rainfall map answers &ldquo;what does the forecast show.&rdquo; This platform answers the harder question
            underneath it: is that signal physically supported by the atmosphere and the ocean that are supposed to be
            driving it &mdash; or is it sitting on thin evidence?
          </p>
          <div className="hero-cta-row">
            <Link className="btn btn-primary" to="/dashboard">
              Open the dashboard
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </Link>
            <a className="btn btn-ghost" href="#purpose">
              How the evidence is built
            </a>
          </div>

          <div className="hero-snapshot">
            <div className="snap-cell">
              <div className="k">Initialization</div>
              <div className="v">May / Jun / Jul 2026</div>
            </div>
            <div className="snap-cell">
              <div className="k">Season</div>
              <div className="v">Kiremt / JJAS 2026</div>
            </div>
            <div className="snap-cell">
              <div className="k">Coverage</div>
              <div className="v">Ethiopia &amp; Greater Horn</div>
            </div>
            <div className="snap-cell">
              <div className="k">Integrated signal</div>
              <div className="v">
                <span className="pill pill-dry">{jjas ? titleCase(jjas.overall_category) : "loading…"}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <section className="section" id="purpose">
        <div className="wrap">
          <div className="section-head">
            <span className="kicker">Why this exists</span>
            <h2>One forecast map is not one piece of evidence</h2>
            <p className="sub">
              Ensemble-mean seasonal forecasts like NMME give a single rainfall anomaly map. On their own, they don&apos;t
              say whether the signal is backed by upper-level winds, moisture transport, and ocean temperatures moving the
              same direction &mdash; or whether it&apos;s a fragile ensemble-mean artifact. This system separates{" "}
              <b>what the forecast shows</b> from <b>what physically supports it</b>, and scores both into one
              transparent, traceable evidence trail.
            </p>
          </div>

          <div className="pillars">
            <div className="pillar-card">
              <div className="pillar-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3v11" />
                  <path d="M7 9l5 5 5-5" />
                  <path d="M5 21h14" />
                </svg>
              </div>
              <h3>Anomaly evidence</h3>
              <p>
                What the CPC NMME ensemble-mean forecast itself says: precipitation and surface-temperature anomalies
                relative to the model&apos;s own climatology, across three real initialization cycles.
              </p>
              <div className="pillar-tag">Direct forecast signal</div>
            </div>
            <div className="pillar-card">
              <div className="pillar-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 12c2-4 4-4 6 0s4 4 6 0 4-4 6 0" />
                  <path d="M3 18c2-4 4-4 6 0s4 4 6 0 4-4 6 0" />
                </svg>
              </div>
              <h3>Atmospheric evidence</h3>
              <p>
                Whether the circulation is dynamically consistent with that signal: Tropical Easterly Jet strength,
                850&nbsp;hPa moisture flux and convergence, vertical motion, and upper-level divergence.
              </p>
              <div className="pillar-tag">Dynamic consistency check</div>
            </div>
            <div className="pillar-card">
              <div className="pillar-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 15c2.5-2 4.5-2 7 0s4.5 2 7 0 4.5-2 6-1" />
                  <circle cx="17" cy="6" r="3.2" />
                </svg>
              </div>
              <h3>Oceanic evidence</h3>
              <p>
                Whether ocean-driver proxies &mdash; a Ni&ntilde;o3.4-like signal and an Indian Ocean Dipole&ndash;like
                gradient built from the NMME temperature field &mdash; point the same direction as the rainfall forecast.
              </p>
              <div className="pillar-tag">Ocean-forcing consistency check</div>
            </div>
          </div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head">
            <span className="kicker">Method, in four steps</span>
            <h2>From raw forecast fields to one integrated signal</h2>
          </div>
          <div className="howitworks">
            <div className="step">
              <div className="num">01</div>
              <h4>Read the anomaly</h4>
              <p>Pull ensemble-mean NMME fields and convert precipitation rate into mm/day, mm/month, and seasonal totals.</p>
            </div>
            <div className="step">
              <div className="num">02</div>
              <h4>Score the atmosphere</h4>
              <p>Classify TEJ strength, moisture flux, omega, and divergence as dry-supporting, wet-supporting, or neutral.</p>
            </div>
            <div className="step">
              <div className="num">03</div>
              <h4>Score the ocean</h4>
              <p>Build Ni&ntilde;o3.4 and IOD-style proxies from the NMME temperature field and classify the driver pattern.</p>
            </div>
            <div className="step">
              <div className="num">04</div>
              <h4>Integrate &amp; weight</h4>
              <p>Combine every diagnostic into one weighted evidence matrix, by period and by season.</p>
            </div>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="wrap cols">
          <div>
            <h5>Forecast Evidence and Diagnostic System</h5>
            <p style={{ maxWidth: "44ch" }}>
              Built for climate services, early-warning, agriculture, water-resource, and food-security decision support.
              Research-grade diagnostics &mdash; not an official seasonal outlook.
            </p>
          </div>
          <div>
            <h5>Primary sources</h5>
            <ul>
              <li>CPC NMME ENSMEAN (May/Jun/Jul 2026 init.)</li>
              <li>ECMWF ERA5 (1991&ndash;2020)</li>
              <li>NOMADS CFSv2 (June 2026 init.)</li>
            </ul>
          </div>
          <div>
            <h5>Coverage</h5>
            <ul>
              <li>Ethiopia</li>
              <li>Greater Horn of Africa</li>
              <li>Kiremt / JJAS 2026</li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
}
