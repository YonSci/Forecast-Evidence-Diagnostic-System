import json
from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.config import REGIONS, INITIALIZATIONS, PERIOD_LABELS, OVERLAYS_DIR
from app.models import AnomalySeriesResponse, AnomalyPeriodReading, AnomalyTableRow, OverlayInfo, GridResponse
from app.services.data import anomaly_table, csv_key_for_init

router = APIRouter(prefix="/api/anomaly", tags=["anomaly"])

GRID_DIR = OVERLAYS_DIR / "grid_data"


@lru_cache(maxsize=1)
def _overlay_index() -> dict:
    path = OVERLAYS_DIR / "overlay_index.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=64)
def _grid_data(init_key: str, region: str, period: str) -> dict | None:
    path = GRID_DIR / init_key / f"prate_{region}_{period}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_init(init: str) -> dict:
    meta = INITIALIZATIONS.get(init)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown initialization: {init}")
    return meta


def _validate_region(region: str) -> None:
    if region not in REGIONS:
        raise HTTPException(status_code=404, detail=f"Unknown region: {region}")


def _reading_for(df: pd.DataFrame, period_2026: str, region: str) -> dict:
    sub = df[df.region == region]
    prate_mean = sub[(sub.field == "prate") & (sub.period == period_2026) & (sub.aggregation.isin(["monthly_mean", "season_mean"]))]
    prate_total = sub[(sub.field == "prate") & (sub.period == period_2026) & (sub.aggregation.isin(["monthly_total", "season_total"]))]
    tmpsfc = sub[(sub.field == "tmpsfc") & (sub.period == period_2026) & (sub.aggregation.isin(["monthly_anomaly", "season_mean_anomaly"]))]

    return {
        "prate_mm_day": round(float(prate_mean["value"].iloc[0]), 4) if len(prate_mean) else None,
        "prate_total": round(float(prate_total["value"].iloc[0]), 3) if len(prate_total) else None,
        "prate_total_unit": prate_total["units"].iloc[0] if len(prate_total) else None,
        "tmpsfc_anomaly_k": round(float(tmpsfc["value"].iloc[0]), 4) if len(tmpsfc) else None,
    }


@router.get("", response_model=AnomalySeriesResponse)
def get_anomaly_series(
    init: str = Query(..., description="Initialization key, e.g. 2026-05-08"),
    region: str = Query("ethiopia"),
    variable: str = Query("prate", pattern="^(prate|tmpsfc)$"),
) -> AnomalySeriesResponse:
    init_meta = _validate_init(init)
    _validate_region(region)

    df = anomaly_table(init_meta["csv_key"])
    readings = []
    for period in init_meta["periods"]:
        period_2026 = f"{period}_2026"
        r = _reading_for(df, period_2026, region)
        readings.append(AnomalyPeriodReading(
            period=period,
            period_label=PERIOD_LABELS.get(period, period),
            **r,
        ))

    return AnomalySeriesResponse(init=init, region=region, variable=variable, readings=readings)


@router.get("/table", response_model=list[AnomalyTableRow])
def get_anomaly_table(
    init: str = Query(...),
    region: str = Query("all", description="A region key, or 'all'"),
) -> list[AnomalyTableRow]:
    init_meta = _validate_init(init)
    if region != "all":
        _validate_region(region)

    df = anomaly_table(init_meta["csv_key"])
    regions_to_use = list(REGIONS.keys()) if region == "all" else [region]

    rows: list[AnomalyTableRow] = []
    for r_key in regions_to_use:
        for period in init_meta["periods"]:
            period_2026 = f"{period}_2026"
            reading = _reading_for(df, period_2026, r_key)
            rows.append(AnomalyTableRow(
                region=r_key,
                region_label=REGIONS[r_key]["label"],
                period=period,
                period_label=PERIOD_LABELS.get(period, period),
                **reading,
            ))
    return rows


@router.get("/overlay", response_model=OverlayInfo)
def get_anomaly_overlay(
    init: str = Query(...),
    region: str = Query(...),
    period: str = Query(...),
    variable: str = Query("prate", pattern="^(prate|tmpsfc)$"),
) -> OverlayInfo:
    init_meta = _validate_init(init)
    _validate_region(region)

    if variable != "prate":
        return OverlayInfo(available=False)
    if period not in init_meta["periods"]:
        return OverlayInfo(available=False)

    key = f"{init_meta['csv_key']}/{region}/{period}"
    entry = _overlay_index().get(key)
    if entry is None:
        return OverlayInfo(available=False)

    return OverlayInfo(
        available=True,
        url=f"/static/overlays/{entry['file']}",
        bounds=entry["bounds"],
        vmin=entry["vmin"],
        vmax=entry["vmax"],
        unit=entry["unit"],
    )


@router.get("/grid", response_model=GridResponse)
def get_anomaly_grid(
    init: str = Query(...),
    region: str = Query(...),
    period: str = Query(...),
    variable: str = Query("prate", pattern="^(prate|tmpsfc)$"),
) -> GridResponse:
    """Raw (unclipped, rectangular-box) grid values backing the overlay map,
    for exact-value hover tooltips -- pre-extracted by
    scripts/23_generate_leaflet_grid_data.py, same pattern as the overlay
    PNGs and overlay_index.json."""
    init_meta = _validate_init(init)
    _validate_region(region)

    if variable != "prate":
        raise HTTPException(status_code=404, detail="Grid data is only available for rainfall (prate).")
    if period not in init_meta["periods"]:
        raise HTTPException(status_code=404, detail=f"Period {period} is not available for this initialization.")

    data = _grid_data(init_meta["csv_key"], region, period)
    if data is None:
        raise HTTPException(status_code=404, detail="No grid data for this combination.")
    return GridResponse(**data)
