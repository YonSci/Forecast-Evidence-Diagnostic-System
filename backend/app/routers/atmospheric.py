from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

from app.services.data import tej_climatology, era5_moisture_flux, era5_vertical_divergence, cfsv2_area_mean

router = APIRouter(prefix="/api/atmospheric", tags=["atmospheric"])

# Same two domains the dashboard's Atmospheric Evidence tab already surfaces
# out of the much larger domain set present in these tables.
DEFAULT_DOMAINS = ["ethiopia", "greater_horn"]


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
