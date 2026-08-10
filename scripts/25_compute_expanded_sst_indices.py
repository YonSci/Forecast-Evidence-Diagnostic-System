"""
25_compute_expanded_sst_indices.py

Purpose
-------
Extend the existing Nino3.4 / IOD-West / IOD-East SST proxy (computed from
NMME tmpsfc anomaly) with the other three standard ENSO index boxes --
Nino1+2, Nino3, Nino4 -- across all three NMME initialization cycles
(May/June/July 2026), matching the box set a standard ENSO/IOD outlook page
shows (e.g. BOM's SST maps page).

Reads the tmpsfc anomaly netCDF files already produced by scripts
04/15/19 (global grid, not subset to any box) -- no re-run of those heavier
scripts needed.

Output
------
    outputs/tables/nmme_sst_indices_extended.csv
        columns: init, period, nino1_2, nino3, nino34, nino4, iod_west,
                 iod_east, dmi, units

Run from project root:
    python scripts\\25_compute_expanded_sst_indices.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"

# (init_key, netcdf_dir, {period: (filename, varname)})
INIT_JOBS = {
    "may": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_may_init_regions",
        "periods": {
            "Jun": ("NMME_tmpsfc_Jun_2026_anomaly.nc", "tmpsfc_Jun_2026_anomaly"),
            "Jul": ("NMME_tmpsfc_Jul_2026_anomaly.nc", "tmpsfc_Jul_2026_anomaly"),
            "Aug": ("NMME_tmpsfc_Aug_2026_anomaly.nc", "tmpsfc_Aug_2026_anomaly"),
            "Sep": ("NMME_tmpsfc_Sep_2026_anomaly.nc", "tmpsfc_Sep_2026_anomaly"),
            "JJA": ("NMME_tmpsfc_JJA_2026_mean_anomaly.nc", "tmpsfc_JJA_2026_mean_anomaly"),
            "JJAS": ("NMME_tmpsfc_JJAS_2026_mean_anomaly.nc", "tmpsfc_JJAS_2026_mean_anomaly"),
        },
    },
    "june": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_june_init",
        "periods": {
            "Jul": ("NMME_tmpsfc_Jul_2026_anomaly.nc", "tmpsfc_Jul_2026_anomaly"),
            "Aug": ("NMME_tmpsfc_Aug_2026_anomaly.nc", "tmpsfc_Aug_2026_anomaly"),
            "Sep": ("NMME_tmpsfc_Sep_2026_anomaly.nc", "tmpsfc_Sep_2026_anomaly"),
            "JAS": ("NMME_tmpsfc_JAS_2026_mean_anomaly.nc", "tmpsfc_JAS_2026_mean_anomaly"),
        },
    },
    "july": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_july_init",
        "periods": {
            "Aug": ("NMME_tmpsfc_Aug_2026_anomaly.nc", "tmpsfc_Aug_2026_anomaly"),
            "Sep": ("NMME_tmpsfc_Sep_2026_anomaly.nc", "tmpsfc_Sep_2026_anomaly"),
            "AS": ("NMME_tmpsfc_AS_2026_mean_anomaly.nc", "tmpsfc_AS_2026_mean_anomaly"),
        },
    },
}

# Standard NOAA CPC ENSO index boxes, plus the IOD boxes already used
# elsewhere in this project. Nino4 straddles the antimeridian (160E-150W),
# so it's expressed as lon >= 160 OR lon <= -150 rather than a single slice.
BOXES = {
    "nino1_2": {"lon": (-90, -80), "lat": (-10, 0)},
    "nino3": {"lon": (-150, -90), "lat": (-5, 5)},
    "nino34": {"lon": (-170, -120), "lat": (-5, 5)},
    "nino4": {"lon": (160, -150), "lat": (-5, 5)},  # wraps the antimeridian
    "iod_west": {"lon": (50, 70), "lat": (-10, 10)},
    "iod_east": {"lon": (90, 110), "lat": (-10, 0)},
}


def standardize_longitude(da: xr.DataArray) -> xr.DataArray:
    lon = da["lon"]
    if float(lon.max()) > 180:
        da = da.assign_coords(lon=((lon + 180) % 360) - 180).sortby("lon")
    return da


def area_weighted_mean_box(da: xr.DataArray, lon_range: tuple[float, float], lat_range: tuple[float, float]) -> float:
    lon_min, lon_max = lon_range
    lat_min, lat_max = lat_range

    lat_vals = da["lat"].values
    lat_slice = slice(lat_min, lat_max) if lat_vals[0] < lat_vals[-1] else slice(lat_max, lat_min)

    if lon_min > lon_max:
        # Antimeridian-wrapping box (e.g. Nino4): union of the two halves.
        sub = xr.concat(
            [da.sel(lon=slice(lon_min, 180), lat=lat_slice), da.sel(lon=slice(-180, lon_max), lat=lat_slice)],
            dim="lon",
        )
    else:
        sub = da.sel(lon=slice(lon_min, lon_max), lat=lat_slice)

    weights = np.cos(np.deg2rad(sub["lat"]))
    weights = weights.where(np.isfinite(weights), 0)
    return float(sub.weighted(weights).mean(("lat", "lon"), skipna=True).values)


def main():
    print("==================================================")
    print("Compute expanded SST index table (Nino1+2/3/3.4/4, IOD)")
    print("==================================================")

    rows = []

    for init_key, job in INIT_JOBS.items():
        nc_dir = job["dir"]
        for period, (fname, varname) in job["periods"].items():
            path = nc_dir / fname
            if not path.exists():
                print(f"Missing: {path}, skipping.")
                continue

            ds = xr.open_dataset(path, decode_times=False)
            da = standardize_longitude(ds[varname])

            values = {name: area_weighted_mean_box(da, b["lon"], b["lat"]) for name, b in BOXES.items()}
            dmi = values["iod_west"] - values["iod_east"]

            rows.append(
                {
                    "init": init_key,
                    "period": period,
                    **values,
                    "dmi": dmi,
                    "units": da.attrs.get("units", "K"),
                }
            )
            ds.close()
            print(f"{init_key}/{period}: nino34={values['nino34']:+.2f}  dmi={dmi:+.2f}")

    df = pd.DataFrame(rows)
    out_csv = TABLE_DIR / "nmme_sst_indices_extended.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nWrote {len(df)} rows -> {out_csv}")


if __name__ == "__main__":
    main()
