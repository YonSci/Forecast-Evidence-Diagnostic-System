"""
23_generate_leaflet_grid_data.py

Purpose
-------
Pre-extract the raw NMME precipitation-anomaly grid (lat/lon/value triples,
as a compact lat-axis + lon-axis + values-matrix JSON) for every
(initialization, region, period) combination already rendered by script 22,
so the frontend can show an exact value on hover over the Leaflet map
without the backend needing netCDF/xarray as a runtime dependency -- same
"pre-render locally, sync a static copy into the backend" pattern already
used for the overlay PNGs and the CSV tables.

Written directly under the leaflet_overlays output tree so it rides along
with the existing sync_static_data.py copytree of that whole folder.

Outputs
-------
    outputs/maps/leaflet_overlays/grid_data/<init>/prate_<region>_<period>.json
        { "lats": [...], "lons": [...], "values": [[...], ...], "unit": "mm/season" }
        values[i][j] is the anomaly at (lats[i], lons[j]); missing cells are null.

Run from project root:
    python scripts\\23_generate_leaflet_grid_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "leaflet_overlays" / "grid_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Same four region boxes as script 22 -- kept in sync manually since this is
# a small, independent extraction step.
REGIONS = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "africa": [-20, 52, -35, 38],
    "global": [-180, 180, -90, 90],
}

INIT_JOBS = {
    "may": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_may_init_regions",
        "periods": {
            "Jun": ("NMME_prate_Jun_2026_total_anomaly_mm_month.nc", "prate_Jun_2026_total_mm_month", "mm/month"),
            "Jul": ("NMME_prate_Jul_2026_total_anomaly_mm_month.nc", "prate_Jul_2026_total_mm_month", "mm/month"),
            "Aug": ("NMME_prate_Aug_2026_total_anomaly_mm_month.nc", "prate_Aug_2026_total_mm_month", "mm/month"),
            "Sep": ("NMME_prate_Sep_2026_total_anomaly_mm_month.nc", "prate_Sep_2026_total_mm_month", "mm/month"),
            "JJA": ("NMME_prate_JJA_2026_total_anomaly_mm_season.nc", "prate_JJA_2026_total_mm_season", "mm/season"),
            "JAS": ("NMME_prate_JAS_2026_total_anomaly_mm_season.nc", "prate_JAS_2026_total_mm_season", "mm/season"),
            "JJAS": ("NMME_prate_JJAS_2026_total_anomaly_mm_season.nc", "prate_JJAS_2026_total_mm_season", "mm/season"),
        },
    },
    "june": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_june_init",
        "periods": {
            "Jul": ("NMME_prate_Jul_2026_total_anomaly_mm_month.nc", "prate_Jul_2026_total_mm_month", "mm/month"),
            "Aug": ("NMME_prate_Aug_2026_total_anomaly_mm_month.nc", "prate_Aug_2026_total_mm_month", "mm/month"),
            "Sep": ("NMME_prate_Sep_2026_total_anomaly_mm_month.nc", "prate_Sep_2026_total_mm_month", "mm/month"),
            "JAS": ("NMME_prate_JAS_2026_total_anomaly_mm_season.nc", "prate_JAS_2026_total_mm_season", "mm/season"),
        },
    },
    "july": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_july_init",
        "periods": {
            "Aug": ("NMME_prate_Aug_2026_total_anomaly_mm_month.nc", "prate_Aug_2026_total_mm_month", "mm/month"),
            "Sep": ("NMME_prate_Sep_2026_total_anomaly_mm_month.nc", "prate_Sep_2026_total_mm_month", "mm/month"),
            "AS": ("NMME_prate_AS_2026_total_anomaly_mm_season.nc", "prate_AS_2026_total_mm_season", "mm/season"),
        },
    },
}


def area_sub(da, box):
    lon_min, lon_max, lat_min, lat_max = box
    lat = da["lat"].values
    lat_slice = slice(lat_min, lat_max) if lat[0] < lat[-1] else slice(lat_max, lat_min)
    return da.sel(lat=lat_slice, lon=slice(lon_min, lon_max))


def to_json_value(v: float) -> float | None:
    return None if not np.isfinite(v) else round(float(v), 2)


def main():
    print("==================================================")
    print("Generate raw grid JSON for Leaflet hover tooltips")
    print("==================================================")

    written = 0
    total_bytes = 0

    for init_key, job in INIT_JOBS.items():
        nc_dir = job["dir"]
        for period, (fname, varname, unit) in job["periods"].items():
            path = nc_dir / fname
            if not path.exists():
                print(f"Missing: {path}, skipping.")
                continue
            ds = xr.open_dataset(path, decode_times=False)
            da_full = ds[varname]

            for region, box in REGIONS.items():
                da = area_sub(da_full, box).squeeze(drop=True)
                if "lat" in da.dims and "lon" in da.dims:
                    da = da.transpose("lat", "lon")

                lats = [round(float(v), 3) for v in da["lat"].values]
                lons = [round(float(v), 3) for v in da["lon"].values]
                values = [[to_json_value(v) for v in row] for row in da.values]

                out_path = OUT_DIR / init_key / f"prate_{region}_{period}.json"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {"lats": lats, "lons": lons, "values": values, "unit": unit}
                text = json.dumps(payload, separators=(",", ":"))
                out_path.write_text(text, encoding="utf-8")

                written += 1
                total_bytes += len(text.encode("utf-8"))
                print(f"Saved: {out_path} ({len(text)/1024:.1f} KB)")
            ds.close()

    print(f"\nWrote {written} grid JSON files, {total_bytes/1024/1024:.2f} MB total")


if __name__ == "__main__":
    main()
