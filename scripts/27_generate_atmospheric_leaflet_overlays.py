"""
27_generate_atmospheric_leaflet_overlays.py

Purpose
-------
Generate react-leaflet <ImageOverlay> rasters (full-bleed, no title/
colorbar/axes baked in) + matching grid JSON for hover tooltips, for the
six atmospheric circulation diagnostics on the Atmospheric Evidence page:
TEJ (200 hPa wind speed), z200 (200 hPa geopotential height anomaly),
850 hPa moisture-flux convergence, 500 hPa omega, 700 hPa omega, and
200 hPa divergence -- the same interactive-map pattern already used for
rainfall (script 22) and the SST proxy (script 26), applied here so each
diagnostic gets a real period dropdown instead of a single static PNG.

z200 is the only one of the six with a genuine per-2026-forecast-period
NMME grid (May initialization, Jun/Jul/Aug/Sep/JJA/JJAS). The other five
are ERA5 1991-2020 climatology, available by calendar month (Jun-Sep) and
JJA/JJAS season -- there is no per-2026-forecast gridded product for
wind/moisture-flux/omega/divergence, so their "period" selector switches
the climatological month/season, not a forecast lead time. This mirrors
the distinction the page's own intro copy already states.

Unlike scripts 22/26 (rainfall/SST), these are upper-air/large-scale
fields that are physically meaningful over land AND ocean, so no land-
or ocean-clip mask is applied here -- full rectangular domain, country
borders drawn separately by the frontend's GeoJSON borders layer.

Outputs
-------
    outputs/maps/atmos_overlays/<variable>/<period>.png
    outputs/maps/atmos_overlays/overlay_index.json
        { "<variable>/<period>": {file, bounds, vmin, vmax, unit} }
    outputs/maps/atmos_overlays/grid_data/<variable>/<period>.json

Run from project root:
    python scripts\\27_generate_atmospheric_leaflet_overlays.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, TwoSlopeNorm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "atmos_overlays"
GRID_OUT_DIR = OUT_DIR / "grid_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Reuse the file-path constants and xarray helpers already defined in
# script 06 (DOMAINS, ERA5_*/Z200_NMME_FILES/MOISTURE_FILES paths,
# open_dataarray/open_dataset, select_month/select_month_ds, subset_box,
# get_symmetric_limits, find_jet_core) instead of redefining them.
_spec = importlib.util.spec_from_file_location("plot06", PROJECT_ROOT / "scripts" / "06_plot_dynamic_maps.py")
s06 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s06)

WEB_MERCATOR_MAX_LAT = 85.05112878
MERCATOR_R = 6378137.0

PERIODS = ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]
MONTH_NUM = {"Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9}

GREATER_HORN_BOX = s06.DOMAINS["greater_horn"]
TEJ_BOX = s06.TEJ_FIG4_BOX


def lon_to_merc_x(lon_deg):
    return np.radians(np.asarray(lon_deg, dtype=float)) * MERCATOR_R


def lat_to_merc_y(lat_deg):
    lat_deg = np.clip(np.asarray(lat_deg, dtype=float), -WEB_MERCATOR_MAX_LAT, WEB_MERCATOR_MAX_LAT)
    return MERCATOR_R * np.log(np.tan(np.pi / 4 + np.radians(lat_deg) / 2))


def clamp_box_lat(box: list[float]) -> list[float]:
    lon_min, lon_max, lat_min, lat_max = box
    return [lon_min, lon_max, max(lat_min, -WEB_MERCATOR_MAX_LAT), min(lat_max, WEB_MERCATOR_MAX_LAT)]


# ==========================================================
# Per-period field loaders -- return a lat/lon DataArray already
# subset+ready to shade, or None if the source file is missing.
# ==========================================================

def load_tej_speed(period: str) -> xr.DataArray | None:
    if period in MONTH_NUM:
        if not (s06.ERA5_U200_MONTHLY.exists() and s06.ERA5_V200_MONTHLY.exists()):
            return None
        u = s06.select_month(s06.open_dataarray(s06.ERA5_U200_MONTHLY, decode_times=True), MONTH_NUM[period])
        v = s06.select_month(s06.open_dataarray(s06.ERA5_V200_MONTHLY, decode_times=True), MONTH_NUM[period])
    else:
        u_path = {"JJA": s06.ERA5_U200_JJA, "JJAS": s06.ERA5_U200_JJAS}[period]
        v_path = {"JJA": s06.ERA5_V200_JJA, "JJAS": s06.ERA5_V200_JJAS}[period]
        if not (u_path.exists() and v_path.exists()):
            return None
        u = s06.open_dataarray(u_path, decode_times=True)
        v = s06.open_dataarray(v_path, decode_times=True)

    speed = np.sqrt(u**2 + v**2)
    speed.attrs["units"] = u.attrs.get("units", "m s-1")
    return speed


def load_z200(period: str) -> xr.DataArray | None:
    path = s06.Z200_NMME_FILES.get(f"{period}_2026")
    if path is None or not path.exists():
        return None
    return s06.open_dataarray(path, decode_times=False)


def load_climatology_da(monthly_path: Path, jja_path: Path, jjas_path: Path, period: str) -> xr.DataArray | None:
    if period in MONTH_NUM:
        if not monthly_path.exists():
            return None
        da = s06.open_dataarray(monthly_path, decode_times=True)
        return s06.select_month(da, MONTH_NUM[period])
    path = {"JJA": jja_path, "JJAS": jjas_path}[period]
    if not path.exists():
        return None
    return s06.open_dataarray(path, decode_times=True)


def load_mfc850(period: str) -> xr.DataArray | None:
    files = s06.MOISTURE_FILES
    if period in MONTH_NUM:
        if not files["monthly"].exists():
            return None
        ds = s06.select_month_ds(s06.open_dataset(files["monthly"], decode_times=True), MONTH_NUM[period])
    else:
        path = files[period]
        if not path.exists():
            return None
        ds = s06.open_dataset(path, decode_times=True)
    return ds["mfc850"]


def load_omega500(period: str) -> xr.DataArray | None:
    f = s06.ERA5_OMEGA_FILES["omega500"]
    return load_climatology_da(f["monthly"], f["JJA"], f["JJAS"], period)


def load_omega700(period: str) -> xr.DataArray | None:
    f = s06.ERA5_OMEGA_FILES["omega700"]
    return load_climatology_da(f["monthly"], f["JJA"], f["JJAS"], period)


def load_divergence200(period: str) -> xr.DataArray | None:
    f = s06.ERA5_DIVERGENCE_FILES
    return load_climatology_da(f["monthly"], f["JJA"], f["JJAS"], period)


# ==========================================================
# Variable registry -- order here is the display order on the page,
# starting from TEJ per the requested layout.
# ==========================================================

VARIABLES = {
    # "unit" is asserted here rather than read from the source netCDF's
    # GRIB-derived attrs, which render as e.g. "m s**-1" or
    # "kg kg-1 s-1 approximately" -- not fit for display.
    "tej": {
        "loader": load_tej_speed,
        "box": TEJ_BOX,
        "cmap": "jet",
        "norm": lambda da: Normalize(vmin=0, vmax=25),
        "unit": "m/s",
    },
    "z200": {
        "loader": load_z200,
        "box": GREATER_HORN_BOX,
        "cmap": "RdBu_r",
        "norm": None,  # symmetric, computed per-field below
        "unit": "m",
    },
    "mfc850": {
        "loader": load_mfc850,
        "box": GREATER_HORN_BOX,
        "cmap": "BrBG",
        "norm": None,
        "unit": "kg/kg/s",
    },
    "omega500": {
        "loader": load_omega500,
        "box": GREATER_HORN_BOX,
        "cmap": "RdBu_r",
        "norm": None,
        "unit": "Pa/s",
    },
    "omega700": {
        "loader": load_omega700,
        "box": GREATER_HORN_BOX,
        "cmap": "RdBu_r",
        "norm": None,
        "unit": "Pa/s",
    },
    "divergence200": {
        "loader": load_divergence200,
        "box": GREATER_HORN_BOX,
        "cmap": "RdBu_r",
        "norm": None,
        "unit": "s⁻¹",
    },
}


def render_overlay(da_2d: xr.DataArray, box: list[float], cmap: str, norm, out_path: Path) -> None:
    lon = da_2d["lon"].values
    lat = da_2d["lat"].values
    lon_min, lon_max, lat_min, lat_max = box

    merc_x = lon_to_merc_x(lon)
    merc_y = lat_to_merc_y(lat)
    x_min, x_max = lon_to_merc_x(np.array([lon_min, lon_max]))
    y_min, y_max = lat_to_merc_y(np.array([lat_min, lat_max]))

    width_m = x_max - x_min
    height_m = max(y_max - y_min, 1.0)
    px_per_m = 1600 / max(width_m, height_m)
    fig_w, fig_h = width_m * px_per_m / 100, height_m * px_per_m / 100

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.axis("off")
    ax.pcolormesh(merc_x, merc_y, da_2d.values, cmap=cmap, norm=norm, shading="auto")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, transparent=True)
    plt.close(fig)


def round_sig(x: float, sig: int = 6) -> float:
    """Round to `sig` significant figures rather than a fixed decimal count
    -- mfc850 values are ~1e-7 and divergence200 ~1e-6, so a fixed
    round(x, 4) silently zeroes them out."""
    x = float(x)
    if x == 0 or not np.isfinite(x):
        return 0.0
    from math import floor, log10
    digits = sig - int(floor(log10(abs(x)))) - 1
    return round(x, digits)


def to_json_value(v: float) -> float | None:
    return None if not np.isfinite(v) else round_sig(v)


def main():
    print("==================================================")
    print("Generate atmospheric circulation leaflet overlays + grid JSON")
    print("==================================================")

    index = {}
    written = 0

    for var_key, cfg in VARIABLES.items():
        box = clamp_box_lat(cfg["box"])

        for period in PERIODS:
            da = cfg["loader"](period)
            if da is None:
                print(f"Skipping {var_key}/{period}: source file missing")
                continue

            da = s06.subset_box(da, box).squeeze(drop=True)
            if "lat" in da.dims and "lon" in da.dims:
                da = da.transpose("lat", "lon")

            unit = cfg["unit"]

            if cfg["norm"] is not None:
                norm = cfg["norm"](da)
                vmin, vmax = norm.vmin, norm.vmax
            else:
                vmin, vmax = s06.get_symmetric_limits(da)
                norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)

            out_path = OUT_DIR / var_key / f"{period}.png"
            render_overlay(da, box, cfg["cmap"], norm, out_path)

            lon_min, lon_max, lat_min, lat_max = box
            index[f"{var_key}/{period}"] = {
                "file": f"{var_key}/{period}.png",
                "bounds": [[lat_min, lon_min], [lat_max, lon_max]],
                "vmin": round_sig(vmin),
                "vmax": round_sig(vmax),
                "unit": unit,
            }

            # Grid JSON for exact-value hover tooltips -- thinned since the
            # underlying ERA5/NMME grids are far finer than needed for a
            # tooltip lookup.
            da_thin = da.isel(lat=slice(None, None, 2), lon=slice(None, None, 2))
            lats = [round(float(v), 3) for v in da_thin["lat"].values]
            lons = [round(float(v), 3) for v in da_thin["lon"].values]
            values = [[to_json_value(v) for v in row] for row in da_thin.values]

            grid_path = GRID_OUT_DIR / var_key / f"{period}.json"
            grid_path.parent.mkdir(parents=True, exist_ok=True)
            grid_path.write_text(
                json.dumps({"lats": lats, "lons": lons, "values": values, "unit": unit}, separators=(",", ":")),
                encoding="utf-8",
            )

            written += 1
            print(f"Saved: {out_path}")

    index_path = OUT_DIR / "overlay_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(f"\nWrote {written} overlay images + grid files, and {index_path}")


if __name__ == "__main__":
    main()
