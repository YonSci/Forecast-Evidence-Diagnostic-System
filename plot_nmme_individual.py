"""
plot_nmme_individual.py

Reads NMME ensemble-mean precipitation anomaly NetCDF files
(downloaded by download_nmme.py) and renders:
  1. panel : one PNG per lead, all N models side by side
  2. single: one PNG per (model, lead)
  3. spread: one PNG per lead showing all models + ensemble mean

Usage:
    python plot_nmme_individual.py
    python plot_nmme_individual.py --init 2026050800
    python plot_nmme_individual.py --leads 1 2 3 4 --mode panel
    python plot_nmme_individual.py --mode single --models CFSv2 CanESM5
"""

import argparse
import math
import os

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
import cartopy.crs as ccrs
import cartopy.feature as cfeature


DEFAULT_MODELS = [
    "CanESM5", "CFSv2", "NASA_GEOS5v2",
    "NCAR_CCSM4", "NCAR_CESM1", "GEM5.2_NEMO",
]
DEFAULT_INIT = "2026050800"
INIT_TARGET_VALUE = 796   # May 2026 in NMME months-since-1960 axis

# ---- tropicaltidbits-style color scale ----
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


# ---- Data loaders ----
def load_model(model, target_lead, data_dir, init):
    """Load a single model's anomaly field, in mm/month."""
    yyyymm = init[:6]
    path = os.path.join(data_dir, f"{model}.prate.{yyyymm}.ENSMEAN.anom.nc")
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing {os.path.basename(path)}")
    ds = xr.open_dataset(path, decode_times=False)
    target_val = INIT_TARGET_VALUE + target_lead
    if target_val not in ds["target"].values:
        ds.close()
        raise ValueError(f"{model}: target {target_val} not in file")
    v = ds["fcst"].sel(target=target_val).values  # mm/s
    v_mm = v * 86400.0 * 30.44                    # mm/month
    lats = ds["lat"].values
    lons = ds["lon"].values
    ds.close()
    if lats[0] > lats[-1]:
        lats = lats[::-1]
        v_mm = v_mm[::-1, :]
    return v_mm, lats, lons


def load_ensemble_mean(target_lead, data_dir, init, models):
    accum = None
    lats = lons = None
    n = 0
    for m in models:
        try:
            v, lats, lons = load_model(m, target_lead, data_dir, init)
        except (FileNotFoundError, ValueError) as e:
            print(f"  WARNING: {e}")
            continue
        accum = v if accum is None else accum + v
        n += 1
    if n == 0:
        raise RuntimeError("No models loaded.")
    return accum / n, lats, lons, n


# ---- Map drawing helper ----
def draw_map(ax, V, lats, lons, title, cmap, norm, title_color='#1a3a6b'):
    proj = ccrs.PlateCarree()
    ax.set_extent([30, 140, -30, 40], crs=proj)
    LON, LAT = np.meshgrid(lons, lats)
    mesh = ax.pcolormesh(LON, LAT, V, cmap=cmap, norm=norm,
                         shading='auto', transform=proj)
    ax.coastlines(linewidth=0.5, color='black', resolution='110m')
    ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor='black')
    ax.set_title(title, fontsize=10, fontweight='bold',
                 color=title_color, loc='left')
    for lo in range(30, 141, 30):
        ax.text(lo, -30.5, f"{lo}°E", transform=proj, fontsize=6,
                ha='center', va='top', color='#333')
    for la in range(-30, 41, 15):
        ax.text(30.5, la, f"{abs(la)}°{'N' if la>=0 else 'S'}",
                transform=proj, fontsize=6, ha='left', va='center', color='#333')
    return mesh


# ---- Plot type 1: per-lead multi-panel (all models) ----
def plot_models_for_month(target_lead, valid_label, data_dir, init,
                          models, outpath, cmap, norm, vals_arr):
    n_models = len(models)
    n_cols = 3
    n_rows = math.ceil(n_models / n_cols)
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(5.5 * n_cols, 4.0 * n_rows),
        subplot_kw={'projection': ccrs.PlateCarree()})
    axes = np.atleast_2d(axes).reshape(n_rows, n_cols)

    fig.suptitle(
        f"NMME Individual Models — Precip Anomaly (mm) — {valid_label}  "
        f"|  Init: 00z {init[6:8]} {init[4:6]} {init[:4]}",
        fontsize=14, fontweight='bold', color='#1a3a6b', y=0.995)

    for i, m in enumerate(models):
        r, c = divmod(i, n_cols)
        ax = axes[r, c]
        try:
            V, lats, lons = load_model(m, target_lead, data_dir, init)
            draw_map(ax, V, lats, lons, m, cmap, norm)
        except (FileNotFoundError, ValueError) as e:
            ax.text(0.5, 0.5, str(e), transform=ax.transAxes,
                    ha='center', va='center', fontsize=8, color='red')
            ax.set_xticks([]); ax.set_yticks([])

    for j in range(n_models, n_rows * n_cols):
        r, c = divmod(j, n_cols)
        axes[r, c].axis('off')

    cax = fig.add_axes([0.93, 0.10, 0.012, 0.80])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
    cb = plt.colorbar(sm, cax=cax, ticks=vals_arr)
    cb.ax.set_yticklabels([str(int(v)) for v in vals_arr], fontsize=7)
    cb.set_label('mm', fontsize=8, rotation=0, labelpad=10, y=1.04)

    plt.subplots_adjust(left=0.02, right=0.91, top=0.94, bottom=0.04,
                        wspace=0.05, hspace=0.18)
    plt.savefig(outpath, dpi=140, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  saved {outpath}")


# ---- Plot type 2: single model, single lead ----
def plot_single_model(model, target_lead, valid_label, data_dir, init,
                      outpath, cmap, norm, vals_arr):
    fig = plt.figure(figsize=(11, 6.4), dpi=150)
    proj = ccrs.PlateCarree()
    ax = fig.add_axes([0.02, 0.06, 0.86, 0.84], projection=proj)
    V, lats, lons = load_model(model, target_lead, data_dir, init)
    mesh = draw_map(ax, V, lats, lons,
                    f"{model} — {valid_label}", cmap, norm)

    fig.text(0.02, 0.965,
             f"NMME {model} — Precipitation Anomaly (mm)",
             fontsize=11, fontweight='bold', color='#1a3a6b')
    fig.text(0.50, 0.965, f"Valid for: {valid_label}",
             fontsize=10, color='#333')
    fig.text(0.78, 0.965, "TROPICALTIDBITS.COM",
             fontsize=9, color='#666', ha='left', style='italic')
    init_label = f"Init: 00z {init[6:8]} {init[4:6]} {init[:4]}"
    fig.text(0.02, 0.935, init_label,
             fontsize=9, color='#333', fontweight='bold')

    cax = fig.add_axes([0.895, 0.10, 0.018, 0.78])
    cb = plt.colorbar(mesh, cax=cax, ticks=vals_arr)
    cb.ax.set_yticklabels([str(int(v)) for v in vals_arr], fontsize=7)
    plt.savefig(outpath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  saved {outpath}  (min={V.min():.1f} max={V.max():.1f} mm)")


# ---- Plot type 3: model spread (per lead, all models + ensemble mean) ----
def plot_spread(target_lead, valid_label, data_dir, init, models,
                outpath, cmap, norm, vals_arr):
    n_models = len(models)
    n_panels = n_models + 1   # +1 for ensemble mean
    n_cols = min(4, n_panels)
    n_rows = math.ceil(n_panels / n_cols)
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(5.0 * n_cols, 3.8 * n_rows),
        subplot_kw={'projection': ccrs.PlateCarree()})
    axes = np.atleast_2d(axes).reshape(n_rows, n_cols)

    fig.suptitle(
        f"NMME Model Spread + Ensemble Mean — {valid_label}  "
        f"|  Init: 00z {init[6:8]} {init[4:6]} {init[:4]}",
        fontsize=14, fontweight='bold', color='#1a3a6b', y=0.995)

    n_used = 0
    for i, m in enumerate(models):
        r, c = divmod(i, n_cols)
        ax = axes[r, c]
        try:
            V, lats, lons = load_model(m, target_lead, data_dir, init)
            draw_map(ax, V, lats, lons, m, cmap, norm)
            n_used += 1
        except (FileNotFoundError, ValueError) as e:
            ax.text(0.5, 0.5, str(e), transform=ax.transAxes,
                    ha='center', va='center', fontsize=8, color='red')
    # Ensemble mean
    r, c = divmod(n_models, n_cols)
    Vm, lats, lons, n_ens = load_ensemble_mean(
        target_lead, data_dir, init, models)
    draw_map(axes[r, c], Vm, lats, lons,
             f"ENSEMBLE MEAN ({n_ens} models)", cmap, norm,
             title_color='#a30000')

    for j in range(n_panels, n_rows * n_cols):
        r, c = divmod(j, n_cols)
        axes[r, c].axis('off')

    cax = fig.add_axes([0.93, 0.10, 0.012, 0.80])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
    cb = plt.colorbar(sm, cax=cax, ticks=vals_arr)
    cb.ax.set_yticklabels([str(int(v)) for v in vals_arr], fontsize=7)
    cb.set_label('mm', fontsize=8, rotation=0, labelpad=10, y=1.04)

    plt.subplots_adjust(left=0.02, right=0.91, top=0.94, bottom=0.04,
                        wspace=0.05, hspace=0.18)
    plt.savefig(outpath, dpi=140, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  saved {outpath}")


# ---- CLI ----
def main():
    p = argparse.ArgumentParser(
        description="Plot individual NMME model precipitation anomaly maps."
    )
    p.add_argument("--init", default=DEFAULT_INIT)
    p.add_argument("--data-dir", default="./nmme_data")
    p.add_argument("--out-dir", default="./nmme_plots_individual")
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    p.add_argument("--leads", nargs="+", type=int, default=[1, 2, 3, 4],
                   help="Lead indices to plot (1=Jun, 2=Jul, ...)")
    p.add_argument("--mode", choices=["panel", "single", "spread", "all"],
                   default="all",
                   help="panel = one PNG per lead (all models). "
                        "single = one PNG per (model, lead). "
                        "spread = one PNG per lead (models + ENSMEAN). "
                        "all = run all three.")
    args = p.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    cmap, norm, vals_arr = build_colormap()

    print(f"=== Individual NMME plots (init {args.init}) ===")
    print(f"  data   : {args.data_dir}")
    print(f"  out    : {args.out_dir}")
    print(f"  models : {', '.join(args.models)}")
    print(f"  mode   : {args.mode}")
    print()

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    init_year = int(args.init[:4])
    init_month = int(args.init[4:6])  # 1-12

    def label_for(lead):
        m_idx = (init_month - 1 + lead) % 12
        y = init_year + (init_month - 1 + lead) // 12
        return f"{month_names[m_idx]} {y}"

    def fname(prefix, lead, model=None):
        lbl = label_for(lead).replace(' ', '_').lower()
        if model:
            return os.path.join(args.out_dir,
                                f"{prefix}_{args.init[:6]}_lead{lead:02d}_{lbl}_{model}.png")
        return os.path.join(args.out_dir,
                            f"{prefix}_{args.init[:6]}_lead{lead:02d}_{lbl}.png")

    modes = ["panel", "single", "spread"] if args.mode == "all" else [args.mode]

    for lead in args.leads:
        valid = label_for(lead)
        if "panel" in modes:
            plot_models_for_month(lead, valid, args.data_dir, args.init,
                                  args.models, fname("panel", lead),
                                  cmap, norm, vals_arr)
        if "spread" in modes:
            plot_spread(lead, valid, args.data_dir, args.init, args.models,
                        fname("spread", lead), cmap, norm, vals_arr)
        if "single" in modes:
            for m in args.models:
                plot_single_model(m, lead, valid, args.data_dir, args.init,
                                  fname("single", lead, m),
                                  cmap, norm, vals_arr)
    print("\nDone.")


if __name__ == "__main__":
    main()
