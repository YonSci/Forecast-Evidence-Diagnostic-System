"""
22_generate_leaflet_overlay_maps.py

Purpose
-------
Generate "clean" precipitation-anomaly raster images for use as real
react-leaflet <ImageOverlay> layers -- full-bleed, no title/colorbar/axis
labels/footer baked into the pixels, in plain equirectangular (PlateCarree,
central_longitude=0) projection so the image's four corners map linearly
onto the same [lon_min, lon_max, lat_min, lat_max] box used for the
region's area-mean statistics.

This is different from scripts 06/11/16/20, which render report-style
figures (title, colorbar, footer) meant to be viewed as static images.
Those stay as-is for the dashboard's map gallery. This script produces the
raster-only counterpart specifically for interactive Leaflet overlays,
where the legend/title/scale are rendered as separate UI elements around
the map, not inside the image.

Covers every (initialization, region, period) combination already
computed by scripts 04/21 (May), 15 (June), and 19 (July).

Outputs
-------
    outputs/maps/leaflet_overlays/<init>/prate_<region>_<period>.png
    outputs/maps/leaflet_overlays/overlay_index.json
        { "<init>/<region>/<period>": {file, bounds:[[latmin,lonmin],[latmax,lonmax]],
                                          vmin, vmax, unit, value_domain} }

Run from project root:
    python scripts\\22_generate_leaflet_overlay_maps.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "leaflet_overlays"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CMAP = LinearSegmentedColormap.from_list(
    "dry_wet", ["#8a3a1c", "#c2703f", "#e8b691", "#f5f1ea", "#a9d6cf", "#3fa89a", "#0f5f57"]
)

REGIONS = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "africa": [-20, 52, -35, 38],
    "global": [-180, 180, -90, 90],
}

# (init_key, netcdf_dir, {period: (filename, varname, unit, is_seasonal)})
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


def render_overlay(da, box, out_path: Path) -> tuple[float, float]:
    lon_min, lon_max, lat_min, lat_max = box
    vmax = max(float(np.nanpercentile(np.abs(da.values), 98)), 1e-6)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    width_deg = lon_max - lon_min
    height_deg = lat_max - lat_min
    # target ~110 px/deg on the long side, capped so global renders don't balloon
    px_per_deg = min(110, 1600 / max(width_deg, height_deg))
    fig_w, fig_h = width_deg * px_per_deg / 100, height_deg * px_per_deg / 100

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.axis("off")
    ax.pcolormesh(da["lon"], da["lat"], da.values, cmap=CMAP, norm=norm, shading="auto")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, transparent=True)
    plt.close(fig)
    return -vmax, vmax


def main():
    print("==================================================")
    print("Generate clean Leaflet ImageOverlay rasters")
    print("==================================================")

    index = {}
    written = 0

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
                da = area_sub(da_full, box)
                out_path = OUT_DIR / init_key / f"prate_{region}_{period}.png"
                vmin, vmax = render_overlay(da, box, out_path)

                lon_min, lon_max, lat_min, lat_max = box
                key = f"{init_key}/{region}/{period}"
                index[key] = {
                    "file": f"{init_key}/prate_{region}_{period}.png",
                    "bounds": [[lat_min, lon_min], [lat_max, lon_max]],
                    "vmin": round(vmin, 4),
                    "vmax": round(vmax, 4),
                    "unit": unit,
                }
                written += 1
                print(f"Saved: {out_path}")
            ds.close()

    index_path = OUT_DIR / "overlay_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"\nWrote {written} overlay images and {index_path}")


if __name__ == "__main__":
    main()
