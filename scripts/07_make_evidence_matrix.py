"""
07_make_evidence_matrix.py

Purpose
-------
Create a final dynamic evidence matrix for Ethiopia Kiremt/JJAS 2026 rainfall
interpretation.

This script combines outputs from:
    04_compute_anomalies.py
    05_compute_dynamic_diagnostics.py
    06_plot_dynamic_maps.py

Main outputs:
-------------
1. outputs/tables/final_dynamic_evidence_matrix.csv
2. outputs/tables/final_dynamic_evidence_summary_by_period.csv
3. outputs/tables/final_dynamic_evidence_matrix.xlsx  optional, if openpyxl is installed
4. outputs/reports/kiremt_2026_dynamic_evidence_report.md

Run from project root:
    python scripts\\07_make_evidence_matrix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import TABLE_DIR, OUTPUT_DIR
except Exception:
    TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
    OUTPUT_DIR = PROJECT_ROOT / "outputs"


REPORT_DIR = OUTPUT_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# INPUT TABLES
# ==========================================================

INPUT_TABLES = {
    "dynamic_evidence_input": TABLE_DIR / "dynamic_evidence_input_table.csv",
    "nmme_rainfall_z200": TABLE_DIR / "nmme_rainfall_z200_diagnostics.csv",
    "nmme_sst_driver": TABLE_DIR / "nmme_sst_driver_diagnostics_from_tmpsfc.csv",
    "nmme_ethiopia_area_mean": TABLE_DIR / "nmme_ethiopia_area_mean_anomalies.csv",
    "era5_tej": TABLE_DIR / "era5_tej_index_climatology.csv",
    "era5_moisture": TABLE_DIR / "era5_850hpa_moisture_flux_diagnostics.csv",
    "era5_vertical": TABLE_DIR / "era5_vertical_divergence_height_diagnostics.csv",
    "diagnostic_status": TABLE_DIR / "diagnostic_field_status.csv",
}


# ==========================================================
# SETTINGS
# ==========================================================

PERIOD_ORDER = {
    "Jun": 1,
    "June": 1,
    "Jun_2026": 1,
    "Jul": 2,
    "July": 2,
    "Jul_2026": 2,
    "Aug": 3,
    "August": 3,
    "Aug_2026": 3,
    "Sep": 4,
    "September": 4,
    "Sep_2026": 4,
    "JJA": 5,
    "JJA_2026": 5,
    "JJAS": 6,
    "JJAS_2026": 6,
}

PERIOD_LABELS = {
    "Jun": "June 2026",
    "July": "July 2026",
    "Jul": "July 2026",
    "Aug": "August 2026",
    "Sep": "September 2026",
    "JJA": "June-August 2026",
    "JJAS": "June-September 2026",
    "Jun_2026": "June 2026",
    "Jul_2026": "July 2026",
    "Aug_2026": "August 2026",
    "Sep_2026": "September 2026",
    "JJA_2026": "June-August 2026",
    "JJAS_2026": "June-September 2026",
}


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def read_table(name: str) -> pd.DataFrame:
    path = INPUT_TABLES[name]

    if not path.exists():
        print(f"Missing table: {path}")
        return pd.DataFrame()

    print(f"Reading: {path}")
    return pd.read_csv(path)


def normalize_period(period: str) -> str:
    if pd.isna(period):
        return "unknown"

    p = str(period).strip()

    mapping = {
        "Jun_2026": "Jun",
        "June": "Jun",
        "June 2026": "Jun",
        "Jul_2026": "Jul",
        "July": "Jul",
        "July 2026": "Jul",
        "Aug_2026": "Aug",
        "August": "Aug",
        "August 2026": "Aug",
        "Sep_2026": "Sep",
        "September": "Sep",
        "September 2026": "Sep",
        "JJA_2026": "JJA",
        "June-August 2026": "JJA",
        "Jun-Aug 2026": "JJA",
        "JJAS_2026": "JJAS",
        "June-September 2026": "JJAS",
        "Jun-Sep 2026": "JJAS",
    }

    return mapping.get(p, p)


def period_sort_key(period: str) -> int:
    return PERIOD_ORDER.get(period, 99)


def safe_float(value) -> float:
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def score_to_strength(score: int) -> str:
    if score >= 2:
        return "strong_dry_support"
    if score == 1:
        return "moderate_dry_support"
    if score == 0:
        return "neutral_or_mixed"
    if score == -1:
        return "moderate_wet_support"
    if score <= -2:
        return "strong_wet_support"
    return "unknown"


def classify_precip_anomaly(value: float, period: str, units: str) -> tuple[str, int, str]:
    """
    Negative precipitation anomaly supports dry Kiremt risk.
    Positive precipitation anomaly supports wet signal.

    Monthly thresholds use mm/month.
    Seasonal thresholds use mm/season.
    """

    if np.isnan(value):
        return "missing", 0, "No value available."

    period_norm = normalize_period(period)

    if period_norm in ["JJA", "JJAS"] or "season" in str(units).lower():
        if value <= -100:
            return "strong_below_normal", 2, "Strong seasonal rainfall deficit signal."
        if value <= -40:
            return "moderate_below_normal", 1, "Moderate seasonal rainfall deficit signal."
        if value < -10:
            return "weak_below_normal", 1, "Weak seasonal rainfall deficit signal."
        if value >= 100:
            return "strong_above_normal", -2, "Strong seasonal wet anomaly signal."
        if value >= 40:
            return "moderate_above_normal", -1, "Moderate seasonal wet anomaly signal."
        if value > 10:
            return "weak_above_normal", -1, "Weak seasonal wet anomaly signal."

        return "near_normal", 0, "Near-normal seasonal rainfall anomaly."

    # Monthly threshold
    if value <= -75:
        return "strong_below_normal", 2, "Strong monthly rainfall deficit signal."
    if value <= -25:
        return "moderate_below_normal", 1, "Moderate monthly rainfall deficit signal."
    if value < -10:
        return "weak_below_normal", 1, "Weak monthly rainfall deficit signal."
    if value >= 75:
        return "strong_above_normal", -2, "Strong monthly wet anomaly signal."
    if value >= 25:
        return "moderate_above_normal", -1, "Moderate monthly wet anomaly signal."
    if value > 10:
        return "weak_above_normal", -1, "Weak monthly wet anomaly signal."

    return "near_normal", 0, "Near-normal monthly rainfall anomaly."


def classify_nino34(value: float) -> tuple[str, int, str]:
    """
    El Niño-like positive Niño3.4 anomaly generally supports increased dry-risk
    during Ethiopia Kiremt, but this is a teleconnection indicator, not direct rainfall.
    """

    if np.isnan(value):
        return "missing", 0, "No Niño3.4 proxy value available."

    if value >= 1.5:
        return "strong_el_nino_like", 2, "Strong El Niño-like SST forcing; supports dry-risk for Ethiopia Kiremt."
    if value >= 0.5:
        return "el_nino_like", 1, "El Niño-like SST forcing; supports dry-risk for Ethiopia Kiremt."
    if value <= -1.0:
        return "la_nina_like", -1, "La Niña-like SST forcing; may reduce El Niño-related dry-risk."
    if value <= -0.5:
        return "weak_la_nina_like", -1, "Weak La Niña-like forcing; does not support El Niño dry-risk."

    return "enso_neutral_or_weak", 0, "ENSO signal is neutral or weak."


def classify_dmi(value: float) -> tuple[str, int, str]:
    """
    IOD influence over Ethiopia is spatially mixed.
    We score it cautiously as mixed unless very strong.
    """

    if np.isnan(value):
        return "missing", 0, "No DMI proxy value available."

    if value >= 0.8:
        return "strong_positive_iod_like", 0, "Strong positive IOD-like signal; effect over Ethiopia can be spatially mixed."
    if value >= 0.4:
        return "positive_iod_like", 0, "Positive IOD-like signal; may introduce regional contrasts."
    if value <= -0.8:
        return "strong_negative_iod_like", 0, "Strong negative IOD-like signal; effect over Ethiopia can be spatially mixed."
    if value <= -0.4:
        return "negative_iod_like", 0, "Negative IOD-like signal; may introduce regional contrasts."

    return "iod_neutral_or_weak", 0, "IOD signal is neutral or weak."


def classify_z200(value: float, domain: str) -> tuple[str, int, str]:
    """
    z200 is a circulation-context diagnostic. Positive height anomaly over
    East Africa/North Africa/Arabia can suggest ridging/subsidence-supporting
    background, but interpretation depends on full circulation pattern.
    """

    if np.isnan(value):
        return "missing", 0, "No z200 value available."

    dry_relevant_domains = {
        "ethiopia",
        "greater_horn",
        "east_africa",
        "north_africa_arabia",
        "arabia_red_sea",
    }

    if value >= 20:
        score = 1 if domain in dry_relevant_domains else 0
        return "positive_height_anomaly", score, "Positive z200 anomaly may suggest ridging/subsidence-supporting circulation."
    if value <= -20:
        score = -1 if domain in dry_relevant_domains else 0
        return "negative_height_anomaly", score, "Negative z200 anomaly may suggest less ridging or altered upper-level circulation."

    return "weak_height_anomaly", 0, "Weak z200 anomaly."


def classify_baseline_only(diagnostic: str) -> tuple[str, int, str]:
    """
    ERA5 climatology is a baseline, not forecast anomaly evidence.
    """

    return (
        "baseline_only",
        0,
        f"{diagnostic} is from ERA5 1991-2020 climatology. It describes normal Kiremt circulation but does not confirm 2026 anomaly by itself.",
    )


def make_row(
    evidence_group: str,
    diagnostic: str,
    period: str,
    domain: str,
    value: float,
    units: str,
    classification: str,
    score: int,
    interpretation: str,
    source_table: str,
    confidence: str,
    limitation: str,
) -> dict:
    period_norm = normalize_period(period)

    if score > 0:
        support_direction = "supports_dry_kiremt"
    elif score < 0:
        support_direction = "supports_wet_or_reduces_dry_risk"
    else:
        support_direction = "neutral_mixed_or_baseline"

    return {
        "evidence_group": evidence_group,
        "diagnostic": diagnostic,
        "period": period_norm,
        "period_label": PERIOD_LABELS.get(period_norm, period_norm),
        "period_order": period_sort_key(period_norm),
        "domain": domain,
        "value": value,
        "units": units,
        "classification": classification,
        "score": score,
        "evidence_strength": score_to_strength(score),
        "support_direction": support_direction,
        "confidence": confidence,
        "interpretation": interpretation,
        "source_table": source_table,
        "limitation": limitation,
    }


# ==========================================================
# BUILD EVIDENCE FROM TABLES
# ==========================================================

def add_precipitation_evidence(rows: list[dict], rainfall_df: pd.DataFrame) -> None:
    if rainfall_df.empty:
        return

    mask = rainfall_df["diagnostic"].astype(str).str.contains("precipitation", case=False, na=False)

    target_domains = ["ethiopia", "north_ethiopia", "central_ethiopia", "west_ethiopia", "east_ethiopia", "greater_horn"]

    df = rainfall_df[mask].copy()

    if "domain" in df.columns:
        df = df[df["domain"].isin(target_domains)]

    for _, r in df.iterrows():
        value = safe_float(r.get("value"))
        period = normalize_period(r.get("period"))
        domain = str(r.get("domain", "unknown"))
        units = str(r.get("units", ""))

        classification, score, interp = classify_precip_anomaly(value, period, units)

        rows.append(
            make_row(
                evidence_group="rainfall_forecast",
                diagnostic="NMME precipitation anomaly",
                period=period,
                domain=domain,
                value=value,
                units=units,
                classification=classification,
                score=score,
                interpretation=interp,
                source_table="nmme_rainfall_z200_diagnostics.csv",
                confidence="moderate",
                limitation="Direct NMME ensemble-mean anomaly; does not show probability or model agreement.",
            )
        )


def add_sst_evidence(rows: list[dict], sst_df: pd.DataFrame) -> None:
    if sst_df.empty:
        return

    for _, r in sst_df.iterrows():
        period = normalize_period(r.get("period"))
        units = str(r.get("units", ""))

        nino34 = safe_float(r.get("nino34_anomaly"))
        nino_class, nino_score, nino_interp = classify_nino34(nino34)

        rows.append(
            make_row(
                evidence_group="ocean_driver",
                diagnostic="Niño3.4 SST anomaly proxy from NMME tmpsfc",
                period=period,
                domain="nino34_box",
                value=nino34,
                units=units,
                classification=nino_class,
                score=nino_score,
                interpretation=nino_interp,
                source_table="nmme_sst_driver_diagnostics_from_tmpsfc.csv",
                confidence="moderate",
                limitation="Computed from NMME tmpsfc anomaly as an SST proxy, not an official Niño3.4 index product.",
            )
        )

        dmi = safe_float(r.get("dmi_proxy"))
        dmi_class, dmi_score, dmi_interp = classify_dmi(dmi)

        rows.append(
            make_row(
                evidence_group="ocean_driver",
                diagnostic="DMI / IOD proxy from NMME tmpsfc",
                period=period,
                domain="iod_west_minus_iod_east",
                value=dmi,
                units=units,
                classification=dmi_class,
                score=dmi_score,
                interpretation=dmi_interp,
                source_table="nmme_sst_driver_diagnostics_from_tmpsfc.csv",
                confidence="low_to_moderate",
                limitation="IOD influence on Ethiopia Kiremt can be spatially mixed; use official DMI products where possible.",
            )
        )


def add_z200_evidence(rows: list[dict], rainfall_z200_df: pd.DataFrame) -> None:
    if rainfall_z200_df.empty:
        return

    mask = rainfall_z200_df["diagnostic"].astype(str).str.contains("z200", case=False, na=False)

    target_domains = ["ethiopia", "greater_horn", "east_africa", "north_africa_arabia", "arabia_red_sea"]

    df = rainfall_z200_df[mask].copy()

    if "domain" in df.columns:
        df = df[df["domain"].isin(target_domains)]

    for _, r in df.iterrows():
        value = safe_float(r.get("value"))
        period = normalize_period(r.get("period"))
        domain = str(r.get("domain", "unknown"))
        units = str(r.get("units", ""))

        classification, score, interp = classify_z200(value, domain)

        rows.append(
            make_row(
                evidence_group="upper_level_circulation",
                diagnostic="NMME z200 anomaly",
                period=period,
                domain=domain,
                value=value,
                units=units,
                classification=classification,
                score=score,
                interpretation=interp,
                source_table="nmme_rainfall_z200_diagnostics.csv",
                confidence="low_to_moderate",
                limitation="z200 alone is not sufficient; interpret together with u200, divergence, omega, and rainfall.",
            )
        )


def add_era5_baseline_evidence(
    rows: list[dict],
    tej_df: pd.DataFrame,
    moisture_df: pd.DataFrame,
    vertical_df: pd.DataFrame,
) -> None:
    """
    Add ERA5 climatological baseline rows. These get score 0 because they are
    not forecast anomalies, but they document the normal circulation background.
    """

    if not tej_df.empty:
        for _, r in tej_df.iterrows():
            period = normalize_period(r.get("period"))
            if period not in ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]:
                continue

            value = safe_float(r.get("value"))
            units = str(r.get("units", ""))
            classification, score, interp = classify_baseline_only("TEJ strength climatology")

            rows.append(
                make_row(
                    evidence_group="circulation_baseline",
                    diagnostic="ERA5 TEJ strength climatology",
                    period=period,
                    domain="tej_core",
                    value=value,
                    units=units,
                    classification=classification,
                    score=score,
                    interpretation=interp,
                    source_table="era5_tej_index_climatology.csv",
                    confidence="high_for_climatology",
                    limitation="Baseline only; not a 2026 forecast anomaly.",
                )
            )

    if not moisture_df.empty:
        selected = moisture_df[
            moisture_df["diagnostic"].isin(["qu850", "qv850", "mfc850", "wind_speed850"])
        ].copy()

        target_domains = ["ethiopia", "congo_moisture_corridor", "western_moisture_entry", "greater_horn"]

        if "domain" in selected.columns:
            selected = selected[selected["domain"].isin(target_domains)]

        for _, r in selected.iterrows():
            period = normalize_period(r.get("period"))

            if period not in ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]:
                continue

            value = safe_float(r.get("value"))
            units = str(r.get("units", ""))
            diagnostic = str(r.get("diagnostic", "ERA5 moisture diagnostic"))
            domain = str(r.get("domain", "unknown"))

            classification, score, interp = classify_baseline_only(diagnostic)

            rows.append(
                make_row(
                    evidence_group="circulation_baseline",
                    diagnostic=f"ERA5 {diagnostic} climatology",
                    period=period,
                    domain=domain,
                    value=value,
                    units=units,
                    classification=classification,
                    score=score,
                    interpretation=interp,
                    source_table="era5_850hpa_moisture_flux_diagnostics.csv",
                    confidence="high_for_climatology",
                    limitation="Baseline only; not a 2026 forecast anomaly.",
                )
            )

    if not vertical_df.empty:
        selected = vertical_df[
            vertical_df["diagnostic"].isin(["omega500", "omega700", "divergence200", "z200", "z500"])
        ].copy()

        target_domains = ["ethiopia", "greater_horn", "north_africa_arabia", "arabia_red_sea"]

        if "domain" in selected.columns:
            selected = selected[selected["domain"].isin(target_domains)]

        for _, r in selected.iterrows():
            period = normalize_period(r.get("period"))

            if period not in ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]:
                continue

            value = safe_float(r.get("value"))
            units = str(r.get("units", ""))
            diagnostic = str(r.get("diagnostic", "ERA5 vertical/circulation diagnostic"))
            domain = str(r.get("domain", "unknown"))

            classification, score, interp = classify_baseline_only(diagnostic)

            rows.append(
                make_row(
                    evidence_group="circulation_baseline",
                    diagnostic=f"ERA5 {diagnostic} climatology",
                    period=period,
                    domain=domain,
                    value=value,
                    units=units,
                    classification=classification,
                    score=score,
                    interpretation=interp,
                    source_table="era5_vertical_divergence_height_diagnostics.csv",
                    confidence="high_for_climatology",
                    limitation="Baseline only; not a 2026 forecast anomaly.",
                )
            )


# ==========================================================
# SUMMARY
# ==========================================================

def build_period_summary(matrix_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    forecast_groups = [
        "rainfall_forecast",
        "ocean_driver",
        "upper_level_circulation",
    ]

    df = matrix_df[matrix_df["evidence_group"].isin(forecast_groups)].copy()

    for period in ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]:
        sub = df[df["period"] == period].copy()

        if sub.empty:
            continue

        score_sum = int(sub["score"].sum())
        dry_count = int((sub["score"] > 0).sum())
        wet_count = int((sub["score"] < 0).sum())
        neutral_count = int((sub["score"] == 0).sum())
        total_count = int(len(sub))

        if score_sum >= 5:
            overall = "strong_dynamic_support_for_dry_signal"
            message = "Most available forecast indicators support a dry-leaning interpretation."
        elif score_sum >= 2:
            overall = "moderate_dynamic_support_for_dry_signal"
            message = "Several available indicators support a dry-leaning interpretation."
        elif score_sum >= 1:
            overall = "weak_dynamic_support_for_dry_signal"
            message = "Some indicators support dryness, but evidence is limited or mixed."
        elif score_sum == 0:
            overall = "neutral_or_mixed_evidence"
            message = "Available indicators are neutral, mixed, or insufficient."
        elif score_sum <= -2:
            overall = "evidence_leans_wet_or_against_dry_signal"
            message = "Available indicators lean away from dry interpretation."
        else:
            overall = "weak_wet_or_non_dry_signal"
            message = "Evidence slightly weakens the dry interpretation."

        rows.append(
            {
                "period": period,
                "period_label": PERIOD_LABELS.get(period, period),
                "period_order": period_sort_key(period),
                "total_forecast_indicators": total_count,
                "dry_support_count": dry_count,
                "wet_support_count": wet_count,
                "neutral_or_mixed_count": neutral_count,
                "score_sum": score_sum,
                "overall_evidence": overall,
                "summary_message": message,
            }
        )

    out = pd.DataFrame(rows).sort_values("period_order")
    return out


def build_report(matrix_df: pd.DataFrame, summary_df: pd.DataFrame, diagnostic_status_df: pd.DataFrame) -> str:
    lines = []

    lines.append("# Dynamic Evidence Matrix Report")
    lines.append("")
    lines.append("## Ethiopia Kiremt/JJAS 2026 rainfall outlook")
    lines.append("")
    lines.append("This report summarizes the available dynamic evidence used to interpret the May-initialized NMME rainfall anomaly forecast for Ethiopia.")
    lines.append("")
    lines.append("The matrix combines direct NMME rainfall anomaly signals, NMME surface-temperature/SST-proxy drivers, NMME z200 circulation context, and ERA5 climatological baseline diagnostics.")
    lines.append("")
    lines.append("> Important: ERA5 diagnostics used here are climatological baselines for 1991–2020. They describe the normal Kiremt circulation background but do not by themselves confirm 2026 circulation anomalies.")
    lines.append("")

    lines.append("## Summary by period")
    lines.append("")
    if not summary_df.empty:
        lines.append(summary_df[
            [
                "period_label",
                "total_forecast_indicators",
                "dry_support_count",
                "wet_support_count",
                "neutral_or_mixed_count",
                "score_sum",
                "overall_evidence",
            ]
        ].to_markdown(index=False))
    else:
        lines.append("No summary data available.")

    lines.append("")
    lines.append("## Key interpretation")
    lines.append("")

    if not summary_df.empty:
        jjas = summary_df[summary_df["period"] == "JJAS"]
        jja = summary_df[summary_df["period"] == "JJA"]

        if not jjas.empty:
            r = jjas.iloc[0]
            lines.append(f"- **JJAS:** {r['summary_message']} Overall classification: `{r['overall_evidence']}`.")
        if not jja.empty:
            r = jja.iloc[0]
            lines.append(f"- **JJA:** {r['summary_message']} Overall classification: `{r['overall_evidence']}`.")

    lines.append("")
    lines.append("Based on the available NMME anomaly products, the direct rainfall signal and SST-driver proxies are the strongest forecast-based evidence. The ERA5 circulation products provide the physical climatological context for interpreting TEJ, moisture transport, omega, and upper-level divergence.")
    lines.append("")

    lines.append("## Main limitations")
    lines.append("")
    lines.append("- The simple CPC NMME realtime anomaly folder does not include forecast anomaly fields for u200, v200, u850, v850, q850, omega, velocity potential, OLR, or full moisture flux.")
    lines.append("- Therefore, full dynamic confirmation of the 2026 circulation anomaly requires additional forecast fields from NMME Phase-II, IRI Data Library, or another seasonal forecast archive.")
    lines.append("- ERA5 fields in this workflow are climatological baseline fields, not future forecast anomalies.")
    lines.append("- The NMME `tmpsfc` field is used as an SST-proxy for Niño3.4 and IOD boxes; official ENSO and IOD index products should also be consulted.")
    lines.append("- NMME precipitation anomaly is an ensemble-mean anomaly, not a probability forecast or model-agreement product.")
    lines.append("")

    if not diagnostic_status_df.empty:
        lines.append("## Diagnostic field availability")
        lines.append("")
        try:
            lines.append(diagnostic_status_df.to_markdown(index=False))
        except Exception:
            lines.append("Diagnostic status table is available as CSV.")
        lines.append("")

    lines.append("## Recommended next step")
    lines.append("")
    lines.append("To strengthen the diagnosis, obtain forecast anomaly fields for u200, u850, v850, q850, omega, OLR, and velocity potential. Then compare 2026 forecast anomalies against the ERA5 1991–2020 climatological baseline generated in this workflow.")
    lines.append("")

    return "\n".join(lines)


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("Create final dynamic evidence matrix")
    print("==================================================")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Tables:       {TABLE_DIR}")
    print(f"Reports:      {REPORT_DIR}")

    rainfall_z200_df = read_table("nmme_rainfall_z200")
    sst_df = read_table("nmme_sst_driver")
    tej_df = read_table("era5_tej")
    moisture_df = read_table("era5_moisture")
    vertical_df = read_table("era5_vertical")
    diagnostic_status_df = read_table("diagnostic_status")

    rows = []

    add_precipitation_evidence(rows, rainfall_z200_df)
    add_sst_evidence(rows, sst_df)
    add_z200_evidence(rows, rainfall_z200_df)
    add_era5_baseline_evidence(
        rows=rows,
        tej_df=tej_df,
        moisture_df=moisture_df,
        vertical_df=vertical_df,
    )

    if not rows:
        raise RuntimeError(
            "No evidence rows were created. Please check that the previous scripts generated the required CSV tables."
        )

    matrix_df = pd.DataFrame(rows)

    matrix_df = matrix_df.sort_values(
        by=["period_order", "evidence_group", "diagnostic", "domain"],
        ascending=[True, True, True, True],
    )

    matrix_csv = TABLE_DIR / "final_dynamic_evidence_matrix.csv"
    matrix_df.to_csv(matrix_csv, index=False)

    print(f"Saved final evidence matrix: {matrix_csv}")

    summary_df = build_period_summary(matrix_df)

    summary_csv = TABLE_DIR / "final_dynamic_evidence_summary_by_period.csv"
    summary_df.to_csv(summary_csv, index=False)

    print(f"Saved final evidence summary: {summary_csv}")

    # Optional Excel workbook
    excel_path = TABLE_DIR / "final_dynamic_evidence_matrix.xlsx"

    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            matrix_df.to_excel(writer, sheet_name="evidence_matrix", index=False)
            summary_df.to_excel(writer, sheet_name="summary_by_period", index=False)

            if not diagnostic_status_df.empty:
                diagnostic_status_df.to_excel(writer, sheet_name="field_status", index=False)

        print(f"Saved Excel workbook: {excel_path}")

    except Exception as exc:
        print("\nExcel workbook was not created.")
        print("Reason:", exc)
        print("CSV outputs were created successfully.")

    report_text = build_report(
        matrix_df=matrix_df,
        summary_df=summary_df,
        diagnostic_status_df=diagnostic_status_df,
    )

    report_path = REPORT_DIR / "kiremt_2026_dynamic_evidence_report.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"Saved markdown report: {report_path}")

    print("\n==================================================")
    print("FINAL EVIDENCE SUMMARY")
    print("==================================================")

    if not summary_df.empty:
        print(summary_df[
            [
                "period_label",
                "total_forecast_indicators",
                "dry_support_count",
                "wet_support_count",
                "neutral_or_mixed_count",
                "score_sum",
                "overall_evidence",
            ]
        ].to_string(index=False))

    print("\nMain outputs:")
    print(f" - {matrix_csv}")
    print(f" - {summary_csv}")
    print(f" - {report_path}")

    if excel_path.exists():
        print(f" - {excel_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()