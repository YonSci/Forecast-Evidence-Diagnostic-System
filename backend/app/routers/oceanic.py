import json
from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.config import INITIALIZATIONS, SST_OVERLAYS_DIR
from app.models import OverlayInfo, GridResponse
from app.services.data import sst_proxy, sst_driver_classification, sst_indices_extended, csv_key_for_init

router = APIRouter(prefix="/api/oceanic", tags=["oceanic"])

SST_GRID_DIR = SST_OVERLAYS_DIR / "grid_data"


@lru_cache(maxsize=1)
def _sst_overlay_index() -> dict:
    path = SST_OVERLAYS_DIR / "overlay_index.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=64)
def _sst_grid_data(init_key: str, period: str) -> dict | None:
    path = SST_GRID_DIR / init_key / f"tmpsfc_global_{period}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_init(init: str) -> dict:
    meta = INITIALIZATIONS.get(init)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown initialization: {init}")
    return meta


@router.get("/sst-proxy")
def get_sst_proxy(init: str = Query("2026-05-08")) -> list[dict]:
    """
    NMME tmpsfc-derived Nino3.4 / IOD-West / IOD-East / DMI proxy indices,
    joined with their el_nino_like / positive_iod_like style classification.
    Not an official ENSO/IOD index product -- see /api/methodology.

    Also folds in Nino1+2 / Nino3 / Nino4 from the expanded index table
    (scripts/25_compute_expanded_sst_indices.py) when available for the
    requested initialization/period, alongside the original four fields.
    """
    init_meta = _validate_init(init)

    sst = sst_proxy().copy()
    sst["period_short"] = sst["period"].str.replace("_2026", "", regex=False)

    drv = sst_driver_classification()[["period", "nino34_classification", "dmi_classification"]]

    merged = sst.merge(drv, left_on="period_short", right_on="period", suffixes=("", "_drv"))
    merged = merged.where(pd.notnull(merged), None)

    extended = sst_indices_extended()
    extended = extended[extended["init"] == init_meta["csv_key"]].set_index("period")

    out = []
    for row in merged.to_dict(orient="records"):
        period = row["period_short"]
        ext_row = extended.loc[period] if period in extended.index else None

        out.append({
            "period": period,
            "nino1_2_anomaly": float(ext_row["nino1_2"]) if ext_row is not None else None,
            "nino3_anomaly": float(ext_row["nino3"]) if ext_row is not None else None,
            "nino34_anomaly": row["nino34_tmpsfc_anomaly"],
            "nino4_anomaly": float(ext_row["nino4"]) if ext_row is not None else None,
            "iod_west_anomaly": row["iod_west_tmpsfc_anomaly"],
            "iod_east_anomaly": row["iod_east_tmpsfc_anomaly"],
            "dmi_proxy": row["dmi_approx"],
            "units": row["units"],
            "nino34_classification": row["nino34_classification"],
            "dmi_classification": row["dmi_classification"],
        })
    return out


@router.get("/overlay", response_model=OverlayInfo)
def get_sst_overlay(
    init: str = Query(...),
    period: str = Query(...),
) -> OverlayInfo:
    """Global tmpsfc-anomaly (SST-proxy) raster, ocean-clipped, for the
    Leaflet map -- see scripts/26_generate_sst_leaflet_overlay_maps.py."""
    init_meta = _validate_init(init)
    if period not in init_meta["periods"]:
        return OverlayInfo(available=False)

    key = f"{init_meta['csv_key']}/global/{period}"
    entry = _sst_overlay_index().get(key)
    if entry is None:
        return OverlayInfo(available=False)

    return OverlayInfo(
        available=True,
        url=f"/static/sst_overlays/{entry['file']}",
        bounds=entry["bounds"],
        vmin=entry["vmin"],
        vmax=entry["vmax"],
        unit=entry["unit"],
    )


@router.get("/grid", response_model=GridResponse)
def get_sst_grid(
    init: str = Query(...),
    period: str = Query(...),
) -> GridResponse:
    init_meta = _validate_init(init)
    if period not in init_meta["periods"]:
        raise HTTPException(status_code=404, detail=f"Period {period} is not available for this initialization.")

    data = _sst_grid_data(init_meta["csv_key"], period)
    if data is None:
        raise HTTPException(status_code=404, detail="No grid data for this combination.")
    return GridResponse(**data)
