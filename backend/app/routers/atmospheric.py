import json
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.config import ATMOS_OVERLAYS_DIR
from app.models import GridResponse, OverlayInfo
from app.services.data import tej_climatology, era5_moisture_flux, era5_vertical_divergence, cfsv2_area_mean

router = APIRouter(prefix="/api/atmospheric", tags=["atmospheric"])

# Same two domains the dashboard's Atmospheric Evidence tab already surfaces
# out of the much larger domain set present in these tables.
DEFAULT_DOMAINS = ["ethiopia", "greater_horn"]

ATMOS_GRID_DIR = ATMOS_OVERLAYS_DIR / "grid_data"

# Ordered for display: TEJ first, then the same order the old static
# gallery used. z200 is a real per-2026-forecast-period NMME grid (May
# init); the other five are ERA5 1991-2020 climatology by calendar
# month/season -- see scripts/27_generate_atmospheric_leaflet_overlays.py.
ATMOS_VARIABLES: dict[str, dict] = {
    "tej": {"label": "TEJ (200 hPa wind speed)", "source": "climatology"},
    "z200": {"label": "200 hPa geopotential height anomaly", "source": "forecast"},
    "mfc850": {"label": "850 hPa moisture-flux convergence", "source": "climatology"},
    "omega500": {"label": "500 hPa omega", "source": "climatology"},
    "omega700": {"label": "700 hPa omega", "source": "climatology"},
    "divergence200": {"label": "200 hPa divergence", "source": "climatology"},
}

ATMOS_PERIODS = ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]


@lru_cache(maxsize=1)
def _atmos_overlay_index() -> dict:
    path = ATMOS_OVERLAYS_DIR / "overlay_index.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=64)
def _atmos_grid_data(variable: str, period: str) -> dict | None:
    path = ATMOS_GRID_DIR / variable / f"{period}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notnull(df), None).to_dict(orient="records")


@router.get("/tej-climatology")
def get_tej_climatology() -> list[dict]:
    """ERA5 1991-2020 climatological Tropical Easterly Jet strength (200 hPa -u)."""
    return _clean(tej_climatology())


@router.get("/moisture-flux")
def get_moisture_flux(domain: Optional[str] = Query(None)) -> list[dict]:
    df = era5_moisture_flux()
    domains = [domain] if domain else DEFAULT_DOMAINS
    return _clean(df[df.domain.isin(domains)])


@router.get("/vertical-divergence")
def get_vertical_divergence(domain: Optional[str] = Query(None)) -> list[dict]:
    df = era5_vertical_divergence()
    domains = [domain] if domain else DEFAULT_DOMAINS
    return _clean(df[df.domain.isin(domains)])


@router.get("/cfsv2")
def get_cfsv2(domain: str = Query("ethiopia")) -> list[dict]:
    """Raw CFSv2 NOMADS June-2026-init dynamic diagnostics (not yet anomaly-corrected)."""
    df = cfsv2_area_mean()
    return _clean(df[df.domain == domain])


@router.get("/circulation-variables")
def get_circulation_variables() -> list[dict]:
    """Ordered list of the interactive circulation maps below, with a flag
    for whether each is a real 2026 NMME forecast field (z200) or an ERA5
    1991-2020 climatology by calendar month/season (everything else)."""
    return [{"key": k, **v} for k, v in ATMOS_VARIABLES.items()]


@router.get("/overlay", response_model=OverlayInfo)
def get_atmospheric_overlay(
    variable: str = Query(...),
    period: str = Query(...),
) -> OverlayInfo:
    """Circulation-diagnostic raster for the Leaflet map -- see
    scripts/27_generate_atmospheric_leaflet_overlays.py."""
    if variable not in ATMOS_VARIABLES or period not in ATMOS_PERIODS:
        return OverlayInfo(available=False)

    entry = _atmos_overlay_index().get(f"{variable}/{period}")
    if entry is None:
        return OverlayInfo(available=False)

    return OverlayInfo(
        available=True,
        url=f"/static/atmos_overlays/{entry['file']}",
        bounds=entry["bounds"],
        vmin=entry["vmin"],
        vmax=entry["vmax"],
        unit=entry["unit"],
    )


@router.get("/grid", response_model=GridResponse)
def get_atmospheric_grid(
    variable: str = Query(...),
    period: str = Query(...),
) -> GridResponse:
    if variable not in ATMOS_VARIABLES or period not in ATMOS_PERIODS:
        raise HTTPException(status_code=404, detail=f"Unknown variable/period: {variable}/{period}")

    data = _atmos_grid_data(variable, period)
    if data is None:
        raise HTTPException(status_code=404, detail="No grid data for this combination.")
    return GridResponse(**data)
