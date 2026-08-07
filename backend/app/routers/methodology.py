from fastapi import APIRouter

from app.config import DOMAIN_REFERENCE

router = APIRouter(prefix="/api/methodology", tags=["methodology"])

EVIDENCE_WEIGHTS = [
    {
        "evidence_type": "NMME forecast anomaly",
        "weight": 1.0,
        "rationale": "Direct, bias-corrected forecast anomaly — highest-confidence evidence.",
    },
    {
        "evidence_type": "CFSv2 raw dynamic fields",
        "weight": 0.5,
        "rationale": "Physically informative but raw (not anomaly-corrected) and from a later initialization.",
    },
    {
        "evidence_type": "CFSv2 context-only fields",
        "weight": 0.25,
        "rationale": "Retained for circulation context (e.g. q850, u200 alone); not independently classified.",
    },
    {
        "evidence_type": "ERA5 climatology",
        "weight": 0.0,
        "rationale": "Describes the normal background circulation, not a 2026 anomaly — informational only.",
    },
]

LIMITATIONS = [
    "NMME (May init.) and CFSv2 (June init.) are not the same forecast cycle — they are combined as complementary, not identical, evidence.",
    "CFSv2 dynamic fields are raw forecast values, not bias-corrected anomalies relative to a CFSv2 hindcast climatology.",
    "ERA5 fields in this workflow are 1991-2020 climatological baselines, not 2026-specific circulation anomalies.",
    "Niño3.4/IOD/DMI values are tmpsfc-based proxies, not official ENSO/IOD index products — cross-check against NOAA/BOM/JMA before use in decision-making.",
    "NMME precipitation anomaly is an ensemble mean, not a probabilistic or model-agreement product.",
    "OLR proxy extraction from CFSv2 longwave fields is not yet complete.",
    "Each successive initialization (May → June → July) covers a narrower set of forecast months, since NMME real-time anomaly products skip the partially-elapsed init month.",
]


@router.get("/domains")
def get_domains() -> list[dict]:
    return [{"name": name, "box": box} for name, box in DOMAIN_REFERENCE.items()]


@router.get("/weights")
def get_weights() -> list[dict]:
    return EVIDENCE_WEIGHTS


@router.get("/limitations")
def get_limitations() -> list[str]:
    return LIMITATIONS
