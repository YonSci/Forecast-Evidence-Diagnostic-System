"""Pydantic response models for the Forecast Evidence and Diagnostic System API."""
from typing import Optional

from pydantic import BaseModel


class RegionMeta(BaseModel):
    key: str
    label: str
    box: list[float]


class InitMeta(BaseModel):
    key: str
    label: str
    short_label: str
    periods: list[str]
    note: str


class MetaResponse(BaseModel):
    regions: list[RegionMeta]
    variables: dict[str, str]
    initializations: list[InitMeta]
    period_labels: dict[str, str]


class AnomalyPeriodReading(BaseModel):
    period: str
    period_label: str
    prate_mm_day: Optional[float] = None
    prate_total: Optional[float] = None
    prate_total_unit: Optional[str] = None
    tmpsfc_anomaly_k: Optional[float] = None


class AnomalySeriesResponse(BaseModel):
    init: str
    region: str
    variable: str
    readings: list[AnomalyPeriodReading]


class AnomalyTableRow(BaseModel):
    region: str
    region_label: str
    period: str
    period_label: str
    prate_mm_day: Optional[float] = None
    prate_total: Optional[float] = None
    prate_total_unit: Optional[str] = None
    tmpsfc_anomaly_k: Optional[float] = None


class OverlayInfo(BaseModel):
    available: bool
    url: Optional[str] = None
    bounds: Optional[list[list[float]]] = None
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    unit: Optional[str] = None


class EvidenceRow(BaseModel):
    source_system: str
    evidence_type: str
    evidence_group: str
    period: str
    period_label: str
    domain: str
    diagnostic: str
    value: Optional[float] = None
    units: Optional[str] = None
    classification: Optional[str] = None
    raw_score: Optional[float] = None
    weight: Optional[float] = None
    weighted_score: Optional[float] = None
    support_direction: Optional[str] = None
    evidence_strength: Optional[str] = None
    confidence: Optional[str] = None
    interpretation: Optional[str] = None
    limitation: Optional[str] = None


class EvidenceSummaryRow(BaseModel):
    period: str
    period_label: str
    period_order: int
    total_evidence_rows: Optional[int] = None
    dry_support_count: int
    wet_or_rain_support_count: int
    neutral_or_context_count: int
    raw_score_sum: Optional[float] = None
    weighted_score_sum: float
    nmme_weighted_score: float
    cfsv2_weighted_score: float
    overall_category: str
    summary_message: Optional[str] = None


class GalleryImage(BaseModel):
    key: str
    url: str
    caption: str
    group: str
