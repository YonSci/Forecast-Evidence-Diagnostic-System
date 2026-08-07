import { useMemo, useState } from "react";
import { useFetch } from "../../hooks/useFetch";
import type { EvidenceRow, EvidenceSummaryRow } from "../../api/types";
import { DivergingBarChart } from "../../components/charts/DivergingBarChart";
import type { DivergingDatum } from "../../components/charts/DivergingBarChart";
import { Pill, directionTone } from "../../components/ui/Pill";
import { fmt, sign, titleCase } from "../../lib/format";

type SortKey = keyof EvidenceRow;

export function EvidenceMatrix() {
  const { data: summary } = useFetch<EvidenceSummaryRow[]>("/api/evidence/summary");
  const [search, setSearch] = useState("");
  const [domain, setDomain] = useState("");
  const [period, setPeriod] = useState("");
  const [sourceFilter, setSourceFilter] = useState<Record<string, boolean>>({ NMME: true, CFSv2: true });
  const [sortKey, setSortKey] = useState<SortKey>("period");
  const [sortDir, setSortDir] = useState(1);

  const { data: matrix } = useFetch<EvidenceRow[]>("/api/evidence/matrix", {
    domain: domain || undefined,
    period: period || undefined,
    q: search || undefined,
  });

  const chartData: DivergingDatum[] = useMemo(
    () => (summary ?? []).map((r) => ({ label: r.period, value: r.weighted_score_sum })),
    [summary]
  );

  const domains = useMemo(() => Array.from(new Set((matrix ?? []).map((r) => r.domain))).sort(), [matrix]);
  const periods = ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"];

  const filteredSorted = useMemo(() => {
    // Only two source_system values exist in the data (NMME_CPC_ENSMEAN,
    // CFSv2_NOMADS_June2026_init) -- ERA5 climatology rows are grouped
    // under the NMME source_system, same as the chip toggle's original intent.
    const rows = (matrix ?? []).filter((r) => {
      if (r.source_system.startsWith("CFSv2")) return sourceFilter.CFSv2;
      return sourceFilter.NMME;
    });
    return [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * sortDir;
      return String(av ?? "").localeCompare(String(bv ?? "")) * sortDir;
    });
  }, [matrix, sourceFilter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    setSortDir((d) => (sortKey === key ? -d : 1));
    setSortKey(key);
  }

  return (
    <div className="tabpanel">
      <div className="panel-head">
        <h2>Integrated evidence matrix</h2>
        <p className="sub">
          Every diagnostic scored on one framework: NMME anomaly evidence carries full weight (1.0), CFSv2 raw
          dynamical fields carry reduced weight (0.5, or 0.25 for context-only fields) because they are not yet
          bias-corrected to an anomaly, and ERA5 climatology is informational context only (weight 0.0) &mdash; it
          describes the normal circulation, not the 2026 anomaly.
        </p>
      </div>

      <div className="chart-card" style={{ marginBottom: 26 }}>
        <div className="card-head">
          <h3>Weighted evidence score by period</h3>
          <span className="hint">positive = dry-support, negative = wet-support</span>
        </div>
        <DivergingBarChart data={chartData} unit="pts" dryIsPositive />
        <div className="legend">
          <div className="legend-item"><span className="legend-swatch" style={{ background: "var(--dry)" }} />Net dry-support</div>
          <div className="legend-item"><span className="legend-swatch" style={{ background: "var(--wet)" }} />Net wet-support</div>
        </div>
      </div>

      <div className="table-scroll" style={{ marginBottom: 32 }}>
        <table className="data-table" style={{ minWidth: 900 }}>
          <thead>
            <tr>
              <th>Period</th>
              <th>Dry support</th>
              <th>Wet support</th>
              <th>Neutral/context</th>
              <th>NMME contrib.</th>
              <th>CFSv2 contrib.</th>
              <th>Weighted total</th>
              <th>Category</th>
            </tr>
          </thead>
          <tbody>
            {(summary ?? []).map((r) => (
              <tr key={r.period}>
                <td className="diag">{r.period_label}</td>
                <td className="num">{r.dry_support_count}</td>
                <td className="num">{r.wet_or_rain_support_count}</td>
                <td className="num">{r.neutral_or_context_count}</td>
                <td className="num">{sign(r.nmme_weighted_score)}{fmt(r.nmme_weighted_score, 2)}</td>
                <td className="num">{sign(r.cfsv2_weighted_score)}{fmt(r.cfsv2_weighted_score, 2)}</td>
                <td className="num">{sign(r.weighted_score_sum)}{fmt(r.weighted_score_sum, 2)}</td>
                <td><Pill tone="dry">{titleCase(r.overall_category)}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 style={{ marginBottom: 14, fontSize: "1.05rem", fontFamily: "var(--sans)" }}>Full evidence matrix</h3>
      <div className="table-toolbar">
        <input className="tt-input" placeholder="Search diagnostic…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="tt-select" value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">All domains</option>
          {domains.map((d) => (
            <option key={d} value={d}>{titleCase(d)}</option>
          ))}
        </select>
        <select className="tt-select" value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="">All periods</option>
          {periods.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <div className="chip-toggle">
          {["NMME", "CFSv2"].map((s) => (
            <button key={s} className={sourceFilter[s] ? "on" : ""} onClick={() => setSourceFilter((f) => ({ ...f, [s]: !f[s] }))}>
              {s}
            </button>
          ))}
        </div>
        <span className="table-count">{filteredSorted.length} rows</span>
      </div>

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th onClick={() => toggleSort("source_system")}>Source</th>
              <th onClick={() => toggleSort("diagnostic")}>Diagnostic</th>
              <th onClick={() => toggleSort("period_label")}>Period</th>
              <th onClick={() => toggleSort("domain")}>Domain</th>
              <th onClick={() => toggleSort("value")}>Value</th>
              <th onClick={() => toggleSort("classification")}>Classification</th>
              <th>Direction</th>
              <th onClick={() => toggleSort("confidence")}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {filteredSorted.slice(0, 600).map((r, i) => {
              const dm = directionTone(r.support_direction);
              const sourceLabel = r.source_system.startsWith("NMME") ? "NMME" : r.source_system.startsWith("CFSv2") ? "CFSv2" : "ERA5";
              return (
                <tr key={`${r.diagnostic}-${r.period}-${r.domain}-${i}`}>
                  <td>{sourceLabel}</td>
                  <td className="diag" title={r.interpretation ?? ""}>{r.diagnostic}</td>
                  <td>{r.period_label}</td>
                  <td>{titleCase(r.domain)}</td>
                  <td className="num">{sign(r.value)}{fmt(r.value, r.value != null && Math.abs(r.value) < 0.001 ? 6 : 3)} {r.units}</td>
                  <td>{titleCase(r.classification ?? "")}</td>
                  <td><Pill tone={dm.tone} small>{dm.label}</Pill></td>
                  <td><Pill tone="outline" small>{titleCase(r.confidence ?? "")}</Pill></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
