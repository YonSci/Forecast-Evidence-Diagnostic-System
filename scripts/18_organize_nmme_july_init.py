"""
18_organize_nmme_july_init.py

Purpose
-------
Organize the downloaded July 2026 NMME ENSMEAN realtime-anomaly files
(from 17_download_nmme_july_init.py) the same way 14_organize_nmme_june
_init.py organizes the June cycle: squeeze each file down to its main
data variable and save it into data/nmme/organized/.

Output filenames embed "202607", so this does not collide with the
May ("202605") or June ("202606") organized files.

Run from project root:
    python scripts\\18_organize_nmme_july_init.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import xarray as xr


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import NMME_DIR
except Exception:
    NMME_DIR = PROJECT_ROOT / "data" / "nmme"

NMME_REALTIME_DIR = NMME_DIR / "realtime_anom" / "ENSMEAN" / "2026070800"
NMME_ORG_DIR = NMME_DIR / "organized"
NMME_ORG_DIR.mkdir(parents=True, exist_ok=True)

NMME_KEYWORDS_TO_ORGANIZE = ["prate", "tmpsfc", "tmp2m", "z200"]


def standardize_coordinate_names(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    for name in list(ds.coords) + list(ds.dims):
        lower = name.lower()
        if lower in ["latitude", "lat", "y"] and name != "lat" and "lat" not in ds.coords:
            rename[name] = "lat"
        if lower in ["longitude", "lon", "x"] and name != "lon" and "lon" not in ds.coords:
            rename[name] = "lon"
    return ds.rename(rename) if rename else ds


def standardize_longitude(ds):
    if "lon" not in ds.coords:
        return ds
    lon = ds["lon"]
    if float(lon.max()) > 180:
        ds = ds.assign_coords(lon=((lon + 180) % 360) - 180).sortby("lon")
    return ds


def choose_main_nmme_variable(ds: xr.Dataset) -> str | None:
    priority = ["prate", "tmpsfc", "tmp2m", "z200", "tmax", "tmin"]
    lower_map = {name.lower(): name for name in ds.data_vars}
    for p in priority:
        for lower_name, original_name in lower_map.items():
            if p in lower_name:
                return original_name
    return max(ds.data_vars, key=lambda x: ds[x].ndim) if ds.data_vars else None


def sanitize_name(text: str) -> str:
    return text.replace(".", "_").replace("-", "_").replace(" ", "_").replace("/", "_").replace("\\", "_")


def main():
    print("==================================================")
    print("Organize July 2026 NMME realtime anomaly fields")
    print("==================================================")
    print(f"Source: {NMME_REALTIME_DIR}")
    print(f"Output: {NMME_ORG_DIR}")

    if not NMME_REALTIME_DIR.exists():
        raise FileNotFoundError(f"Not found: {NMME_REALTIME_DIR}. Run 17_download_nmme_july_init.py first.")

    nc_files = sorted(NMME_REALTIME_DIR.glob("*.nc"))
    print(f"Found {len(nc_files)} files.")

    organized = []
    for nc_file in nc_files:
        lower_name = nc_file.name.lower()
        should_organize = nc_file.name.startswith("NMME.") and any(k in lower_name for k in NMME_KEYWORDS_TO_ORGANIZE)
        if not should_organize:
            continue

        ds = xr.open_dataset(nc_file, decode_times=False)
        ds = standardize_coordinate_names(ds)
        ds = standardize_longitude(ds)

        main_var = choose_main_nmme_variable(ds)
        if main_var is None:
            print(f"No usable variable in {nc_file.name}, skipping.")
            continue

        out_key = f"nmme_{sanitize_name(nc_file.stem)}"
        out_path = NMME_ORG_DIR / f"{out_key}.nc"

        da = ds[main_var].squeeze(drop=True)
        da.attrs["diagnostic_name"] = out_key
        da.attrs["source_file"] = str(nc_file)
        da.attrs["source_note"] = "CPC NMME realtime anomaly ENSMEAN file (July 2026 init)."

        out_ds = da.to_dataset(name=main_var)
        if out_path.exists():
            out_path.unlink()
        out_ds.to_netcdf(out_path)

        print(f"Saved organized NMME field: {out_path}")
        organized.append(out_path)
        ds.close()

    print(f"\nOrganized {len(organized)} fields into {NMME_ORG_DIR}")


if __name__ == "__main__":
    main()
