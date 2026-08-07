from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

from app.models import EvidenceRow, EvidenceSummaryRow
from app.services.data import evidence_matrix, evidence_summary

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

_ROW_FIELDS = [
    "source_system", "evidence_type", "evidence_group", "period", "period_label",
    "domain", "diagnostic", "value", "units", "classification", "raw_score",
    "weight", "weighted_score", "support_direction", "evidence_strength",
    "confidence", "interpretation", "limitation",
]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    return df.where(pd.notnull(df), None)


@router.get("/matrix", response_model=list[EvidenceRow])
def get_evidence_matrix(
    source: Optional[str] = Query(None, description="Substring match against source_system, e.g. 'NMME' or 'CFSv2'"),
    domain: Optional[str] = Query(None),
    period: Optional[str] = Query(None, description="Period code, e.g. Jun, JJAS"),
    q: Optional[str] = Query(None, description="Case-insensitive substring search over diagnostic/domain"),
) -> list[EvidenceRow]:
    df = evidence_matrix()

    if source:
        df = df[df.source_system.str.contains(source, case=False, na=False)]
    if domain:
        df = df[df.domain == domain]
    if period:
        df = df[df.period == period]
    if q:
        mask = df.diagnostic.str.lower().str.contains(q.lower(), na=False) | df.domain.str.lower().str.contains(q.lower(), na=False)
        df = df[mask]

    df = _clean(df[_ROW_FIELDS])
    return [EvidenceRow(**row) for row in df.to_dict(orient="records")]


@router.get("/summary", response_model=list[EvidenceSummaryRow])
def get_evidence_summary() -> list[EvidenceSummaryRow]:
    df = _clean(evidence_summary())
    return [EvidenceSummaryRow(**row) for row in df.to_dict(orient="records")]
