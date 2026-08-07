"""
12_integrate_nmme_cfsv2_evidence.py

Purpose
-------
Integrate NMME anomaly evidence and CFSv2 dynamic diagnostic evidence into
one final JJAS/Kiremt 2026 evidence matrix.

Inputs:
    outputs/tables/final_dynamic_evidence_matrix.csv
    outputs/tables/final_dynamic_evidence_summary_by_period.csv
    outputs/tables/cfsv2_dynamic_area_mean_diagnostics.csv
    outputs/tables/cfsv2_dynamic_diagnostic_field_status.csv

Outputs:
    outputs/tables/integrated_nmme_cfsv2_evidence_matrix.csv
    outputs/tables/integrated_nmme_cfsv2_summary_by_period.csv
    outputs/reports/integrated_nmme_cfsv2_kiremt_2026_report.md

Run:
    python scripts\\12_integrate_nmme_cfsv2_evidence.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# INPUTS
# ==========================================================

NMME_MATRIX_CSV = TABLE_DIR / "final_dynamic_evidence_matrix.csv"
NMME_SUMMARY_CSV = TABLE_DIR / "final_dynamic_evidence_summary_by_period.csv"

CFSV2_AREA_CSV = TABLE_DIR / "cfsv2_dynamic_area_mean_diagnostics.csv"
CFSV2_STATUS_CSV = TABLE_DIR / "cfsv2_dynamic_diagnostic_field_status.csv"


# ==========================================================
# OUTPUTS
# ==========================================================

OUT_MATRIX_CSV = TABLE_DIR / "integrated_nmme_cfsv2_evidence_matrix.csv"
OUT_SUMMARY_CSV = TABLE_DIR / "integrated_nmme_cfsv2_summary_by_period.csv"
OUT_REPORT_MD = REPORT_DIR / "integrated_nmme_cfsv2_kiremt_2026_report.md"


# ==========================================================
# PERIODS
# ==========================================================

PERIOD_ORDER = {
    "Jun": 1,
    "Jul": 2,
    "Aug": 3,
    "Sep": 4,
    "JJA": 5,
    "JJAS": 6,
}

PERIOD_LABELS = {
    "Jun": "June 2026",
    "Jul": "July 2026",
    "Aug": "August 2026",
    "Sep": "September 2026",
    "JJA": "June-August 2026",
    "JJAS": "June-September 2026",
}


# ==========================================================
# HELPERS
# ==========================================================

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
        "JJAS_2026": "JJAS",
        "June-September 2026": "JJAS",
    }

    return mapping.get(p, p)


def safe_float(value) -> float:
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def score_to_support(score: float) -> str:
    if score > 0:
        return "supports_dry_kiremt"
    if score < 0:
        return "supports_wet_or_reduces_dry_risk"
    return "neutral_mixed_or_context_only"


def score_to_strength(score: float) -> str:
    if score >= 2:
        return "strong_dry_support"
    if score >= 1:
        return "moderate_dry_support"
    if score > 0:
        return "weak_dry_support"
    if score == 0:
        return "neutral_or_context"
    if score <= -2:
        return "strong_wet_support"
    if score <= -1:
        return "moderate_wet_support"
    return "weak_wet_support"


def overall_category(weighted_score: float) -> tuple[str, str]:
    if weighted_score >= 4:
        return (
            "strong_dry_signal",
            "Integrated evidence strongly supports a dry-leaning interpretation.",
        )
    if weighted_score >= 2:
        return (
            "moderate_dry_signal",
            "Integrated evidence moderately supports a dry-leaning interpretation.",
        )
    if weighted_score >= 0.75:
        return (
            "weak_dry_signal",
            "Integrated evidence weakly supports a dry-leaning interpretation.",
        )
    if weighted_score > -0.75:
        return (
            "mixed_or_neutral_signal",
            "Integrated evidence is mixed, neutral, or insufficient for a confident dry/wet conclusion.",
        )
    if weighted_score > -2:
        return (
            "weak_wet_or_rain_support_signal",
            "Integrated evidence weakly reduces dry-risk confidence or supports rainfall potential.",
        )
    if weighted_score > -4:
        return (
            "moderate_wet_or_rain_support_signal",
            "Integrated evidence moderately reduces dry-risk confidence or supports rainfall potential.",
        )
    return (
        "strong_wet_or_rain_support_signal",
        "Integrated evidence strongly reduces dry-risk confidence or supports rainfall potential.",
    )


# ==========================================================
# NMME EVIDENCE
# ==========================================================

def load_nmme_evidence() -> pd.DataFrame:
    if not NMME_MATRIX_CSV.exists():
        print(f"NMME evidence matrix not found: {NMME_MATRIX_CSV}")
        print("Run scripts\\07_make_evidence_matrix.py first if you want NMME evidence included.")
        return pd.DataFrame()

    df = pd.read_csv(NMME_MATRIX_CSV)

    rows = []

    for _, r in df.iterrows():
        period = normalize_period(r.get("period"))
        score = safe_float(r.get("score"))

        if np.isnan(score):
            score = 0.0

        evidence_group = str(r.get("evidence_group", "unknown"))
        diagnostic = str(r.get("diagnostic", "unknown"))
        domain = str(r.get("domain", "unknown"))

        # ERA5 baseline rows from the old matrix are useful context,
        # but should not drive the integrated forecast conclusion.
        if evidence_group == "circulation_baseline":
            weight = 0.0
            evidence_type = "era5_climatological_context"
        else:
            weight = 1.0
            evidence_type = "nmme_forecast_anomaly"

        rows.append(
            {
                "source_system": "NMME_CPC_ENSMEAN",
                "evidence_type": evidence_type,
                "evidence_group": evidence_group,
                "period": period,
                "period_label": PERIOD_LABELS.get(period, period),
                "period_order": PERIOD_ORDER.get(period, 99),
                "domain": domain,
                "diagnostic": diagnostic,
                "value": safe_float(r.get("value")),
                "units": str(r.get("units", "")),
                "classification": str(r.get("classification", "")),
                "raw_score": score,
                "weight": weight,
                "weighted_score": score * weight,
                "support_direction": score_to_support(score),
                "evidence_strength": score_to_strength(score),
                "confidence": str(r.get("confidence", "")),
                "interpretation": str(r.get("interpretation", "")),
                "limitation": str(r.get("limitation", "")),
                "source_table": "final_dynamic_evidence_matrix.csv",
            }
        )

    return pd.DataFrame(rows)


# ==========================================================
# CFSV2 EVIDENCE
# ==========================================================

def classify_cfsv2_row(diagnostic: str, value: float, classification: str) -> tuple[float, float, str, str, str]:
    """
    Score convention:
        positive score  = supports dry Kiremt interpretation
        negative score  = supports rainfall potential / reduces dry-risk confidence
        zero score      = neutral, context-only, or not interpretable without anomaly

    CFSv2 fields here are raw forecast fields from June 2026 initialization,
    not anomalies from the May 2026 NMME ensemble. Therefore, weights are lower
    than direct NMME anomaly evidence.
    """

    diagnostic = str(diagnostic)
    classification = str(classification)

    # Default: context only
    score = 0.0
    weight = 0.5
    confidence = "low_to_moderate"
    support_text = "Context-only diagnostic."
    limitation = "Raw CFSv2 forecast field; not an anomaly relative to model hindcast climatology."

    if np.isnan(value):
        return 0.0, 0.0, "missing", "Missing diagnostic value.", "Missing value."

    # ------------------------------------------------------
    # TEJ
    # Stronger/moderate easterly jet is usually favorable for Kiremt convection.
    # Weak TEJ would support dry risk.
    # ------------------------------------------------------
    if diagnostic == "tej_strength":
        if classification in ["strong_tej", "moderate_tej"]:
            score = -1.0
            support_text = "Moderate/strong TEJ supports an active Kiremt upper-level jet background and reduces dry-risk confidence."
        elif classification in ["weak_tej", "no_easterly_tej"]:
            score = 1.0
            support_text = "Weak/no TEJ would support a dry-risk interpretation."
        else:
            score = 0.0
            support_text = "TEJ signal is not clearly interpretable."

        return score, weight, confidence, support_text, limitation

    # ------------------------------------------------------
    # 200 hPa divergence
    # Upper-level divergence supports convection; convergence suppresses it.
    # ------------------------------------------------------
    if diagnostic == "div200":
        if value > 0:
            score = -1.0
            support_text = "Upper-level divergence supports convection and rainfall potential."
        elif value < 0:
            score = 1.0
            support_text = "Upper-level convergence may suppress deep convection and supports dry-risk interpretation."
        else:
            score = 0.0
            support_text = "Near-zero upper-level divergence."

        return score, weight, confidence, support_text, limitation

    # ------------------------------------------------------
    # Moisture-flux convergence
    # Positive MFC supports rainfall; negative MFC supports dryness.
    # ------------------------------------------------------
    if diagnostic == "mfc850":
        if value > 0:
            score = -1.0
            support_text = "Low-level moisture-flux convergence supports rainfall potential."
        elif value < 0:
            score = 1.0
            support_text = "Low-level moisture-flux divergence supports dry-risk interpretation."
        else:
            score = 0.0
            support_text = "Near-zero moisture-flux convergence."

        return score, weight, confidence, support_text, limitation

    # ------------------------------------------------------
    # Omega
    # Positive omega = subsidence; negative omega = rising motion.
    # ------------------------------------------------------
    if diagnostic in ["omega500", "omega700"]:
        if value > 0:
            score = 1.0
            support_text = "Positive omega indicates subsidence tendency and supports dry-risk interpretation."
        elif value < 0:
            score = -1.0
            support_text = "Negative omega indicates rising-motion tendency and supports rainfall potential."
        else:
            score = 0.0
            support_text = "Near-zero vertical-motion tendency."

        return score, weight, confidence, support_text, limitation

    # ------------------------------------------------------
    # u200
    # Raw u200 is less direct than TEJ strength but still useful.
    # ------------------------------------------------------
    if diagnostic == "u200":
        if value < 0:
            score = -0.5
            support_text = "Easterly 200 hPa flow is consistent with TEJ background and supports rainfall potential."
        elif value > 0:
            score = 0.5
            support_text = "Westerly 200 hPa flow would weaken TEJ support and may support dry-risk interpretation."
        else:
            score = 0.0
            support_text = "Near-zero 200 hPa zonal flow."

        return score, weight, "low", support_text, limitation

    # ------------------------------------------------------
    # Raw VP, streamfunction, height, SST, q/wind fields
    # These need anomalies or pattern interpretation; keep neutral.
    # ------------------------------------------------------
    if diagnostic in [
        "vp200",
        "strf200",
        "z200",
        "z500",
        "sst_proxy",
        "dmi_raw_sst_proxy",
        "u850",
        "v850",
        "q850",
        "wind_speed850",
        "qu850",
        "qv850",
        "v200",
    ]:
        score = 0.0
        weight = 0.25
        confidence = "context_only"
        support_text = (
            f"{diagnostic} is retained as circulation context, but it is not scored because raw values require anomaly or pattern-based interpretation."
        )
        return score, weight, confidence, support_text, limitation

    return score, weight, confidence, support_text, limitation


def load_cfsv2_evidence() -> pd.DataFrame:
    if not CFSV2_AREA_CSV.exists():
        print(f"CFSv2 area diagnostics not found: {CFSV2_AREA_CSV}")
        print("Run scripts\\10_compute_cfsv2_dynamic_diagnostics.py first.")
        return pd.DataFrame()

    df = pd.read_csv(CFSV2_AREA_CSV)

    rows = []

    # Focus scoring on Ethiopia area means.
    # Other domains can be added later as context, but Ethiopia is the cleanest first integrated summary.
    df_focus = df[df["domain"].isin(["ethiopia"])].copy()

    for _, r in df_focus.iterrows():
        period = normalize_period(r.get("period"))
        diagnostic = str(r.get("diagnostic"))
        value = safe_float(r.get("value"))
        classification = str(r.get("classification", ""))

        score, weight, confidence, interpretation, limitation = classify_cfsv2_row(
            diagnostic=diagnostic,
            value=value,
            classification=classification,
        )

        rows.append(
            {
                "source_system": "CFSv2_NOMADS_June2026_init",
                "evidence_type": "cfsv2_raw_dynamic_consistency",
                "evidence_group": "dynamic_circulation_forecast",
                "period": period,
                "period_label": PERIOD_LABELS.get(period, period),
                "period_order": PERIOD_ORDER.get(period, 99),
                "domain": str(r.get("domain", "")),
                "diagnostic": diagnostic,
                "value": value,
                "units": str(r.get("units", "")),
                "classification": classification,
                "raw_score": score,
                "weight": weight,
                "weighted_score": score * weight,
                "support_direction": score_to_support(score),
                "evidence_strength": score_to_strength(score),
                "confidence": confidence,
                "interpretation": interpretation,
                "limitation": limitation,
                "source_table": "cfsv2_dynamic_area_mean_diagnostics.csv",
            }
        )

    return pd.DataFrame(rows)


# ==========================================================
# INTEGRATION AND REPORT
# ==========================================================

def build_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for period in ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]:
        sub = matrix[matrix["period"] == period].copy()

        if sub.empty:
            continue

        nmme = sub[sub["source_system"] == "NMME_CPC_ENSMEAN"]
        cfsv2 = sub[sub["source_system"] == "CFSv2_NOMADS_June2026_init"]

        weighted_score_sum = float(sub["weighted_score"].sum())
        raw_score_sum = float(sub["raw_score"].sum())

        dry_count = int((sub["raw_score"] > 0).sum())
        wet_count = int((sub["raw_score"] < 0).sum())
        neutral_count = int((sub["raw_score"] == 0).sum())

        nmme_weighted_score = float(nmme["weighted_score"].sum()) if not nmme.empty else 0.0
        cfsv2_weighted_score = float(cfsv2["weighted_score"].sum()) if not cfsv2.empty else 0.0

        category, message = overall_category(weighted_score_sum)

        rows.append(
            {
                "period": period,
                "period_label": PERIOD_LABELS.get(period, period),
                "period_order": PERIOD_ORDER.get(period, 99),
                "total_evidence_rows": int(len(sub)),
                "dry_support_count": dry_count,
                "wet_or_rain_support_count": wet_count,
                "neutral_or_context_count": neutral_count,
                "raw_score_sum": raw_score_sum,
                "weighted_score_sum": weighted_score_sum,
                "nmme_weighted_score": nmme_weighted_score,
                "cfsv2_weighted_score": cfsv2_weighted_score,
                "overall_category": category,
                "summary_message": message,
            }
        )

    return pd.DataFrame(rows).sort_values("period_order")


def build_markdown_report(matrix: pd.DataFrame, summary: pd.DataFrame) -> str:
    lines = []

    lines.append("# Integrated NMME–CFSv2 Dynamic Evidence Report")
    lines.append("")
    lines.append("## Ethiopia Kiremt/JJAS 2026 rainfall interpretation")
    lines.append("")
    lines.append("This report integrates two complementary evidence streams:")
    lines.append("")
    lines.append("1. **NMME CPC ensemble-mean anomaly evidence**: precipitation anomaly, surface-temperature/SST proxy, and z200 anomaly.")
    lines.append("2. **CFSv2 NOMADS dynamic forecast evidence**: TEJ strength, 200 hPa divergence, 850 hPa moisture-flux convergence, omega500/omega700, velocity potential, streamfunction, and geopotential height.")
    lines.append("")
    lines.append("> Important: the CFSv2 dynamic diagnostics are raw forecast fields from the June 2026 initialization. They are not the same as May-initialized NMME ensemble-mean anomalies. Therefore, they are treated as lower-weight physical-consistency evidence.")
    lines.append("")

    lines.append("## Integrated summary by period")
    lines.append("")
    if not summary.empty:
        show_cols = [
            "period_label",
            "dry_support_count",
            "wet_or_rain_support_count",
            "neutral_or_context_count",
            "weighted_score_sum",
            "nmme_weighted_score",
            "cfsv2_weighted_score",
            "overall_category",
        ]
        lines.append(summary[show_cols].to_markdown(index=False))
    else:
        lines.append("No integrated summary available.")
    lines.append("")

    lines.append("## Key JJAS interpretation")
    lines.append("")
    jjas = summary[summary["period"] == "JJAS"]

    if not jjas.empty:
        r = jjas.iloc[0]
        lines.append(f"- **JJAS integrated classification:** `{r['overall_category']}`.")
        lines.append(f"- **Weighted score:** {r['weighted_score_sum']:.2f}.")
        lines.append(f"- **NMME contribution:** {r['nmme_weighted_score']:.2f}.")
        lines.append(f"- **CFSv2 dynamic contribution:** {r['cfsv2_weighted_score']:.2f}.")
        lines.append(f"- **Interpretation:** {r['summary_message']}")
    else:
        lines.append("No JJAS summary row was available.")
    lines.append("")

    lines.append("## Ethiopia JJAS CFSv2 dynamic details")
    lines.append("")
    cfs_jjas = matrix[
        (matrix["source_system"] == "CFSv2_NOMADS_June2026_init")
        & (matrix["period"] == "JJAS")
        & (matrix["domain"] == "ethiopia")
        & (
            matrix["diagnostic"].isin(
                [
                    "tej_strength",
                    "div200",
                    "mfc850",
                    "omega500",
                    "omega700",
                    "vp200",
                    "z200",
                    "z500",
                ]
            )
        )
    ].copy()

    if not cfs_jjas.empty:
        lines.append(
            cfs_jjas[
                [
                    "diagnostic",
                    "value",
                    "units",
                    "classification",
                    "raw_score",
                    "weighted_score",
                    "interpretation",
                ]
            ].to_markdown(index=False)
        )
    else:
        lines.append("No Ethiopia JJAS CFSv2 diagnostic details were available.")
    lines.append("")

    lines.append("## Main limitations")
    lines.append("")
    lines.append("- NMME and CFSv2 evidence are not identical forecast systems in this workflow.")
    lines.append("- The NMME evidence is anomaly-based and comes from the CPC May 2026 NMME ensemble-mean anomaly products.")
    lines.append("- The CFSv2 dynamic evidence comes from June 2026 NOMADS operational forecast fields and is raw, not bias-corrected anomaly evidence.")
    lines.append("- Raw velocity potential, streamfunction, geopotential height, and SST fields should be interpreted with anomaly maps or hindcast climatology before being scored strongly.")
    lines.append("- OLR proxy was not extracted yet; it should be added after inspecting the `flxf` GRIB variable names.")
    lines.append("")

    lines.append("## Recommended next steps")
    lines.append("")
    lines.append("1. Add CFSv2 hindcast climatology or operational climatology to convert raw CFSv2 dynamic fields into anomalies.")
    lines.append("2. Fix OLR extraction from the CFSv2 `flxf` files after identifying the correct longwave-radiation variable.")
    lines.append("3. Compare NMME dry/wet anomaly maps against CFSv2 dynamic consistency maps.")
    lines.append("4. Prepare the final Kiremt 2026 narrative using only diagnostics that are consistent across rainfall anomaly, ocean forcing, and circulation dynamics.")
    lines.append("")

    return "\n".join(lines)


def main():
    print("\n==================================================")
    print("Integrate NMME and CFSv2 evidence")
    print("==================================================")
    print(f"Tables:  {TABLE_DIR}")
    print(f"Reports: {REPORT_DIR}")

    nmme_df = load_nmme_evidence()
    cfsv2_df = load_cfsv2_evidence()

    if nmme_df.empty and cfsv2_df.empty:
        raise RuntimeError("No NMME or CFSv2 evidence available. Run previous scripts first.")

    matrix = pd.concat([nmme_df, cfsv2_df], ignore_index=True, sort=False)

    matrix = matrix.sort_values(
        by=["period_order", "source_system", "evidence_group", "diagnostic", "domain"],
        ascending=True,
    )

    matrix.to_csv(OUT_MATRIX_CSV, index=False)

    summary = build_summary(matrix)
    summary.to_csv(OUT_SUMMARY_CSV, index=False)

    report_text = build_markdown_report(matrix, summary)

    with open(OUT_REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n==================================================")
    print("INTEGRATED EVIDENCE FINISHED")
    print("==================================================")
    print(f"Integrated matrix:  {OUT_MATRIX_CSV}")
    print(f"Integrated summary: {OUT_SUMMARY_CSV}")
    print(f"Markdown report:    {OUT_REPORT_MD}")

    print("\nIntegrated period summary:")
    if not summary.empty:
        print(
            summary[
                [
                    "period_label",
                    "dry_support_count",
                    "wet_or_rain_support_count",
                    "neutral_or_context_count",
                    "weighted_score_sum",
                    "nmme_weighted_score",
                    "cfsv2_weighted_score",
                    "overall_category",
                ]
            ].to_string(index=False)
        )

    print("\nDone.")


if __name__ == "__main__":
    main()