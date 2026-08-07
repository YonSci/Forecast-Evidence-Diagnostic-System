import { Link } from "react-router-dom";
import { API_BASE } from "../api/client";

interface EndpointDoc {
  method: string;
  path: string;
  desc: string;
}

const ENDPOINTS: { group: string; items: EndpointDoc[] }[] = [
  {
    group: "Meta",
    items: [{ method: "GET", path: "/api/meta", desc: "Regions, variables, initializations (with their valid periods), and period labels — drives every selector in the app." }],
  },
  {
    group: "Anomaly",
    items: [
      { method: "GET", path: "/api/anomaly?init=&region=&variable=", desc: "All periods valid for the given initialization, for one region/variable — feeds the chart and stat tiles." },
      { method: "GET", path: "/api/anomaly/table?init=&region=", desc: "Full readout rows; region=all returns every region." },
      { method: "GET", path: "/api/anomaly/overlay?init=&region=&period=&variable=", desc: "Geo-referenced image overlay metadata (url, bounds, vmin/vmax, unit) for the Leaflet map, or { available: false }." },
    ],
  },
  {
    group: "Evidence",
    items: [
      { method: "GET", path: "/api/evidence/matrix?source=&domain=&period=&q=", desc: "The full integrated NMME + CFSv2 + ERA5 evidence matrix, filterable." },
      { method: "GET", path: "/api/evidence/summary", desc: "Weighted score, dry/wet support counts, and overall classification by period." },
    ],
  },
  {
    group: "Atmospheric",
    items: [
      { method: "GET", path: "/api/atmospheric/tej-climatology", desc: "ERA5 1991-2020 Tropical Easterly Jet strength climatology." },
      { method: "GET", path: "/api/atmospheric/moisture-flux?domain=", desc: "ERA5 850 hPa moisture flux / convergence." },
      { method: "GET", path: "/api/atmospheric/vertical-divergence?domain=", desc: "ERA5 omega500/700 and 200 hPa divergence climatology." },
      { method: "GET", path: "/api/atmospheric/cfsv2?domain=", desc: "Raw CFSv2 NOMADS dynamic diagnostics." },
    ],
  },
  {
    group: "Oceanic",
    items: [{ method: "GET", path: "/api/oceanic/sst-proxy", desc: "Nino3.4 / IOD-West / IOD-East / DMI proxies from NMME tmpsfc, with classification." }],
  },
  {
    group: "Methodology & assets",
    items: [
      { method: "GET", path: "/api/methodology/domains", desc: "Named bounding boxes used throughout the pipeline." },
      { method: "GET", path: "/api/methodology/weights", desc: "Evidence-type -> scoring weight -> rationale." },
      { method: "GET", path: "/api/methodology/limitations", desc: "The project's own stated limitations." },
      { method: "GET", path: "/api/gallery", desc: "Curated report-style diagnostic map metadata (url, caption, group)." },
    ],
  },
];

export function Docs() {
  return (
    <div>
      <div className="topbar">
        <div className="wrap topbar-inner">
          <Link to="/" className="back-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M19 12H5M11 18l-6-6 6-6" />
            </svg>
            Overview
          </Link>
          <Link to="/dashboard" className="brand">
            Forecast Evidence &amp; Diagnostic System
          </Link>
        </div>
      </div>

      <div className="wrap tabpanel">
        <div className="panel-head">
          <h2>Docs</h2>
          <p className="sub">
            How this app is put together, and the API the React frontend talks to. For a live, interactive schema, see{" "}
            <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
              {API_BASE}/docs
            </a>{" "}
            (FastAPI&apos;s auto-generated Swagger UI).
          </p>
        </div>

        <div className="docs-body">
          <h2>Architecture</h2>
          <p>
            <b>Frontend:</b> React + React Router + Vite, deployed on Vercel. <b>Maps:</b> react-leaflet, rendering the
            pipeline&apos;s precipitation-anomaly rasters as geo-referenced <code>ImageOverlay</code> layers over a
            CartoDB Positron basemap. <b>Charts:</b> Recharts. <b>Backend:</b> FastAPI + Uvicorn, deployed on Render,
            reading directly from the project&apos;s own pipeline output CSVs and pre-rendered map assets &mdash; not a
            frozen snapshot.
          </p>
          <p>
            The data itself comes from a Python pipeline (CPC NMME downloads, ERA5 climatology, CFSv2 NOMADS extraction,
            anomaly computation, evidence scoring) that runs independently of this web app; the API layer is a thin,
            read-only surface over its outputs.
          </p>

          <h2>API reference</h2>
          {ENDPOINTS.map((group) => (
            <div key={group.group}>
              <h3 style={{ fontFamily: "var(--sans)", fontSize: "0.95rem", marginTop: 24 }}>{group.group}</h3>
              {group.items.map((e) => (
                <div className="endpoint-card" key={e.path}>
                  <div className="path">
                    {e.method} {e.path}
                  </div>
                  <div className="desc">{e.desc}</div>
                </div>
              ))}
            </div>
          ))}

          <h2>Known caveats</h2>
          <ul style={{ color: "var(--ink-2)", fontSize: "0.95rem" }}>
            <li>
              This is a research-grade diagnostic tool, not an official seasonal outlook &mdash; see the Methodology tab
              for the full limitations list.
            </li>
            <li>
              react-router-dom currently carries an upstream advisory (GHSA-qwww-vcr4-c8h2) scoped to React Server
              Components mode. This app is a plain client-side SPA and does not use RSC, so the advisory does not apply
              here, but it&apos;s worth re-checking before adopting any RSC features later.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
