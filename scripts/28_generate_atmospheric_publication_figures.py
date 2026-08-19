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

u200 and u200_vectors additionally get a traced TEJ axis line (the
latitude of maximum 200 hPa wind speed at each longitude, restricted to
a tropical/subtropical band and to where that maximum is at least
15 m/s -- see compute_tej_axis()), so "where exactly is the jet core"
doesn't have to be read off the shading by eye.

u200 additionally gets a solid zero-contour line. This follows from
scripts/_cvd_check.py, a one-off simulation of protanopia/deuteranopia/
tritanopia on this script's actual discrete color bins (Coblis-style
matrices): the near-zero bins were consistently the least separable
pair under every simulated deficiency, for every diverging palette
tested -- an inherent property of any diverging colormap fading through
white at its center, not fixable by picking a different diverging
scheme without abandoning the (well-established elsewhere in this app)
blue=negative/red=positive convention. A shape cue (the zero line)
marks the sign boundary independent of hue for every viewer, not just
CVD ones. This is deliberately NOT applied to divergence200, omega500,
or mfc850 despite sharing the same CVD finding: those are small-scale
spatial-derivative fields, and their zero crossing turned out to be a
dense tangle of tiny closed contours (confirmed visually) rather than a
clean sign boundary like u200's smooth wind field -- it cluttered those
panels instead of clarifying them, so it's restricted to u200 only.

Also generates a second figure type: a climatology-vs-target comparison
(ERA5 1991-2020 climatology alongside the actual CFSv2 June-2026-init
forecast grid for the same variable/period, side by side, same fixed
color scale). scripts/09-10 already computed a full gridded CFSv2
forecast for these exact fields
(outputs/netcdf/cfsv2_dynamic_diagnostics/) -- previously unused by any
map, only collapsed to an area-mean scalar table. This is deliberately
NOT a three-panel climatology/target/anomaly figure: CFSv2 (operational
forecast) and ERA5 (reanalysis) are different modeling systems, so
diffing them isn't a like-for-like anomaly the way NMME's own
climatology-vs-forecast anomalies are elsewhere in this app -- there is
no CFSv2-own climatology in this project to diff against instead. The
two fields are shown side by side for qualitative comparison only, with
that caveat printed on the figure itself.

Outputs
-------
    outputs/maps/atmos_publication/<variable>/<variable>_<period>.png  (600 dpi)
    outputs/maps/atmos_publication/<variable>/<variable>_<period>.pdf  (vector)
    outputs/maps/atmos_publication/<variable>/<variable>_<period>.svg  (vector)
    outputs/maps/atmos_publication_comparison/<variable>/<variable>_<period>_comparison.{png,pdf,svg}

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

# Same two boxes script 27 generates the dashboard's "large"/"regional"
# scope overlays from -- shared from there (not redefined here) so the
# publication dual-panel figure and the dashboard scope toggle always
# agree on what "large-scale" and "regional" mean.
PANEL_A_BOX = s27.LARGE_SCALE_BOX
PANEL_B_BOX = s27.REGIONAL_BOX
COMPARISON_OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "atmos_publication_comparison"
CFSV2_DIR = PROJECT_ROOT / "outputs" / "netcdf" / "cfsv2_dynamic_diagnostics"
# 600 dpi (manuscript-quality) is safe to use unconditionally here: these
# PNGs are local-only (outputs/, gitignored) -- what actually gets synced
# to the deployed backend is a separately resized/quantized copy (see
# backend/scripts/sync_static_data.py), so this doesn't affect deploy size.
PNG_DPI = 600

PERIODS = s27.PERIODS
PERIOD_LABELS = {"Jun": "June", "Jul": "July", "Aug": "August", "Sep": "September", "JJA": "JJA", "JJAS": "JJAS"}

# Comparison figure uses a single fixed box per variable (unlike the
# dashboard's scope toggle, this figure type isn't interactive) -- same
# large/regional split as ATMOS_VARIABLES' default_scope in
# backend/app/routers/atmospheric.py: the wind fields default to the
# wide TEJ-context view, the other four to the Ethiopia-focused one.
DEFAULT_SCOPE_BOX = {
    "u200": PANEL_A_BOX,
    "u200_vectors": PANEL_A_BOX,
    "divergence200": PANEL_B_BOX,
    "omega500": PANEL_B_BOX,
    "qflux850": PANEL_B_BOX,
    "mfc850": PANEL_B_BOX,
}

# Which raw CFSv2 grid variable(s) back each of script 27's six variable
# keys -- mirrors the ERA5-side u/v -> speed, qu/qv -> flux-magnitude
# derivations already done in script 27, just against the CFSv2 file
# instead of the ERA5 climatology files.
CFSV2_VARS = {
    "u200": ("u200",),
    "u200_vectors": ("u200", "v200"),
    "divergence200": ("div200",),
    "omega500": ("omega500",),
    "qflux850": ("qu850", "qv850"),
    "mfc850": ("mfc850",),
}


def load_cfsv2_shade_and_quiver(var_key: str, period: str):
    """Returns (shade_da, quiver_tuple_or_None) from the CFSv2 June-2026-
    init gridded forecast, or (None, None) if the file/variable is
    missing. Shade field matches what script 27 shades for the ERA5 side
    of the same var_key (raw field, or magnitude for the two vector
    variables) so the two panels are the same physical quantity."""
    path = CFSV2_DIR / f"CFSv2_dynamic_diagnostics_{period}_2026.nc"
    if not path.exists():
        return None, None

    ds = s06.open_dataset(path, decode_times=False)
    names = CFSV2_VARS[var_key]
    if any(n not in ds for n in names):
        return None, None

    if var_key == "u200_vectors":
        u, v = ds["u200"], ds["v200"]
        shade = np.sqrt(u**2 + v**2)
        shade.attrs["units"] = "m/s"
        return shade, (u, v)

    if var_key == "qflux850":
        qu, qv = ds["qu850"], ds["qv850"]
        shade = np.sqrt(qu**2 + qv**2)
        shade.attrs["units"] = "kg/kg*m/s"
        return shade, (qu, qv)

    return ds[names[0]], None

# Display metadata per variable: compact notation (matches the legend
# title used in the dashboard), full title, and an optional physical-
# meaning note for diverging fields. Kept in lockstep with
# AtmosphericEvidence.tsx's CIRCULATION_MAPS by hand -- both describe
# the same six fields.
DISPLAY = {
    "u200": {
        "notation": "u₂₀₀",
        "title": "200-hPa Zonal Wind",
        "note": "Negative: easterly (stronger TEJ).  Positive: westerly.",
    },
    "u200_vectors": {
        "notation": "Wind speed",
        "title": "200-hPa Wind Vectors",
        "note": "Arrows show direction; shading shows speed.",
    },
    "divergence200": {
        "notation": "∇·V₂₀₀",
        "title": "200-hPa Divergence",
        "note": "Negative: convergence.  Positive: divergence (favorable upper-level outflow).",
    },
    "omega500": {
        "notation": "ω₅₀₀",
        "title": "500-hPa Vertical Velocity",
        "note": "Negative: forced ascent.  Positive: subsidence.",
    },
    "qflux850": {
        "notation": "qV₈₅₀",
        "title": "850-hPa Moisture Flux",
        "note": "Arrows show transport direction; shading shows flux magnitude.",
    },
    "mfc850": {
        "notation": "MFC₈₅₀",
        "title": "850-hPa Moisture-Flux Convergence",
        "note": "Negative: divergence.  Positive: convergence (moisture accumulating).",
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


# compute_tej_axis lives in script 27 now (the dashboard overlays need it
# too) -- use s27.compute_tej_axis, not a local copy, so the axis-line
# logic can't drift between the two scripts.


def render_panel(
    ax, da_2d, box, cmap, levels,
    quiver=None, contour_levels=None, zero_contour=False, axis_line=None, panel_label: str = "",
):
    lon, lat = da_2d["lon"].values, da_2d["lat"].values
    data = np.clip(da_2d.values, levels[0], levels[-1])
    norm = BoundaryNorm(levels, ncolors=256)

    # rasterized=True: with thousands of grid cells, an SVG/PDF backend
    # would otherwise emit one vector path per cell -- 25 MB+ per SVG,
    # confirmed. This keeps only the mesh fill as an embedded raster
    # (matching what the PDF backend already does automatically) while
    # text, contours, gridlines, and coastlines stay true vector paths.
    mesh = ax.pcolormesh(
        lon, lat, data, cmap=cmap, norm=norm, shading="auto", transform=ccrs.PlateCarree(), rasterized=True,
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

    # A solid zero-contour helps every reader (not just color-vision-
    # deficient ones) tell the blue side from the red side without relying
    # on hue alone -- CVD simulation (Coblis-style matrices) on this
    # palette's discrete bins showed the near-zero bins are the least
    # separable under protanopia/deuteranopia, exactly where this line
    # matters most. Not used for the two sequential (speed-magnitude)
    # variables, which have no zero crossing to mark.
    if zero_contour and levels[0] < 0 < levels[-1]:
        ax.contour(
            lon, lat, da_2d.values, levels=[0],
            colors="#1a1a1a", linewidths=1.1, linestyles="solid", transform=ccrs.PlateCarree(), zorder=4,
        )

    if contour_levels is not None:
        cs = ax.contour(
            lon, lat, da_2d.values, levels=contour_levels,
            colors="black", linewidths=0.8, transform=ccrs.PlateCarree(),
        )
        ax.clabel(cs, inline=True, fontsize=7, fmt="%g")

    if axis_line is not None:
        axis_lon, axis_lat = axis_line
        if len(axis_lon) > 1:
            ax.plot(
                axis_lon, axis_lat, color="#e6a817", linewidth=2.4, solid_capstyle="round",
                transform=ccrs.PlateCarree(), zorder=6,
            )
            ax.text(
                axis_lon[-1], axis_lat[-1], "  TEJ axis", color="#8a6200", fontsize=7.5, fontweight="bold",
                va="center", ha="left", transform=ccrs.PlateCarree(), zorder=6,
            )

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

    # TEJ axis line needs u/v regardless of whether this panel is shaded
    # by signed u200 (no vector_loader of its own) or by speed
    # (u200_vectors, which already has quiver_full) -- load separately for
    # u200 so the axis still draws on top of the signed-wind panel.
    axis_uv_full = None
    if var_key in ("u200", "u200_vectors"):
        axis_uv_full = quiver_full if quiver_full is not None else s27.load_u200_v200(period)

    # Restricted to u200 only -- verified empirically: divergence200,
    # omega500, and mfc850 are small-scale spatial-derivative fields whose
    # zero crossing is a dense tangle of tiny closed contours (confirmed
    # visually, not a clean sign boundary like u200's smooth wind field),
    # so a zero line clutters those panels instead of clarifying them.
    zero_contour = cfg["zero_contour"]

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
        axis = None
        if axis_uv_full is not None:
            au, av = axis_uv_full
            au = s06.subset_box(au, s27.clamp_box_lat(box)).squeeze(drop=True)
            av = s06.subset_box(av, s27.clamp_box_lat(box)).squeeze(drop=True)
            if "lat" in au.dims and "lon" in au.dims:
                au, av = au.transpose("lat", "lon"), av.transpose("lat", "lon")
            axis = s27.compute_tej_axis(au, av)
        return da, q, axis

    da_a, quiver_a, axis_a = subset_for(PANEL_A_BOX)
    da_b, quiver_b, axis_b = subset_for(PANEL_B_BOX)

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
        quiver=quiver_a, contour_levels=cfg["contour_levels"], zero_contour=zero_contour, axis_line=axis_a,
        panel_label="A — Large-scale TEJ context",
    )
    mesh = render_panel(
        ax_b, da_b, PANEL_B_BOX, cfg["cmap"], cfg["levels"],
        quiver=quiver_b, contour_levels=cfg["contour_levels"], zero_contour=zero_contour, axis_line=axis_b,
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
    svg_path = out_dir / f"{var_key}_{period}.svg"
    fig.savefig(png_path, dpi=PNG_DPI, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {png_path.name} + {pdf_path.name} + {svg_path.name}")


def plot_climatology_vs_target_figure(var_key: str, period: str) -> None:
    """ERA5 1991-2020 climatology next to the actual CFSv2 June-2026-init
    forecast grid, same variable/period/box/color scale -- side-by-side
    comparison only, no anomaly (see module docstring for why)."""
    cfg = s27.VARIABLES[var_key]
    disp = DISPLAY[var_key]
    box = DEFAULT_SCOPE_BOX[var_key]

    da_clim = cfg["loader"](period)
    if da_clim is None:
        print(f"Skipping comparison {var_key}/{period}: ERA5 source missing")
        return

    quiver_clim = None
    if cfg["vector_loader"] is not None:
        uv = cfg["vector_loader"](period)
        if uv is not None:
            quiver_clim = uv

    da_target, quiver_target = load_cfsv2_shade_and_quiver(var_key, period)
    if da_target is None:
        print(f"Skipping comparison {var_key}/{period}: CFSv2 target missing")
        return

    # TEJ axis line for both panels -- see plot_publication_figure for why
    # u200 needs its own u/v load (its own panel shades signed u200, not
    # speed, so it has no vector_loader/quiver of its own).
    axis_uv_clim = axis_uv_target = None
    if var_key in ("u200", "u200_vectors"):
        axis_uv_clim = quiver_clim if quiver_clim is not None else s27.load_u200_v200(period)
        axis_uv_target = quiver_target if quiver_target is not None else load_cfsv2_shade_and_quiver("u200_vectors", period)[1]

    # Restricted to u200 only -- verified empirically: divergence200,
    # omega500, and mfc850 are small-scale spatial-derivative fields whose
    # zero crossing is a dense tangle of tiny closed contours (confirmed
    # visually, not a clean sign boundary like u200's smooth wind field),
    # so a zero line clutters those panels instead of clarifying them.
    zero_contour = cfg["zero_contour"]

    def prep(da, quiver, axis_uv):
        da = s06.subset_box(da, s27.clamp_box_lat(box)).squeeze(drop=True)
        if "lat" in da.dims and "lon" in da.dims:
            da = da.transpose("lat", "lon")
        q = None
        if quiver is not None:
            u, v = quiver
            u = s06.subset_box(u, s27.clamp_box_lat(box)).squeeze(drop=True)
            v = s06.subset_box(v, s27.clamp_box_lat(box)).squeeze(drop=True)
            if "lat" in u.dims and "lon" in u.dims:
                u, v = u.transpose("lat", "lon"), v.transpose("lat", "lon")
            q = (u, v)
        axis = None
        if axis_uv is not None:
            au, av = axis_uv
            au = s06.subset_box(au, s27.clamp_box_lat(box)).squeeze(drop=True)
            av = s06.subset_box(av, s27.clamp_box_lat(box)).squeeze(drop=True)
            if "lat" in au.dims and "lon" in au.dims:
                au, av = au.transpose("lat", "lon"), av.transpose("lat", "lon")
            axis = s27.compute_tej_axis(au, av)
        return da, q, axis

    da_clim, quiver_clim, axis_clim = prep(da_clim, quiver_clim, axis_uv_clim)
    da_target, quiver_target, axis_target = prep(da_target, quiver_target, axis_uv_target)

    fig = plt.figure(figsize=(15, 7.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 0.06], width_ratios=[1, 1], hspace=0.35, wspace=0.12, top=0.80, bottom=0.13)
    ax_clim = fig.add_subplot(gs[0, 0], projection=ccrs.PlateCarree())
    ax_target = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
    cax = fig.add_subplot(gs[1, :])

    render_panel(
        ax_clim, da_clim, box, cfg["cmap"], cfg["levels"],
        quiver=quiver_clim, contour_levels=cfg["contour_levels"], zero_contour=zero_contour, axis_line=axis_clim,
        panel_label="A — ERA5 1991–2020 climatology",
    )
    mesh = render_panel(
        ax_target, da_target, box, cfg["cmap"], cfg["levels"],
        quiver=quiver_target, contour_levels=cfg["contour_levels"], zero_contour=zero_contour, axis_line=axis_target,
        panel_label="B — CFSv2 2026 target (June init)",
    )

    cbar = fig.colorbar(mesh, cax=cax, orientation="horizontal")
    cbar.set_label(f"{disp['notation']} ({cfg['unit']})", fontsize=10)
    cbar.ax.tick_params(labelsize=8)

    period_label = PERIOD_LABELS[period]
    fig.text(
        0.5, 0.965, f"{period_label} {disp['notation']} ({cfg['unit']}) — Climatology vs. 2026 Target",
        fontsize=15, fontweight="bold", ha="center", va="top",
    )
    fig.text(0.5, 0.925, disp["title"], fontsize=10.5, ha="center", va="top", color="#333333")
    fig.text(
        0.5, 0.895,
        "Not an anomaly: ERA5 (reanalysis climatology) and CFSv2 (operational forecast) are different\n"
        "modeling systems, so this is a qualitative side-by-side, not a same-model anomaly.",
        fontsize=8, ha="center", va="top", color="#9a3b12", style="italic",
    )

    fig.text(
        0.5, 0.03,
        f"Panel A: ERA5, ref. 1991–2020, {period_label} mean, 0.25°  ·  "
        f"Panel B: CFSv2 NOMADS, June-2026 init, {period_label} mean  ·  Variable: {disp['title']}",
        fontsize=7.5, ha="center", va="bottom", color="#666666",
    )

    out_dir = COMPARISON_OUT_DIR / var_key
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{var_key}_{period}_comparison.png"
    pdf_path = out_dir / f"{var_key}_{period}_comparison.pdf"
    svg_path = out_dir / f"{var_key}_{period}_comparison.svg"
    fig.savefig(png_path, dpi=PNG_DPI, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {png_path.name} + {pdf_path.name} + {svg_path.name}")


def main():
    print("==================================================")
    print("Generate atmospheric publication figures")
    print("==================================================")
    for var_key in s27.VARIABLES:
        for period in PERIODS:
            plot_publication_figure(var_key, period)

    print("\n==================================================")
    print("Generate climatology-vs-target comparison figures")
    print("==================================================")
    for var_key in s27.VARIABLES:
        for period in PERIODS:
            plot_climatology_vs_target_figure(var_key, period)

    print(f"\nOutput folders: {OUT_DIR}")
    print(f"                 {COMPARISON_OUT_DIR}")


if __name__ == "__main__":
    main()
