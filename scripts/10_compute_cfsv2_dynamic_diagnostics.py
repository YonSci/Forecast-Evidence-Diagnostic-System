"""
10_compute_cfsv2_dynamic_diagnostics.py

Purpose
-------
Compute CFSv2 dynamic diagnostics from organized CFSv2 monthly and seasonal
forecast fields extracted from NOMADS GRIB2 files.

This corrected version fixes xarray merge errors caused by scalar pressure
coordinates such as isobaricInhPa=200, 850, 500, etc.

Inputs:
    data/cfsv2/organized_v4/

Required fields:
    u200, v200, u850, v850, q850, omega500, omega700,
    vp200, strf200, z200, z500, sst_proxy

Outputs:
    outputs/netcdf/cfsv2_dynamic_diagnostics/
    outputs/tables/cfsv2_dynamic_area_mean_diagnostics.csv
    outputs/tables/cfsv2_dynamic_diagnostic_field_status.csv

Run:
    python scripts\\10_compute_cfsv2_dynamic_diagnostics.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CFSV2_ORG_DIR = PROJECT_ROOT / "data" / "cfsv2" / "organized_v4"

OUT_NETCDF_DIR = PROJECT_ROOT / "outputs" / "netcdf" / "cfsv2_dynamic_diagnostics"
OUT_TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"

OUT_NETCDF_DIR.mkdir(parents=True, exist_ok=True)
OUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# SETTINGS
# ==========================================================

PERIODS = [
    "Jun_2026",
    "Jul_2026",
    "Aug_2026",
    "Sep_2026",
    "JJA_2026",
    "JJAS_2026",
]

REQUIRED_FIELDS = [
    "u200",
    "v200",
    "u850",
    "v850",
    "q850",
    "omega500",
    "omega700",
    "vp200",
    "strf200",
    "z200",
    "z500",
    "sst_proxy",
]

DOMAINS = {
    "ethiopia": [32, 48, 3, 15],
    "ethiopia_highlands_broad": [34, 42, 6, 14],
    "north_ethiopia": [35, 42, 10, 15],
    "central_ethiopia": [36, 41, 7, 11],
    "west_ethiopia": [33, 37.5, 6, 13],
    "east_ethiopia": [40, 48, 5, 12],
    "greater_horn": [20, 55, -15, 25],
    "east_africa": [20, 55, -15, 20],
    "atlantic_congo_ethiopia": [-20, 50, -20, 20],
    "congo_moisture_corridor": [15, 38, -5, 12],
    "western_moisture_entry": [25, 36, 2, 12],
    "western_indian_ocean": [40, 70, -15, 15],
    "arabia_red_sea": [35, 60, 10, 30],
    "north_africa_arabia": [10, 60, 10, 35],
    "tej_core": [20, 100, 5, 20],
    "somali_jet_box": [40, 55, -10, 15],
    "turkana_corridor": [35, 40, -5, 5],
}

SST_BOXES = {
    "nino34": [-170, -120, -5, 5],
    "iod_west": [50, 70, -10, 10],
    "iod_east": [90, 110, -10, 0],
}


# ==========================================================
# BASIC HELPERS
# ==========================================================

def field_path(field: str, period: str) -> Path:
    return CFSV2_ORG_DIR / f"CFSv2_{field}_{period}.nc"


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


def clean_for_merge(da: xr.DataArray) -> xr.DataArray:
    """
    Clean DataArray before merging variables into one xarray Dataset.

    CFSv2 fields extracted at different pressure levels can retain scalar coords:
        isobaricInhPa = 200
        isobaricInhPa = 850
        isobaricInhPa = 500

    These conflict when variables are combined into one Dataset. This function
    keeps only spatial coordinates and drops scalar GRIB/time/pressure metadata.
    """
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

    for dim in list(da.dims):
        if dim not in ["lat", "lon"] and da.sizes.get(dim, 0) == 1:
            da = da.isel({dim: 0}, drop=True)

    return da


def open_field(field: str, period: str) -> xr.DataArray:
    path = field_path(field, period)

    if not path.exists():
        raise FileNotFoundError(f"Missing field file: {path}")

    ds = xr.open_dataset(path)
    ds = standardize_coordinate_names(ds)
    ds = standardize_longitude(ds)

    if field in ds.data_vars:
        da = ds[field]
    else:
        var_name = list(ds.data_vars)[0]
        da = ds[var_name]

    da = da.load()
    ds.close()

    da.attrs["source_file"] = str(path)

    return clean_for_merge(da)


def ensure_lat_lon_last(da: xr.DataArray) -> xr.DataArray:
    if "lat" in da.dims and "lon" in da.dims:
        other_dims = [d for d in da.dims if d not in ["lat", "lon"]]
        return da.transpose(*other_dims, "lat", "lon")

    return da


def subset_box(da: xr.DataArray, box: list[float]) -> xr.DataArray:
    lon_min, lon_max, lat_min, lat_max = box

    da = standardize_longitude(da)

    if "lat" not in da.coords or "lon" not in da.coords:
        raise ValueError("DataArray must contain lat and lon coordinates.")

    lat_values = da["lat"].values

    if lat_values[0] < lat_values[-1]:
        lat_slice = slice(lat_min, lat_max)
    else:
        lat_slice = slice(lat_max, lat_min)

    return da.sel(
        lon=slice(lon_min, lon_max),
        lat=lat_slice,
    )


def area_weighted_mean(da: xr.DataArray, box: list[float]) -> float:
    sub = subset_box(da, box)

    if "lat" not in sub.coords or "lon" not in sub.coords:
        return float(sub.mean(skipna=True).values)

    weights = np.cos(np.deg2rad(sub["lat"]))
    weights = weights.where(np.isfinite(weights), 0)

    dims = [d for d in ["lat", "lon"] if d in sub.dims]
    val = sub.weighted(weights).mean(dims, skipna=True)

    # If extra dimensions remain, average them too.
    if hasattr(val, "dims") and len(val.dims) > 0:
        val = val.mean(list(val.dims), skipna=True)

    return float(np.asarray(val.values))


# ==========================================================
# DYNAMIC DIAGNOSTIC HELPERS
# ==========================================================

def compute_horizontal_divergence(
    fx: xr.DataArray,
    fy: xr.DataArray,
) -> xr.DataArray:
    """
    Compute horizontal divergence on a lat/lon grid.

    fx = zonal component
    fy = meridional component

    div = d(fx)/dx + d(fy)/dy
    """

    fx = clean_for_merge(fx)
    fy = clean_for_merge(fy)

    fx = ensure_lat_lon_last(fx)
    fy = ensure_lat_lon_last(fy)

    if fx.dims != fy.dims:
        fy = fy.transpose(*fx.dims)

    if "lat" not in fx.coords or "lon" not in fx.coords:
        raise ValueError("Both vector components must have lat and lon coordinates.")

    lat = fx["lat"].values.astype(float)
    lon = fx["lon"].values.astype(float)

    lat_rad = np.deg2rad(lat)
    lon_rad = np.deg2rad(lon)

    earth_radius = 6_371_000.0

    fx_values = fx.values.astype(float)
    fy_values = fy.values.astype(float)

    dfx_dlambda = np.gradient(fx_values, lon_rad, axis=-1)
    dfy_dphi = np.gradient(fy_values, lat_rad, axis=-2)

    coslat = np.cos(lat_rad)
    coslat = np.where(np.abs(coslat) < 1e-8, np.nan, coslat)

    cos_shape = (1,) * (fx_values.ndim - 2) + (len(lat), 1)
    coslat_broadcast = coslat.reshape(cos_shape)

    dfx_dx = dfx_dlambda / (earth_radius * coslat_broadcast)
    dfy_dy = dfy_dphi / earth_radius

    div_values = dfx_dx + dfy_dy

    div = xr.DataArray(
        div_values,
        coords=fx.coords,
        dims=fx.dims,
        attrs={
            "description": "Horizontal divergence computed on lat/lon grid.",
            "units": "s-1 or input_units_per_meter depending on vector units",
        },
    )

    return clean_for_merge(div)


def compute_wind_speed(u: xr.DataArray, v: xr.DataArray) -> xr.DataArray:
    out = np.sqrt(u ** 2 + v ** 2)
    out.attrs["description"] = "Wind speed computed as sqrt(u^2 + v^2)."
    out.attrs["units"] = u.attrs.get("units", "m s-1")
    return clean_for_merge(out)


def save_dataset(ds: xr.Dataset, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        out_path.unlink()

    ds.to_netcdf(out_path)
    print(f"Saved: {out_path}")


# ==========================================================
# CLASSIFICATION HELPERS
# ==========================================================

def classify_omega(value: float) -> str:
    if np.isnan(value):
        return "missing"
    if value > 0:
        return "subsidence_tendency"
    if value < 0:
        return "rising_motion_tendency"
    return "neutral"


def classify_divergence(value: float) -> str:
    if np.isnan(value):
        return "missing"
    if value > 0:
        return "divergence"
    if value < 0:
        return "convergence"
    return "neutral"


def classify_mfc(value: float) -> str:
    if np.isnan(value):
        return "missing"
    if value > 0:
        return "moisture_convergence"
    if value < 0:
        return "moisture_divergence"
    return "neutral"


def classify_u200(value: float) -> str:
    if np.isnan(value):
        return "missing"
    if value < 0:
        return "easterly_flow"
    if value > 0:
        return "westerly_flow"
    return "neutral"


def classify_tej_strength(value: float) -> str:
    if np.isnan(value):
        return "missing"
    if value >= 20:
        return "strong_tej"
    if value >= 10:
        return "moderate_tej"
    if value > 0:
        return "weak_tej"
    return "no_easterly_tej"


# ==========================================================
# CORE DIAGNOSTICS
# ==========================================================

def compute_period_diagnostics(period: str) -> tuple[xr.Dataset, list[dict]]:
    print("\n==================================================")
    print(f"Computing CFSv2 diagnostics for {period}")
    print("==================================================")

    # Load core fields. open_field() already cleans scalar coordinates.
    u200 = open_field("u200", period)
    v200 = open_field("v200", period)
    u850 = open_field("u850", period)
    v850 = open_field("v850", period)
    q850 = open_field("q850", period)
    omega500 = open_field("omega500", period)
    omega700 = open_field("omega700", period)
    vp200 = open_field("vp200", period)
    strf200 = open_field("strf200", period)
    z200 = open_field("z200", period)
    z500 = open_field("z500", period)
    sst_proxy = open_field("sst_proxy", period)

    # Align grids for vector calculations
    v200 = clean_for_merge(v200.interp_like(u200))
    u850 = clean_for_merge(u850.interp_like(q850))
    v850 = clean_for_merge(v850.interp_like(q850))

    # sst_proxy is natively on a finer 0.5deg grid (360x720) than every
    # other CFSv2 field here (1deg, 181x360) -- merging mismatched grids
    # with join="outer" below unions the coordinate axes instead of
    # aligning them, so every variable ends up NaN everywhere except its
    # own native grid points (~89% NaN in the merged output, confirmed).
    # area_weighted_mean() on the ORIGINAL fine-resolution sst_proxy
    # (used below for the SST-proxy/IOD/DMI scalar diagnostics) is
    # unaffected by this -- only the regridded copy that goes into the
    # merged Dataset needs aligning, same as v200/u850/v850 above.
    sst_proxy_on_grid = clean_for_merge(sst_proxy.interp_like(u200))

    # Derived fields
    tej_strength_map = clean_for_merge(-u200)
    tej_strength_map.attrs["description"] = (
        "TEJ strength proxy: -u200. Larger positive values indicate stronger easterly flow."
    )
    tej_strength_map.attrs["units"] = u200.attrs.get("units", "m s-1")

    div200 = compute_horizontal_divergence(u200, v200)
    div200.attrs["description"] = "200 hPa horizontal divergence computed from CFSv2 u200 and v200."
    div200.attrs["units"] = "s-1"

    wind_speed850 = compute_wind_speed(u850, v850)
    wind_speed850.attrs["description"] = "850 hPa wind speed."

    qu850 = clean_for_merge(q850 * u850)
    qv850 = clean_for_merge(q850 * v850)

    qu850.attrs["description"] = "850 hPa zonal moisture flux proxy: q850 * u850."
    qv850.attrs["description"] = "850 hPa meridional moisture flux proxy: q850 * v850."
    qu850.attrs["units"] = "kg kg-1 m s-1"
    qv850.attrs["units"] = "kg kg-1 m s-1"

    mfc850 = clean_for_merge(-compute_horizontal_divergence(qu850, qv850))
    mfc850.attrs["description"] = "850 hPa moisture-flux convergence proxy: -div(q850*u850, q850*v850)."
    mfc850.attrs["units"] = "kg kg-1 s-1 approximately"

    # Clean again before merging into one Dataset
    data_vars = {
        "u200": clean_for_merge(u200),
        "v200": clean_for_merge(v200),
        "tej_strength": clean_for_merge(tej_strength_map),
        "div200": clean_for_merge(div200),
        "u850": clean_for_merge(u850),
        "v850": clean_for_merge(v850),
        "q850": clean_for_merge(q850),
        "wind_speed850": clean_for_merge(wind_speed850),
        "qu850": clean_for_merge(qu850),
        "qv850": clean_for_merge(qv850),
        "mfc850": clean_for_merge(mfc850),
        "omega500": clean_for_merge(omega500),
        "omega700": clean_for_merge(omega700),
        "vp200": clean_for_merge(vp200),
        "strf200": clean_for_merge(strf200),
        "z200": clean_for_merge(z200),
        "z500": clean_for_merge(z500),
        "sst_proxy": sst_proxy_on_grid,
    }

    ds_list = []

    for var_name, da in data_vars.items():
        da = clean_for_merge(da)
        ds_list.append(da.to_dataset(name=var_name))

    ds_out = xr.merge(
        ds_list,
        compat="override",
        join="outer",
        combine_attrs="override",
    )

    ds_out.attrs["period"] = period
    ds_out.attrs["source"] = "NOMADS CFSv2 monthly forecast fields"
    ds_out.attrs["note"] = (
        "These are CFSv2 forecast fields initialized from 2026061000 files, "
        "not the exact May 2026 NMME ENSMEAN anomaly fields."
    )

    rows = []

    diagnostic_vars = [
        "u200",
        "v200",
        "tej_strength",
        "div200",
        "u850",
        "v850",
        "q850",
        "wind_speed850",
        "qu850",
        "qv850",
        "mfc850",
        "omega500",
        "omega700",
        "vp200",
        "strf200",
        "z200",
        "z500",
        "sst_proxy",
    ]

    for domain_name, box in DOMAINS.items():
        for var_name in diagnostic_vars:
            try:
                value = area_weighted_mean(ds_out[var_name], box)
            except Exception:
                value = np.nan

            classification = "not_classified"

            if var_name == "u200":
                classification = classify_u200(value)
            elif var_name == "tej_strength":
                classification = classify_tej_strength(value)
            elif var_name == "div200":
                classification = classify_divergence(value)
            elif var_name == "mfc850":
                classification = classify_mfc(value)
            elif var_name in ["omega500", "omega700"]:
                classification = classify_omega(value)

            rows.append(
                {
                    "period": period,
                    "domain": domain_name,
                    "diagnostic": var_name,
                    "value": value,
                    "units": ds_out[var_name].attrs.get("units", ""),
                    "classification": classification,
                    "description": ds_out[var_name].attrs.get("description", ""),
                }
            )

    # SST driver boxes
    for box_name, box in SST_BOXES.items():
        try:
            value = area_weighted_mean(sst_proxy, box)
        except Exception:
            value = np.nan

        rows.append(
            {
                "period": period,
                "domain": box_name,
                "diagnostic": "sst_proxy",
                "value": value,
                "units": sst_proxy.attrs.get("units", ""),
                "classification": "raw_sst_proxy_mean",
                "description": "CFSv2 raw SST proxy area mean; not an anomaly unless climatology is subtracted.",
            }
        )

    # DMI proxy from raw SST values
    try:
        iod_west = area_weighted_mean(sst_proxy, SST_BOXES["iod_west"])
        iod_east = area_weighted_mean(sst_proxy, SST_BOXES["iod_east"])
        dmi_proxy = iod_west - iod_east
    except Exception:
        dmi_proxy = np.nan

    rows.append(
        {
            "period": period,
            "domain": "iod_west_minus_iod_east",
            "diagnostic": "dmi_raw_sst_proxy",
            "value": dmi_proxy,
            "units": sst_proxy.attrs.get("units", ""),
            "classification": "raw_gradient_not_anomaly",
            "description": "Raw west-minus-east Indian Ocean SST proxy. This is not an official DMI anomaly.",
        }
    )

    return ds_out, rows


def check_field_status() -> pd.DataFrame:
    rows = []

    for period in PERIODS:
        for field in REQUIRED_FIELDS:
            p = field_path(field, period)

            rows.append(
                {
                    "period": period,
                    "field": field,
                    "path": str(p),
                    "available": p.exists(),
                }
            )

    return pd.DataFrame(rows)


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("Compute CFSv2 dynamic diagnostics")
    print("==================================================")
    print(f"CFSv2 organized input: {CFSV2_ORG_DIR}")
    print(f"Output NetCDF folder:  {OUT_NETCDF_DIR}")
    print(f"Output table folder:   {OUT_TABLE_DIR}")

    status_df = check_field_status()
    status_csv = OUT_TABLE_DIR / "cfsv2_dynamic_diagnostic_field_status.csv"
    status_df.to_csv(status_csv, index=False)

    print(f"\nSaved field status table: {status_csv}")

    missing_required = status_df[~status_df["available"]]

    if not missing_required.empty:
        print("\nSome required files are missing:")
        print(missing_required.to_string(index=False))
        raise FileNotFoundError("Required CFSv2 organized files are missing.")

    all_rows = []

    for period in PERIODS:
        ds_out, rows = compute_period_diagnostics(period)

        out_nc = OUT_NETCDF_DIR / f"CFSv2_dynamic_diagnostics_{period}.nc"
        save_dataset(ds_out, out_nc)

        all_rows.extend(rows)

    area_df = pd.DataFrame(all_rows)

    area_csv = OUT_TABLE_DIR / "cfsv2_dynamic_area_mean_diagnostics.csv"
    area_df.to_csv(area_csv, index=False)

    print("\n==================================================")
    print("CFSv2 DYNAMIC DIAGNOSTICS FINISHED")
    print("==================================================")
    print(f"Area-mean diagnostics: {area_csv}")
    print(f"NetCDF diagnostics:    {OUT_NETCDF_DIR}")

    print("\nQuick Ethiopia/JJAS summary:")

    summary = area_df[
        (area_df["period"] == "JJAS_2026")
        & (area_df["domain"] == "ethiopia")
        & (
            area_df["diagnostic"].isin(
                [
                    "tej_strength",
                    "div200",
                    "mfc850",
                    "omega500",
                    "omega700",
                    "vp200",
                    "z200",
                    "z500",
                ]
            )
        )
    ]

    if not summary.empty:
        print(
            summary[
                ["diagnostic", "value", "units", "classification"]
            ].to_string(index=False)
        )

    print("\nNext step:")
    print("Create plotting script for CFSv2 dynamic diagnostics:")
    print("    scripts\\11_plot_cfsv2_dynamic_diagnostics.py")


if __name__ == "__main__":
    main()