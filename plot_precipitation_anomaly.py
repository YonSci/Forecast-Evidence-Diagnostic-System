from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

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

# Main downloaded NMME May 2026 precipitation anomaly file
NC_FILE = Path("NMME_May2026/NMME.prate.202605.ENSMEAN.anom.nc")

# Output folder
OUT_DIR = Path("plots/NMME_May2026_precip_anomaly")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Regions: [lon_min, lon_max, lat_min, lat_max]
REGIONS = {
    "global": None,
    "east_africa": [20, 55, -15, 20],
    "ethiopia": [32, 49, 3, 15],
}

# Color map for precipitation anomaly
CMAP = "BrBG"


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def find_lat_lon_names(ds):
    """
    Detect latitude and longitude coordinate names.
    """
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
    """
    Choose the main gridded precipitation variable.
    """
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
    """
    Convert longitude from 0–360 to -180–180 if needed.
    """
    lon = da[lon_name]

    if float(lon.max()) > 180:
        new_lon = ((lon + 180) % 360) - 180
        da = da.assign_coords({lon_name: new_lon})
        da = da.sortby(lon_name)

    return da


def convert_precip_units_if_needed(da):
    """
    Convert precipitation rate anomaly to mm/day when needed.

    Common CPC/NMME units may appear as:
        mm/s
        mm s-1
        mm sec-1
        kg m-2 s-1

    Conversion:
        1 mm/s = 86400 mm/day
        1 kg m-2 s-1 = 1 mm/s = 86400 mm/day
    """

    units_original = str(da.attrs.get("units", "")).strip()
    units = units_original.lower().replace(" ", "")

    print(f"\nOriginal precipitation units: {units_original}")

    should_convert = False

    # Explicit mm/s forms
    if units in ["mm/s", "mms-1", "mmsec-1", "mmsecond-1"]:
        should_convert = True

    if "mm/s" in units:
        should_convert = True

    if "s-1" in units and "mm" in units:
        should_convert = True

    # kg m-2 s-1 is equivalent to mm/s for precipitation water depth
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
    """
    Detect forecast lead/target/month dimension.
    CPC NMME files often use 'target'.
    """
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
    """
    Average over extra dimensions, for example ensemble member/model dimensions.
    """
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
    Select June, July, August 2026 from May 2026 initialization.

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
    """
    Subset map to selected region.
    """
    if extent is None:
        return da

    lon_min, lon_max, lat_min, lat_max = extent

    lat_values = da[lat_name].values

    if lat_values[0] < lat_values[-1]:
        lat_slice = slice(lat_min, lat_max)
    else:
        lat_slice = slice(lat_max, lat_min)

    da_sub = da.sel(
        {
            lon_name: slice(lon_min, lon_max),
            lat_name: lat_slice,
        }
    )

    return da_sub


def get_symmetric_limits(da):
    """
    Use symmetric color limits around zero.
    """
    values = da.values
    values = values[np.isfinite(values)]

    if values.size == 0:
        return -1, 1

    max_abs = np.nanpercentile(np.abs(values), 98)

    if np.isnan(max_abs) or max_abs == 0:
        max_abs = 1

    return -max_abs, max_abs


def plot_map(da, title, out_file, extent, lat_name, lon_name):
    """
    Plot one anomaly map and save it.
    """
    da_plot = subset_region(da, extent, lat_name, lon_name)

    vmin, vmax = get_symmetric_limits(da_plot)
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)

    units = da_plot.attrs.get("units", "unknown")

    if HAS_CARTOPY:
        fig = plt.figure(figsize=(11, 6))
        ax = plt.axes(projection=ccrs.PlateCarree())

        if extent is not None:
            ax.set_extent(extent, crs=ccrs.PlateCarree())

        da_plot.plot.pcolormesh(
            ax=ax,
            x=lon_name,
            y=lat_name,
            transform=ccrs.PlateCarree(),
            cmap=CMAP,
            norm=norm,
            add_colorbar=True,
            cbar_kwargs={
                "label": f"Precipitation anomaly ({units})",
                "shrink": 0.82,
                "pad": 0.04,
            },
        )

        ax.coastlines(linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5)
        ax.add_feature(cfeature.LAKES, linewidth=0.3, alpha=0.6)
        ax.add_feature(cfeature.RIVERS, linewidth=0.3, alpha=0.5)

        gl = ax.gridlines(
            draw_labels=True,
            linewidth=0.3,
            alpha=0.5,
            linestyle="--",
        )
        gl.top_labels = False
        gl.right_labels = False

    else:
        fig, ax = plt.subplots(figsize=(11, 6))

        da_plot.plot.pcolormesh(
            ax=ax,
            x=lon_name,
            y=lat_name,
            cmap=CMAP,
            norm=norm,
            add_colorbar=True,
            cbar_kwargs={
                "label": f"Precipitation anomaly ({units})"
            },
        )

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

    plt.title(title, fontsize=13)
    plt.tight_layout()

    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved: {out_file}")


# ==========================================================
# MAIN WORKFLOW
# ==========================================================

def main():
    if not NC_FILE.exists():
        raise FileNotFoundError(
            f"\nFile not found:\n{NC_FILE}\n\n"
            "Check that the NetCDF file exists in this folder:\n"
            "NMME_May2026/\n"
        )

    print(f"Opening: {NC_FILE}")

    # Important:
    # CPC NMME files use target units like:
    # "months since 1960-01-02 21:00:00"
    # xarray cannot decode this automatically with the default calendar.
    ds = xr.open_dataset(NC_FILE, decode_times=False)

    print("\nDataset summary:")
    print(ds)

    lat_name, lon_name = find_lat_lon_names(ds)
    var_name = choose_main_variable(ds, lat_name, lon_name)

    print(f"\nDetected latitude coordinate:  {lat_name}")
    print(f"Detected longitude coordinate: {lon_name}")
    print(f"Selected variable:             {var_name}")

    da = ds[var_name]

    # Remove dimensions with length 1
    da = da.squeeze(drop=True)

    # Standardize longitude to -180 to 180
    da = standardize_longitude(da, lon_name)

    # Convert precipitation units from mm/s to mm/day
    da = convert_precip_units_if_needed(da)

    # Detect forecast dimension
    forecast_dim = find_forecast_dimension(da, lat_name, lon_name)
    print(f"Detected forecast dimension:   {forecast_dim}")

    # Average extra dimensions if needed
    da = reduce_extra_dimensions(da, lat_name, lon_name, forecast_dim)

    # Select June, July, August 2026
    monthly_maps = select_june_july_august(da, forecast_dim)

    # JJA mean anomaly in mm/day
    jja_mean = xr.concat(
        [
            monthly_maps["Jun_2026"],
            monthly_maps["Jul_2026"],
            monthly_maps["Aug_2026"],
        ],
        dim="month",
    ).mean("month", skipna=True)

    jja_mean.attrs = monthly_maps["Jun_2026"].attrs
    jja_mean.attrs["units"] = "mm/day"
    monthly_maps["JJA_2026_mean"] = jja_mean

    # JJA total anomaly in mm/season
    jja_total = (
        monthly_maps["Jun_2026"] * 30
        + monthly_maps["Jul_2026"] * 31
        + monthly_maps["Aug_2026"] * 31
    )

    jja_total.attrs = monthly_maps["Jun_2026"].attrs
    jja_total.attrs["units"] = "mm/season"
    monthly_maps["JJA_2026_total"] = jja_total

    # Model name from file
    model_name = NC_FILE.name.split(".")[0]

    # Plot all regions and products
    for region_name, extent in REGIONS.items():
        for label, data in monthly_maps.items():
            clean_label = label.replace("_", " ")

            title = (
                f"{model_name} precipitation anomaly: {clean_label}\n"
                "Initialized May 2026"
            )

            out_file = (
                OUT_DIR
                / region_name
                / f"{model_name}_prate_{label}_{region_name}.png"
            )

            plot_map(
                da=data,
                title=title,
                out_file=out_file,
                extent=extent,
                lat_name=lat_name,
                lon_name=lon_name,
            )

    # Save JJA mean and total as NetCDF
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