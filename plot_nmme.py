"""
plot_nmme.py

Reads NMME ensemble-mean precipitation anomaly NetCDF files
(downloaded by download_nmme.py) and renders monthly maps
in tropicaltidbits style.

Usage:
    python plot_nmme.py
    python plot_nmme.py --init 2026050800
    python plot_nmme.py --data-dir ./nmme_data --out-dir ./my_plots
    python plot_nmme.py --leads 1 2 3 4 --labels "Jun 2026" "Jul 2026" ...
"""

import argparse
import os
import sys

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
import cartopy.crs as ccrs
import cartopy.feature as cfeature


# Default 6 operational NMME v2 models
DEFAULT_MODELS = [
    "CanESM5",
    "CFSv2",
    "NASA_GEOS5v2",
    "NCAR_CCSM4",
    "NCAR_CESM1",
    "GEM5.2_NEMO",
]

DEFAULT_INIT = "2026050800"  # 00z May 8 2026

# 796 = months since 1960-01 for May 2026 (NMME target-axis encoding)
INIT_TARGET_VALUE = 796


# ---------------- Color scale (tropicaltidbits NMME look) ----------------
ANOM_STOPS = [
    (-500,'#7a1d1d'),(-300,'#9a3a1a'),(-200,'#b04a1a'),(-125,'#c6641f'),
    ( -75,'#d99a3a'),( -40,'#e7c66a'),( -20,'#f1e0a0'),(  -5,'#fbf3d4'),
    (   0,'#ffffff'),(   5,'#e7f1d0'),(  20,'#c8e0a2'),(  40,'#9bcb73'),
    (  75,'#6cb04a'),( 125,'#3f9536'),( 200,'#1f7a36'),( 300,'#15607a'),
    ( 400,'#234a8c'),( 500,'#5a2a8a'),
]
def build_colormap():
    vals = np.array([s[0] for s in ANOM_STOPS])
    cols = [s[1] for s in ANOM_STOPS]
    cmap = LinearSegmentedColormap.from_list(
        "nmme_anom", list(zip((vals + 500) / 1000, cols)), N=512)
    norm = BoundaryNorm(vals, cmap.N, extend='both')
    return cmap, norm, vals


# ---------------- Data loading ----------------
def load_ensemble_mean(target_lead: int, data_dir: str,
                       init: str, models: list):
    """
    Average all available model files for the given target lead month.
    Returns:
        V (lat, lon) - mm anomaly for that month
        lats, lons   - 1-D coord arrays
        n_used       - how many models contributed
    """
    yyyymm = init[:6]
    accum = None
    lats = lons = None
    n_used = 0
    target_val = INIT_TARGET_VALUE + target_lead

    for m in models:
        path = os.path.join(data_dir, f"{m}.prate.{yyyymm}.ENSMEAN.anom.nc")
        if not os.path.exists(path):
            print(f"  WARNING: {m} missing, skipping")
            continue
        ds = xr.open_dataset(path, decode_times=False)
        if target_val not in ds["target"].values:
            print(f"  WARNING: {m} has no target {target_val}")
            ds.close()
            continue
        v = ds["fcst"].sel(target=target_val).values  # mm/s
        v_mm = v * 86400.0 * 30.44                    # mm/month
        if accum is None:
            accum = v_mm
            lats = ds["lat"].values
            lons = ds["lon"].values
        else:
            accum = accum + v_mm
        n_used += 1
        ds.close()

    if n_used == 0:
        raise RuntimeError("No models loaded.")
    return accum / n_used, lats, lons, n_used


# ---------------- Plotting ----------------
def plot_month(target_lead, valid_label, banner, banner_sub,
               outpath, data_dir, init, models, cmap, norm, vals_arr):
    V, lats, lons, n_used = load_ensemble_mean(
        target_lead, data_dir, init, models)

    # Some files store lats descending; flip so cartopy is happy
    if lats[0] > lats[-1]:
        lats = lats[::-1]
        V = V[::-1, :]

    fig = plt.figure(figsize=(11, 6.4), dpi=150)
    proj = ccrs.PlateCarree()
    ax = fig.add_axes([0.02, 0.06, 0.86, 0.84], projection=proj)
    ax.set_extent([30, 140, -30, 40], crs=proj)

    LON, LAT = np.meshgrid(lons, lats)
    mesh = ax.pcolormesh(LON, LAT, V, cmap=cmap, norm=norm,
                         shading='auto', transform=proj)

    ax.coastlines(linewidth=0.7, color='black', resolution='110m')
    ax.add_feature(cfeature.BORDERS, linewidth=0.4, edgecolor='black')
    ax.add_feature(cfeature.LAND, facecolor='none', edgecolor='black', linewidth=0.3)

    for lo in range(30, 141, 30):
        ax.text(lo, -30.5, f"{lo}°E", transform=proj, fontsize=8,
                ha='center', va='top', color='#222')
    for la in range(-30, 41, 15):
        ax.text(30.5, la, f"{abs(la)}°{'N' if la>=0 else 'S'}",
                transform=proj, fontsize=8, ha='left', va='center', color='#222')

    # Header strip
    fig.text(0.02, 0.965,
             "NMME Total Accumulated Precipitation Anomaly (mm)",
             fontsize=11, fontweight='bold', color='#1a3a6b')
    fig.text(0.45, 0.965, f"Valid for: {valid_label}",
             fontsize=10, color='#333')
    fig.text(0.78, 0.965, "TROPICALTIDBITS.COM",
             fontsize=9, color='#666', ha='left', style='italic')
    init_label = f"Init: 00z {init[6:8]} {init[4:6]} {init[:4]}"
    fig.text(0.02, 0.935, init_label,
             fontsize=9, color='#333', fontweight='bold')

    # Colorbar
    cax = fig.add_axes([0.895, 0.10, 0.018, 0.78])
    cb = plt.colorbar(mesh, cax=cax, ticks=vals_arr)
    cb.ax.set_yticklabels([str(int(v)) for v in vals_arr], fontsize=7)
    cb.outline.set_linewidth(0.5)

    # Watermark
    fig.text(0.86, 0.085,
             "WEATHER PATTERN DYNAMICS AGROMETEOROLOGY",
             fontsize=7.5, color='#5a4a1a', fontweight='bold',
             ha='right', style='italic')

    # Yellow banner
    fig.text(0.5, 0.025, banner, ha='center', va='center',
             fontsize=11.5, fontweight='bold', color='#1a1a1a',
             bbox=dict(boxstyle="round,pad=0.4", facecolor='#d8c878',
                       edgecolor='#a8943a', linewidth=0.8))
    if banner_sub:
        fig.text(0.5, -0.01, banner_sub, ha='center', va='center',
                 fontsize=8, color='#3a2a10', style='italic')

    plt.savefig(outpath, dpi=150, bbox_inches='tight',
                facecolor='white', pad_inches=0.1)
    plt.close(fig)
    print(f"  saved {outpath}  ({n_used} models, "
          f"min={V.min():.1f} max={V.max():.1f} mm)")


# ---------------- CLI ----------------
def main():
    p = argparse.ArgumentParser(
        description="Plot NMME precipitation anomaly maps from "
                    "pre-downloaded NetCDF files."
    )
    p.add_argument("--init", default=DEFAULT_INIT,
                   help="Initialization tag, e.g. 2026050800 "
                        "(default: %(default)s)")
    p.add_argument("--data-dir", default="./nmme_data",
                   help="Directory holding downloaded .nc files "
                        "(default: ./nmme_data)")
    p.add_argument("--out-dir", default="./nmme_plots",
                   help="Output directory for PNGs (default: ./nmme_plots)")
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                   help="Models to include in ensemble mean "
                        "(default: %(default)s)")
    p.add_argument(
        "--leads", nargs="+", type=int, default=[1, 2, 3, 4],
        help="Target lead indices (1=Jun, 2=Jul, ...) "
             "(default: 1 2 3 4)"
    )
    p.add_argument(
        "--labels", nargs="+", default=None,
        help="Optional labels for each lead, e.g. 'Jun 2026' 'Jul 2026' ..."
    )
    p.add_argument(
        "--banners", nargs="+", default=None,
        help="Optional banner text for each lead (use \\n for line breaks)."
    )
    p.add_argument(
        "--banner-subs", nargs="+", default=None,
        help="Optional sub-banner text for each lead."
    )
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    n = len(args.leads)
    if args.labels is None:
        args.labels = [f"Lead {l}" for l in args.leads]
    if args.banners is None:
        args.banners = [""] * n
    if args.banner_subs is None:
        args.banner_subs = [""] * n
    assert len(args.labels) == n
    assert len(args.banners) == n
    assert len(args.banner_subs) == n

    cmap, norm, vals_arr = build_colormap()

    print(f"=== Plotting NMME anomalies (init {args.init}) ===")
    print(f"  data   : {args.data_dir}")
    print(f"  out    : {args.out_dir}")
    print(f"  models : {', '.join(args.models)}")
    print(f"  leads  : {args.leads}")
    print()

    for lead, lbl, ban, sub in zip(
            args.leads, args.labels, args.banners, args.banner_subs):
        yyyymm = args.init[:6]
        lead_label = f"lead{lead:02d}_{lbl.replace(' ', '_').lower()}"
        outpath = os.path.join(args.out_dir,
                               f"nmme_{yyyymm}_{lead_label}.png")
        plot_month(lead, lbl, ban, sub, outpath,
                   args.data_dir, args.init, args.models,
                   cmap, norm, vals_arr)
    print("\nDone.")


if __name__ == "__main__":
    main()
