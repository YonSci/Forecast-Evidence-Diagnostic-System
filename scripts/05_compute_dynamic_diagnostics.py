"""
05_compute_dynamic_diagnostics.py

Purpose
-------
Compute dynamic diagnostic indicators for Ethiopia Kiremt/JJAS 2026 rainfall
interpretation.

This script uses:

1. NMME forecast anomaly outputs from:
   outputs/netcdf/nmme_anomalies/

2. ERA5 organized climatological fields from:
   data/era5/organized/

3. ERA5 climatology outputs from:
   outputs/netcdf/era5_climatology/

Main diagnostics:
-----------------
- TEJ index from 200 hPa zonal wind
- 850 hPa moisture flux: q850*u850 and q850*v850
- 850 hPa moisture-flux convergence
- Omega/subsidence diagnostics
- 200 hPa divergence diagnostics
- SST indices from NMME tmpsfc anomaly:
  Niño3.4 proxy, western Indian Ocean, eastern Indian Ocean, DMI proxy
- NMME rainfall anomaly area means
- NMME z200 anomaly area means

Run from project root:
    python scripts\\05_compute_dynamic_diagnostics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import (
        ERA5_DIR,
        NMME_DIR,
        TABLE_DIR,
        NETCDF_OUT_DIR,
    )
except Exception:
    ERA5_DIR = PROJECT_ROOT / "data" / "era5"
    NMME_DIR = PROJECT_ROOT / "data" / "nmme"
    TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
    NETCDF_OUT_DIR = PROJECT_ROOT / "outputs" / "netcdf"


# ==========================================================
# INPUT DIRECTORIES
# ==========================================================

ERA5_ORG_DIR = ERA5_DIR / "organized"
NMME_ANOM_DIR = NETCDF_OUT_DIR / "nmme_anomalies"
ERA5_CLIM_DIR = NETCDF_OUT_DIR / "era5_climatology"


# ==========================================================
# OUTPUT DIRECTORIES
# ==========================================================

DIAG_OUT_DIR = NETCDF_OUT_DIR / "dynamic_diagnostics"
DIAG_TABLE_DIR = TABLE_DIR

DIAG_OUT_DIR.mkdir(parents=True, exist_ok=True)
DIAG_TABLE_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# ERA5 ORGANIZED INPUT FILES
# ==========================================================

ERA5_FILES = {
    "u200": ERA5_ORG_DIR / "era5_u200_1991_2020_JJAS.nc",
    "v200": ERA5_ORG_DIR / "era5_v200_1991_2020_JJAS.nc",
    "u850": ERA5_ORG_DIR / "era5_u850_1991_2020_JJAS.nc",
    "v850": ERA5_ORG_DIR / "era5_v850_1991_2020_JJAS.nc",
    "q850": ERA5_ORG_DIR / "era5_q850_1991_2020_JJAS.nc",
    "omega500": ERA5_ORG_DIR / "era5_omega500_1991_2020_JJAS.nc",
    "omega700": ERA5_ORG_DIR / "era5_omega700_1991_2020_JJAS.nc",
    "z200": ERA5_ORG_DIR / "era5_z200_1991_2020_JJAS.nc",
    "z500": ERA5_ORG_DIR / "era5_z500_1991_2020_JJAS.nc",
    "divergence200": ERA5_ORG_DIR / "era5_divergence200_1991_2020_JJAS.nc",
    "sst": ERA5_ORG_DIR / "era5_sst_1991_2020_JJAS.nc",
}


# ==========================================================
# NMME FORECAST ANOMALY FILES
# ==========================================================

NMME_FILES = {
    "prate_Jun_total": NMME_ANOM_DIR / "NMME_prate_Jun_2026_total_anomaly_mm_month.nc",
    "prate_Jul_total": NMME_ANOM_DIR / "NMME_prate_Jul_2026_total_anomaly_mm_month.nc",
    "prate_Aug_total": NMME_ANOM_DIR / "NMME_prate_Aug_2026_total_anomaly_mm_month.nc",
    "prate_Sep_total": NMME_ANOM_DIR / "NMME_prate_Sep_2026_total_anomaly_mm_month.nc",
    "prate_JJA_total": NMME_ANOM_DIR / "NMME_prate_JJA_2026_total_anomaly_mm_season.nc",
    "prate_JJAS_total": NMME_ANOM_DIR / "NMME_prate_JJAS_2026_total_anomaly_mm_season.nc",

    "tmpsfc_Jun": NMME_ANOM_DIR / "NMME_tmpsfc_Jun_2026_anomaly.nc",
    "tmpsfc_Jul": NMME_ANOM_DIR / "NMME_tmpsfc_Jul_2026_anomaly.nc",
    "tmpsfc_Aug": NMME_ANOM_DIR / "NMME_tmpsfc_Aug_2026_anomaly.nc",
    "tmpsfc_Sep": NMME_ANOM_DIR / "NMME_tmpsfc_Sep_2026_anomaly.nc",
    "tmpsfc_JJA": NMME_ANOM_DIR / "NMME_tmpsfc_JJA_2026_mean_anomaly.nc",
    "tmpsfc_JJAS": NMME_ANOM_DIR / "NMME_tmpsfc_JJAS_2026_mean_anomaly.nc",

    "z200_Jun": NMME_ANOM_DIR / "NMME_z200_Jun_2026_anomaly.nc",
    "z200_Jul": NMME_ANOM_DIR / "NMME_z200_Jul_2026_anomaly.nc",
    "z200_Aug": NMME_ANOM_DIR / "NMME_z200_Aug_2026_anomaly.nc",
    "z200_Sep": NMME_ANOM_DIR / "NMME_z200_Sep_2026_anomaly.nc",
    "z200_JJA": NMME_ANOM_DIR / "NMME_z200_JJA_2026_mean_anomaly.nc",
    "z200_JJAS": NMME_ANOM_DIR / "NMME_z200_JJAS_2026_mean_anomaly.nc",
}


# ==========================================================
# DOMAINS
# Format: [lon_min, lon_max, lat_min, lat_max]
# ==========================================================

DOMAINS = {
    "ethiopia": [32, 48, 3, 15],
    "ethiopia_highlands_broad": [34, 42, 6, 14],
    "north_ethiopia": [35, 42, 10, 15],
    "central_ethiopia": [36, 41, 7, 11],
    "west_ethiopia": [33, 37.5, 6, 13],
    "east_ethiopia": [40, 48, 5, 12],
    "greater_horn": [20, 55, -15, 25],
    "east_africa": [20, 55, -15, 20],
    "atlantic_congo_ethiopia": [-20, 50, -20, 20],
    "congo_moisture_corridor": [15, 38, -5, 12],
    "western_moisture_entry": [25, 36, 2, 12],
    "western_indian_ocean": [40, 70, -15, 15],
    "arabia_red_sea": [35, 60, 10, 30],
    "north_africa_arabia": [10, 60, 10, 35],
    "tej_core": [20, 100, 5, 20],
    "somali_jet_box": [40, 55, -10, 15],
    "turkana_corridor": [35, 40, -5, 5],
}

SST_BOXES = {
    "nino34": [-170, -120, -5, 5],
    "iod_west": [50, 70, -10, 10],
    "iod_east": [90, 110, -10, 0],
    "western_indian_ocean": [40, 70, -15, 15],
    "eastern_indian_ocean": [90, 115, -15, 5],
}


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
        raise ValueError(f"No data variable found in {path}")

    var_name = list(ds.data_vars)[0]
    da = ds[var_name]

    da.attrs["source_file"] = str(path)
    da.attrs["source_variable"] = var_name

    return da


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
        raise ValueError("DataArray must have lat and lon coordinates.")

    lat_values = da["lat"].values

    if lat_values[0] < lat_values[-1]:
        lat_slice = slice(lat_min, lat_max)
    else:
        lat_slice = slice(lat_max, lat_min)

    return da.sel(
        lon=slice(lon_min, lon_max),
        lat=lat_slice,
    )


def area_weighted_mean(da: xr.DataArray, box: list[float]) -> xr.DataArray:
    sub = subset_box(da, box)

    if "lat" not in sub.coords:
        return sub.mean(skipna=True)

    weights = np.cos(np.deg2rad(sub["lat"]))
    weights = weights.where(np.isfinite(weights), 0)

    dims = [d for d in ["lat", "lon"] if d in sub.dims]

    return sub.weighted(weights).mean(dims, skipna=True)


def scalar_area_mean(da: xr.DataArray, box: list[float]) -> float:
    val = area_weighted_mean(da, box)

    if hasattr(val, "values"):
        return float(np.asarray(val.values))

    return float(val)


def save_dataarray(da: xr.DataArray, out_path: Path, var_name: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ds_out = da.to_dataset(name=var_name)

    if out_path.exists():
        out_path.unlink()

    ds_out.to_netcdf(out_path)

    print(f"Saved: {out_path}")


def save_dataset(ds: xr.Dataset, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        out_path.unlink()

    ds.to_netcdf(out_path)

    print(f"Saved: {out_path}")


def get_monthly_climatology(da: xr.DataArray) -> xr.DataArray:
    if "time" not in da.coords:
        raise ValueError("ERA5 field must contain time coordinate.")

    return da.groupby("time.month").mean("time", skipna=True)


def get_seasonal_climatology(da: xr.DataArray, months: list[int]) -> xr.DataArray:
    if "time" not in da.coords:
        raise ValueError("ERA5 field must contain time coordinate.")

    selected = da.sel(time=da["time"].dt.month.isin(months))
    return selected.mean("time", skipna=True)


def compute_wind_speed(u: xr.DataArray, v: xr.DataArray) -> xr.DataArray:
    speed = np.sqrt(u ** 2 + v ** 2)
    speed.attrs["units"] = u.attrs.get("units", "m s**-1")
    speed.attrs["description"] = "Wind speed computed as sqrt(u^2 + v^2)"
    return speed


def compute_moisture_flux(
    q: xr.DataArray,
    u: xr.DataArray,
    v: xr.DataArray,
) -> xr.Dataset:
    qu = q * u
    qv = q * v

    qu.attrs["units"] = "kg kg-1 m s-1"
    qv.attrs["units"] = "kg kg-1 m s-1"

    qu.attrs["description"] = "850 hPa zonal moisture flux proxy q850*u850"
    qv.attrs["description"] = "850 hPa meridional moisture flux proxy q850*v850"

    ds = xr.Dataset(
        {
            "qu850": qu,
            "qv850": qv,
        }
    )

    return ds


def compute_horizontal_divergence(
    fx: xr.DataArray,
    fy: xr.DataArray,
) -> xr.DataArray:
    """
    Compute horizontal divergence of vector field (fx, fy).

    fx = zonal component
    fy = meridional component

    Uses finite differences in meters based on lat/lon grid.
    Suitable for diagnostic maps, not precision dynamical-core output.
    """

    if "lat" not in fx.coords or "lon" not in fx.coords:
        raise ValueError("fx/fy must contain lat and lon coordinates.")

    fx = fx.transpose(..., "lat", "lon")
    fy = fy.transpose(..., "lat", "lon")

    lat = fx["lat"].values
    lon = fx["lon"].values

    earth_radius = 6_371_000.0

    lat_rad = np.deg2rad(lat)
    lon_rad = np.deg2rad(lon)

    # Grid spacing
    dlat = np.gradient(lat_rad)
    dlon = np.gradient(lon_rad)

    dy = earth_radius * dlat
    dx = earth_radius * np.cos(lat_rad)[:, None] * dlon[None, :]

    fx_values = fx.values
    fy_values = fy.values

    # np.gradient works along the last two dimensions
    dfx_dlon_index = np.gradient(fx_values, axis=-1)
    dfy_dlat_index = np.gradient(fy_values, axis=-2)

    dfx_dx = dfx_dlon_index / dx
    dfy_dy = dfy_dlat_index / dy.reshape((1,) * (fy_values.ndim - 2) + (len(lat), 1))

    div_values = dfx_dx + dfy_dy

    div = xr.DataArray(
        div_values,
        coords=fx.coords,
        dims=fx.dims,
        attrs={
            "description": "Horizontal divergence computed from finite differences.",
            "units": "flux_units m-1",
        },
    )

    return div


def compute_moisture_flux_convergence(
    qu: xr.DataArray,
    qv: xr.DataArray,
) -> xr.DataArray:
    div = compute_horizontal_divergence(qu, qv)
    mfc = -div

    mfc.attrs["description"] = "850 hPa moisture-flux convergence proxy: -div(q850*u850, q850*v850)"
    mfc.attrs["units"] = "kg kg-1 s-1 approximately"

    return mfc


def classify_value(
    value: float,
    positive_threshold: float,
    negative_threshold: float,
    positive_label: str,
    negative_label: str,
    neutral_label: str = "neutral_or_weak",
) -> str:
    if np.isnan(value):
        return "missing"

    if value >= positive_threshold:
        return positive_label

    if value <= negative_threshold:
        return negative_label

    return neutral_label


# ==========================================================
# DIAGNOSTIC COMPUTATIONS
# ==========================================================

def compute_era5_tej_indices() -> pd.DataFrame:
    print("\n==================================================")
    print("Computing ERA5 TEJ diagnostics")
    print("==================================================")

    u200 = open_dataarray(ERA5_FILES["u200"], decode_times=True)

    # TEJ strength is defined as -u200 because easterly wind is negative u.
    tej_strength = -area_weighted_mean(u200, DOMAINS["tej_core"])
    tej_strength.name = "tej_strength_index"

    tej_strength.attrs["description"] = (
        "TEJ strength index computed as -area mean u200 over 5N-20N, 20E-100E. "
        "Larger positive values indicate stronger easterly jet."
    )
    tej_strength.attrs["units"] = u200.attrs.get("units", "m s-1")

    out_path = DIAG_OUT_DIR / "ERA5_TEJ_strength_index_1991_2020_JJAS.nc"
    save_dataarray(tej_strength, out_path, "tej_strength_index")

    rows = []

    df = tej_strength.to_dataframe().reset_index()

    if "time" in df.columns:
        df["year"] = pd.to_datetime(df["time"]).dt.year
        df["month"] = pd.to_datetime(df["time"]).dt.month

        monthly_clim = df.groupby("month")["tej_strength_index"].mean().reset_index()
        monthly_clim["diagnostic"] = "TEJ_strength"
        monthly_clim["period"] = monthly_clim["month"].map(
            {6: "June", 7: "July", 8: "August", 9: "September"}
        )
        monthly_clim["units"] = tej_strength.attrs.get("units", "")

        for _, r in monthly_clim.iterrows():
            rows.append(
                {
                    "diagnostic": "TEJ_strength_climatology",
                    "period": r["period"],
                    "value": r["tej_strength_index"],
                    "units": r["units"],
                    "interpretation": "Higher value means stronger climatological Tropical Easterly Jet.",
                }
            )

        for season_name, months in {"JJA": [6, 7, 8], "JJAS": [6, 7, 8, 9]}.items():
            val = df[df["month"].isin(months)]["tej_strength_index"].mean()

            rows.append(
                {
                    "diagnostic": "TEJ_strength_climatology",
                    "period": season_name,
                    "value": val,
                    "units": tej_strength.attrs.get("units", ""),
                    "interpretation": "Higher value means stronger climatological Tropical Easterly Jet.",
                }
            )

    out_csv = DIAG_TABLE_DIR / "era5_tej_index_climatology.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"Saved TEJ index table: {out_csv}")

    return pd.DataFrame(rows)


def compute_era5_moisture_flux_diagnostics() -> pd.DataFrame:
    print("\n==================================================")
    print("Computing ERA5 850 hPa moisture flux diagnostics")
    print("==================================================")

    q850 = open_dataarray(ERA5_FILES["q850"], decode_times=True)
    u850 = open_dataarray(ERA5_FILES["u850"], decode_times=True)
    v850 = open_dataarray(ERA5_FILES["v850"], decode_times=True)

    flux_ds = compute_moisture_flux(q850, u850, v850)

    qu = flux_ds["qu850"]
    qv = flux_ds["qv850"]

    wind_speed = compute_wind_speed(u850, v850)
    wind_speed.name = "wind_speed850"

    mfc = compute_moisture_flux_convergence(qu, qv)
    mfc.name = "mfc850"

    # Save full monthly fields
    full_flux_out = DIAG_OUT_DIR / "ERA5_850hPa_moisture_flux_proxy_1991_2020_JJAS.nc"
    full_ds = xr.Dataset(
        {
            "qu850": qu,
            "qv850": qv,
            "wind_speed850": wind_speed,
            "mfc850": mfc,
        }
    )
    save_dataset(full_ds, full_flux_out)

    # Monthly climatology maps
    monthly_clim = full_ds.groupby("time.month").mean("time", skipna=True)
    monthly_out = DIAG_OUT_DIR / "ERA5_850hPa_moisture_flux_monthly_climatology_1991_2020.nc"
    save_dataset(monthly_clim, monthly_out)

    # Seasonal climatologies
    rows = []

    for season_name, months in {"JJA": [6, 7, 8], "JJAS": [6, 7, 8, 9]}.items():
        season_ds = full_ds.sel(time=full_ds["time"].dt.month.isin(months)).mean("time", skipna=True)

        season_out = DIAG_OUT_DIR / f"ERA5_850hPa_moisture_flux_{season_name}_climatology_1991_2020.nc"
        save_dataset(season_ds, season_out)

        for domain_name, box in DOMAINS.items():
            for var_name in ["qu850", "qv850", "wind_speed850", "mfc850"]:
                val = scalar_area_mean(season_ds[var_name], box)

                interpretation = ""

                if var_name == "qu850":
                    interpretation = "Positive value indicates eastward moisture transport; negative value indicates westward moisture transport."
                elif var_name == "qv850":
                    interpretation = "Positive value indicates northward moisture transport; negative value indicates southward moisture transport."
                elif var_name == "mfc850":
                    interpretation = "Positive value indicates moisture convergence; negative value indicates moisture divergence."
                elif var_name == "wind_speed850":
                    interpretation = "Higher value indicates stronger low-level wind speed."

                rows.append(
                    {
                        "diagnostic": var_name,
                        "period": season_name,
                        "domain": domain_name,
                        "value": val,
                        "units": season_ds[var_name].attrs.get("units", ""),
                        "interpretation": interpretation,
                    }
                )

    # Monthly area means
    monthly = full_ds.groupby("time.month").mean("time", skipna=True)

    for month in [6, 7, 8, 9]:
        month_ds = monthly.sel(month=month)
        period = {6: "June", 7: "July", 8: "August", 9: "September"}[month]

        for domain_name, box in DOMAINS.items():
            for var_name in ["qu850", "qv850", "wind_speed850", "mfc850"]:
                val = scalar_area_mean(month_ds[var_name], box)

                rows.append(
                    {
                        "diagnostic": var_name,
                        "period": period,
                        "domain": domain_name,
                        "value": val,
                        "units": month_ds[var_name].attrs.get("units", ""),
                        "interpretation": "Monthly climatological diagnostic.",
                    }
                )

    out_csv = DIAG_TABLE_DIR / "era5_850hpa_moisture_flux_diagnostics.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    print(f"Saved moisture flux diagnostics table: {out_csv}")

    return pd.DataFrame(rows)


def compute_era5_vertical_and_divergence_diagnostics() -> pd.DataFrame:
    print("\n==================================================")
    print("Computing ERA5 vertical motion and upper-level divergence diagnostics")
    print("==================================================")

    diagnostic_files = {
        "omega500": ERA5_FILES["omega500"],
        "omega700": ERA5_FILES["omega700"],
        "divergence200": ERA5_FILES["divergence200"],
        "z200": ERA5_FILES["z200"],
        "z500": ERA5_FILES["z500"],
    }

    rows = []

    for field_name, path in diagnostic_files.items():
        da = open_dataarray(path, decode_times=True)

        monthly_clim = get_monthly_climatology(da)
        monthly_out = DIAG_OUT_DIR / f"ERA5_{field_name}_monthly_climatology_dynamic_1991_2020.nc"
        save_dataarray(monthly_clim, monthly_out, f"{field_name}_monthly_climatology")

        for month in [6, 7, 8, 9]:
            if month not in monthly_clim["month"]:
                continue

            month_da = monthly_clim.sel(month=month)
            period = {6: "June", 7: "July", 8: "August", 9: "September"}[month]

            for domain_name, box in DOMAINS.items():
                val = scalar_area_mean(month_da, box)

                interpretation = ""

                if field_name.startswith("omega"):
                    interpretation = "Positive omega means subsidence/sinking motion; negative omega means rising motion."
                elif field_name == "divergence200":
                    interpretation = "Positive 200 hPa divergence supports upper-level outflow and convection."
                elif field_name in ["z200", "z500"]:
                    interpretation = "Geopotential height climatology used for circulation and Rossby-wave context."

                rows.append(
                    {
                        "diagnostic": field_name,
                        "period": period,
                        "domain": domain_name,
                        "value": val,
                        "units": da.attrs.get("units", ""),
                        "interpretation": interpretation,
                    }
                )

        for season_name, months in {"JJA": [6, 7, 8], "JJAS": [6, 7, 8, 9]}.items():
            season_da = get_seasonal_climatology(da, months)
            season_out = DIAG_OUT_DIR / f"ERA5_{field_name}_{season_name}_climatology_dynamic_1991_2020.nc"
            save_dataarray(season_da, season_out, f"{field_name}_{season_name}_climatology")

            for domain_name, box in DOMAINS.items():
                val = scalar_area_mean(season_da, box)

                interpretation = ""

                if field_name.startswith("omega"):
                    interpretation = "Positive omega means subsidence/sinking motion; negative omega means rising motion."
                elif field_name == "divergence200":
                    interpretation = "Positive 200 hPa divergence supports upper-level outflow and convection."
                elif field_name in ["z200", "z500"]:
                    interpretation = "Geopotential height climatology used for circulation and Rossby-wave context."

                rows.append(
                    {
                        "diagnostic": field_name,
                        "period": season_name,
                        "domain": domain_name,
                        "value": val,
                        "units": da.attrs.get("units", ""),
                        "interpretation": interpretation,
                    }
                )

    out_csv = DIAG_TABLE_DIR / "era5_vertical_divergence_height_diagnostics.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    print(f"Saved vertical/divergence/height diagnostics table: {out_csv}")

    return pd.DataFrame(rows)


def compute_nmme_sst_driver_diagnostics() -> pd.DataFrame:
    print("\n==================================================")
    print("Computing NMME SST-driver diagnostics from tmpsfc anomaly")
    print("==================================================")

    rows = []

    for key, path in NMME_FILES.items():
        if not key.startswith("tmpsfc"):
            continue

        if not path.exists():
            print(f"Skipping missing NMME tmpsfc file: {path}")
            continue

        da = open_dataarray(path, decode_times=False)

        nino34 = scalar_area_mean(da, SST_BOXES["nino34"])
        iod_west = scalar_area_mean(da, SST_BOXES["iod_west"])
        iod_east = scalar_area_mean(da, SST_BOXES["iod_east"])
        dmi = iod_west - iod_east

        period = key.replace("tmpsfc_", "")

        nino_class = classify_value(
            nino34,
            positive_threshold=0.5,
            negative_threshold=-0.5,
            positive_label="el_nino_like",
            negative_label="la_nina_like",
            neutral_label="enso_neutral_or_weak",
        )

        dmi_class = classify_value(
            dmi,
            positive_threshold=0.4,
            negative_threshold=-0.4,
            positive_label="positive_iod_like",
            negative_label="negative_iod_like",
            neutral_label="iod_neutral_or_weak",
        )

        rows.append(
            {
                "diagnostic": "NMME_tmpsfc_SST_indices",
                "period": period,
                "nino34_anomaly": nino34,
                "iod_west_anomaly": iod_west,
                "iod_east_anomaly": iod_east,
                "dmi_proxy": dmi,
                "nino34_classification": nino_class,
                "dmi_classification": dmi_class,
                "units": da.attrs.get("units", ""),
                "interpretation": (
                    "Computed from NMME tmpsfc anomaly as an ocean-temperature proxy. "
                    "Use with caution because tmpsfc is not identical to a dedicated SST index dataset."
                ),
            }
        )

    df = pd.DataFrame(rows)

    out_csv = DIAG_TABLE_DIR / "nmme_sst_driver_diagnostics_from_tmpsfc.csv"
    df.to_csv(out_csv, index=False)

    print(f"Saved NMME SST driver diagnostics table: {out_csv}")

    return df


def compute_nmme_rainfall_and_z200_diagnostics() -> pd.DataFrame:
    print("\n==================================================")
    print("Computing NMME rainfall and z200 anomaly diagnostics")
    print("==================================================")

    rows = []

    for key, path in NMME_FILES.items():
        if not path.exists():
            continue

        if not (key.startswith("prate") or key.startswith("z200")):
            continue

        da = open_dataarray(path, decode_times=False)

        if key.startswith("prate"):
            diagnostic = "NMME_precipitation_anomaly"
            period = (
                key.replace("prate_", "")
                .replace("_total", "")
            )
        else:
            diagnostic = "NMME_z200_anomaly"
            period = key.replace("z200_", "")

        for domain_name, box in DOMAINS.items():
            try:
                val = scalar_area_mean(da, box)
            except Exception:
                continue

            if key.startswith("prate"):
                if "JJA" in period or "JJAS" in period:
                    dry_class = classify_value(
                        val,
                        positive_threshold=20.0,
                        negative_threshold=-20.0,
                        positive_label="above_normal_wet_signal",
                        negative_label="below_normal_dry_signal",
                        neutral_label="near_normal_or_weak_signal",
                    )
                else:
                    dry_class = classify_value(
                        val,
                        positive_threshold=10.0,
                        negative_threshold=-10.0,
                        positive_label="above_normal_wet_signal",
                        negative_label="below_normal_dry_signal",
                        neutral_label="near_normal_or_weak_signal",
                    )

                interpretation = (
                    "Negative precipitation anomaly indicates drier-than-normal rainfall. "
                    "Positive anomaly indicates wetter-than-normal rainfall."
                )

                rows.append(
                    {
                        "diagnostic": diagnostic,
                        "period": period,
                        "domain": domain_name,
                        "value": val,
                        "classification": dry_class,
                        "units": da.attrs.get("units", ""),
                        "interpretation": interpretation,
                    }
                )

            elif key.startswith("z200"):
                z_class = classify_value(
                    val,
                    positive_threshold=5.0,
                    negative_threshold=-5.0,
                    positive_label="positive_height_anomaly",
                    negative_label="negative_height_anomaly",
                    neutral_label="weak_height_anomaly",
                )

                interpretation = (
                    "z200 anomaly provides upper-level circulation context. "
                    "Positive anomalies may indicate ridging/subsidence-supporting circulation depending on location."
                )

                rows.append(
                    {
                        "diagnostic": diagnostic,
                        "period": period,
                        "domain": domain_name,
                        "value": val,
                        "classification": z_class,
                        "units": da.attrs.get("units", ""),
                        "interpretation": interpretation,
                    }
                )

    df = pd.DataFrame(rows)

    out_csv = DIAG_TABLE_DIR / "nmme_rainfall_z200_diagnostics.csv"
    df.to_csv(out_csv, index=False)

    print(f"Saved NMME rainfall/z200 diagnostics table: {out_csv}")

    return df


def build_dynamic_evidence_input_table(
    rainfall_df: pd.DataFrame,
    sst_df: pd.DataFrame,
    era5_moisture_df: pd.DataFrame,
    era5_vertical_df: pd.DataFrame,
    tej_df: pd.DataFrame,
) -> pd.DataFrame:
    print("\n==================================================")
    print("Building dynamic evidence input table")
    print("==================================================")

    rows = []

    # NMME rainfall signal over Ethiopia
    if not rainfall_df.empty:
        mask = (
            (rainfall_df["diagnostic"] == "NMME_precipitation_anomaly")
            & (rainfall_df["domain"] == "ethiopia")
            & (rainfall_df["period"].isin(["JJA", "JJAS"]))
        )

        for _, r in rainfall_df[mask].iterrows():
            rows.append(
                {
                    "evidence_group": "rainfall_forecast",
                    "period": r["period"],
                    "indicator": "Ethiopia NMME rainfall anomaly",
                    "value": r["value"],
                    "units": r["units"],
                    "classification": r["classification"],
                    "supports_dry_kiremt": "yes" if "dry" in str(r["classification"]) else "no_or_weak",
                    "note": "Direct NMME precipitation anomaly signal.",
                }
            )

    # ENSO/IOD proxy
    if not sst_df.empty:
        for _, r in sst_df[sst_df["period"].isin(["JJA", "JJAS"])].iterrows():
            rows.append(
                {
                    "evidence_group": "ocean_driver",
                    "period": r["period"],
                    "indicator": "Nino3.4 tmpsfc anomaly proxy",
                    "value": r["nino34_anomaly"],
                    "units": r["units"],
                    "classification": r["nino34_classification"],
                    "supports_dry_kiremt": "yes" if r["nino34_classification"] == "el_nino_like" else "no_or_weak",
                    "note": "El Niño-like warming usually increases dry-risk for Ethiopia Kiremt.",
                }
            )

            rows.append(
                {
                    "evidence_group": "ocean_driver",
                    "period": r["period"],
                    "indicator": "DMI/IOD tmpsfc proxy",
                    "value": r["dmi_proxy"],
                    "units": r["units"],
                    "classification": r["dmi_classification"],
                    "supports_dry_kiremt": "mixed",
                    "note": "IOD influence over Ethiopia is spatially mixed; interpret with caution.",
                }
            )

    # ERA5 climatology baseline: not forecast evidence
    rows.append(
        {
            "evidence_group": "circulation_baseline",
            "period": "JJAS",
            "indicator": "ERA5 TEJ / moisture / omega climatology",
            "value": np.nan,
            "units": "",
            "classification": "baseline_only",
            "supports_dry_kiremt": "not_direct_forecast_evidence",
            "note": (
                "ERA5 1991-2020 fields provide climatological baseline. "
                "To dynamically confirm 2026 anomalies, future forecast or observed 2026 fields are still needed."
            ),
        }
    )

    df = pd.DataFrame(rows)

    out_csv = DIAG_TABLE_DIR / "dynamic_evidence_input_table.csv"
    df.to_csv(out_csv, index=False)

    print(f"Saved dynamic evidence input table: {out_csv}")

    return df


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("Compute dynamic diagnostics for Kiremt/JJAS forecast")
    print("==================================================")
    print(f"Project root:       {PROJECT_ROOT}")
    print(f"ERA5 organized:     {ERA5_ORG_DIR}")
    print(f"NMME anomaly input: {NMME_ANOM_DIR}")
    print(f"Diagnostic output:  {DIAG_OUT_DIR}")
    print(f"Tables:             {DIAG_TABLE_DIR}")

    # Check important input files
    required = [
        ERA5_FILES["u200"],
        ERA5_FILES["u850"],
        ERA5_FILES["v850"],
        ERA5_FILES["q850"],
        ERA5_FILES["omega500"],
        ERA5_FILES["omega700"],
        ERA5_FILES["divergence200"],
        NMME_FILES["prate_JJA_total"],
        NMME_FILES["prate_JJAS_total"],
    ]

    missing = [str(p) for p in required if not p.exists()]

    if missing:
        print("\nSome required files are missing:")
        for p in missing:
            print(f" - {p}")

        print("\nPlease run the previous scripts first:")
        print("  python scripts\\03_inspect_and_organize_fields.py")
        print("  python scripts\\04_compute_anomalies.py")
        raise FileNotFoundError("Required files missing.")

    # 1. TEJ
    tej_df = compute_era5_tej_indices()

    # 2. Moisture flux and moisture-flux convergence
    moisture_df = compute_era5_moisture_flux_diagnostics()

    # 3. Omega, divergence, height diagnostics
    vertical_df = compute_era5_vertical_and_divergence_diagnostics()

    # 4. NMME SST indices from tmpsfc
    sst_df = compute_nmme_sst_driver_diagnostics()

    # 5. NMME rainfall and z200 anomaly diagnostics
    rainfall_z200_df = compute_nmme_rainfall_and_z200_diagnostics()

    # 6. Build summary input table for evidence matrix
    evidence_df = build_dynamic_evidence_input_table(
        rainfall_df=rainfall_z200_df,
        sst_df=sst_df,
        era5_moisture_df=moisture_df,
        era5_vertical_df=vertical_df,
        tej_df=tej_df,
    )

    # 7. Combined diagnostic table
    combined_parts = []

    if not tej_df.empty:
        tej_df["source_table"] = "era5_tej_index_climatology"
        combined_parts.append(tej_df)

    if not moisture_df.empty:
        moisture_df["source_table"] = "era5_850hpa_moisture_flux_diagnostics"
        combined_parts.append(moisture_df)

    if not vertical_df.empty:
        vertical_df["source_table"] = "era5_vertical_divergence_height_diagnostics"
        combined_parts.append(vertical_df)

    if not rainfall_z200_df.empty:
        rainfall_z200_df["source_table"] = "nmme_rainfall_z200_diagnostics"
        combined_parts.append(rainfall_z200_df)

    if combined_parts:
        combined_df = pd.concat(combined_parts, ignore_index=True, sort=False)
    else:
        combined_df = pd.DataFrame()

    combined_csv = DIAG_TABLE_DIR / "combined_dynamic_diagnostics.csv"
    combined_df.to_csv(combined_csv, index=False)

    print(f"\nSaved combined diagnostic table: {combined_csv}")

    print("\n==================================================")
    print("DYNAMIC DIAGNOSTICS FINISHED")
    print("==================================================")

    print("\nKey NetCDF outputs:")
    print(f" - {DIAG_OUT_DIR / 'ERA5_TEJ_strength_index_1991_2020_JJAS.nc'}")
    print(f" - {DIAG_OUT_DIR / 'ERA5_850hPa_moisture_flux_proxy_1991_2020_JJAS.nc'}")
    print(f" - {DIAG_OUT_DIR / 'ERA5_850hPa_moisture_flux_monthly_climatology_1991_2020.nc'}")

    print("\nKey table outputs:")
    print(f" - {DIAG_TABLE_DIR / 'era5_tej_index_climatology.csv'}")
    print(f" - {DIAG_TABLE_DIR / 'era5_850hpa_moisture_flux_diagnostics.csv'}")
    print(f" - {DIAG_TABLE_DIR / 'era5_vertical_divergence_height_diagnostics.csv'}")
    print(f" - {DIAG_TABLE_DIR / 'nmme_sst_driver_diagnostics_from_tmpsfc.csv'}")
    print(f" - {DIAG_TABLE_DIR / 'nmme_rainfall_z200_diagnostics.csv'}")
    print(f" - {DIAG_TABLE_DIR / 'dynamic_evidence_input_table.csv'}")
    print(f" - {combined_csv}")

    print("\nImportant note:")
    print(
        "This script computes ERA5 climatological circulation diagnostics and NMME forecast "
        "anomaly indicators. Full dynamic confirmation of 2026 circulation anomalies still "
        "requires future NMME u/v/q/omega fields or observed/reanalysis 2026 fields when available."
    )

    print("\nRecommended next script:")
    print("    python scripts\\06_plot_dynamic_maps.py")


if __name__ == "__main__":
    main()