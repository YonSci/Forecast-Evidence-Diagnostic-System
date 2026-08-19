"""
27_generate_atmospheric_leaflet_overlays.py

Purpose
-------
Generate react-leaflet <ImageOverlay> rasters (full-bleed, no title/
colorbar/axes baked in) + matching grid JSON for hover tooltips, for the
six circulation diagnostics used to check whether the forecast's TEJ
signal is dynamically self-consistent -- jet strength and structure,
upper-level divergence at the jet exit, forced ascent, and whether
moisture is actually being supplied and accumulating at low levels:

    1. u200          -- 200 hPa zonal wind (signed; primary TEJ-strength indicator)
    2. u200_vectors   -- 200 hPa wind speed + direction vectors (circulation/jet orientation)
    3. divergence200  -- 200 hPa divergence (upper-level outflow)
    4. omega500       -- 500 hPa vertical velocity (forced ascent/subsidence)
    5. qflux850       -- 850 hPa moisture flux magnitude + direction vectors (is moisture supplied?)
    6. mfc850         -- 850 hPa moisture-flux convergence (is moisture accumulating?)

Same interactive-map pattern already used for rainfall (script 22) and
the SST proxy (script 26): Web-Mercator-projected pixel spacing (so it
lines up with the Leaflet basemap) plus a matching raw grid JSON for
exact-value hover tooltips. Unlike 22/26 these are upper-air fields,
physically meaningful over land AND ocean, so no land/ocean clip mask is
applied -- full rectangular domain, country borders drawn separately by
the frontend's GeoJSON borders layer.

Every variable is generated at TWO scopes -- "large" (LARGE_SCALE_BOX,
South Asia across the Indian Ocean to Africa) and "regional"
(REGIONAL_BOX, Ethiopia/Sudan/Somalia/Kenya/Red Sea/Arabia) -- the same
two boxes scripts/28's publication figures use as Panel A/B, so the
dashboard's scope toggle and the publication dual-panel figure always
agree on what "large-scale" and "regional" mean.

Direction vectors (u200_vectors, qflux850) are baked into the raster
itself as a matplotlib quiver on top of the shaded background, rather
than a real Leaflet vector layer -- arrow density is fixed at render
time instead of rescaling with zoom, which is an acceptable trade-off
against building a genuine interactive vector layer. u200/u200_vectors
also get a traced TEJ axis line (see compute_tej_axis) and u200 alone
gets labeled threshold contours plus a solid zero-contour line -- the
same three additions scripts/28 already applies to the publication
figures, shared from here so the two never drift apart. (divergence200/
omega500/mfc850 deliberately do NOT get a zero-contour: confirmed
visually in the publication-figure work that those small-scale
spatial-derivative fields turn a zero line into a dense, unreadable
tangle instead of a clean sign boundary like u200's smooth wind field.)
The hover-tooltip grid always reflects only the shaded scalar field,
never the vectors/contours/axis line.

All six are ERA5 1991-2020 climatology, available by calendar month
(Jun-Sep) and JJA/JJAS season -- there is no per-2026-forecast gridded
product for any of them yet, so the page's period selector switches the
climatological month/season, not a forecast lead time. (z200, which
does have a real per-2026-forecast NMME grid, isn't part of this
TEJ-consistency set and stays out of this script.)

Outputs
-------
    outputs/maps/atmos_overlays/<variable>/<scope>/<period>.png
    outputs/maps/atmos_overlays/overlay_index.json
        { "<variable>/<scope>/<period>": {file, bounds, vmin, vmax, unit, legend_gradient} }
    outputs/maps/atmos_overlays/grid_data/<variable>/<scope>/<period>.json

Run from project root:
    python scripts\\27_generate_atmospheric_leaflet_overlays.py
"""

from __future__ import annotations

import importlib.util
import json
from math import floor, log10
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "atmos_overlays"
GRID_OUT_DIR = OUT_DIR / "grid_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Reuse the file-path constants and xarray helpers already defined in
# script 06 (DOMAINS, ERA5_*/MOISTURE_FILES paths, open_dataarray/
# open_dataset, select_month/select_month_ds, subset_box/
# subset_dataset_box, get_symmetric_limits, get_positive_limits) instead
# of redefining them.
_spec = importlib.util.spec_from_file_location("plot06", PROJECT_ROOT / "scripts" / "06_plot_dynamic_maps.py")
s06 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s06)

WEB_MERCATOR_MAX_LAT = 85.05112878
MERCATOR_R = 6378137.0

PERIODS = ["Jun", "Jul", "Aug", "Sep", "JJA", "JJAS"]
MONTH_NUM = {"Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9}

# Canonical two-scope domains, shared with scripts/28's Panel A/B so the
# dashboard scope toggle and the publication dual-panel figure agree.
LARGE_SCALE_BOX = [-20, 100, -20, 40]   # South Asia -> Indian Ocean -> Africa
REGIONAL_BOX = [25, 55, 0, 20]          # Ethiopia, Sudan, South Sudan, Somalia, Kenya, Red Sea, Arabia
SCOPES = {"large": LARGE_SCALE_BOX, "regional": REGIONAL_BOX}


def lon_to_merc_x(lon_deg):
    return np.radians(np.asarray(lon_deg, dtype=float)) * MERCATOR_R


def lat_to_merc_y(lat_deg):
    lat_deg = np.clip(np.asarray(lat_deg, dtype=float), -WEB_MERCATOR_MAX_LAT, WEB_MERCATOR_MAX_LAT)
    return MERCATOR_R * np.log(np.tan(np.pi / 4 + np.radians(lat_deg) / 2))


def clamp_box_lat(box: list[float]) -> list[float]:
    lon_min, lon_max, lat_min, lat_max = box
    return [lon_min, lon_max, max(lat_min, -WEB_MERCATOR_MAX_LAT), min(lat_max, WEB_MERCATOR_MAX_LAT)]


def compute_tej_axis(u_da, v_da, lat_band=(0, 20), min_speed=15.0):
    """Traces the TEJ axis: the latitude of maximum 200 hPa wind speed at
    each longitude, restricted to a tropical/subtropical band so this
    follows the easterly jet core instead of the (also fast) midlatitude
    westerlies, and masked to longitudes where that maximum is at least
    min_speed m/s so the line stops where there's no real jet to trace.
    u_da/v_da must already share the same (lat, lon) grid/subset used for
    the panel's shading. Returns (lons, lats) ready to plot as a line."""
    speed = np.sqrt(u_da.values ** 2 + v_da.values ** 2)
    lat = u_da["lat"].values
    lon = u_da["lon"].values

    band_mask = (lat >= min(lat_band)) & (lat <= max(lat_band))
    if not band_mask.any():
        return np.array([]), np.array([])
    lat_band_vals = lat[band_mask]
    speed_band = speed[band_mask, :]

    safe = np.where(np.isnan(speed_band), -np.inf, speed_band)
    max_idx = np.argmax(safe, axis=0)
    max_speed = speed_band[max_idx, np.arange(speed_band.shape[1])]
    max_lat = lat_band_vals[max_idx]

    keep = np.isfinite(max_speed) & (max_speed >= min_speed)
    return lon[keep], max_lat[keep]


# ==========================================================
# Per-period source loaders
# ==========================================================

def load_u200_v200(period: str) -> tuple[xr.DataArray, xr.DataArray] | None:
    if period in MONTH_NUM:
        if not (s06.ERA5_U200_MONTHLY.exists() and s06.ERA5_V200_MONTHLY.exists()):
            return None
        u = s06.select_month(s06.open_dataarray(s06.ERA5_U200_MONTHLY, decode_times=True), MONTH_NUM[period])
        v = s06.select_month(s06.open_dataarray(s06.ERA5_V200_MONTHLY, decode_times=True), MONTH_NUM[period])
    else:
        u_path = {"JJA": s06.ERA5_U200_JJA, "JJAS": s06.ERA5_U200_JJAS}[period]
        v_path = {"JJA": s06.ERA5_V200_JJA, "JJAS": s06.ERA5_V200_JJAS}[period]
        if not (u_path.exists() and v_path.exists()):
            return None
        u = s06.open_dataarray(u_path, decode_times=True)
        v = s06.open_dataarray(v_path, decode_times=True)
    return u, v


def load_u200(period: str) -> xr.DataArray | None:
    uv = load_u200_v200(period)
    return None if uv is None else uv[0]


def load_u200_speed(period: str) -> xr.DataArray | None:
    uv = load_u200_v200(period)
    if uv is None:
        return None
    u, v = uv
    speed = np.sqrt(u**2 + v**2)
    speed.attrs["units"] = "m/s"
    return speed


def load_climatology_da(monthly_path: Path, jja_path: Path, jjas_path: Path, period: str) -> xr.DataArray | None:
    if period in MONTH_NUM:
        if not monthly_path.exists():
            return None
        da = s06.open_dataarray(monthly_path, decode_times=True)
        return s06.select_month(da, MONTH_NUM[period])
    path = {"JJA": jja_path, "JJAS": jjas_path}[period]
    if not path.exists():
        return None
    return s06.open_dataarray(path, decode_times=True)


def load_omega500(period: str) -> xr.DataArray | None:
    f = s06.ERA5_OMEGA_FILES["omega500"]
    return load_climatology_da(f["monthly"], f["JJA"], f["JJAS"], period)


def load_divergence200(period: str) -> xr.DataArray | None:
    f = s06.ERA5_DIVERGENCE_FILES
    return load_climatology_da(f["monthly"], f["JJA"], f["JJAS"], period)


def load_mfc_dataset(period: str) -> xr.Dataset | None:
    files = s06.MOISTURE_FILES
    if period in MONTH_NUM:
        if not files["monthly"].exists():
            return None
        return s06.select_month_ds(s06.open_dataset(files["monthly"], decode_times=True), MONTH_NUM[period])
    path = files[period]
    if not path.exists():
        return None
    return s06.open_dataset(path, decode_times=True)


def load_mfc850(period: str) -> xr.DataArray | None:
    ds = load_mfc_dataset(period)
    return None if ds is None else ds["mfc850"]


def load_qflux850_qu_qv(period: str) -> tuple[xr.DataArray, xr.DataArray] | None:
    ds = load_mfc_dataset(period)
    return None if ds is None else (ds["qu850"], ds["qv850"])


def load_qflux850_magnitude(period: str) -> xr.DataArray | None:
    qv = load_qflux850_qu_qv(period)
    if qv is None:
        return None
    qu, qvv = qv
    mag = np.sqrt(qu**2 + qvv**2)
    mag.attrs["units"] = "kg/kg*m/s"
    return mag


# ==========================================================
# Variable registry -- order here is the display order on the page,
# matching the TEJ dynamical-consistency mental model: jet strength ->
# jet structure -> upper divergence -> forced ascent -> moisture supply
# -> moisture accumulation.
#
# "levels" are FIXED discrete bin edges, the same for every period AND
# scope of a given variable -- computed once from each field's actual
# distribution across all 6 periods (min/max/p99 inspected beforehand),
# not derived per-period. A per-period percentile-based range (the
# previous approach) makes different months visually incomparable: June
# at +-12 m/s and August at +-23 m/s both fill the whole colorbar, which
# reads as "similar magnitude" when it isn't. Values outside the range
# are clipped to the end bins rather than using BoundaryNorm's
# under/over colors, which need explicit per-colormap configuration to
# render as anything but a hard-to-see default.
#
# "vector_loader" (optional) supplies the (u, v) pair quiver-drawn on top
# of the shaded background for the two "does direction/transport matter"
# entries (wind vectors, moisture flux). "axis_line"/"contour_levels"/
# "zero_contour" are u200-only (see module docstring for why the other
# three diverging fields don't get a zero-contour). "unit" is asserted
# rather than read from the source netCDF's GRIB-derived attrs, which
# render as e.g. "m s**-1" or "kg kg-1 s-1 approximately" -- not fit for
# display; uses the same "unit s⁻¹"-style notation throughout rather
# than mixing "m/s"/"m s-1"/"m*s-1".
# ==========================================================

VARIABLES = {
    "u200": {
        "loader": load_u200,
        "cmap": "RdBu_r",
        "levels": np.arange(-32, 33, 4),
        "unit": "m s⁻¹",
        "vector_loader": None,
        "axis_line": True,
        "contour_levels": [-40, -30, -20, -10],
        "zero_contour": True,
    },
    "u200_vectors": {
        "loader": load_u200_speed,
        "cmap": "jet",
        "levels": np.arange(0, 36, 4),
        "unit": "m s⁻¹",
        "vector_loader": load_u200_v200,
        "axis_line": True,
        "contour_levels": None,
        "zero_contour": False,
    },
    "divergence200": {
        "loader": load_divergence200,
        "cmap": "RdBu_r",
        "levels": np.arange(-8e-6, 8.1e-6, 2e-6),
        "unit": "s⁻¹",
        "vector_loader": None,
        "axis_line": False,
        "contour_levels": None,
        "zero_contour": False,
    },
    "omega500": {
        "loader": load_omega500,
        "cmap": "RdBu_r",
        "levels": np.arange(-0.15, 0.151, 0.025),
        "unit": "Pa s⁻¹",
        "vector_loader": None,
        "axis_line": False,
        "contour_levels": None,
        "zero_contour": False,
    },
    "qflux850": {
        "loader": load_qflux850_magnitude,
        "cmap": "YlGnBu",
        "levels": np.arange(0, 0.271, 0.03),
        "unit": "kg kg⁻¹ m s⁻¹",
        "vector_loader": load_qflux850_qu_qv,
        "axis_line": False,
        "contour_levels": None,
        "zero_contour": False,
    },
    "mfc850": {
        "loader": load_mfc850,
        "cmap": "BrBG",
        "levels": np.arange(-6e-7, 6.1e-7, 1e-7),
        "unit": "kg kg⁻¹ s⁻¹",
        "vector_loader": None,
        "axis_line": False,
        "contour_levels": None,
        "zero_contour": False,
    },
}


def render_overlay(
    da_2d: xr.DataArray,
    box: list[float],
    cmap: str,
    levels: np.ndarray,
    out_path: Path,
    quiver: tuple[xr.DataArray, xr.DataArray] | None = None,
    contour_levels: list[float] | None = None,
    zero_contour: bool = False,
    axis_line: tuple[np.ndarray, np.ndarray] | None = None,
) -> None:
    lon = da_2d["lon"].values
    lat = da_2d["lat"].values
    lon_min, lon_max, lat_min, lat_max = box

    merc_x = lon_to_merc_x(lon)
    merc_y = lat_to_merc_y(lat)
    x_min, x_max = lon_to_merc_x(np.array([lon_min, lon_max]))
    y_min, y_max = lat_to_merc_y(np.array([lat_min, lat_max]))

    width_m = x_max - x_min
    height_m = max(y_max - y_min, 1.0)
    px_per_m = 1600 / max(width_m, height_m)
    fig_w, fig_h = width_m * px_per_m / 100, height_m * px_per_m / 100

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.axis("off")

    # Discrete meteorological intervals (BoundaryNorm) instead of
    # continuous shading, on a FIXED scale shared across every period --
    # clip rather than extend so out-of-range outliers still render as
    # the nearest end bin instead of vanishing.
    norm = BoundaryNorm(levels, ncolors=256)
    data = np.clip(da_2d.values, levels[0], levels[-1])
    ax.pcolormesh(merc_x, merc_y, data, cmap=cmap, norm=norm, shading="auto")

    if quiver is not None:
        u, v = quiver
        lon2d, lat2d = np.meshgrid(lon, lat)
        merc_x2d = lon_to_merc_x(lon2d)
        merc_y2d = lat_to_merc_y(lat2d)
        nlat, nlon = len(lat), len(lon)
        stride_lat = max(1, nlat // 22)
        stride_lon = max(1, nlon // 28)
        sl = (slice(None, None, stride_lat), slice(None, None, stride_lon))

        # scale_units="width" makes `scale` a unit-independent ratio (U per
        # fraction of axes width), so this adapts to whatever magnitude the
        # field has -- wind speed (~m/s) and moisture flux differ by orders
        # of magnitude, and a single hardcoded scale can't fit both.
        mag = np.sqrt(u.values**2 + v.values**2)
        typical = float(np.nanpercentile(mag, 90))
        if not np.isfinite(typical) or typical <= 0:
            typical = 1.0
        scale = typical / 0.05  # ~90th-percentile arrow spans ~5% of axes width

        ax.quiver(
            merc_x2d[sl], merc_y2d[sl], u.values[sl], v.values[sl],
            color="black", scale=scale, scale_units="width", width=0.0022, alpha=0.85,
        )

    # Solid zero-contour (u200 only, see module docstring) -- a shape cue
    # marking the sign boundary independent of hue, which a CVD simulation
    # (scripts/_cvd_check.py) showed matters since the near-zero bins are
    # the least separable pair under every simulated color-vision
    # deficiency, for every diverging palette used here.
    if zero_contour and levels[0] < 0 < levels[-1]:
        ax.contour(merc_x, merc_y, data, levels=[0], colors="#1a1a1a", linewidths=1.3, linestyles="solid", zorder=4)

    if contour_levels is not None:
        cs = ax.contour(merc_x, merc_y, da_2d.values, levels=contour_levels, colors="black", linewidths=0.9)
        ax.clabel(cs, inline=True, fontsize=8, fmt="%g")

    if axis_line is not None:
        axis_lon, axis_lat = axis_line
        if len(axis_lon) > 1:
            axis_x = lon_to_merc_x(axis_lon)
            axis_y = lat_to_merc_y(axis_lat)
            ax.plot(axis_x, axis_y, color="#e6a817", linewidth=2.6, solid_capstyle="round", zorder=6)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, transparent=True)
    plt.close(fig)


def css_hard_stop_gradient(cmap_name: str, levels: np.ndarray) -> str:
    """A CSS linear-gradient with hard color stops matching the exact
    discrete bins/colors BoundaryNorm renders into the PNG -- so the
    legend bar shows the same stepped bands as the map instead of a
    smooth gradient implying continuous shading that isn't there."""
    cmap = plt.get_cmap(cmap_name)
    n = len(levels) - 1
    colors = [cmap(x) for x in np.linspace(0, 1, n)]
    hexes = ["#%02x%02x%02x" % tuple(int(round(c * 255)) for c in col[:3]) for col in colors]
    stops = []
    for i, hx in enumerate(hexes):
        lo = 100 * i / n
        hi = 100 * (i + 1) / n
        stops.append(f"{hx} {lo:.3f}%")
        stops.append(f"{hx} {hi:.3f}%")
    return f"linear-gradient(90deg, {', '.join(stops)})"


def round_sig(x: float, sig: int = 6) -> float:
    """Round to `sig` significant figures rather than a fixed decimal count
    -- mfc850 values are ~1e-7 and divergence200 ~1e-6, so a fixed
    round(x, 4) silently zeroes them out."""
    x = float(x)
    if x == 0 or not np.isfinite(x):
        return 0.0
    digits = sig - int(floor(log10(abs(x)))) - 1
    return round(x, digits)


def to_json_value(v: float) -> float | None:
    return None if not np.isfinite(v) else round_sig(v)


def main():
    print("==================================================")
    print("Generate atmospheric circulation leaflet overlays + grid JSON")
    print("==================================================")

    index = {}
    written = 0

    for var_key, cfg in VARIABLES.items():
        for scope, raw_box in SCOPES.items():
            box = clamp_box_lat(raw_box)

            for period in PERIODS:
                da = cfg["loader"](period)
                if da is None:
                    print(f"Skipping {var_key}/{scope}/{period}: source file missing")
                    continue

                da = s06.subset_box(da, box).squeeze(drop=True)
                if "lat" in da.dims and "lon" in da.dims:
                    da = da.transpose("lat", "lon")

                unit = cfg["unit"]
                levels = cfg["levels"]
                vmin, vmax = float(levels[0]), float(levels[-1])

                quiver = None
                if cfg["vector_loader"] is not None:
                    uv = cfg["vector_loader"](period)
                    if uv is not None:
                        u, v = uv
                        u = s06.subset_box(u, box).squeeze(drop=True)
                        v = s06.subset_box(v, box).squeeze(drop=True)
                        if "lat" in u.dims and "lon" in u.dims:
                            u = u.transpose("lat", "lon")
                            v = v.transpose("lat", "lon")
                        quiver = (u, v)

                axis_line = None
                if cfg["axis_line"]:
                    uv_axis = quiver if quiver is not None else load_u200_v200(period)
                    if uv_axis is not None:
                        au, av = uv_axis
                        au = s06.subset_box(au, box).squeeze(drop=True)
                        av = s06.subset_box(av, box).squeeze(drop=True)
                        if "lat" in au.dims and "lon" in au.dims:
                            au = au.transpose("lat", "lon")
                            av = av.transpose("lat", "lon")
                        axis_line = compute_tej_axis(au, av)

                out_path = OUT_DIR / var_key / scope / f"{period}.png"
                render_overlay(
                    da, box, cfg["cmap"], levels, out_path, quiver=quiver,
                    contour_levels=cfg["contour_levels"], zero_contour=cfg["zero_contour"], axis_line=axis_line,
                )

                lon_min, lon_max, lat_min, lat_max = box
                index[f"{var_key}/{scope}/{period}"] = {
                    "file": f"{var_key}/{scope}/{period}.png",
                    "bounds": [[lat_min, lon_min], [lat_max, lon_max]],
                    "vmin": round_sig(vmin),
                    "vmax": round_sig(vmax),
                    "unit": unit,
                    "legend_gradient": css_hard_stop_gradient(cfg["cmap"], levels),
                }

                # Grid JSON for exact-value hover tooltips -- reflects only
                # the shaded scalar field, not the baked-in vectors/
                # contours/axis line. Thinned since the underlying ERA5
                # grids are far finer than needed for a tooltip lookup.
                da_thin = da.isel(lat=slice(None, None, 2), lon=slice(None, None, 2))
                lats = [round(float(v), 3) for v in da_thin["lat"].values]
                lons = [round(float(v), 3) for v in da_thin["lon"].values]
                values = [[to_json_value(v) for v in row] for row in da_thin.values]

                grid_path = GRID_OUT_DIR / var_key / scope / f"{period}.json"
                grid_path.parent.mkdir(parents=True, exist_ok=True)
                grid_path.write_text(
                    json.dumps({"lats": lats, "lons": lons, "values": values, "unit": unit}, separators=(",", ":")),
                    encoding="utf-8",
                )

                written += 1
                print(f"Saved: {out_path}")

    index_path = OUT_DIR / "overlay_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(f"\nWrote {written} overlay images + grid files, and {index_path}")


if __name__ == "__main__":
    main()
