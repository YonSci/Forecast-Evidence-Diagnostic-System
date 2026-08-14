"""
28_generate_atmospheric_publication_figures.py

Purpose
-------
Publication-quality static figures for the 6 TEJ-consistency circulation
diagnostics (u200, u200_vectors, divergence200, omega500, qflux850,
mfc850) -- the report-style counterpart to the interactive Leaflet maps
in scripts/27_generate_atmospheric_leaflet_overlays.py, which are
full-bleed rasters with no title/axes/colorbar baked in by design.

This script instead produces cartopy/matplotlib figures meant to be
read as a standalone image: title/subtitle hierarchy, lat/lon gridlines
with tick labels, Ethiopia's border emphasized over every other
country's, a horizontal colorbar below the map with the same discrete
bins used in the interactive version (imported from script 27, so the
two never drift apart), and a source/metadata caption line. u200 also
gets labeled contour lines of the raw wind-speed field itself (its one
available field -- there's no per-2026-forecast u200 grid to treat as
"actual" against an "anomaly"), marking specific jet-strength
thresholds instead of relying on shading alone.

Two panels per figure, stacked:
    Panel A -- large-scale TEJ context (20W-100E, 20S-40N): South Asia
               across the Indian Ocean to Africa.
    Panel B -- Ethiopia-focused regional view (25E-55E, 0-20N): Sudan,
               South Sudan, Somalia, Kenya, Red Sea, Arabian Peninsula.

Explicitly not attempted here (no data for it): a three-panel
climatology/target/anomaly comparison, since none of these six fields
has a per-2026-forecast gridded counterpart to diff against -- what's
shown is the ERA5 1991-2020 climatology itself, labeled as such.

Outputs
-------
    outputs/maps/atmos_publication/<variable>/<variable>_<period>.png  (300 dpi)
    outputs/maps/atmos_publication/<variable>/<variable>_<period>.pdf  (vector)

Run from project root:
    python scripts\\28_generate_atmospheric_publication_figures.py
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "atmos_publication"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Reuse script 27's variable registry, loaders, and fixed discrete levels
# directly -- this script must never define its own color scale, or the
# interactive dashboard and the publication figure would silently drift
# apart on what "strong" vs "weak" means for the same field.
_spec = importlib.util.spec_from_file_location("s27", PROJECT_ROOT / "scripts" / "27_generate_atmospheric_leaflet_overlays.py")
s27 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s27)
s06 = s27.s06

PANEL_A_BOX = [-20, 100, -20, 40]   # large-scale TEJ context
PANEL_B_BOX = [25, 55, 0, 20]       # Ethiopia-focused regional view

PERIODS = s27.PERIODS
PERIOD_LABELS = {"Jun": "June", "Jul": "July", "Aug": "August", "Sep": "September", "JJA": "JJA", "JJAS": "JJAS"}

# Display metadata per variable: compact notation (matches the legend
# title used in the dashboard), full title, and an optional physical-
# meaning note for diverging fields. Kept in lockstep with
# AtmosphericEvidence.tsx's CIRCULATION_MAPS by hand -- both describe
# the same six fields.
DISPLAY = {
    "u200": {
        "notation": "u₂₀₀",
        "title": "200-hPa Zonal Wind",
        "note": "Negative: anomalously easterly → stronger TEJ.  Positive: westerly.",
        "contour_levels": [-40, -30, -20, -10],
    },
    "u200_vectors": {
        "notation": "Wind speed",
        "title": "200-hPa Wind Vectors",
        "note": "Arrows show direction; shading shows speed.",
        "contour_levels": None,
    },
    "divergence200": {
        "notation": "∇·V₂₀₀",
        "title": "200-hPa Divergence",
        "note": "Negative: convergence.  Positive: divergence (favorable upper-level outflow).",
        "contour_levels": None,
    },
    "omega500": {
        "notation": "ω₅₀₀",
        "title": "500-hPa Vertical Velocity",
        "note": "Negative: forced ascent.  Positive: subsidence.",
        "contour_levels": None,
    },
    "qflux850": {
        "notation": "qV₈₅₀",
        "title": "850-hPa Moisture Flux",
        "note": "Arrows show transport direction; shading shows flux magnitude.",
        "contour_levels": None,
    },
    "mfc850": {
        "notation": "MFC₈₅₀",
        "title": "850-hPa Moisture-Flux Convergence",
        "note": "Negative: divergence.  Positive: convergence (moisture accumulating).",
        "contour_levels": None,
    },
}


@lru_cache(maxsize=1)
def ethiopia_geometry():
    shp = shpreader.natural_earth(resolution="10m", category="cultural", name="admin_0_countries")
    for rec in shpreader.Reader(shp).records():
        if rec.attributes.get("NAME") == "Ethiopia":
            return rec.geometry
    return None


def add_map_features(ax, box, draw_labels: bool) -> None:
    ax.set_extent(box, crs=ccrs.PlateCarree())
    ax.coastlines(linewidth=0.6, color="#444444")
    ax.add_feature(cfeature.BORDERS, linewidth=0.4, edgecolor="#777777")

    geom = ethiopia_geometry()
    if geom is not None:
        ax.add_geometries(
            [geom], ccrs.PlateCarree(),
            facecolor="none", edgecolor="#0a0a0a", linewidth=1.6, zorder=5,
        )

    gl = ax.gridlines(draw_labels=draw_labels, linewidth=0.35, linestyle="--", alpha=0.4, color="gray")
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 8}
    gl.ylabel_style = {"size": 8}


def render_panel(
    ax, da_2d, box, cmap, levels,
    quiver=None, contour_levels=None, panel_label: str = "",
):
    lon, lat = da_2d["lon"].values, da_2d["lat"].values
    data = np.clip(da_2d.values, levels[0], levels[-1])
    norm = BoundaryNorm(levels, ncolors=256)

    mesh = ax.pcolormesh(
        lon, lat, data, cmap=cmap, norm=norm, shading="auto", transform=ccrs.PlateCarree(),
    )

    if quiver is not None:
        u, v = quiver
        lon2d, lat2d = np.meshgrid(lon, lat)
        nlat, nlon = len(lat), len(lon)
        stride_lat = max(1, nlat // 20)
        stride_lon = max(1, nlon // 26)
        sl = (slice(None, None, stride_lat), slice(None, None, stride_lon))
        mag = np.sqrt(u.values**2 + v.values**2)
        typical = float(np.nanpercentile(mag, 90))
        typical = typical if np.isfinite(typical) and typical > 0 else 1.0
        ax.quiver(
            lon2d[sl], lat2d[sl], u.values[sl], v.values[sl],
            color="black", scale=typical / 0.045, scale_units="width",
            width=0.0022, alpha=0.85, transform=ccrs.PlateCarree(),
        )

    if contour_levels is not None:
        cs = ax.contour(
            lon, lat, da_2d.values, levels=contour_levels,
            colors="black", linewidths=0.8, transform=ccrs.PlateCarree(),
        )
        ax.clabel(cs, inline=True, fontsize=7, fmt="%g")

    add_map_features(ax, box, draw_labels=True)
    ax.text(
        0.015, 0.965, panel_label, transform=ax.transAxes, fontsize=10, fontweight="bold",
        va="top", ha="left", bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.75),
    )
    return mesh


def plot_publication_figure(var_key: str, period: str) -> None:
    cfg = s27.VARIABLES[var_key]
    disp = DISPLAY[var_key]

    da_full = cfg["loader"](period)
    if da_full is None:
        print(f"Skipping {var_key}/{period}: source file missing")
        return

    quiver_full = None
    if cfg["vector_loader"] is not None:
        uv = cfg["vector_loader"](period)
        if uv is not None:
            quiver_full = uv

    def subset_for(box):
        da = s06.subset_box(da_full, s27.clamp_box_lat(box)).squeeze(drop=True)
        if "lat" in da.dims and "lon" in da.dims:
            da = da.transpose("lat", "lon")
        q = None
        if quiver_full is not None:
            u, v = quiver_full
            u = s06.subset_box(u, s27.clamp_box_lat(box)).squeeze(drop=True)
            v = s06.subset_box(v, s27.clamp_box_lat(box)).squeeze(drop=True)
            if "lat" in u.dims and "lon" in u.dims:
                u, v = u.transpose("lat", "lon"), v.transpose("lat", "lon")
            q = (u, v)
        return da, q

    da_a, quiver_a = subset_for(PANEL_A_BOX)
    da_b, quiver_b = subset_for(PANEL_B_BOX)

    fig = plt.figure(figsize=(10, 12.5))
    # top/bottom reserve fixed bands for the 3-line title block and the
    # caption line respectively, so text() calls placed above/below the
    # gridspec never overlap the axes or each other regardless of font size.
    gs = fig.add_gridspec(3, 1, height_ratios=[1.35, 1, 0.06], hspace=0.3, top=0.87, bottom=0.05)
    ax_a = fig.add_subplot(gs[0], projection=ccrs.PlateCarree())
    ax_b = fig.add_subplot(gs[1], projection=ccrs.PlateCarree())
    cax = fig.add_subplot(gs[2])

    render_panel(
        ax_a, da_a, PANEL_A_BOX, cfg["cmap"], cfg["levels"],
        quiver=quiver_a, contour_levels=disp["contour_levels"],
        panel_label="A — Large-scale TEJ context",
    )
    mesh = render_panel(
        ax_b, da_b, PANEL_B_BOX, cfg["cmap"], cfg["levels"],
        quiver=quiver_b, contour_levels=disp["contour_levels"],
        panel_label="B — Ethiopia focus",
    )

    cbar = fig.colorbar(mesh, cax=cax, orientation="horizontal")
    cbar.set_label(f"{disp['notation']} ({cfg['unit']})", fontsize=10)
    cbar.ax.tick_params(labelsize=8)

    period_label = PERIOD_LABELS[period]
    fig.text(
        0.5, 0.975, f"{period_label} {disp['notation']} ({cfg['unit']}) — ERA5",
        fontsize=15, fontweight="bold", ha="center", va="top",
    )
    fig.text(
        0.5, 0.94, f"{disp['title']}  |  Relative period: 1991–2020 climatology",
        fontsize=10.5, ha="center", va="top", color="#333333",
    )
    fig.text(0.5, 0.915, disp["note"], fontsize=8.5, ha="center", va="top", color="#555555", style="italic")

    fig.text(
        0.5, 0.012,
        f"Data: ERA5  ·  Reference: 1991–2020  ·  Aggregation: {period_label} mean  ·  "
        f"Resolution: 0.25°  ·  Variable: {disp['title']}",
        fontsize=7.5, ha="center", va="bottom", color="#666666",
    )

    out_dir = OUT_DIR / var_key
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{var_key}_{period}.png"
    pdf_path = out_dir / f"{var_key}_{period}.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {png_path.name} + {pdf_path.name}")


def main():
    print("==================================================")
    print("Generate atmospheric publication figures")
    print("==================================================")
    for var_key in s27.VARIABLES:
        for period in PERIODS:
            plot_publication_figure(var_key, period)
    print(f"\nOutput folder: {OUT_DIR}")


if __name__ == "__main__":
    main()
