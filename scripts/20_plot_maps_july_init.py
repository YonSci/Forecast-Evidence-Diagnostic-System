"""
20_plot_maps_july_init.py

Purpose
-------
Plot NMME precipitation-anomaly maps for the July 2026 initialization,
for the periods actually available from that cycle: Aug, Sep, and AS
(Aug-Sep). July, JJA, JAS, and JJAS are not produced -- see
19_compute_anomalies_july_init.py for why.

Inputs:
    outputs/netcdf/nmme_anomalies_july_init/NMME_prate_*_total_anomaly_*.nc

Outputs:
    outputs/maps/dynamic_diagnostics_july_init/prate_<region>_<period>.png

Same diverging ochre (dry) <-> teal (wet) color convention as the rest
of the project.

Run from project root:
    python scripts\\20_plot_maps_july_init.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
import cartopy.crs as ccrs
import cartopy.feature as cfeature


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NC_DIR = PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_july_init"
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "dynamic_diagnostics_july_init"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CMAP = LinearSegmentedColormap.from_list(
    "dry_wet", ["#8a3a1c", "#c2703f", "#e8b691", "#f5f1ea", "#a9d6cf", "#3fa89a", "#0f5f57"]
)

REGIONS = {
    "ethiopia":     {"box": [30, 50, 1, 17],   "label": "Ethiopia",              "figsize": (6.4, 6.4), "central_lon": 40},
    "greater_horn": {"box": [18, 57, -17, 27], "label": "Greater Horn of Africa", "figsize": (7.2, 7.2), "central_lon": 37},
    "africa":       {"box": [-24, 56, -37, 40],"label": "Africa",                "figsize": (7.2, 7.6), "central_lon": 15},
    "global":       {"box": [-180, 180, -90, 90], "label": "Global",             "figsize": (9.6, 5.2), "central_lon": 20},
}

JOBS = [
    ("Aug", "NMME_prate_Aug_2026_total_anomaly_mm_month.nc", "prate_Aug_2026_total_mm_month", "mm/month", "August 2026"),
    ("Sep", "NMME_prate_Sep_2026_total_anomaly_mm_month.nc", "prate_Sep_2026_total_mm_month", "mm/month", "September 2026"),
    ("AS",  "NMME_prate_AS_2026_total_anomaly_mm_season.nc", "prate_AS_2026_total_mm_season", "mm/season","Aug-Sep 2026 (AS)"),
]


def area_sub(da, box):
    lon_min, lon_max, lat_min, lat_max = box
    lat = da["lat"].values
    lat_slice = slice(lat_min, lat_max) if lat[0] < lat[-1] else slice(lat_max, lat_min)
    return da.sel(lat=lat_slice, lon=slice(lon_min, lon_max))


def main():
    print("==================================================")
    print("Plot NMME precipitation-anomaly maps -- July 2026 init")
    print("==================================================")

    written = []
    for period, fname, varname, unit, plabel in JOBS:
        path = NC_DIR / fname
        if not path.exists():
            print(f"Missing: {path}, skipping.")
            continue

        ds = xr.open_dataset(path, decode_times=False)
        da_full = ds[varname]

        for region, meta in REGIONS.items():
            da = area_sub(da_full, meta["box"])
            vmax = max(float(np.nanpercentile(np.abs(da.values), 98)), 1e-6)
            norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

            proj = ccrs.PlateCarree(central_longitude=meta["central_lon"])
            fig = plt.figure(figsize=meta["figsize"], dpi=150, facecolor="white")
            ax = plt.axes(projection=proj)
            ax.set_extent(meta["box"], crs=ccrs.PlateCarree())
            mesh = ax.pcolormesh(da["lon"], da["lat"], da.values, transform=ccrs.PlateCarree(),
                                  cmap=CMAP, norm=norm, shading="auto")
            ax.add_feature(cfeature.COASTLINE, linewidth=0.6, edgecolor="#2b2b28")
            ax.add_feature(cfeature.BORDERS, linewidth=0.35, edgecolor="#6b6b66", alpha=0.7)
            gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="#999", alpha=0.4, linestyle="--")
            gl.top_labels = False
            gl.right_labels = False
            gl.xlabel_style = {"size": 8, "color": "#555"}
            gl.ylabel_style = {"size": 8, "color": "#555"}

            cbar = plt.colorbar(mesh, ax=ax, orientation="horizontal", pad=0.07, shrink=0.85, extend="both")
            cbar.set_label(f"Precipitation anomaly ({unit})", fontsize=9, color="#333")
            cbar.ax.tick_params(labelsize=8, color="#333")

            ax.set_title(f"NMME ensemble-mean precipitation anomaly — {meta['label']} — {plabel}",
                         fontsize=10.5, color="#111", pad=10)
            fig.text(0.5, 0.015, "CPC NMME ENSMEAN · initialized 2026-07-08 00Z · below normal (ochre) / above normal (teal)",
                      ha="center", fontsize=7.3, color="#666")

            out_path = OUT_DIR / f"prate_{region}_{period}.png"
            fig.savefig(out_path, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            written.append(out_path)
            print(f"Saved: {out_path}")

        ds.close()

    print(f"\nWrote {len(written)} maps to {OUT_DIR}")


if __name__ == "__main__":
    main()
