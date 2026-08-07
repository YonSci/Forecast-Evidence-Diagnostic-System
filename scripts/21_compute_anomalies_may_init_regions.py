"""
21_compute_anomalies_may_init_regions.py

Purpose
-------
Compute the same 4-region (Ethiopia / Greater Horn / Africa / Global) NMME
precipitation and surface-temperature anomaly summary for the May 2026
initialization that 15_compute_anomalies_june_init.py and
19_compute_anomalies_july_init.py already compute for June and July.

This closes a gap: 04_compute_anomalies.py only ever produced an
Ethiopia-only summary (nmme_ethiopia_area_mean_anomalies.csv) for the May
cycle. Africa/Global/Greater-Horn numbers for May existed only as ad hoc
scratch computation, never as a real pipeline output. After this script,
all three initializations have a uniformly-named, uniformly-shaped table:
    outputs/tables/nmme_area_mean_anomalies_{may,june,july}_init.csv

Target months
-------------
May-init's first available forecast target is JUNE 2026 (index 0 of the
organized file's target dimension), same convention documented in
13_download_nmme_june_init.py. This branch covers the full Kiremt/JJAS
window already used by 04_compute_anomalies.py: Jun, Jul, Aug, Sep, plus
JJA, JAS, and JJAS seasons.

Run from project root:
    python scripts\\21_compute_anomalies_may_init_regions.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import NMME_DIR, TABLE_DIR, NETCDF_OUT_DIR
except Exception:
    NMME_DIR = PROJECT_ROOT / "data" / "nmme"
    TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
    NETCDF_OUT_DIR = PROJECT_ROOT / "outputs" / "netcdf"

NMME_ORG_DIR = NMME_DIR / "organized"
NMME_PRATE_FILE = NMME_ORG_DIR / "nmme_NMME_prate_202605_ENSMEAN_anom.nc"
NMME_TMPSFC_FILE = NMME_ORG_DIR / "nmme_NMME_tmpsfc_202605_ENSMEAN_anom.nc"

NMME_ANOM_OUT_DIR = NETCDF_OUT_DIR / "nmme_anomalies_may_init_regions"
NMME_ANOM_OUT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

# index 0 of the organized May-init file == June 2026 (verified against
# nmme_ethiopia_area_mean_anomalies.csv in 13_download_nmme_june_init.py)
TARGET_MONTHS = {
    "Jun_2026": {"index": 0, "month": 6, "days": 30},
    "Jul_2026": {"index": 1, "month": 7, "days": 31},
    "Aug_2026": {"index": 2, "month": 8, "days": 31},
    "Sep_2026": {"index": 3, "month": 9, "days": 30},
}

SEASONS = {
    "JJA_2026": ["Jun_2026", "Jul_2026", "Aug_2026"],
    "JAS_2026": ["Jul_2026", "Aug_2026", "Sep_2026"],
    "JJAS_2026": ["Jun_2026", "Jul_2026", "Aug_2026", "Sep_2026"],
}

# same four regions used by the dashboard's Anomaly Evidence region selector
# and by scripts 15/19 for the June/July init cycles
DOMAINS = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "africa": [-20, 52, -35, 38],
    "global": [-180, 180, -90, 90],
}

SST_INDEX_BOXES = {
    "nino34": [-170, -120, -5, 5],
    "iod_west": [50, 70, -10, 10],
    "iod_east": [90, 110, -10, 0],
}


def standardize_longitude(da):
    if "lon" not in da.coords:
        return da
    lon = da["lon"]
    if float(lon.max()) > 180:
        da = da.assign_coords(lon=((lon + 180) % 360) - 180).sortby("lon")
    return da


def open_dataarray(path: Path) -> xr.DataArray:
    ds = xr.open_dataset(path, decode_times=False)
    var_name = list(ds.data_vars)[0]
    return ds[var_name]


def subset_box(da, box):
    lon_min, lon_max, lat_min, lat_max = box
    da = standardize_longitude(da)
    lat = da["lat"].values
    lat_slice = slice(lat_min, lat_max) if lat[0] < lat[-1] else slice(lat_max, lat_min)
    return da.sel(lon=slice(lon_min, lon_max), lat=lat_slice)


def area_weighted_mean(da, box) -> float:
    sub = subset_box(da, box)
    weights = np.cos(np.deg2rad(sub["lat"]))
    return float(sub.weighted(weights).mean(("lat", "lon"), skipna=True).values)


def save_dataarray(da, out_path: Path, var_name: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    da.to_dataset(name=var_name).to_netcdf(out_path)
    print(f"Saved: {out_path}")


def convert_prate_to_mm_day(da):
    units = str(da.attrs.get("units", "")).strip().lower().replace(" ", "")
    if "mm/s" in units or "mms-1" in units or ("s-1" in units and "mm" in units) or ("kg" in units and "s-1" in units):
        out = da * 86400.0
        out.attrs = da.attrs.copy()
        out.attrs["units"] = "mm/day"
        return out
    return da


def select_target_months(da):
    return {label: da.isel(target=info["index"]).squeeze(drop=True) for label, info in TARGET_MONTHS.items()}


def make_season_mean(monthly, season_name):
    labels = SEASONS[season_name]
    available = [monthly[m] for m in labels if m in monthly]
    if not available:
        return None
    out = xr.concat(available, dim="season_month").mean("season_month", skipna=True)
    out.attrs = available[0].attrs.copy()
    return out


def make_season_total(monthly_total, season_name):
    labels = [m for m in SEASONS[season_name] if m in monthly_total]
    if not labels:
        return None
    out = monthly_total[labels[0]].copy(deep=True)
    for label in labels[1:]:
        out = out + monthly_total[label]
    out.attrs = monthly_total[labels[0]].attrs.copy()
    out.attrs["units"] = "mm/season"
    return out


def process_prate():
    print("\n== Processing NMME precipitation anomaly (May 2026 init, 4 regions) ==")
    da = open_dataarray(NMME_PRATE_FILE)
    da = convert_prate_to_mm_day(da)
    monthly_mean = select_target_months(da)

    monthly_total = {}
    rows = []

    for label, month_da in monthly_mean.items():
        days = TARGET_MONTHS[label]["days"]
        month_da.attrs["units"] = "mm/day"
        save_dataarray(month_da, NMME_ANOM_OUT_DIR / f"NMME_prate_{label}_mean_anomaly_mm_day.nc", f"prate_{label}_mean_mm_day")

        total_da = month_da * days
        total_da.attrs = month_da.attrs.copy()
        total_da.attrs["units"] = "mm/month"
        monthly_total[label] = total_da
        save_dataarray(total_da, NMME_ANOM_OUT_DIR / f"NMME_prate_{label}_total_anomaly_mm_month.nc", f"prate_{label}_total_mm_month")

        for region, box in DOMAINS.items():
            rows.append({"field": "prate", "period": label, "region": region, "aggregation": "monthly_mean", "value": area_weighted_mean(month_da, box), "units": "mm/day"})
            rows.append({"field": "prate", "period": label, "region": region, "aggregation": "monthly_total", "value": area_weighted_mean(total_da, box), "units": "mm/month"})

    for season_name in SEASONS:
        season_mean = make_season_mean(monthly_mean, season_name)
        if season_mean is not None:
            season_mean.attrs["units"] = "mm/day"
            save_dataarray(season_mean, NMME_ANOM_OUT_DIR / f"NMME_prate_{season_name}_mean_anomaly_mm_day.nc", f"prate_{season_name}_mean_mm_day")
            for region, box in DOMAINS.items():
                rows.append({"field": "prate", "period": season_name, "region": region, "aggregation": "season_mean", "value": area_weighted_mean(season_mean, box), "units": "mm/day"})

        season_total = make_season_total(monthly_total, season_name)
        if season_total is not None:
            save_dataarray(season_total, NMME_ANOM_OUT_DIR / f"NMME_prate_{season_name}_total_anomaly_mm_season.nc", f"prate_{season_name}_total_mm_season")
            for region, box in DOMAINS.items():
                rows.append({"field": "prate", "period": season_name, "region": region, "aggregation": "season_total", "value": area_weighted_mean(season_total, box), "units": "mm/season"})

    return pd.DataFrame(rows)


def process_tmpsfc():
    print("\n== Processing NMME surface-temperature anomaly (May 2026 init, 4 regions) ==")
    if not NMME_TMPSFC_FILE.exists():
        print(f"Skipping. File not found: {NMME_TMPSFC_FILE}")
        return pd.DataFrame(), pd.DataFrame()

    da = open_dataarray(NMME_TMPSFC_FILE)
    monthly = select_target_months(da)

    rows = []
    sst_rows = []

    for label, month_da in monthly.items():
        units = month_da.attrs.get("units", "K")
        save_dataarray(month_da, NMME_ANOM_OUT_DIR / f"NMME_tmpsfc_{label}_anomaly.nc", f"tmpsfc_{label}_anomaly")
        for region, box in DOMAINS.items():
            rows.append({"field": "tmpsfc", "period": label, "region": region, "aggregation": "monthly_anomaly", "value": area_weighted_mean(month_da, box), "units": units})

        nino34 = area_weighted_mean(month_da, SST_INDEX_BOXES["nino34"])
        iod_west = area_weighted_mean(month_da, SST_INDEX_BOXES["iod_west"])
        iod_east = area_weighted_mean(month_da, SST_INDEX_BOXES["iod_east"])
        sst_rows.append({"period": label, "nino34_tmpsfc_anomaly": nino34, "iod_west_tmpsfc_anomaly": iod_west, "iod_east_tmpsfc_anomaly": iod_east, "dmi_approx": iod_west - iod_east, "units": units})

    for season_name in SEASONS:
        season_mean = make_season_mean(monthly, season_name)
        if season_mean is not None:
            units = season_mean.attrs.get("units", "K")
            save_dataarray(season_mean, NMME_ANOM_OUT_DIR / f"NMME_tmpsfc_{season_name}_mean_anomaly.nc", f"tmpsfc_{season_name}_mean_anomaly")
            for region, box in DOMAINS.items():
                rows.append({"field": "tmpsfc", "period": season_name, "region": region, "aggregation": "season_mean_anomaly", "value": area_weighted_mean(season_mean, box), "units": units})

            nino34 = area_weighted_mean(season_mean, SST_INDEX_BOXES["nino34"])
            iod_west = area_weighted_mean(season_mean, SST_INDEX_BOXES["iod_west"])
            iod_east = area_weighted_mean(season_mean, SST_INDEX_BOXES["iod_east"])
            sst_rows.append({"period": season_name, "nino34_tmpsfc_anomaly": nino34, "iod_west_tmpsfc_anomaly": iod_west, "iod_east_tmpsfc_anomaly": iod_east, "dmi_approx": iod_west - iod_east, "units": units})

    return pd.DataFrame(rows), pd.DataFrame(sst_rows)


def main():
    print("==================================================")
    print("Compute NMME 4-region anomalies -- May 2026 initialization")
    print("==================================================")
    print(f"NMME organized: {NMME_ORG_DIR}")
    print(f"Output NetCDF:  {NMME_ANOM_OUT_DIR}")

    prate_df = process_prate()
    tmpsfc_df, sst_df = process_tmpsfc()

    summary_df = pd.concat([prate_df, tmpsfc_df], ignore_index=True)
    summary_csv = TABLE_DIR / "nmme_area_mean_anomalies_may_init.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"\nSaved area-mean summary: {summary_csv}")

    sst_csv = TABLE_DIR / "nmme_sst_indices_from_tmpsfc_may_init_4region.csv"
    sst_df.to_csv(sst_csv, index=False)
    print(f"Saved SST proxy index table: {sst_csv}")

    print("\nDone. Periods produced: Jun_2026, Jul_2026, Aug_2026, Sep_2026, JJA_2026, JAS_2026, JJAS_2026.")


if __name__ == "__main__":
    main()
