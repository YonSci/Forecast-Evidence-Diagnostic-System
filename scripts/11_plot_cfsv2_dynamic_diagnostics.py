"""
11_plot_cfsv2_dynamic_diagnostics.py

Purpose
-------
Plot CFSv2 dynamic diagnostic maps from:

    outputs/netcdf/cfsv2_dynamic_diagnostics/

Inputs:
    CFSv2_dynamic_diagnostics_Jun_2026.nc
    CFSv2_dynamic_diagnostics_Jul_2026.nc
    CFSv2_dynamic_diagnostics_Aug_2026.nc
    CFSv2_dynamic_diagnostics_Sep_2026.nc
    CFSv2_dynamic_diagnostics_JJA_2026.nc
    CFSv2_dynamic_diagnostics_JJAS_2026.nc

Outputs:
    outputs/maps/cfsv2_dynamic_diagnostics/

Run:
    python scripts\\11_plot_cfsv2_dynamic_diagnostics.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle


# ==========================================================
# OPTIONAL CARTOPY
# ==========================================================

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
except Exception:
    HAS_CARTOPY = False
    print("Cartopy is not available. Maps will be plotted without coastlines/borders.")


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DIAG_DIR = PROJECT_ROOT / "outputs" / "netcdf" / "cfsv2_dynamic_diagnostics"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
MAP_DIR = PROJECT_ROOT / "outputs" / "maps" / "cfsv2_dynamic_diagnostics"

MAP_DIR.mkdir(parents=True, exist_ok=True)

PLOT_DIRS = {
    "tej": MAP_DIR / "01_tej_u200",
    "div200": MAP_DIR / "02_200hpa_divergence",
    "moisture": MAP_DIR / "03_850hpa_moisture_flux_mfc",
    "omega": MAP_DIR / "04_vertical_motion_omega",
    "vp_strf": MAP_DIR / "05_velocity_potential_streamfunction",
    "height": MAP_DIR / "06_geopotential_height",
    "sst": MAP_DIR / "07_sst_proxy",
    "charts": MAP_DIR / "08_area_mean_charts",
}

for folder in PLOT_DIRS.values():
    folder.mkdir(parents=True, exist_ok=True)


# ==========================================================
# SETTINGS
# ==========================================================

DPI = 300

PERIODS = [
    "Jun_2026",
    "Jul_2026",
    "Aug_2026",
    "Sep_2026",
    "JJA_2026",
    "JJAS_2026",
]

PERIOD_LABELS = {
    "Jun_2026": "June 2026",
    "Jul_2026": "July 2026",
    "Aug_2026": "August 2026",
    "Sep_2026": "September 2026",
    "JJA_2026": "June-August 2026",
    "JJAS_2026": "June-September 2026",
}

DOMAINS = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "africa_indian": [-20, 120, -35, 40],
    "atlantic_congo_ethiopia": [-20, 55, -20, 25],
    "indian_ocean": [30, 120, -30, 30],
    "global_tropics": [-180, 180, -30, 30],
    "tej_domain": [20, 100, -5, 30],
    "north_africa_arabia": [10, 60, 10, 35],
}

SST_BOXES = {
    "Niño3.4": [-170, -120, -5, 5],
    "IOD West": [50, 70, -10, 10],
    "IOD East": [90, 110, -10, 0],
}


# ==========================================================
# HELPERS
# ==========================================================

def diag_path(period: str) -> Path:
    return DIAG_DIR / f"CFSv2_dynamic_diagnostics_{period}.nc"


def open_diag(period: str) -> xr.Dataset:
    path = diag_path(period)

    if not path.exists():
        raise FileNotFoundError(f"Missing diagnostic file: {path}")

    ds = xr.open_dataset(path)
    ds = standardize_coordinate_names(ds)
    ds = standardize_longitude(ds)

    return ds


def standardize_coordinate_names(ds: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
    rename = {}

    names = list(ds.coords) + list(ds.dims)

    for name in names:
        lower = name.lower()

        if lower in ["latitude", "lat", "y"] and name != "lat":
            if "lat" not in ds.coords and "lat" not in ds.dims:
                rename[name] = "lat"

        if lower in ["longitude", "lon", "x"] and name != "lon":
            if "lon" not in ds.coords and "lon" not in ds.dims:
                rename[name] = "lon"

    if rename:
        ds = ds.rename(rename)

    return ds


def standardize_longitude(ds: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
    if "lon" not in ds.coords:
        return ds

    lon = ds["lon"]

    if float(lon.max()) > 180:
        new_lon = ((lon + 180) % 360) - 180
        ds = ds.assign_coords(lon=new_lon)
        ds = ds.sortby("lon")

    return ds


def clean_da(da: xr.DataArray) -> xr.DataArray:
    da = standardize_coordinate_names(da)
    da = standardize_longitude(da)
    da = da.squeeze(drop=True)

    keep_coords = {"lat", "lon"}

    drop_coords = []
    for coord in list(da.coords):
        if coord not in keep_coords and coord not in da.dims:
            drop_coords.append(coord)

    if drop_coords:
        da = da.drop_vars(drop_coords, errors="ignore")

    if "lat" in da.dims and "lon" in da.dims:
        other_dims = [d for d in da.dims if d not in ["lat", "lon"]]
        da = da.transpose(*other_dims, "lat", "lon")

    return da


def subset_box(da: xr.DataArray, box: list[float]) -> xr.DataArray:
    lon_min, lon_max, lat_min, lat_max = box

    da = standardize_longitude(da)

    lat_values = da["lat"].values

    if lat_values[0] < lat_values[-1]:
        lat_slice = slice(lat_min, lat_max)
    else:
        lat_slice = slice(lat_max, lat_min)

    return da.sel(
        lon=slice(lon_min, lon_max),
        lat=lat_slice,
    )


def symmetric_limits(da: xr.DataArray, percentile: float = 98.0, minimum: float = 1e-12) -> tuple[float, float]:
    vals = da.values
    vals = vals[np.isfinite(vals)]

    if vals.size == 0:
        return -1.0, 1.0

    vmax = float(np.nanpercentile(np.abs(vals), percentile))

    if not np.isfinite(vmax) or vmax < minimum:
        vmax = 1.0

    return -vmax, vmax


def add_map_features(ax, draw_labels: bool = True):
    if not HAS_CARTOPY:
        return

    ax.coastlines(linewidth=0.8)
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, linewidth=0.3, alpha=0.6)
    ax.add_feature(cfeature.RIVERS, linewidth=0.25, alpha=0.4)

    gl = ax.gridlines(
        draw_labels=draw_labels,
        linewidth=0.25,
        linestyle="--",
        alpha=0.45,
    )

    if draw_labels:
        gl.top_labels = False
        gl.right_labels = False


def add_sst_boxes(ax):
    for label, box in SST_BOXES.items():
        lon_min, lon_max, lat_min, lat_max = box

        if HAS_CARTOPY:
            rect = Rectangle(
                (lon_min, lat_min),
                lon_max - lon_min,
                lat_max - lat_min,
                fill=False,
                linewidth=1.5,
                edgecolor="black",
                transform=ccrs.PlateCarree(),
            )
            ax.add_patch(rect)

            ax.text(
                lon_min,
                lat_max + 1.0,
                label,
                fontsize=8,
                fontweight="bold",
                transform=ccrs.PlateCarree(),
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.65),
            )
        else:
            rect = Rectangle(
                (lon_min, lat_min),
                lon_max - lon_min,
                lat_max - lat_min,
                fill=False,
                linewidth=1.5,
                edgecolor="black",
            )
            ax.add_patch(rect)
            ax.text(lon_min, lat_max + 1.0, label, fontsize=8, fontweight="bold")


def safe_name(text: str) -> str:
    return (
        text.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
    )


# ==========================================================
# MAP FUNCTIONS
# ==========================================================

def plot_scalar_map(
    da: xr.DataArray,
    title: str,
    out_file: Path,
    domain_box: list[float],
    cmap: str = "RdBu_r",
    symmetric: bool = True,
    vmin: float | None = None,
    vmax: float | None = None,
    cbar_label: str = "",
    add_boxes: bool = False,
    figsize: tuple[float, float] = (11.5, 7.3),
):
    da = clean_da(da)
    da_plot = subset_box(da, domain_box)
    da_plot = clean_da(da_plot)

    if vmin is None or vmax is None:
        if symmetric:
            vmin, vmax = symmetric_limits(da_plot)
        else:
            vals = da_plot.values
            vals = vals[np.isfinite(vals)]
            if vals.size == 0:
                vmin, vmax = 0, 1
            else:
                vmin = float(np.nanpercentile(vals, 2))
                vmax = float(np.nanpercentile(vals, 98))

    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax) if symmetric else None

    if HAS_CARTOPY:
        fig = plt.figure(figsize=figsize)
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent(domain_box, crs=ccrs.PlateCarree())

        mesh = ax.pcolormesh(
            da_plot["lon"],
            da_plot["lat"],
            da_plot.values,
            cmap=cmap,
            norm=norm,
            vmin=None if norm else vmin,
            vmax=None if norm else vmax,
            shading="auto",
            transform=ccrs.PlateCarree(),
        )

        add_map_features(ax, draw_labels=True)

        if add_boxes:
            add_sst_boxes(ax)

    else:
        fig, ax = plt.subplots(figsize=figsize)

        mesh = ax.pcolormesh(
            da_plot["lon"],
            da_plot["lat"],
            da_plot.values,
            cmap=cmap,
            norm=norm,
            vmin=None if norm else vmin,
            vmax=None if norm else vmax,
            shading="auto",
        )

        ax.set_xlim(domain_box[0], domain_box[1])
        ax.set_ylim(domain_box[2], domain_box[3])
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

        if add_boxes:
            add_sst_boxes(ax)

    cbar = plt.colorbar(mesh, ax=ax, orientation="vertical", shrink=0.82, pad=0.035)
    cbar.set_label(cbar_label, fontsize=10)
    cbar.ax.tick_params(labelsize=9)

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
    plt.close()

    print(f"Saved map: {out_file}")


def plot_vector_shaded_map(
    shade: xr.DataArray,
    u: xr.DataArray,
    v: xr.DataArray,
    title: str,
    out_file: Path,
    domain_box: list[float],
    cmap: str = "BrBG",
    cbar_label: str = "",
    symmetric: bool = True,
    figsize: tuple[float, float] = (12, 7.5),
):
    shade = clean_da(shade)
    u = clean_da(u)
    v = clean_da(v)

    shade_plot = clean_da(subset_box(shade, domain_box))
    u_plot = clean_da(subset_box(u, domain_box))
    v_plot = clean_da(subset_box(v, domain_box))

    u_plot = clean_da(u_plot.interp_like(shade_plot))
    v_plot = clean_da(v_plot.interp_like(shade_plot))

    vmin, vmax = symmetric_limits(shade_plot, percentile=98)

    lon = shade_plot["lon"].values
    lat = shade_plot["lat"].values
    lon2d, lat2d = np.meshgrid(lon, lat)

    stride_lat = max(1, len(lat) // 24)
    stride_lon = max(1, len(lon) // 32)
    sl = (slice(None, None, stride_lat), slice(None, None, stride_lon))

    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax) if symmetric else None

    if HAS_CARTOPY:
        fig = plt.figure(figsize=figsize)
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent(domain_box, crs=ccrs.PlateCarree())

        mesh = ax.pcolormesh(
            shade_plot["lon"],
            shade_plot["lat"],
            shade_plot.values,
            cmap=cmap,
            norm=norm,
            shading="auto",
            transform=ccrs.PlateCarree(),
        )

        ax.quiver(
            lon2d[sl],
            lat2d[sl],
            u_plot.values[sl],
            v_plot.values[sl],
            transform=ccrs.PlateCarree(),
            scale=None,
            width=0.0022,
            alpha=0.85,
        )

        add_map_features(ax, draw_labels=True)

    else:
        fig, ax = plt.subplots(figsize=figsize)

        mesh = ax.pcolormesh(
            shade_plot["lon"],
            shade_plot["lat"],
            shade_plot.values,
            cmap=cmap,
            norm=norm,
            shading="auto",
        )

        ax.quiver(
            lon2d[sl],
            lat2d[sl],
            u_plot.values[sl],
            v_plot.values[sl],
            scale=None,
            width=0.0022,
            alpha=0.85,
        )

        ax.set_xlim(domain_box[0], domain_box[1])
        ax.set_ylim(domain_box[2], domain_box[3])
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    cbar = plt.colorbar(mesh, ax=ax, orientation="vertical", shrink=0.82, pad=0.035)
    cbar.set_label(cbar_label, fontsize=10)
    cbar.ax.tick_params(labelsize=9)

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
    plt.close()

    print(f"Saved vector map: {out_file}")


# ==========================================================
# PLOT GROUPS
# ==========================================================

def plot_tej_and_u200():
    print("\n==================================================")
    print("Plotting TEJ and u200 maps")
    print("==================================================")

    domains = {
        "tej_domain": DOMAINS["tej_domain"],
        "africa_indian": DOMAINS["africa_indian"],
        "greater_horn": DOMAINS["greater_horn"],
    }

    for period in PERIODS:
        ds = open_diag(period)

        for domain_name, box in domains.items():
            title = (
                f"CFSv2 TEJ strength proxy (-u200)\n"
                f"{PERIOD_LABELS[period]} | stronger positive values = stronger easterly jet"
            )

            out_file = PLOT_DIRS["tej"] / domain_name / f"CFSv2_TEJ_strength_{period}_{domain_name}.png"

            plot_scalar_map(
                da=ds["tej_strength"],
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="RdBu_r",
                symmetric=True,
                cbar_label="TEJ strength proxy: -u200 (m s⁻¹)",
                figsize=(12, 7.4),
            )

            title = (
                f"CFSv2 200 hPa zonal wind\n"
                f"{PERIOD_LABELS[period]} | negative = easterly flow"
            )

            out_file = PLOT_DIRS["tej"] / domain_name / f"CFSv2_u200_{period}_{domain_name}.png"

            plot_scalar_map(
                da=ds["u200"],
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="RdBu_r",
                symmetric=True,
                cbar_label="u200 (m s⁻¹)",
                figsize=(12, 7.4),
            )

        ds.close()


def plot_divergence200():
    print("\n==================================================")
    print("Plotting 200 hPa divergence maps")
    print("==================================================")

    domains = {
        "greater_horn": DOMAINS["greater_horn"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    for period in PERIODS:
        ds = open_diag(period)

        for domain_name, box in domains.items():
            title = (
                f"CFSv2 200 hPa divergence\n"
                f"{PERIOD_LABELS[period]} | positive = upper-level divergence"
            )

            out_file = PLOT_DIRS["div200"] / domain_name / f"CFSv2_div200_{period}_{domain_name}.png"

            plot_scalar_map(
                da=ds["div200"],
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="RdBu_r",
                symmetric=True,
                cbar_label="200 hPa divergence (s⁻¹)",
                figsize=(12, 7.4),
            )

        ds.close()


def plot_moisture_flux_mfc():
    print("\n==================================================")
    print("Plotting 850 hPa moisture flux and MFC maps")
    print("==================================================")

    domains = {
        "greater_horn": DOMAINS["greater_horn"],
        "atlantic_congo_ethiopia": DOMAINS["atlantic_congo_ethiopia"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    for period in PERIODS:
        ds = open_diag(period)

        for domain_name, box in domains.items():
            title = (
                f"CFSv2 850 hPa moisture-flux convergence and moisture transport\n"
                f"{PERIOD_LABELS[period]} | positive shading = moisture convergence"
            )

            out_file = (
                PLOT_DIRS["moisture"]
                / domain_name
                / f"CFSv2_mfc850_quqv850_{period}_{domain_name}.png"
            )

            plot_vector_shaded_map(
                shade=ds["mfc850"],
                u=ds["qu850"],
                v=ds["qv850"],
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="BrBG",
                cbar_label="MFC850 proxy (kg kg⁻¹ s⁻¹)",
                symmetric=True,
                figsize=(12, 7.5),
            )

            title = (
                f"CFSv2 850 hPa wind speed and wind vectors\n"
                f"{PERIOD_LABELS[period]}"
            )

            out_file = (
                PLOT_DIRS["moisture"]
                / domain_name
                / f"CFSv2_wind850_vectors_{period}_{domain_name}.png"
            )

            plot_vector_shaded_map(
                shade=ds["wind_speed850"],
                u=ds["u850"],
                v=ds["v850"],
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="viridis",
                cbar_label="850 hPa wind speed (m s⁻¹)",
                symmetric=False,
                figsize=(12, 7.5),
            )

        ds.close()


def plot_omega():
    print("\n==================================================")
    print("Plotting omega vertical motion maps")
    print("==================================================")

    domains = {
        "greater_horn": DOMAINS["greater_horn"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    for period in PERIODS:
        ds = open_diag(period)

        for omega_var in ["omega500", "omega700"]:
            for domain_name, box in domains.items():
                level = "500 hPa" if omega_var == "omega500" else "700 hPa"

                title = (
                    f"CFSv2 {level} omega vertical motion\n"
                    f"{PERIOD_LABELS[period]} | negative = rising motion, positive = subsidence"
                )

                out_file = (
                    PLOT_DIRS["omega"]
                    / omega_var
                    / domain_name
                    / f"CFSv2_{omega_var}_{period}_{domain_name}.png"
                )

                plot_scalar_map(
                    da=ds[omega_var],
                    title=title,
                    out_file=out_file,
                    domain_box=box,
                    cmap="RdBu_r",
                    symmetric=True,
                    cbar_label=f"{omega_var} (Pa s⁻¹)",
                    figsize=(12, 7.4),
                )

        ds.close()


def plot_vp_strf():
    print("\n==================================================")
    print("Plotting velocity potential and streamfunction maps")
    print("==================================================")

    domains = {
        "global_tropics": DOMAINS["global_tropics"],
        "africa_indian": DOMAINS["africa_indian"],
    }

    for period in PERIODS:
        ds = open_diag(period)

        for var_name, label in {
            "vp200": "200 hPa velocity potential",
            "strf200": "200 hPa streamfunction",
        }.items():
            for domain_name, box in domains.items():
                title = (
                    f"CFSv2 {label}\n"
                    f"{PERIOD_LABELS[period]}"
                )

                out_file = (
                    PLOT_DIRS["vp_strf"]
                    / var_name
                    / domain_name
                    / f"CFSv2_{var_name}_{period}_{domain_name}.png"
                )

                plot_scalar_map(
                    da=ds[var_name],
                    title=title,
                    out_file=out_file,
                    domain_box=box,
                    cmap="RdBu_r",
                    symmetric=True,
                    cbar_label=label,
                    figsize=(13, 6.8) if domain_name == "global_tropics" else (12, 7.4),
                )

        ds.close()


def plot_heights():
    print("\n==================================================")
    print("Plotting z200 and z500 maps")
    print("==================================================")

    domains = {
        "greater_horn": DOMAINS["greater_horn"],
        "africa_indian": DOMAINS["africa_indian"],
        "north_africa_arabia": DOMAINS["north_africa_arabia"],
    }

    for period in PERIODS:
        ds = open_diag(period)

        for var_name, label in {
            "z200": "200 hPa geopotential height",
            "z500": "500 hPa geopotential height",
        }.items():
            for domain_name, box in domains.items():
                title = (
                    f"CFSv2 {label}\n"
                    f"{PERIOD_LABELS[period]}"
                )

                out_file = (
                    PLOT_DIRS["height"]
                    / var_name
                    / domain_name
                    / f"CFSv2_{var_name}_{period}_{domain_name}.png"
                )

                plot_scalar_map(
                    da=ds[var_name],
                    title=title,
                    out_file=out_file,
                    domain_box=box,
                    cmap="viridis",
                    symmetric=False,
                    cbar_label=f"{label} (gpm)",
                    figsize=(12, 7.4),
                )

        ds.close()


def plot_sst_proxy():
    print("\n==================================================")
    print("Plotting SST proxy maps")
    print("==================================================")

    domains = {
        "global_tropics": DOMAINS["global_tropics"],
        "indian_ocean": DOMAINS["indian_ocean"],
    }

    for period in PERIODS:
        ds = open_diag(period)

        for domain_name, box in domains.items():
            title = (
                f"CFSv2 SST / near-surface ocean temperature proxy\n"
                f"{PERIOD_LABELS[period]} | raw forecast field, not anomaly"
            )

            out_file = PLOT_DIRS["sst"] / domain_name / f"CFSv2_sst_proxy_{period}_{domain_name}.png"

            plot_scalar_map(
                da=ds["sst_proxy"],
                title=title,
                out_file=out_file,
                domain_box=box,
                cmap="coolwarm",
                symmetric=False,
                cbar_label="SST proxy",
                add_boxes=True,
                figsize=(13, 6.8) if domain_name == "global_tropics" else (12, 7.4),
            )

        ds.close()


def plot_area_mean_charts():
    print("\n==================================================")
    print("Plotting area-mean diagnostic charts")
    print("==================================================")

    csv_path = TABLE_DIR / "cfsv2_dynamic_area_mean_diagnostics.csv"

    if not csv_path.exists():
        print(f"Missing area-mean table: {csv_path}")
        return

    df = pd.read_csv(csv_path)

    period_order = {
        "Jun_2026": 1,
        "Jul_2026": 2,
        "Aug_2026": 3,
        "Sep_2026": 4,
        "JJA_2026": 5,
        "JJAS_2026": 6,
    }

    df["period_order"] = df["period"].map(period_order)
    df = df.sort_values("period_order")

    diagnostics_to_plot = [
        "tej_strength",
        "div200",
        "mfc850",
        "omega500",
        "omega700",
        "vp200",
        "z200",
        "z500",
    ]

    for diagnostic in diagnostics_to_plot:
        sub = df[
            (df["domain"] == "ethiopia")
            & (df["diagnostic"] == diagnostic)
        ].copy()

        if sub.empty:
            continue

        fig, ax = plt.subplots(figsize=(9, 5.2))

        ax.plot(sub["period"], sub["value"], marker="o")
        ax.axhline(0, linewidth=0.9, alpha=0.7)
        ax.grid(axis="y", linestyle="--", alpha=0.35)

        units = str(sub["units"].iloc[0])

        ax.set_title(
            f"CFSv2 Ethiopia area-mean {diagnostic}",
            fontsize=14,
            fontweight="bold",
        )
        ax.set_xlabel("Period")
        ax.set_ylabel(f"{diagnostic} ({units})")
        ax.tick_params(axis="x", rotation=30)

        out_file = PLOT_DIRS["charts"] / f"CFSv2_Ethiopia_area_mean_{diagnostic}.png"

        plt.tight_layout()
        plt.savefig(out_file, dpi=DPI, bbox_inches="tight")
        plt.close()

        print(f"Saved chart: {out_file}")


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("Plot CFSv2 dynamic diagnostics")
    print("==================================================")
    print(f"Input diagnostics: {DIAG_DIR}")
    print(f"Output maps:       {MAP_DIR}")

    plot_tej_and_u200()
    plot_divergence200()
    plot_moisture_flux_mfc()
    plot_omega()
    plot_vp_strf()
    plot_heights()
    plot_sst_proxy()
    plot_area_mean_charts()

    print("\n==================================================")
    print("CFSv2 DYNAMIC DIAGNOSTIC PLOTTING FINISHED")
    print("==================================================")
    print(f"Main output folder: {MAP_DIR}")

    print("\nKey interpretation from the current Ethiopia/JJAS summary:")
    print("- Moderate TEJ strength supports a physically active Kiremt upper-level jet background.")
    print("- Negative div200 indicates upper-level convergence over Ethiopia, which can suppress deep convection locally.")
    print("- Positive mfc850 indicates low-level moisture convergence, which supports rainfall potential.")
    print("- Negative omega500 and omega700 indicate rising-motion tendency, which supports convection.")
    print("- These are raw CFSv2 forecast diagnostics from the June 2026 initialization, not anomalies from the May 2026 NMME ensemble mean.")

    print("\nNext recommended script:")
    print("    scripts\\12_integrate_nmme_cfsv2_evidence.py")


if __name__ == "__main__":
    main()