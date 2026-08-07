"""
04_compute_anomalies.py

Purpose
-------
Compute and organize NMME forecast anomalies and ERA5 climatologies for
dynamic diagnosis of Ethiopia Kiremt/JJAS 2026 rainfall.

This script uses files already prepared by:
    01_download_nmme_fields.py
    02_download_era5_fields.py
    03_inspect_and_organize_fields.py

Main outputs:
------------
1. NMME monthly and seasonal anomaly NetCDF files:
   outputs/netcdf/nmme_anomalies/

2. ERA5 monthly and seasonal climatology NetCDF files:
   outputs/netcdf/era5_climatology/

3. Tables:
   outputs/tables/nmme_ethiopia_area_mean_anomalies.csv
   outputs/tables/nmme_sst_indices_from_tmpsfc.csv
   outputs/tables/era5_climatology_area_means.csv

Run from project root:
    python scripts\\04_compute_anomalies.py
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
        NMME_DIR,
        ERA5_DIR,
        TABLE_DIR,
        NETCDF_OUT_DIR,
    )
except Exception:
    NMME_DIR = PROJECT_ROOT / "data" / "nmme"
    ERA5_DIR = PROJECT_ROOT / "data" / "era5"
    TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
    NETCDF_OUT_DIR = PROJECT_ROOT / "outputs" / "netcdf"


# ==========================================================
# INPUT FILES
# ==========================================================

NMME_ORG_DIR = NMME_DIR / "organized"
ERA5_ORG_DIR = ERA5_DIR / "organized"

NMME_PRATE_FILE = NMME_ORG_DIR / "nmme_NMME_prate_202605_ENSMEAN_anom.nc"
NMME_TMPSFC_FILE = NMME_ORG_DIR / "nmme_NMME_tmpsfc_202605_ENSMEAN_anom.nc"
NMME_TMP2M_FILE = NMME_ORG_DIR / "nmme_NMME_tmp2m_202605_ENSMEAN_anom.nc"
NMME_Z200_FILE = NMME_ORG_DIR / "nmme_NMME_z200_202605_ENSMEAN_anom.nc"

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
# OUTPUT FOLDERS
# ==========================================================

NMME_ANOM_OUT_DIR = NETCDF_OUT_DIR / "nmme_anomalies"
ERA5_CLIM_OUT_DIR = NETCDF_OUT_DIR / "era5_climatology"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
NMME_ANOM_OUT_DIR.mkdir(parents=True, exist_ok=True)
ERA5_CLIM_OUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# SETTINGS
# ==========================================================

TARGET_MONTHS = {
    "Jun_2026": {"index": 0, "month": 6, "days": 30},
    "Jul_2026": {"index": 1, "month": 7, "days": 31},
    "Aug_2026": {"index": 2, "month": 8, "days": 31},
    "Sep_2026": {"index": 3, "month": 9, "days": 30},
}

SEASONS = {
    "JJA_2026": ["Jun_2026", "Jul_2026", "Aug_2026"],
    "JJAS_2026": ["Jun_2026", "Jul_2026", "Aug_2026", "Sep_2026"],
}

DOMAINS = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "east_africa": [20, 55, -15, 20],
    "atlantic_congo_ethiopia": [-20, 50, -20, 20],
    "indian_ocean": [30, 120, -30, 30],
}

SST_INDEX_BOXES = {
    "nino34": [-170, -120, -5, 5],
    "iod_west": [50, 70, -10, 10],
    "iod_east": [90, 110, -10, 0],
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
        raise ValueError(f"No data variables found in {path}")

    var_name = list(ds.data_vars)[0]
    da = ds[var_name]

    da.attrs["source_file"] = str(path)
    da.attrs["source_variable"] = var_name

    return da


def standardize_coordinate_names(ds: xr.Dataset) -> xr.Dataset:
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

        if lower in ["target", "lead", "leads", "forecast_month"] and name != "target":
            if "target" not in ds.coords and "target" not in ds.dims:
                rename[name] = "target"

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


def find_forecast_dim(da: xr.DataArray) -> str:
    spatial_dims = {"lat", "lon"}
    non_spatial_dims = [d for d in da.dims if d not in spatial_dims]

    preferred = ["target", "lead", "time", "month", "forecast_month"]

    for p in preferred:
        for d in non_spatial_dims:
            if d.lower() == p.lower():
                return d

    if non_spatial_dims:
        return non_spatial_dims[0]

    raise ValueError(f"No forecast dimension found in dims: {da.dims}")


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

    return da.sel(
        lon=slice(lon_min, lon_max),
        lat=lat_slice,
    )


def area_weighted_mean(da: xr.DataArray, box: list[float]) -> float:
    sub = subset_box(da, box)

    if "lat" not in sub.coords:
        return float(sub.mean().values)

    weights = np.cos(np.deg2rad(sub["lat"]))
    weights = weights.where(np.isfinite(weights), 0)

    mean_value = sub.weighted(weights).mean(("lat", "lon"), skipna=True)

    return float(mean_value.values)


def save_dataarray(da: xr.DataArray, out_path: Path, var_name: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ds_out = da.to_dataset(name=var_name)

    if out_path.exists():
        out_path.unlink()

    ds_out.to_netcdf(out_path)

    print(f"Saved: {out_path}")


def convert_prate_to_mm_day(da: xr.DataArray) -> xr.DataArray:
    units_original = str(da.attrs.get("units", "")).strip()
    units = units_original.lower().replace(" ", "")

    should_convert = False

    if "mm/s" in units:
        should_convert = True

    if "mms-1" in units:
        should_convert = True

    if "s-1" in units and "mm" in units:
        should_convert = True

    if "kg" in units and ("s-1" in units or "/s" in units):
        should_convert = True

    if should_convert:
        out = da * 86400.0
        out.attrs = da.attrs.copy()
        out.attrs["units"] = "mm/day"
        out.attrs["conversion_note"] = (
            f"Converted from {units_original} to mm/day by multiplying by 86400."
        )
        return out

    return da


def select_nmme_target_months(da: xr.DataArray) -> dict[str, xr.DataArray]:
    forecast_dim = find_forecast_dim(da)
    n_targets = da.sizes[forecast_dim]

    print(f"Forecast dimension: {forecast_dim}")
    print(f"Number of targets:  {n_targets}")

    selected = {}

    for label, info in TARGET_MONTHS.items():
        idx = info["index"]

        if idx >= n_targets:
            print(f"Skipping {label}: target index {idx} not available.")
            continue

        selected[label] = da.isel({forecast_dim: idx}).squeeze(drop=True)

    return selected


def make_season_mean(monthly_data: dict[str, xr.DataArray], season_name: str) -> xr.DataArray | None:
    month_labels = SEASONS[season_name]

    available = [monthly_data[m] for m in month_labels if m in monthly_data]

    if len(available) == 0:
        return None

    out = xr.concat(available, dim="season_month").mean("season_month", skipna=True)
    out.attrs = available[0].attrs.copy()
    out.attrs["aggregation"] = f"Mean over {', '.join([m for m in month_labels if m in monthly_data])}"

    return out


def make_precip_season_total(monthly_total: dict[str, xr.DataArray], season_name: str) -> xr.DataArray | None:
    month_labels = SEASONS[season_name]

    available_labels = [m for m in month_labels if m in monthly_total]

    if len(available_labels) == 0:
        return None

    out = monthly_total[available_labels[0]].copy(deep=True)

    for label in available_labels[1:]:
        out = out + monthly_total[label]

    out.attrs = monthly_total[available_labels[0]].attrs.copy()
    out.attrs["units"] = "mm/season"
    out.attrs["aggregation"] = f"Total over {', '.join(available_labels)}"

    return out


def get_month_coord_name(da: xr.DataArray) -> str:
    if "time" not in da.coords:
        raise ValueError("ERA5 data must contain time coordinate.")

    return "time"


def compute_monthly_climatology(da: xr.DataArray) -> xr.DataArray:
    time_name = get_month_coord_name(da)
    clim = da.groupby(f"{time_name}.month").mean(time_name, skipna=True)

    clim.attrs = da.attrs.copy()
    clim.attrs["climatology"] = "Monthly climatology over available years"
    clim.attrs["climatology_period"] = "1991-2020"
    return clim


def compute_seasonal_climatology(da: xr.DataArray, months: list[int], season_name: str) -> xr.DataArray:
    time_name = get_month_coord_name(da)

    selected = da.sel({time_name: da[time_name].dt.month.isin(months)})
    clim = selected.mean(time_name, skipna=True)

    clim.attrs = da.attrs.copy()
    clim.attrs["climatology"] = f"{season_name} seasonal climatology"
    clim.attrs["months"] = ",".join(str(m) for m in months)
    clim.attrs["climatology_period"] = "1991-2020"

    return clim


# ==========================================================
# NMME PROCESSING
# ==========================================================

def process_nmme_prate() -> pd.DataFrame:
    print("\n==================================================")
    print("Processing NMME precipitation anomaly")
    print("==================================================")

    da = open_dataarray(NMME_PRATE_FILE, decode_times=False)
    da = convert_prate_to_mm_day(da)

    monthly_mean = select_nmme_target_months(da)

    monthly_total = {}

    summary_rows = []

    # Monthly mean mm/day and monthly total mm/month
    for label, month_da in monthly_mean.items():
        month_days = TARGET_MONTHS[label]["days"]

        # Save monthly mean anomaly
        month_da.attrs["units"] = "mm/day"
        out_mean = NMME_ANOM_OUT_DIR / f"NMME_prate_{label}_mean_anomaly_mm_day.nc"
        save_dataarray(month_da, out_mean, f"prate_{label}_mean_mm_day")

        # Save monthly total anomaly
        total_da = month_da * month_days
        total_da.attrs = month_da.attrs.copy()
        total_da.attrs["units"] = "mm/month"
        total_da.attrs["aggregation"] = f"{label} mean anomaly multiplied by {month_days} days"

        monthly_total[label] = total_da

        out_total = NMME_ANOM_OUT_DIR / f"NMME_prate_{label}_total_anomaly_mm_month.nc"
        save_dataarray(total_da, out_total, f"prate_{label}_total_mm_month")

        # Ethiopia area mean
        eth_mean_total = area_weighted_mean(total_da, DOMAINS["ethiopia"])
        eth_mean_daily = area_weighted_mean(month_da, DOMAINS["ethiopia"])

        summary_rows.append(
            {
                "field": "prate",
                "period": label,
                "aggregation": "monthly_mean",
                "ethiopia_area_mean": eth_mean_daily,
                "units": "mm/day",
            }
        )

        summary_rows.append(
            {
                "field": "prate",
                "period": label,
                "aggregation": "monthly_total",
                "ethiopia_area_mean": eth_mean_total,
                "units": "mm/month",
            }
        )

    # Seasonal mean and total
    for season_name in SEASONS:
        season_mean = make_season_mean(monthly_mean, season_name)

        if season_mean is not None:
            season_mean.attrs["units"] = "mm/day"
            out_path = NMME_ANOM_OUT_DIR / f"NMME_prate_{season_name}_mean_anomaly_mm_day.nc"
            save_dataarray(season_mean, out_path, f"prate_{season_name}_mean_mm_day")

            eth_mean = area_weighted_mean(season_mean, DOMAINS["ethiopia"])

            summary_rows.append(
                {
                    "field": "prate",
                    "period": season_name,
                    "aggregation": "season_mean",
                    "ethiopia_area_mean": eth_mean,
                    "units": "mm/day",
                }
            )

        season_total = make_precip_season_total(monthly_total, season_name)

        if season_total is not None:
            out_path = NMME_ANOM_OUT_DIR / f"NMME_prate_{season_name}_total_anomaly_mm_season.nc"
            save_dataarray(season_total, out_path, f"prate_{season_name}_total_mm_season")

            eth_total = area_weighted_mean(season_total, DOMAINS["ethiopia"])

            summary_rows.append(
                {
                    "field": "prate",
                    "period": season_name,
                    "aggregation": "season_total",
                    "ethiopia_area_mean": eth_total,
                    "units": "mm/season",
                }
            )

    return pd.DataFrame(summary_rows)


def process_generic_nmme_anomaly(path: Path, field_name: str) -> pd.DataFrame:
    print("\n==================================================")
    print(f"Processing NMME {field_name} anomaly")
    print("==================================================")

    if not path.exists():
        print(f"Skipping {field_name}. File not found: {path}")
        return pd.DataFrame()

    da = open_dataarray(path, decode_times=False)
    monthly = select_nmme_target_months(da)

    summary_rows = []

    for label, month_da in monthly.items():
        units = month_da.attrs.get("units", "")

        out_path = NMME_ANOM_OUT_DIR / f"NMME_{field_name}_{label}_anomaly.nc"
        save_dataarray(month_da, out_path, f"{field_name}_{label}_anomaly")

        eth_mean = area_weighted_mean(month_da, DOMAINS["ethiopia"])

        summary_rows.append(
            {
                "field": field_name,
                "period": label,
                "aggregation": "monthly_anomaly",
                "ethiopia_area_mean": eth_mean,
                "units": units,
            }
        )

    for season_name in SEASONS:
        season_mean = make_season_mean(monthly, season_name)

        if season_mean is not None:
            units = season_mean.attrs.get("units", "")

            out_path = NMME_ANOM_OUT_DIR / f"NMME_{field_name}_{season_name}_mean_anomaly.nc"
            save_dataarray(season_mean, out_path, f"{field_name}_{season_name}_mean_anomaly")

            eth_mean = area_weighted_mean(season_mean, DOMAINS["ethiopia"])

            summary_rows.append(
                {
                    "field": field_name,
                    "period": season_name,
                    "aggregation": "season_mean_anomaly",
                    "ethiopia_area_mean": eth_mean,
                    "units": units,
                }
            )

    return pd.DataFrame(summary_rows)


def compute_nmme_sst_indices_from_tmpsfc() -> pd.DataFrame:
    print("\n==================================================")
    print("Computing approximate NMME SST indices from tmpsfc anomaly")
    print("==================================================")

    if not NMME_TMPSFC_FILE.exists():
        print(f"Skipping SST indices. File not found: {NMME_TMPSFC_FILE}")
        return pd.DataFrame()

    da = open_dataarray(NMME_TMPSFC_FILE, decode_times=False)
    monthly = select_nmme_target_months(da)

    rows = []

    for label, month_da in monthly.items():
        nino34 = area_weighted_mean(month_da, SST_INDEX_BOXES["nino34"])
        iod_west = area_weighted_mean(month_da, SST_INDEX_BOXES["iod_west"])
        iod_east = area_weighted_mean(month_da, SST_INDEX_BOXES["iod_east"])
        dmi = iod_west - iod_east

        rows.append(
            {
                "period": label,
                "nino34_tmpsfc_anomaly": nino34,
                "iod_west_tmpsfc_anomaly": iod_west,
                "iod_east_tmpsfc_anomaly": iod_east,
                "dmi_approx": dmi,
                "units": month_da.attrs.get("units", ""),
                "note": "Computed from NMME tmpsfc anomaly as an SST proxy over oceanic index boxes.",
            }
        )

    for season_name in SEASONS:
        season_mean = make_season_mean(monthly, season_name)

        if season_mean is None:
            continue

        nino34 = area_weighted_mean(season_mean, SST_INDEX_BOXES["nino34"])
        iod_west = area_weighted_mean(season_mean, SST_INDEX_BOXES["iod_west"])
        iod_east = area_weighted_mean(season_mean, SST_INDEX_BOXES["iod_east"])
        dmi = iod_west - iod_east

        rows.append(
            {
                "period": season_name,
                "nino34_tmpsfc_anomaly": nino34,
                "iod_west_tmpsfc_anomaly": iod_west,
                "iod_east_tmpsfc_anomaly": iod_east,
                "dmi_approx": dmi,
                "units": season_mean.attrs.get("units", ""),
                "note": "Seasonal mean computed from available NMME target months.",
            }
        )

    df = pd.DataFrame(rows)

    out_csv = TABLE_DIR / "nmme_sst_indices_from_tmpsfc.csv"
    df.to_csv(out_csv, index=False)

    print(f"Saved NMME SST index table: {out_csv}")

    return df


# ==========================================================
# ERA5 CLIMATOLOGY PROCESSING
# ==========================================================

def process_era5_climatologies() -> pd.DataFrame:
    print("\n==================================================")
    print("Processing ERA5 monthly and seasonal climatologies")
    print("==================================================")

    summary_rows = []

    season_months = {
        "JJA": [6, 7, 8],
        "JJAS": [6, 7, 8, 9],
    }

    for field_name, path in ERA5_FILES.items():
        if not path.exists():
            print(f"Skipping missing ERA5 file: {field_name} -> {path}")
            continue

        print(f"\nProcessing ERA5 field: {field_name}")
        da = open_dataarray(path, decode_times=True)

        monthly_clim = compute_monthly_climatology(da)

        monthly_out = ERA5_CLIM_OUT_DIR / f"ERA5_{field_name}_monthly_climatology_1991_2020_JJAS.nc"
        save_dataarray(monthly_clim, monthly_out, f"{field_name}_monthly_climatology")

        # Area means for monthly climatology
        for month in [6, 7, 8, 9]:
            if month in monthly_clim["month"]:
                month_da = monthly_clim.sel(month=month)

                for domain_name, box in DOMAINS.items():
                    mean_val = area_weighted_mean(month_da, box)

                    summary_rows.append(
                        {
                            "field": field_name,
                            "period": f"month_{month:02d}",
                            "domain": domain_name,
                            "area_mean": mean_val,
                            "units": month_da.attrs.get("units", ""),
                            "aggregation": "monthly_climatology",
                        }
                    )

        # Seasonal climatology
        for season_name, months in season_months.items():
            season_clim = compute_seasonal_climatology(da, months, season_name)

            season_out = ERA5_CLIM_OUT_DIR / f"ERA5_{field_name}_{season_name}_climatology_1991_2020.nc"
            save_dataarray(season_clim, season_out, f"{field_name}_{season_name}_climatology")

            for domain_name, box in DOMAINS.items():
                mean_val = area_weighted_mean(season_clim, box)

                summary_rows.append(
                    {
                        "field": field_name,
                        "period": season_name,
                        "domain": domain_name,
                        "area_mean": mean_val,
                        "units": season_clim.attrs.get("units", ""),
                        "aggregation": "seasonal_climatology",
                    }
                )

    df = pd.DataFrame(summary_rows)

    out_csv = TABLE_DIR / "era5_climatology_area_means.csv"
    df.to_csv(out_csv, index=False)

    print(f"Saved ERA5 climatology area-mean table: {out_csv}")

    return df


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("Compute NMME anomalies and ERA5 climatologies")
    print("==================================================")
    print(f"Project root:      {PROJECT_ROOT}")
    print(f"NMME organized:    {NMME_ORG_DIR}")
    print(f"ERA5 organized:    {ERA5_ORG_DIR}")
    print(f"NMME anomaly out:  {NMME_ANOM_OUT_DIR}")
    print(f"ERA5 climatology:  {ERA5_CLIM_OUT_DIR}")
    print(f"Tables:            {TABLE_DIR}")

    all_nmme_summary = []

    # 1. NMME precipitation anomaly
    prate_df = process_nmme_prate()
    if not prate_df.empty:
        all_nmme_summary.append(prate_df)

    # 2. NMME surface temperature / SST proxy anomaly
    tmpsfc_df = process_generic_nmme_anomaly(
        path=NMME_TMPSFC_FILE,
        field_name="tmpsfc",
    )
    if not tmpsfc_df.empty:
        all_nmme_summary.append(tmpsfc_df)

    # 3. NMME 2m temperature anomaly
    tmp2m_df = process_generic_nmme_anomaly(
        path=NMME_TMP2M_FILE,
        field_name="tmp2m",
    )
    if not tmp2m_df.empty:
        all_nmme_summary.append(tmp2m_df)

    # 4. NMME z200 anomaly
    z200_df = process_generic_nmme_anomaly(
        path=NMME_Z200_FILE,
        field_name="z200",
    )
    if not z200_df.empty:
        all_nmme_summary.append(z200_df)

    # 5. NMME SST index proxy
    sst_index_df = compute_nmme_sst_indices_from_tmpsfc()

    # 6. Save NMME Ethiopia summary
    if all_nmme_summary:
        nmme_summary_df = pd.concat(all_nmme_summary, ignore_index=True)
    else:
        nmme_summary_df = pd.DataFrame()

    nmme_summary_csv = TABLE_DIR / "nmme_ethiopia_area_mean_anomalies.csv"
    nmme_summary_df.to_csv(nmme_summary_csv, index=False)
    print(f"\nSaved NMME Ethiopia anomaly summary: {nmme_summary_csv}")

    # 7. ERA5 climatologies
    era5_summary_df = process_era5_climatologies()

    print("\n==================================================")
    print("ANOMALY / CLIMATOLOGY COMPUTATION FINISHED")
    print("==================================================")

    print("\nKey outputs:")
    print(f" - NMME anomaly NetCDFs:      {NMME_ANOM_OUT_DIR}")
    print(f" - ERA5 climatology NetCDFs:  {ERA5_CLIM_OUT_DIR}")
    print(f" - NMME Ethiopia summary:     {nmme_summary_csv}")
    print(f" - NMME SST index table:      {TABLE_DIR / 'nmme_sst_indices_from_tmpsfc.csv'}")
    print(f" - ERA5 area means:           {TABLE_DIR / 'era5_climatology_area_means.csv'}")

    print("\nRecommended next script:")
    print("    python scripts\\05_compute_dynamic_diagnostics.py")


if __name__ == "__main__":
    main()