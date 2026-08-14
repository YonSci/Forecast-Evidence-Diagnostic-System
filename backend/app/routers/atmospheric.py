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

# Ordered as a TEJ dynamical-consistency check: jet strength -> jet
# structure/orientation -> upper-level divergence at the jet exit ->
# forced ascent -> is moisture actually being supplied -> is it
# accumulating at low levels. All six are ERA5 1991-2020 climatology by
# calendar month/season -- none has a per-2026-forecast gridded product
# yet -- see scripts/27_generate_atmospheric_leaflet_overlays.py.
ATMOS_VARIABLES: dict[str, dict] = {
    "u200": {"label": "200 hPa zonal wind (TEJ strength)", "source": "climatology"},
    "u200_vectors": {"label": "200 hPa wind vectors (circulation/jet orientation)", "source": "climatology"},
    "divergence200": {"label": "200 hPa divergence (upper-level outflow)", "source": "climatology"},
    "omega500": {"label": "500 hPa vertical velocity (forced ascent)", "source": "climatology"},
    "qflux850": {"label": "850 hPa moisture flux (is moisture supplied?)", "source": "climatology"},
    "mfc850": {"label": "850 hPa moisture-flux convergence (is it accumulating?)", "source": "climatology"},
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
        legend_gradient=entry.get("legend_gradient"),
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
