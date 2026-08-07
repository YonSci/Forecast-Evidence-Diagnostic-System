from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, ListedColormap, BoundaryNorm
from matplotlib.patches import Rectangle

# ==========================================================
# OPTIONAL CARTOPY IMPORT
# ==========================================================
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
except Exception:
    HAS_CARTOPY = False
    print("Cartopy not available. Maps will be plotted without coastlines/borders.")


# ==========================================================
# USER SETTINGS
# ==========================================================

NC_FILE = Path("NMME_May2026/NMME.prate.202605.ENSMEAN.anom.nc")

OUT_DIR = Path("plots/NMME_May2026_precip_anomaly_dualstyle")
OUT_DIR.mkdir(parents=True, exist_ok=True)

REGIONS = {
    "global": None,
    "east_africa": [20, 55, -15, 20],
    "ethiopia": [32, 49, 3, 15],
    "indian_ocean_asia": [30, 130, -35, 45],
}

IRI_LIKE_REGIONS = {
    "africa_iri_style": [-20, 65, -40, 43],
    "east_africa": [20, 55, -15, 20],
    "ethiopia": [32, 49, 3, 15],
}

STANDARD_CMAP = "BrBG"


# ==========================================================
# REFERENCE-STYLE COLOR BAR
# ==========================================================

REFERENCE_LEVELS = [
    -500, -400, -300, -200, -125, -75, -40, -20, -5,
       5,   20,   40,   75,  125, 200, 300, 400, 500
]

REFERENCE_COLORS = [
    "#8b004f",
    "#c0005a",
    "#d73027",
    "#f46d43",
    "#fdae61",
    "#d98c00",
    "#f2c230",
    "#fff176",
    "#fff7bc",
    "#ffffff",
    "#d9f0d3",
    "#a6e6a3",
    "#4dd84d",
    "#00b050",
    "#00bcd4",
    "#3399ff",
    "#7e57c2",
    "#b388ff",
    "#6a1b9a",
]

REFERENCE_CMAP = ListedColormap(REFERENCE_COLORS)
REFERENCE_NORM = BoundaryNorm(
    boundaries=REFERENCE_LEVELS,
    ncolors=REFERENCE_CMAP.N,
    extend="both"
)


# ==========================================================
# IRI-LIKE ANOMALY CATEGORY STYLE
# This is anomaly-category style, not true probability.
# ==========================================================

ANOM_CLASS_LEVELS = [
    -1e9, -200, -125, -75, -40, -20,
       20,   40,   75, 125, 200, 1e9
]

ANOM_CLASS_COLORS = [
    "#7f3b08",
    "#b35806",
    "#e08214",
    "#e6c22e",
    "#ffff00",
    "#ffffff",
    "#d9f0d3",
    "#a6dba0",
    "#5aae61",
    "#4393c3",
    "#2166ac",
]

ANOM_CLASS_CMAP = ListedColormap(ANOM_CLASS_COLORS)
ANOM_CLASS_NORM = BoundaryNorm(
    boundaries=ANOM_CLASS_LEVELS,
    ncolors=ANOM_CLASS_CMAP.N
)


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def find_lat_lon_names(ds):
    names = list(ds.coords) + list(ds.dims)

    lat_name = None
    lon_name = None

    for name in names:
        n = name.lower()

        if n in ["lat", "latitude", "y"]:
            lat_name = name

        if n in ["lon", "longitude", "x"]:
            lon_name = name

    if lat_name is None or lon_name is None:
        raise ValueError(
            f"Could not find latitude/longitude names.\nAvailable names: {names}"
        )

    return lat_name, lon_name


def choose_main_variable(ds, lat_name, lon_name):
    priority_names = [
        "prate",
        "precip",
        "precipitation",
        "precip_anom",
        "rain",
        "rainfall",
    ]

    for name in priority_names:
        if name in ds.data_vars:
            return name

    for var in ds.data_vars:
        da = ds[var]
        if lat_name in da.dims and lon_name in da.dims:
            return var

    raise ValueError(
        f"Could not find suitable gridded variable.\nData variables: {list(ds.data_vars)}"
    )


def standardize_longitude(da, lon_name):
    lon = da[lon_name]

    if float(lon.max()) > 180:
        new_lon = ((lon + 180) % 360) - 180
        da = da.assign_coords({lon_name: new_lon})
        da = da.sortby(lon_name)

    return da


def convert_precip_units_if_needed(da):
    """
    Convert precipitation rate anomaly to mm/day when needed.

    Common CPC/NMME units:
        mm/s
        mm s-1
        kg m-2 s-1

    Conversion:
        1 mm/s = 86400 mm/day
    """

    units_original = str(da.attrs.get("units", "")).strip()
    units = units_original.lower().replace(" ", "")

    print(f"\nOriginal precipitation units: {units_original}")

    should_convert = False

    if units in ["mm/s", "mms-1", "mmsec-1", "mmsecond-1"]:
        should_convert = True

    if "mm/s" in units:
        should_convert = True

    if "s-1" in units and "mm" in units:
        should_convert = True

    if "kg" in units and "s-1" in units:
        should_convert = True

    if "kg" in units and "/s" in units:
        should_convert = True

    if should_convert:
        da = da * 86400.0
        da.attrs["units"] = "mm/day"
        da.attrs["conversion_note"] = (
            f"Converted from {units_original} to mm/day by multiplying by 86400."
        )
        print("Converted precipitation anomaly from rate to mm/day.")
    else:
        print("No precipitation unit conversion applied.")

    return da


def find_forecast_dimension(da, lat_name, lon_name):
    non_spatial_dims = [
        d for d in da.dims
        if d not in [lat_name, lon_name]
    ]

    if not non_spatial_dims:
        raise ValueError("No forecast/lead dimension found.")

    preferred = [
        "target",
        "lead",
        "leads",
        "l",
        "time",
        "t",
        "month",
        "forecast_month",
    ]

    for p in preferred:
        for d in non_spatial_dims:
            if d.lower() == p.lower():
                return d

    for d in non_spatial_dims:
        attrs_text = ""

        if d in da.coords:
            attrs_text = " ".join(
                [
                    str(da[d].attrs.get("long_name", "")),
                    str(da[d].attrs.get("standard_name", "")),
                    str(da[d].attrs.get("axis", "")),
                    str(da[d].attrs.get("units", "")),
                ]
            ).lower()

        if (
            "target" in attrs_text
            or "forecast" in attrs_text
            or "lead" in attrs_text
            or "time" in attrs_text
        ):
            return d

    return non_spatial_dims[0]


def reduce_extra_dimensions(da, lat_name, lon_name, forecast_dim):
    keep_dims = [forecast_dim, lat_name, lon_name]

    extra_dims = [
        d for d in da.dims
        if d not in keep_dims
    ]

    if extra_dims:
        print(f"\nAveraging over extra dimensions: {extra_dims}")
        da = da.mean(dim=extra_dims, skipna=True)

    return da


def select_june_july_august(da, forecast_dim):
    """
    For CPC May 2026 NMME files:
        index 0 = June 2026
        index 1 = July 2026
        index 2 = August 2026
    """

    print(f"\nForecast dimension: {forecast_dim}")

    if forecast_dim in da.coords:
        print("Forecast coordinate values:")
        print(da[forecast_dim].values)

    n_forecasts = da.sizes[forecast_dim]

    if n_forecasts < 3:
        raise ValueError(
            f"Need at least 3 forecast months, but found only {n_forecasts}."
        )

    jun = da.isel({forecast_dim: 0}).squeeze(drop=True)
    jul = da.isel({forecast_dim: 1}).squeeze(drop=True)
    aug = da.isel({forecast_dim: 2}).squeeze(drop=True)

    return {
        "Jun_2026": jun,
        "Jul_2026": jul,
        "Aug_2026": aug,
    }


def subset_region(da, extent, lat_name, lon_name):
    if extent is None:
        return da

    lon_min, lon_max, lat_min, lat_max = extent

    lat_values = da[lat_name].values

    if lat_values[0] < lat_values[-1]:
        lat_slice = slice(lat_min, lat_max)
    else:
        lat_slice = slice(lat_max, lat_min)

    return da.sel(
        {
            lon_name: slice(lon_min, lon_max),
            lat_name: lat_slice,
        }
    )


def ensure_lat_lon_order(da, lat_name, lon_name):
    if lat_name in da.dims and lon_name in da.dims:
        return da.transpose(lat_name, lon_name)
    return da


def get_symmetric_limits(da):
    values = da.values
    values = values[np.isfinite(values)]

    if values.size == 0:
        return -1, 1

    max_abs = np.nanpercentile(np.abs(values), 98)

    if np.isnan(max_abs) or max_abs == 0:
        max_abs = 1

    return -max_abs, max_abs


def add_map_features(ax):
    if not HAS_CARTOPY:
        return

    ax.coastlines(linewidth=1.0)
    ax.add_feature(cfeature.BORDERS, linewidth=0.6)
    ax.add_feature(cfeature.LAKES, linewidth=0.4, alpha=0.6)
    ax.add_feature(cfeature.RIVERS, linewidth=0.35, alpha=0.45)

    gl = ax.gridlines(
        draw_labels=True,
        linewidth=0.35,
        alpha=0.5,
        linestyle="--",
    )

    gl.top_labels = False
    gl.right_labels = False


# ==========================================================
# PLOTTING FUNCTIONS
# ==========================================================

def plot_standard_map(da, title, out_file, extent, lat_name, lon_name):
    da_plot = subset_region(da, extent, lat_name, lon_name)
    da_plot = ensure_lat_lon_order(da_plot, lat_name, lon_name)

    vmin, vmax = get_symmetric_limits(da_plot)
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)

    units = da_plot.attrs.get("units", "unknown")

    if HAS_CARTOPY:
        fig = plt.figure(figsize=(12, 7))
        ax = plt.axes(projection=ccrs.PlateCarree())

        if extent is not None:
            ax.set_extent(extent, crs=ccrs.PlateCarree())

        da_plot.plot.pcolormesh(
            ax=ax,
            x=lon_name,
            y=lat_name,
            transform=ccrs.PlateCarree(),
            cmap=STANDARD_CMAP,
            norm=norm,
            add_colorbar=True,
            cbar_kwargs={
                "label": f"Precipitation anomaly ({units})",
                "shrink": 0.82,
                "pad": 0.04,
            },
        )

        add_map_features(ax)

    else:
        fig, ax = plt.subplots(figsize=(12, 7))

        da_plot.plot.pcolormesh(
            ax=ax,
            x=lon_name,
            y=lat_name,
            cmap=STANDARD_CMAP,
            norm=norm,
            add_colorbar=True,
            cbar_kwargs={
                "label": f"Precipitation anomaly ({units})"
            },
        )

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    plt.title(title, fontsize=17, fontweight="bold")
    plt.tight_layout()

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved standard plot: {out_file}")


def plot_reference_style_map(
    da,
    title,
    out_file,
    extent,
    lat_name,
    lon_name,
    init_label="Init: 00Z May 08 2026",
    valid_label=None,
):
    """
    Discrete fixed-level plot similar to TropicalTidbits-style maps.

    Global plots use a special compact layout to avoid large blank space.
    """

    da_plot = subset_region(da, extent, lat_name, lon_name)
    da_plot = ensure_lat_lon_order(da_plot, lat_name, lon_name)

    units = da_plot.attrs.get("units", "unknown")
    is_global = extent is None

    if is_global:
        fig = plt.figure(figsize=(16, 8))
        map_rect = [0.055, 0.08, 0.77, 0.78]
        cbar_rect = [0.865, 0.12, 0.026, 0.70]
        title_y = 0.975
        header_y = 0.905
    else:
        fig = plt.figure(figsize=(14.5, 9.2))
        map_rect = [0.065, 0.08, 0.78, 0.80]
        cbar_rect = [0.875, 0.13, 0.028, 0.72]
        title_y = 0.975
        header_y = 0.910

    if HAS_CARTOPY:
        ax = fig.add_axes(map_rect, projection=ccrs.PlateCarree())

        if extent is not None:
            ax.set_extent(extent, crs=ccrs.PlateCarree())

        mesh = ax.pcolormesh(
            da_plot[lon_name],
            da_plot[lat_name],
            da_plot.values,
            transform=ccrs.PlateCarree(),
            cmap=REFERENCE_CMAP,
            norm=REFERENCE_NORM,
            shading="auto",
        )

        add_map_features(ax)

    else:
        ax = fig.add_axes(map_rect)

        mesh = ax.pcolormesh(
            da_plot[lon_name],
            da_plot[lat_name],
            da_plot.values,
            cmap=REFERENCE_CMAP,
            norm=REFERENCE_NORM,
            shading="auto",
        )

        ax.set_xlabel("Longitude", fontsize=15)
        ax.set_ylabel("Latitude", fontsize=15)

    cax = fig.add_axes(cbar_rect)

    cbar = fig.colorbar(
        mesh,
        cax=cax,
        orientation="vertical",
        extend="both",
        ticks=REFERENCE_LEVELS,
    )

    cbar.set_label(
        f"Precipitation anomaly ({units})",
        fontsize=17,
        fontweight="bold"
    )
    cbar.ax.tick_params(labelsize=15)

    fig.suptitle(
        title,
        fontsize=24,
        fontweight="bold",
        y=title_y
    )

    fig.text(
        0.08,
        header_y,
        init_label,
        ha="left",
        va="center",
        fontsize=17,
        fontweight="bold",
    )

    if valid_label is not None:
        fig.text(
            0.50,
            header_y,
            valid_label,
            ha="center",
            va="center",
            fontsize=17,
            fontweight="bold",
        )

    fig.text(
        0.86,
        header_y,
        "NMME / CPC",
        ha="right",
        va="center",
        fontsize=17,
        fontweight="bold",
        alpha=0.80,
    )

    ax.tick_params(labelsize=15)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved reference-style plot: {out_file}")


def draw_iri_like_legend(fig, units):
    """
    Draw a clean IRI-like bottom legend with no overlap.
    This legend represents anomaly magnitude classes, not probability.
    """

    legend_ax = fig.add_axes([0.10, 0.035, 0.80, 0.135])
    legend_ax.set_xlim(0, 1)
    legend_ax.set_ylim(0, 1)
    legend_ax.axis("off")

    legend_ax.text(
        0.50,
        0.96,
        f"Anomaly-category strength ({units}) — not probability",
        ha="center",
        va="top",
        fontsize=14,
        fontweight="bold",
    )

    below_colors = ["#ffff00", "#e6c22e", "#e08214", "#b35806", "#7f3b08"]
    above_colors = ["#d9f0d3", "#a6dba0", "#5aae61", "#4393c3", "#2166ac"]
    labels = ["20", "40", "75", "125", "200+"]

    box_w = 0.055
    box_h = 0.20
    box_y = 0.30
    label_y = 0.18
    title_y = 0.61

    # Below normal legend
    x0 = 0.03
    legend_ax.text(
        x0 + 2.5 * box_w,
        title_y,
        "Below normal / negative anomaly",
        ha="center",
        va="bottom",
        fontsize=11,
    )

    for i, color in enumerate(below_colors):
        legend_ax.add_patch(
            Rectangle(
                (x0 + i * box_w, box_y),
                box_w,
                box_h,
                facecolor=color,
                edgecolor="black",
                linewidth=0.45,
            )
        )
        legend_ax.text(
            x0 + i * box_w + box_w / 2,
            label_y,
            labels[i],
            ha="center",
            va="top",
            fontsize=10,
        )

    # Near normal legend
    x1 = 0.445
    legend_ax.text(
        x1 + 0.055,
        title_y,
        "Near normal",
        ha="center",
        va="bottom",
        fontsize=11,
    )

    legend_ax.add_patch(
        Rectangle(
            (x1, box_y),
            0.11,
            box_h,
            facecolor="#ffffff",
            edgecolor="black",
            linewidth=0.45,
        )
    )

    legend_ax.text(
        x1 + 0.055,
        label_y,
        "−20 to 20",
        ha="center",
        va="top",
        fontsize=10,
    )

    # Above normal legend
    x2 = 0.66
    legend_ax.text(
        x2 + 2.5 * box_w,
        title_y,
        "Above normal / positive anomaly",
        ha="center",
        va="bottom",
        fontsize=11,
    )

    for i, color in enumerate(above_colors):
        legend_ax.add_patch(
            Rectangle(
                (x2 + i * box_w, box_y),
                box_w,
                box_h,
                facecolor=color,
                edgecolor="black",
                linewidth=0.45,
            )
        )
        legend_ax.text(
            x2 + i * box_w + box_w / 2,
            label_y,
            labels[i],
            ha="center",
            va="top",
            fontsize=10,
        )


def plot_iri_like_anomaly_category_map(
    da,
    title,
    out_file,
    extent,
    lat_name,
    lon_name,
    issued_label="Issued May 2026",
    valid_label="June-July-August 2026",
):
    """
    Produce a map visually similar to the IRI most-likely-category map.

    IMPORTANT:
    This is an anomaly-category map, not a true IRI probability map.
    True IRI probability maps require tercile probability data.
    """

    da_plot = subset_region(da, extent, lat_name, lon_name)
    da_plot = ensure_lat_lon_order(da_plot, lat_name, lon_name)

    units = da_plot.attrs.get("units", "unknown")

    # Larger figure and explicit layout areas to prevent footer overlap
    fig = plt.figure(figsize=(12.0, 11.0))

    map_rect = [0.08, 0.255, 0.82, 0.655]
    note_y = 0.205

    if HAS_CARTOPY:
        ax = fig.add_axes(map_rect, projection=ccrs.PlateCarree())
        ax.set_extent(extent, crs=ccrs.PlateCarree())

        mesh = ax.pcolormesh(
            da_plot[lon_name],
            da_plot[lat_name],
            da_plot.values,
            transform=ccrs.PlateCarree(),
            cmap=ANOM_CLASS_CMAP,
            norm=ANOM_CLASS_NORM,
            shading="auto",
        )

        ax.coastlines(linewidth=0.9)
        ax.add_feature(cfeature.BORDERS, linewidth=0.45)
        ax.add_feature(cfeature.LAKES, linewidth=0.25, alpha=0.5)
        ax.add_feature(cfeature.RIVERS, linewidth=0.25, alpha=0.35)

        gl = ax.gridlines(
            draw_labels=True,
            linewidth=0.25,
            alpha=0.45,
            linestyle="--",
        )
        gl.top_labels = False
        gl.right_labels = False

    else:
        ax = fig.add_axes(map_rect)

        mesh = ax.pcolormesh(
            da_plot[lon_name],
            da_plot[lat_name],
            da_plot.values,
            cmap=ANOM_CLASS_CMAP,
            norm=ANOM_CLASS_NORM,
            shading="auto",
        )

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    ax.set_title(
        f"{title}\n{valid_label}, {issued_label}",
        fontsize=18,
        fontweight="normal",
        pad=14,
    )

    ax.tick_params(labelsize=11)

    # Explanatory note placed between map and legend, no overlap
    fig.text(
        0.08,
        note_y,
        "White indicates near-zero anomaly. This plot is derived from NMME anomaly data, not official IRI probability terciles.",
        ha="left",
        va="center",
        fontsize=9,
        bbox=dict(facecolor="white", edgecolor="black", linewidth=0.5),
    )

    draw_iri_like_legend(fig, units)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved IRI-like anomaly-category plot: {out_file}")


# ==========================================================
# MAIN WORKFLOW
# ==========================================================

def main():
    if not NC_FILE.exists():
        raise FileNotFoundError(
            f"\nFile not found:\n{NC_FILE}\n\n"
            "Check that the NetCDF file exists in:\n"
            "NMME_May2026/\n"
        )

    print(f"Opening: {NC_FILE}")

    ds = xr.open_dataset(NC_FILE, decode_times=False)

    print("\nDataset summary:")
    print(ds)

    lat_name, lon_name = find_lat_lon_names(ds)
    var_name = choose_main_variable(ds, lat_name, lon_name)

    print(f"\nDetected latitude coordinate:  {lat_name}")
    print(f"Detected longitude coordinate: {lon_name}")
    print(f"Selected variable:             {var_name}")

    da = ds[var_name]

    da = da.squeeze(drop=True)
    da = standardize_longitude(da, lon_name)
    da = convert_precip_units_if_needed(da)

    forecast_dim = find_forecast_dimension(da, lat_name, lon_name)
    print(f"Detected forecast dimension:   {forecast_dim}")

    da = reduce_extra_dimensions(da, lat_name, lon_name, forecast_dim)

    monthly_mean = select_june_july_august(da, forecast_dim)

    # JJA mean anomaly in mm/day
    jja_mean = xr.concat(
        [
            monthly_mean["Jun_2026"],
            monthly_mean["Jul_2026"],
            monthly_mean["Aug_2026"],
        ],
        dim="month",
    ).mean("month", skipna=True)

    jja_mean.attrs = monthly_mean["Jun_2026"].attrs.copy()
    jja_mean.attrs["units"] = "mm/day"

    monthly_mean["JJA_2026_mean"] = jja_mean

    # JJA total anomaly in mm/season
    jja_total = (
        monthly_mean["Jun_2026"] * 30
        + monthly_mean["Jul_2026"] * 31
        + monthly_mean["Aug_2026"] * 31
    )

    jja_total.attrs = monthly_mean["Jun_2026"].attrs.copy()
    jja_total.attrs["units"] = "mm/season"

    monthly_mean["JJA_2026_total"] = jja_total

    # Monthly total anomalies in mm/month for reference-style and IRI-like maps
    monthly_total = {
        "Jun_2026_total": monthly_mean["Jun_2026"] * 30,
        "Jul_2026_total": monthly_mean["Jul_2026"] * 31,
        "Aug_2026_total": monthly_mean["Aug_2026"] * 31,
        "JJA_2026_total": jja_total,
    }

    monthly_total["Jun_2026_total"].attrs = monthly_mean["Jun_2026"].attrs.copy()
    monthly_total["Jul_2026_total"].attrs = monthly_mean["Jul_2026"].attrs.copy()
    monthly_total["Aug_2026_total"].attrs = monthly_mean["Aug_2026"].attrs.copy()

    monthly_total["Jun_2026_total"].attrs["units"] = "mm/month"
    monthly_total["Jul_2026_total"].attrs["units"] = "mm/month"
    monthly_total["Aug_2026_total"].attrs["units"] = "mm/month"
    monthly_total["JJA_2026_total"].attrs["units"] = "mm/season"

    valid_labels = {
        "Jun_2026": "Valid for: Jun 2026",
        "Jul_2026": "Valid for: Jul 2026",
        "Aug_2026": "Valid for: Aug 2026",
        "JJA_2026_mean": "Valid for: Jun-Aug 2026",
        "JJA_2026_total": "Valid for: Jun-Aug 2026",
        "Jun_2026_total": "Valid for: Jun 2026",
        "Jul_2026_total": "Valid for: Jul 2026",
        "Aug_2026_total": "Valid for: Aug 2026",
    }

    iri_valid_labels = {
        "Jun_2026_total": "June 2026",
        "Jul_2026_total": "July 2026",
        "Aug_2026_total": "August 2026",
        "JJA_2026_total": "June-July-August 2026",
    }

    model_name = NC_FILE.name.split(".")[0]

    # ======================================================
    # STANDARD PLOTS
    # ======================================================
    for region_name, extent in REGIONS.items():
        for label, data in monthly_mean.items():
            clean_label = label.replace("_", " ")

            title = (
                f"{model_name} precipitation anomaly: {clean_label}\n"
                "Initialized May 2026"
            )

            out_file = (
                OUT_DIR
                / "standard"
                / region_name
                / f"{model_name}_prate_{label}_{region_name}_standard.png"
            )

            plot_standard_map(
                da=data,
                title=title,
                out_file=out_file,
                extent=extent,
                lat_name=lat_name,
                lon_name=lon_name,
            )

    # ======================================================
    # REFERENCE-STYLE PLOTS
    # ======================================================
    for region_name, extent in REGIONS.items():
        for label, data in monthly_total.items():
            clean_label = label.replace("_", " ")

            title = f"NMME precipitation anomaly: {clean_label}"

            out_file = (
                OUT_DIR
                / "reference_style"
                / region_name
                / f"{model_name}_prate_{label}_{region_name}_reference_style.png"
            )

            plot_reference_style_map(
                da=data,
                title=title,
                out_file=out_file,
                extent=extent,
                lat_name=lat_name,
                lon_name=lon_name,
                init_label="Init: 00Z May 08 2026",
                valid_label=valid_labels.get(label),
            )

    # ======================================================
    # IRI-LIKE ANOMALY CATEGORY PLOTS
    # ======================================================
    for region_name, extent in IRI_LIKE_REGIONS.items():
        for label, data in monthly_total.items():
            out_file = (
                OUT_DIR
                / "iri_like_anomaly_category"
                / region_name
                / f"{model_name}_prate_{label}_{region_name}_iri_like_anomaly_category.png"
            )

            plot_iri_like_anomaly_category_map(
                da=data,
                title="NMME anomaly-category forecast for precipitation",
                out_file=out_file,
                extent=extent,
                lat_name=lat_name,
                lon_name=lon_name,
                issued_label="Issued May 2026",
                valid_label=iri_valid_labels.get(label, label),
            )

    # ======================================================
    # SAVE NETCDF OUTPUTS
    # ======================================================
    jja_mean_out = OUT_DIR / f"{model_name}_prate_JJA_2026_mean_anomaly_mm_day.nc"
    jja_total_out = OUT_DIR / f"{model_name}_prate_JJA_2026_total_anomaly_mm_season.nc"

    jja_mean.to_netcdf(jja_mean_out)
    jja_total.to_netcdf(jja_total_out)

    print("\nDone.")
    print(f"Saved JJA mean NetCDF:  {jja_mean_out}")
    print(f"Saved JJA total NetCDF: {jja_total_out}")
    print(f"Saved plots in:         {OUT_DIR}")


if __name__ == "__main__":
    main()