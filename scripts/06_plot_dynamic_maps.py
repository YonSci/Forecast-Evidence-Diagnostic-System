"""
06_plot_dynamic_maps.py

Purpose
-------
Plot dynamic diagnostic maps for Ethiopia Kiremt/JJAS 2026 rainfall analysis.

Inputs expected from previous scripts:
-------------------------------------
01_download_nmme_fields.py
02_download_era5_fields.py
03_inspect_and_organize_fields.py
04_compute_anomalies.py
05_compute_dynamic_diagnostics.py

Main plot groups:
-----------------
1. NMME precipitation anomaly maps
2. NMME tmpsfc / SST-proxy anomaly maps
3. NMME z200 anomaly maps
4. ERA5 u200 / TEJ climatology maps
5. ERA5 850 hPa moisture flux + moisture-flux convergence maps
6. ERA5 omega500 / omega700 climatology maps
7. ERA5 divergence200 climatology maps
8. Summary charts for TEJ and SST driver indices

Run from project root:
    python scripts\\06_plot_dynamic_maps.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle


# ==========================================================
# OPTIONAL CARTOPY
# ==========================================================

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
except Exception:
    HAS_CARTOPY = False
    print("Cartopy is not available. Maps will be plotted without coastlines/borders.")


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import (
        TABLE_DIR,
        NETCDF_OUT_DIR,
        MAP_DIR,
    )
except Exception:
    TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
    NETCDF_OUT_DIR = PROJECT_ROOT / "outputs" / "netcdf"
    MAP_DIR = PROJECT_ROOT / "outputs" / "maps"


# ==========================================================
# INPUT DIRECTORIES
# ==========================================================

NMME_ANOM_DIR = NETCDF_OUT_DIR / "nmme_anomalies"
ERA5_CLIM_DIR = NETCDF_OUT_DIR / "era5_climatology"
DIAG_DIR = NETCDF_OUT_DIR / "dynamic_diagnostics"


# ==========================================================
# OUTPUT DIRECTORIES
# ==========================================================

DYNAMIC_MAP_DIR = MAP_DIR / "dynamic_diagnostics"

PLOT_DIRS = {
    "precip": DYNAMIC_MAP_DIR / "01_nmme_precipitation_anomaly",
    "sst": DYNAMIC_MAP_DIR / "02_nmme_tmpsfc_sst_proxy",
    "z200": DYNAMIC_MAP_DIR / "03_nmme_z200_anomaly",
    "tej": DYNAMIC_MAP_DIR / "04_era5_u200_tej_climatology",
    "moisture": DYNAMIC_MAP_DIR / "05_era5_850hpa_moisture_flux",
    "omega": DYNAMIC_MAP_DIR / "06_era5_omega_vertical_motion",
    "divergence": DYNAMIC_MAP_DIR / "07_era5_200hpa_divergence",
    "charts": DYNAMIC_MAP_DIR / "08_summary_charts",
}

for folder in PLOT_DIRS.values():
    folder.mkdir(parents=True, exist_ok=True)


# ==========================================================
# USER SETTINGS
# ==========================================================

DPI = 300

MAKE_PRECIP_MAPS = True
MAKE_SST_MAPS = True
MAKE_Z200_MAPS = True
MAKE_TEJ_MAPS = True
MAKE_MOISTURE_MAPS = True
MAKE_OMEGA_MAPS = True
MAKE_DIVERGENCE_MAPS = True
MAKE_SUMMARY_CHARTS = True


# ==========================================================
# DOMAINS
# Format: [lon_min, lon_max, lat_min, lat_max]
# ==========================================================

DOMAINS = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "africa_indian": [-20, 130, -40, 40],
    "atlantic_congo_ethiopia": [-20, 55, -20, 25],
    "indian_ocean": [30, 120, -30, 30],
    "global_tropics": [-180, 180, -30, 30],
    "pacific_enso": [120, 290, -30, 30],
}

SST_BOXES = {
    "Niño3.4": [-170, -120, -5, 5],
    "IOD West": [50, 70, -10, 10],
    "IOD East": [90, 110, -10, 0],
}

PERIOD_LABELS = {
    "Jun_2026": "June 2026",
    "Jul_2026": "July 2026",
    "Aug_2026": "August 2026",
    "Sep_2026": "September 2026",
    "JJA_2026": "June-August 2026",
    "JJAS_2026": "June-September 2026",
    "June": "June",
    "July": "July",
    "August": "August",
    "September": "September",
    "JJA": "JJA",
    "JJAS": "JJAS",
}


# ==========================================================
# FILE LISTS
# ==========================================================

PRECIP_FILES = {
    "Jun_2026": NMME_ANOM_DIR / "NMME_prate_Jun_2026_total_anomaly_mm_month.nc",
    "Jul_2026": NMME_ANOM_DIR / "NMME_prate_Jul_2026_total_anomaly_mm_month.nc",
    "Aug_2026": NMME_ANOM_DIR / "NMME_prate_Aug_2026_total_anomaly_mm_month.nc",
    "Sep_2026": NMME_ANOM_DIR / "NMME_prate_Sep_2026_total_anomaly_mm_month.nc",
    "JJA_2026": NMME_ANOM_DIR / "NMME_prate_JJA_2026_total_anomaly_mm_season.nc",
    "JJAS_2026": NMME_ANOM_DIR / "NMME_prate_JJAS_2026_total_anomaly_mm_season.nc",
}

TMPSFC_FILES = {
    "Jun_2026": NMME_ANOM_DIR / "NMME_tmpsfc_Jun_2026_anomaly.nc",
    "Jul_2026": NMME_ANOM_DIR / "NMME_tmpsfc_Jul_2026_anomaly.nc",
    "Aug_2026": NMME_ANOM_DIR / "NMME_tmpsfc_Aug_2026_anomaly.nc",
    "Sep_2026": NMME_ANOM_DIR / "NMME_tmpsfc_Sep_2026_anomaly.nc",
    "JJA_2026": NMME_ANOM_DIR / "NMME_tmpsfc_JJA_2026_mean_anomaly.nc",
    "JJAS_2026": NMME_ANOM_DIR / "NMME_tmpsfc_JJAS_2026_mean_anomaly.nc",
}

Z200_NMME_FILES = {
    "Jun_2026": NMME_ANOM_DIR / "NMME_z200_Jun_2026_anomaly.nc",
    "Jul_2026": NMME_ANOM_DIR / "NMME_z200_Jul_2026_anomaly.nc",
    "Aug_2026": NMME_ANOM_DIR / "NMME_z200_Aug_2026_anomaly.nc",
    "Sep_2026": NMME_ANOM_DIR / "NMME_z200_Sep_2026_anomaly.nc",
    "JJA_2026": NMME_ANOM_DIR / "NMME_z200_JJA_2026_mean_anomaly.nc",
    "JJAS_2026": NMME_ANOM_DIR / "NMME_z200_JJAS_2026_mean_anomaly.nc",
}

ERA5_U200_MONTHLY = ERA5_CLIM_DIR / "ERA5_u200_monthly_climatology_1991_2020_JJAS.nc"
ERA5_U200_JJA = ERA5_CLIM_DIR / "ERA5_u200_JJA_climatology_1991_2020.nc"
ERA5_U200_JJAS = ERA5_CLIM_DIR / "ERA5_u200_JJAS_climatology_1991_2020.nc"

ERA5_OMEGA_FILES = {
    "omega500": {
        "monthly": DIAG_DIR / "ERA5_omega500_monthly_climatology_dynamic_1991_2020.nc",
        "JJA": DIAG_DIR / "ERA5_omega500_JJA_climatology_dynamic_1991_2020.nc",
        "JJAS": DIAG_DIR / "ERA5_omega500_JJAS_climatology_dynamic_1991_2020.nc",
    },
    "omega700": {
        "monthly": DIAG_DIR / "ERA5_omega700_monthly_climatology_dynamic_1991_2020.nc",
        "JJA": DIAG_DIR / "ERA5_omega700_JJA_climatology_dynamic_1991_2020.nc",
        "JJAS": DIAG_DIR / "ERA5_omega700_JJAS_climatology_dynamic_1991_2020.nc",
    },
}

ERA5_DIVERGENCE_FILES = {
    "monthly": DIAG_DIR / "ERA5_divergence200_monthly_climatology_dynamic_1991_2020.nc",
    "JJA": DIAG_DIR / "ERA5_divergence200_JJA_climatology_dynamic_1991_2020.nc",
    "JJAS": DIAG_DIR / "ERA5_divergence200_JJAS_climatology_dynamic_1991_2020.nc",
}

MOISTURE_FILES = {
    "monthly": DIAG_DIR / "ERA5_850hPa_moisture_flux_monthly_climatology_1991_2020.nc",
    "JJA": DIAG_DIR / "ERA5_850hPa_moisture_flux_JJA_climatology_1991_2020.nc",
    "JJAS": DIAG_DIR / "ERA5_850hPa_moisture_flux_JJAS_climatology_1991_2020.nc",
}

TEJ_TABLE = TABLE_DIR / "era5_tej_index_climatology.csv"
SST_DRIVER_TABLE = TABLE_DIR / "nmme_sst_driver_diagnostics_from_tmpsfc.csv"


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def open_dataarray(path: Path, decode_times: bool = True) -> xr.DataArray:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    try:
        ds = xr.open_dataset(path, decode_times=decode_times)
    except Exception:
        ds = xr.open_dataset(path, decode_times=False)

    ds = standardize_coordinate_names(ds)
    ds = standardize_longitude(ds)

    if len(ds.data_vars) == 0:
        raise ValueError(f"No data variables found in {path}")

    var_name = list(ds.data_vars)[0]
    da = ds[var_name]
    da.attrs["source_file"] = str(path)
    da.attrs["source_variable"] = var_name

    return da


def open_dataset(path: Path, decode_times: bool = True) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    try:
        ds = xr.open_dataset(path, decode_times=decode_times)
    except Exception:
        ds = xr.open_dataset(path, decode_times=False)

    ds = standardize_coordinate_names(ds)
    ds = standardize_longitude(ds)

    return ds


def standardize_coordinate_names(ds: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
    rename = {}

    names = list(ds.coords) + list(ds.dims)

    for name in names:
        lower = name.lower()

        if lower in ["latitude", "lat", "y"] and name != "lat":
            if "lat" not in ds.coords and "lat" not in ds.dims:
                rename[name] = "lat"

        if lower in ["longitude", "lon", "x"] and name != "lon":
            if "lon" not in ds.coords and "lon" not in ds.dims:
                rename[name] = "lon"

        if lower in ["valid_time", "time"] and name != "time":
            if "time" not in ds.coords and "time" not in ds.dims:
                rename[name] = "time"

    if rename:
        ds = ds.rename(rename)

    return ds


def standardize_longitude(ds: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
    if "lon" not in ds.coords:
        return ds

    lon = ds["lon"]

    if float(lon.max()) > 180:
        new_lon = ((lon + 180) % 360) - 180
        ds = ds.assign_coords(lon=new_lon)
        ds = ds.sortby("lon")

    return ds


def subset_box(da: xr.DataArray, box: list[float]) -> xr.DataArray:
    lon_min, lon_max, lat_min, lat_max = box

    da = standardize_longitude(da)

    if "lat" not in da.coords or "lon" not in da.coords:
        raise ValueError("DataArray must contain lat and lon coordinates.")

    lat_values = da["lat"].values

    if lat_values[0] < lat_values[-1]:
        lat_slice = slice(lat_min, lat_max)
    else:
        lat_slice = slice(lat_max, lat_min)

    return da.sel(lon=slice(lon_min, lon_max), lat=lat_slice)


def subset_dataset_box(ds: xr.Dataset, box: list[float]) -> xr.Dataset:
    lon_min, lon_max, lat_min, lat_max = box

    ds = standardize_longitude(ds)

    if "lat" not in ds.coords or "lon" not in ds.coords:
        raise ValueError("Dataset must contain lat and lon coordinates.")

    lat_values = ds["lat"].values

    if lat_values[0] < lat_values[-1]:
        lat_slice = slice(lat_min, lat_max)
    else:
        lat_slice = slice(lat_max, lat_min)

    return ds.sel(lon=slice(lon_min, lon_max), lat=lat_slice)


def get_symmetric_limits(da: xr.DataArray, percentile: float = 98.0, min_abs: float = 1e-12) -> tuple[float, float]:
    vals = da.values
    vals = vals[np.isfinite(vals)]

    if vals.size == 0:
        return -1.0, 1.0

    max_abs = float(np.nanpercentile(np.abs(vals), percentile))

    if not np.isfinite(max_abs) or max_abs < min_abs:
        max_abs = 1.0

    return -max_abs, max_abs


def get_positive_limits(da: xr.DataArray, percentile: float = 98.0) -> tuple[float, float]:
    vals = da.values
    vals = vals[np.isfinite(vals)]

    if vals.size == 0:
        return 0.0, 1.0

    vmax = float(np.nanpercentile(vals, percentile))

    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0

    return 0.0, vmax


def add_map_features(ax, draw_labels: bool = True):
    if not HAS_CARTOPY:
        return

    ax.coastlines(linewidth=0.9)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, linewidth=0.3, alpha=0.6)
    ax.add_feature(cfeature.RIVERS, linewidth=0.25, alpha=0.4)

    gl = ax.gridlines(
        draw_labels=draw_labels,
        linewidth=0.25,
        linestyle="--",
        alpha=0.45,
    )

    if draw_labels:
        gl.top_labels = False
        gl.right_labels = False


def add_sst_index_boxes(ax):
    for label, box in SST_BOXES.items():
        lon_min, lon_max, lat_min, lat_max = box

        if HAS_CARTOPY:
            rect = Rectangle(
                (lon_min, lat_min),
                lon_max - lon_min,
                lat_max - lat_min,
                fill=False,
                linewidth=1.5,
                edgecolor="black",
                transform=ccrs.PlateCarree(),
            )
            ax.add_patch(rect)

            ax.text(
                lon_min,
                lat_max + 1.0,
                label,
                fontsize=8,
                fontweight="bold",
                transform=ccrs.PlateCarree(),
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.65),
            )
        else:
            rect = Rectangle(
                (lon_min, lat_min),
                lon_max - lon_min,
                lat_max - lat_min,
                fill=False,
                linewidth=1.5,
                edgecolor="black",
            )
            ax.add_patch(rect)
            ax.text(lon_min, lat_max + 1.0, label, fontsize=8, fontweight="bold")


def make_safe_filename(text: str) -> str:
    return (
        text.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
        .replace("–", "-")
        .replace("—", "-")
    )


def select_month(da: xr.DataArray, month: int) -> xr.DataArray:
    if "month" not in da.coords and "month" not in da.dims:
        raise ValueError("Monthly climatology DataArray does not contain 'month' coordinate.")

    return da.sel(month=month).squeeze(drop=True)


def select_month_ds(ds: xr.Dataset, month: int) -> xr.Dataset:
    if "month" not in ds.coords and "month" not in ds.dims:
        raise ValueError("Monthly climatology Dataset does not contain 'month' coordinate.")

    return ds.sel(month=month).squeeze(drop=True)


# ==========================================================
# GENERIC PLOTTING FUNCTIONS
# ==========================================================

def plot_scalar_map(
    da: xr.DataArray,
    title: str,
    out_file: Path,
    domain_box: list[float],
    cmap: str = "RdBu_r",
    symmetric: bool = True,
    vmin: float | None = None,
    vmax: float | None = None,
    cbar_label: str | None = None,
    add_sst_boxes: bool = False,
    figsize: tuple[float, float] = (11.5, 7.5),
):
    da_plot = subset_box(da, domain_box).squeeze(drop=True)

    if "lat" in da_plot.dims and "lon" in da_plot.dims:
        da_plot = da_plot.transpose("lat", "lon")

    if vmin is None or vmax is None:
        if symmetric:
            vmin, vmax = get_symmetric_limits(da_plot)
        else:
            vmin, vmax = get_positive_limits(da_plot)

    if symmetric:
        norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
    else:
        norm = None

    if cbar_label is None:
        units = da_plot.attrs.get("units", "")
        cbar_label = units if units else "value"

    if HAS_CARTOPY:
        fig = plt.figure(figsize=figsize)
        ax = plt.axes(projection=ccrs.PlateCarree())

        ax.set_extent(domain_box, crs=ccrs.PlateCarree())

        mesh = ax.pcolormesh(
            da_plot["lon"],
            da_plot["lat"],
            da_plot.values,
            cmap=cmap,
            norm=norm,
            vmin=None if norm else vmin,
            vmax=None if norm else vmax,
            shading="auto",
            transform=ccrs.PlateCarree(),
        )

        add_map_features(ax, draw_labels=True)

        if add_sst_boxes:
            add_sst_index_boxes(ax)

    else:
        fig, ax = plt.subplots(figsize=figsize)

        mesh = ax.pcolormesh(
            da_plot["lon"],
            da_plot["lat"],
            da_plot.values,
            cmap=cmap,
            norm=norm,
            vmin=None if norm else vmin,
            vmax=None if norm else vmax,
            shading="auto",
        )

        ax.set_xlim(domain_box[0], domain_box[1])
        ax.set_ylim(domain_box[2], domain_box[3])
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

        if add_sst_boxes:
            add_sst_index_boxes(ax)

    cbar = plt.colorbar(mesh, ax=ax, orientation="vertical", shrink=0.82, pad=0.035)
    cbar.set_label(cbar_label, fontsize=11)
    cbar.ax.tick_params(labelsize=9)

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
    plt.close()

    print(f"Saved map: {out_file}")


def plot_moisture_flux_map(
    ds: xr.Dataset,
    title: str,
    out_file: Path,
    domain_box: list[float],
    shade_var: str = "mfc850",
    qu_var: str = "qu850",
    qv_var: str = "qv850",
):
    ds_plot = subset_dataset_box(ds, domain_box).squeeze(drop=True)

    shade = ds_plot[shade_var]
    qu = ds_plot[qu_var]
    qv = ds_plot[qv_var]

    if "lat" in shade.dims and "lon" in shade.dims:
        shade = shade.transpose("lat", "lon")
        qu = qu.transpose("lat", "lon")
        qv = qv.transpose("lat", "lon")

    vmin, vmax = get_symmetric_limits(shade, percentile=98)

    lon = shade["lon"].values
    lat = shade["lat"].values

    lon2d, lat2d = np.meshgrid(lon, lat)

    nlat = len(lat)
    nlon = len(lon)

    stride_lat = max(1, nlat // 24)
    stride_lon = max(1, nlon // 32)

    sl = (slice(None, None, stride_lat), slice(None, None, stride_lon))

    if HAS_CARTOPY:
        fig = plt.figure(figsize=(12, 7.8))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent(domain_box, crs=ccrs.PlateCarree())

        mesh = ax.pcolormesh(
            shade["lon"],
            shade["lat"],
            shade.values,
            cmap="BrBG",
            norm=TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax),
            shading="auto",
            transform=ccrs.PlateCarree(),
        )

        ax.quiver(
            lon2d[sl],
            lat2d[sl],
            qu.values[sl],
            qv.values[sl],
            transform=ccrs.PlateCarree(),
            scale=1.2,
            width=0.0022,
            alpha=0.85,
        )

        add_map_features(ax, draw_labels=True)

    else:
        fig, ax = plt.subplots(figsize=(12, 7.8))

        mesh = ax.pcolormesh(
            shade["lon"],
            shade["lat"],
            shade.values,
            cmap="BrBG",
            norm=TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax),
            shading="auto",
        )

        ax.quiver(
            lon2d[sl],
            lat2d[sl],
            qu.values[sl],
            qv.values[sl],
            scale=1.2,
            width=0.0022,
            alpha=0.85,
        )

        ax.set_xlim(domain_box[0], domain_box[1])
        ax.set_ylim(domain_box[2], domain_box[3])
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    cbar = plt.colorbar(mesh, ax=ax, orientation="vertical", shrink=0.82, pad=0.035)
    cbar.set_label(
        "850 hPa moisture-flux convergence proxy\npositive = convergence, negative = divergence",
        fontsize=10,
    )
    cbar.ax.tick_params(labelsize=9)

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
    plt.close()

    print(f"Saved moisture flux map: {out_file}")


# ==========================================================
# PLOT GROUPS
# ==========================================================

def plot_nmme_precipitation_maps():
    print("\n==================================================")
    print("Plotting NMME precipitation anomaly maps")
    print("==================================================")

    domains_to_plot = {
        "ethiopia": DOMAINS["ethiopia"],
        "greater_horn": DOMAINS["greater_horn"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    for period, path in PRECIP_FILES.items():
        if not path.exists():
            print(f"Skipping missing precipitation file: {path}")
            continue

        da = open_dataarray(path, decode_times=False)
        units = da.attrs.get("units", "")

        for domain_name, box in domains_to_plot.items():
            title = (
                f"NMME precipitation anomaly\n"
                f"{PERIOD_LABELS.get(period, period)} | May 2026 initialization"
            )

            out_file = (
                PLOT_DIRS["precip"]
                / domain_name
                / f"NMME_precipitation_anomaly_{period}_{domain_name}.png"
            )

            plot_scalar_map(
                da=da,
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="BrBG",
                symmetric=True,
                cbar_label=f"Precipitation anomaly ({units})",
                figsize=(12, 7.6),
            )


def plot_nmme_tmpsfc_sst_maps():
    print("\n==================================================")
    print("Plotting NMME tmpsfc / SST-proxy anomaly maps")
    print("==================================================")

    domains_to_plot = {
        "global_tropics": DOMAINS["global_tropics"],
        "indian_ocean": DOMAINS["indian_ocean"],
        "pacific_enso": DOMAINS["pacific_enso"],
    }

    for period, path in TMPSFC_FILES.items():
        if not path.exists():
            print(f"Skipping missing tmpsfc file: {path}")
            continue

        da = open_dataarray(path, decode_times=False)
        units = da.attrs.get("units", "K")

        for domain_name, box in domains_to_plot.items():
            add_boxes = domain_name in ["global_tropics", "indian_ocean", "pacific_enso"]

            title = (
                f"NMME surface temperature / SST-proxy anomaly\n"
                f"{PERIOD_LABELS.get(period, period)} | May 2026 initialization"
            )

            out_file = (
                PLOT_DIRS["sst"]
                / domain_name
                / f"NMME_tmpsfc_SST_proxy_anomaly_{period}_{domain_name}.png"
            )

            plot_scalar_map(
                da=da,
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="RdBu_r",
                symmetric=True,
                vmin=-3.0,
                vmax=3.0,
                cbar_label=f"Temperature anomaly ({units})",
                add_sst_boxes=add_boxes,
                figsize=(13, 6.8) if domain_name == "global_tropics" else (11.5, 7.5),
            )


def plot_nmme_z200_maps():
    print("\n==================================================")
    print("Plotting NMME z200 anomaly maps")
    print("==================================================")

    domains_to_plot = {
        "africa_indian": DOMAINS["africa_indian"],
        "greater_horn": DOMAINS["greater_horn"],
        "north_africa_arabia": [10, 70, 0, 40],
    }

    for period, path in Z200_NMME_FILES.items():
        if not path.exists():
            print(f"Skipping missing z200 file: {path}")
            continue

        da = open_dataarray(path, decode_times=False)
        units = da.attrs.get("units", "")

        for domain_name, box in domains_to_plot.items():
            title = (
                f"NMME 200 hPa geopotential height anomaly\n"
                f"{PERIOD_LABELS.get(period, period)} | May 2026 initialization"
            )

            out_file = (
                PLOT_DIRS["z200"]
                / domain_name
                / f"NMME_z200_anomaly_{period}_{domain_name}.png"
            )

            plot_scalar_map(
                da=da,
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="RdBu_r",
                symmetric=True,
                cbar_label=f"z200 anomaly ({units})",
                figsize=(12, 7.5),
            )


def plot_era5_u200_tej_maps():
    print("\n==================================================")
    print("Plotting ERA5 u200 / TEJ climatology maps")
    print("==================================================")

    domain_name = "africa_indian"
    box = DOMAINS[domain_name]

    # Monthly u200 climatology
    if ERA5_U200_MONTHLY.exists():
        da_monthly = open_dataarray(ERA5_U200_MONTHLY, decode_times=True)
        units = da_monthly.attrs.get("units", "m s-1")

        for month, month_name in {
            6: "June",
            7: "July",
            8: "August",
            9: "September",
        }.items():
            da = select_month(da_monthly, month)

            title = (
                f"ERA5 200 hPa zonal wind climatology / TEJ\n"
                f"{month_name} mean, 1991-2020 | negative u = easterly jet"
            )

            out_file = (
                PLOT_DIRS["tej"]
                / f"ERA5_u200_TEJ_climatology_{month_name}_{domain_name}.png"
            )

            plot_scalar_map(
                da=da,
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="RdBu_r",
                symmetric=True,
                vmin=-35,
                vmax=35,
                cbar_label=f"u200 ({units})",
                figsize=(12, 7.4),
            )

    # Seasonal u200 climatology
    seasonal_files = {
        "JJA": ERA5_U200_JJA,
        "JJAS": ERA5_U200_JJAS,
    }

    for season, path in seasonal_files.items():
        if not path.exists():
            print(f"Skipping missing u200 seasonal file: {path}")
            continue

        da = open_dataarray(path, decode_times=True)
        units = da.attrs.get("units", "m s-1")

        title = (
            f"ERA5 200 hPa zonal wind climatology / TEJ\n"
            f"{season} mean, 1991-2020 | negative u = easterly jet"
        )

        out_file = PLOT_DIRS["tej"] / f"ERA5_u200_TEJ_climatology_{season}_{domain_name}.png"

        plot_scalar_map(
            da=da,
            title=title,
            out_file=out_file,
            domain_box=box,
            cmap="RdBu_r",
            symmetric=True,
            vmin=-35,
            vmax=35,
            cbar_label=f"u200 ({units})",
            figsize=(12, 7.4),
        )


def plot_era5_moisture_flux_maps():
    print("\n==================================================")
    print("Plotting ERA5 850 hPa moisture flux maps")
    print("==================================================")

    domains_to_plot = {
        "greater_horn": DOMAINS["greater_horn"],
        "atlantic_congo_ethiopia": DOMAINS["atlantic_congo_ethiopia"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    # Monthly maps
    monthly_path = MOISTURE_FILES["monthly"]

    if monthly_path.exists():
        ds_monthly = open_dataset(monthly_path, decode_times=True)

        for month, month_name in {
            6: "June",
            7: "July",
            8: "August",
            9: "September",
        }.items():
            ds = select_month_ds(ds_monthly, month)

            for domain_name, box in domains_to_plot.items():
                title = (
                    f"ERA5 850 hPa moisture flux and convergence climatology\n"
                    f"{month_name} mean, 1991-2020"
                )

                out_file = (
                    PLOT_DIRS["moisture"]
                    / domain_name
                    / f"ERA5_850hPa_moisture_flux_MFC_{month_name}_{domain_name}.png"
                )

                plot_moisture_flux_map(
                    ds=ds,
                    title=title,
                    out_file=out_file,
                    domain_box=box,
                )

    # Seasonal maps
    for season in ["JJA", "JJAS"]:
        path = MOISTURE_FILES[season]

        if not path.exists():
            print(f"Skipping missing moisture flux seasonal file: {path}")
            continue

        ds = open_dataset(path, decode_times=True)

        for domain_name, box in domains_to_plot.items():
            title = (
                f"ERA5 850 hPa moisture flux and convergence climatology\n"
                f"{season} mean, 1991-2020"
            )

            out_file = (
                PLOT_DIRS["moisture"]
                / domain_name
                / f"ERA5_850hPa_moisture_flux_MFC_{season}_{domain_name}.png"
            )

            plot_moisture_flux_map(
                ds=ds,
                title=title,
                out_file=out_file,
                domain_box=box,
            )


def plot_era5_omega_maps():
    print("\n==================================================")
    print("Plotting ERA5 omega vertical motion maps")
    print("==================================================")

    domains_to_plot = {
        "greater_horn": DOMAINS["greater_horn"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    for field_name, file_group in ERA5_OMEGA_FILES.items():
        # Monthly
        monthly_path = file_group["monthly"]

        if monthly_path.exists():
            da_monthly = open_dataarray(monthly_path, decode_times=True)
            units = da_monthly.attrs.get("units", "Pa s-1")

            for month, month_name in {
                6: "June",
                7: "July",
                8: "August",
                9: "September",
            }.items():
                da = select_month(da_monthly, month)

                for domain_name, box in domains_to_plot.items():
                    title = (
                        f"ERA5 {field_name} climatology\n"
                        f"{month_name} mean, 1991-2020 | positive = subsidence"
                    )

                    out_file = (
                        PLOT_DIRS["omega"]
                        / field_name
                        / domain_name
                        / f"ERA5_{field_name}_{month_name}_{domain_name}.png"
                    )

                    plot_scalar_map(
                        da=da,
                        title=title,
                        out_file=out_file,
                        domain_box=box,
                        cmap="RdBu_r",
                        symmetric=True,
                        cbar_label=f"{field_name} ({units})",
                        figsize=(12, 7.4),
                    )

        # Seasonal
        for season in ["JJA", "JJAS"]:
            path = file_group[season]

            if not path.exists():
                print(f"Skipping missing omega seasonal file: {path}")
                continue

            da = open_dataarray(path, decode_times=True)
            units = da.attrs.get("units", "Pa s-1")

            for domain_name, box in domains_to_plot.items():
                title = (
                    f"ERA5 {field_name} climatology\n"
                    f"{season} mean, 1991-2020 | positive = subsidence"
                )

                out_file = (
                    PLOT_DIRS["omega"]
                    / field_name
                    / domain_name
                    / f"ERA5_{field_name}_{season}_{domain_name}.png"
                )

                plot_scalar_map(
                    da=da,
                    title=title,
                    out_file=out_file,
                    domain_box=box,
                    cmap="RdBu_r",
                    symmetric=True,
                    cbar_label=f"{field_name} ({units})",
                    figsize=(12, 7.4),
                )


def plot_era5_divergence_maps():
    print("\n==================================================")
    print("Plotting ERA5 200 hPa divergence maps")
    print("==================================================")

    domains_to_plot = {
        "greater_horn": DOMAINS["greater_horn"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    monthly_path = ERA5_DIVERGENCE_FILES["monthly"]

    if monthly_path.exists():
        da_monthly = open_dataarray(monthly_path, decode_times=True)
        units = da_monthly.attrs.get("units", "s-1")

        for month, month_name in {
            6: "June",
            7: "July",
            8: "August",
            9: "September",
        }.items():
            da = select_month(da_monthly, month)

            for domain_name, box in domains_to_plot.items():
                title = (
                    f"ERA5 200 hPa divergence climatology\n"
                    f"{month_name} mean, 1991-2020 | positive = upper-level outflow"
                )

                out_file = (
                    PLOT_DIRS["divergence"]
                    / domain_name
                    / f"ERA5_divergence200_{month_name}_{domain_name}.png"
                )

                plot_scalar_map(
                    da=da,
                    title=title,
                    out_file=out_file,
                    domain_box=box,
                    cmap="RdBu_r",
                    symmetric=True,
                    cbar_label=f"200 hPa divergence ({units})",
                    figsize=(12, 7.4),
                )

    for season in ["JJA", "JJAS"]:
        path = ERA5_DIVERGENCE_FILES[season]

        if not path.exists():
            print(f"Skipping missing divergence seasonal file: {path}")
            continue

        da = open_dataarray(path, decode_times=True)
        units = da.attrs.get("units", "s-1")

        for domain_name, box in domains_to_plot.items():
            title = (
                f"ERA5 200 hPa divergence climatology\n"
                f"{season} mean, 1991-2020 | positive = upper-level outflow"
            )

            out_file = (
                PLOT_DIRS["divergence"]
                / domain_name
                / f"ERA5_divergence200_{season}_{domain_name}.png"
            )

            plot_scalar_map(
                da=da,
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="RdBu_r",
                symmetric=True,
                cbar_label=f"200 hPa divergence ({units})",
                figsize=(12, 7.4),
            )


def plot_summary_charts():
    print("\n==================================================")
    print("Plotting summary diagnostic charts")
    print("==================================================")

    # ------------------------------------------------------
    # TEJ chart
    # ------------------------------------------------------
    if TEJ_TABLE.exists():
        df = pd.read_csv(TEJ_TABLE)

        df_plot = df[
            df["period"].isin(["June", "July", "August", "September", "JJA", "JJAS"])
        ].copy()

        if not df_plot.empty:
            fig, ax = plt.subplots(figsize=(9, 5.2))

            ax.bar(df_plot["period"], df_plot["value"])

            ax.set_title(
                "ERA5 Tropical Easterly Jet strength climatology\n1991-2020",
                fontsize=14,
                fontweight="bold",
            )
            ax.set_ylabel("TEJ strength index: -mean u200")
            ax.set_xlabel("Period")
            ax.grid(axis="y", linestyle="--", alpha=0.4)

            out_file = PLOT_DIRS["charts"] / "ERA5_TEJ_strength_climatology_chart.png"
            plt.tight_layout()
            plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
            plt.close()

            print(f"Saved chart: {out_file}")

    else:
        print(f"TEJ table not found: {TEJ_TABLE}")

    # ------------------------------------------------------
    # SST driver chart
    # ------------------------------------------------------
    if SST_DRIVER_TABLE.exists():
        df = pd.read_csv(SST_DRIVER_TABLE)

        df_plot = df[
            df["period"].isin(["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"])
        ].copy()

        if not df_plot.empty:
            x = np.arange(len(df_plot))
            width = 0.28

            fig, ax = plt.subplots(figsize=(10.5, 5.4))

            ax.bar(
                x - width,
                df_plot["nino34_anomaly"],
                width,
                label="Niño3.4 proxy",
            )
            ax.bar(
                x,
                df_plot["iod_west_anomaly"],
                width,
                label="IOD west",
            )
            ax.bar(
                x + width,
                df_plot["iod_east_anomaly"],
                width,
                label="IOD east",
            )

            ax.axhline(0, linewidth=0.9)
            ax.axhline(0.5, linestyle="--", linewidth=0.8, alpha=0.6)
            ax.axhline(-0.5, linestyle="--", linewidth=0.8, alpha=0.6)

            ax.set_xticks(x)
            ax.set_xticklabels(df_plot["period"])
            ax.set_ylabel("Temperature anomaly proxy")
            ax.set_title(
                "NMME tmpsfc ocean-driver anomaly proxies\nMay 2026 initialization",
                fontsize=14,
                fontweight="bold",
            )
            ax.legend()
            ax.grid(axis="y", linestyle="--", alpha=0.35)

            out_file = PLOT_DIRS["charts"] / "NMME_tmpsfc_ENSO_IOD_proxy_chart.png"
            plt.tight_layout()
            plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
            plt.close()

            print(f"Saved chart: {out_file}")

            # DMI chart
            fig, ax = plt.subplots(figsize=(9, 5.2))

            ax.bar(df_plot["period"], df_plot["dmi_proxy"])
            ax.axhline(0, linewidth=0.9)
            ax.axhline(0.4, linestyle="--", linewidth=0.8, alpha=0.6)
            ax.axhline(-0.4, linestyle="--", linewidth=0.8, alpha=0.6)

            ax.set_title(
                "Approximate DMI / IOD proxy from NMME tmpsfc anomaly",
                fontsize=14,
                fontweight="bold",
            )
            ax.set_ylabel("DMI proxy: IOD west - IOD east")
            ax.set_xlabel("Period")
            ax.grid(axis="y", linestyle="--", alpha=0.35)

            out_file = PLOT_DIRS["charts"] / "NMME_tmpsfc_DMI_proxy_chart.png"
            plt.tight_layout()
            plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
            plt.close()

            print(f"Saved chart: {out_file}")

    else:
        print(f"SST driver table not found: {SST_DRIVER_TABLE}")


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("Plot dynamic diagnostic maps")
    print("==================================================")
    print(f"Project root:       {PROJECT_ROOT}")
    print(f"NMME anomaly dir:   {NMME_ANOM_DIR}")
    print(f"ERA5 climatology:   {ERA5_CLIM_DIR}")
    print(f"Dynamic diag dir:   {DIAG_DIR}")
    print(f"Output map dir:     {DYNAMIC_MAP_DIR}")

    if MAKE_PRECIP_MAPS:
        plot_nmme_precipitation_maps()

    if MAKE_SST_MAPS:
        plot_nmme_tmpsfc_sst_maps()

    if MAKE_Z200_MAPS:
        plot_nmme_z200_maps()

    if MAKE_TEJ_MAPS:
        plot_era5_u200_tej_maps()

    if MAKE_MOISTURE_MAPS:
        plot_era5_moisture_flux_maps()

    if MAKE_OMEGA_MAPS:
        plot_era5_omega_maps()

    if MAKE_DIVERGENCE_MAPS:
        plot_era5_divergence_maps()

    if MAKE_SUMMARY_CHARTS:
        plot_summary_charts()

    print("\n==================================================")
    print("DYNAMIC MAP PLOTTING FINISHED")
    print("==================================================")

    print("\nMain output folder:")
    print(DYNAMIC_MAP_DIR)

    print("\nKey folders:")
    for key, folder in PLOT_DIRS.items():
        print(f" - {key}: {folder}")

    print("\nRecommended next script:")
    print("    python scripts\\07_make_evidence_matrix.py")


if __name__ == "__main__":
    main()