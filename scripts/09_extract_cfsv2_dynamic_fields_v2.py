"""
09_extract_cfsv2_dynamic_fields_v2.py

Purpose
-------
Robustly extract dynamic forecast fields from NOMADS CFSv2 monthly GRIB2 files.

This version uses cfgrib filter_by_keys with GRIB shortName and typeOfLevel.
It is more reliable than searching only xarray variable names.

Inputs:
    data/cfsv2/monthly_grib/

Outputs:
    data/cfsv2/organized_v2/
    outputs/tables/cfsv2_extraction_status_v2.csv

Run:
    python scripts\\09_extract_cfsv2_dynamic_fields_v2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GRIB_DIR = PROJECT_ROOT / "data" / "cfsv2" / "monthly_grib"
OUT_DIR = PROJECT_ROOT / "data" / "cfsv2" / "organized_v2"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"

OUT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

STATUS_CSV = TABLE_DIR / "cfsv2_extraction_status_v2.csv"


TARGET_MONTHS = {
    "202606": "Jun_2026",
    "202607": "Jul_2026",
    "202608": "Aug_2026",
    "202609": "Sep_2026",
}


FIELD_SPECS = {
    "u200": {
        "family": "pgbf",
        "short_names": ["u", "UGRD", "ugrd"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 200,
        "description": "200 hPa zonal wind",
    },
    "v200": {
        "family": "pgbf",
        "short_names": ["v", "VGRD", "vgrd"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 200,
        "description": "200 hPa meridional wind",
    },
    "u850": {
        "family": "pgbf",
        "short_names": ["u", "UGRD", "ugrd"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 850,
        "description": "850 hPa zonal wind",
    },
    "v850": {
        "family": "pgbf",
        "short_names": ["v", "VGRD", "vgrd"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 850,
        "description": "850 hPa meridional wind",
    },
    "q850": {
        "family": "pgbf",
        "short_names": ["q", "spfh", "SPFH"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 850,
        "description": "850 hPa specific humidity",
    },
    "z500": {
        "family": "pgbf",
        "short_names": ["gh", "hgt", "HGT", "z"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 500,
        "description": "500 hPa geopotential height",
    },
    "omega500": {
        "family": "pgbf",
        "short_names": ["w", "vvel", "VVEL"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 500,
        "description": "500 hPa vertical velocity / omega",
    },
    "omega700": {
        "family": "pgbf",
        "short_names": ["w", "vvel", "VVEL"],
        "type_of_levels": ["isobaricInhPa", "isobaricInPa"],
        "level_hpa": 700,
        "description": "700 hPa vertical velocity / omega",
    },
    "olr_proxy": {
        "family": "flxf",
        "short_names": ["ulwrf", "ULWRF", "ttr", "olr"],
        "type_of_levels": ["nominalTop", "topOfAtmosphere", "atmosphere", "surface"],
        "level_hpa": None,
        "description": "Outgoing longwave radiation proxy",
    },
    "sst_proxy": {
        "family": "ocnh",
        "short_names": ["sst", "SST", "wtmp", "WTMP", "t"],
        "type_of_levels": ["surface", "depthBelowSea", "depthBelowSeaLayer"],
        "level_hpa": None,
        "description": "Sea surface temperature or near-surface ocean temperature proxy",
    },
}


def infer_valid_month(path: Path) -> str:
    parts = path.name.split(".")
    for part in parts:
        if part.isdigit() and len(part) == 6 and part.startswith("2026"):
            return part
    return "unknown"


def family_matches(path: Path, family: str) -> bool:
    return path.name.lower().startswith(family.lower())


def standardize_coordinate_names(ds: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
    rename = {}

    names = list(ds.coords) + list(ds.dims)

    for name in names:
        lower = name.lower()

        if lower in ["latitude", "lat"] and name != "lat":
            if "lat" not in ds.coords and "lat" not in ds.dims:
                rename[name] = "lat"

        if lower in ["longitude", "lon"] and name != "lon":
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


def get_first_dataarray(ds: xr.Dataset) -> xr.DataArray | None:
    if len(ds.data_vars) == 0:
        return None

    var_name = list(ds.data_vars)[0]
    return ds[var_name]


def select_pressure_level(da: xr.DataArray, level_hpa: int | None) -> xr.DataArray:
    if level_hpa is None:
        return da.squeeze(drop=True)

    # Common cfgrib pressure coordinates
    if "isobaricInhPa" in da.coords:
        return da.sel(isobaricInhPa=level_hpa, method="nearest").squeeze(drop=True)

    if "isobaricInPa" in da.coords:
        level_pa = level_hpa * 100
        return da.sel(isobaricInPa=level_pa, method="nearest").squeeze(drop=True)

    if "level" in da.coords:
        vals = np.asarray(da["level"].values)

        # If values look like Pa, convert hPa to Pa
        if np.nanmax(vals) > 2000:
            return da.sel(level=level_hpa * 100, method="nearest").squeeze(drop=True)

        return da.sel(level=level_hpa, method="nearest").squeeze(drop=True)

    raise ValueError(f"No pressure coordinate found for level {level_hpa} hPa. Coordinates: {list(da.coords)}")


def select_surface_or_first_level(da: xr.DataArray) -> xr.DataArray:
    """
    For SST/OLR proxies, select the first vertical-like level if one exists.
    """
    vertical_candidates = [
        "depthBelowSea",
        "depthBelowSeaLayer",
        "nominalTop",
        "heightAboveGround",
    ]

    for coord in vertical_candidates:
        if coord in da.coords and coord in da.dims:
            return da.isel({coord: 0}).squeeze(drop=True)

        if coord in da.coords and coord not in da.dims:
            return da.squeeze(drop=True)

    return da.squeeze(drop=True)


def try_open_with_filter(path: Path, short_name: str, type_of_level: str) -> xr.Dataset | None:
    backend_kwargs = {
        "filter_by_keys": {
            "shortName": short_name,
            "typeOfLevel": type_of_level,
        },
        "indexpath": "",
    }

    try:
        ds = xr.open_dataset(
            path,
            engine="cfgrib",
            backend_kwargs=backend_kwargs,
        )
        return ds
    except Exception:
        return None


def try_open_shortname_only(path: Path, short_name: str) -> xr.Dataset | None:
    backend_kwargs = {
        "filter_by_keys": {
            "shortName": short_name,
        },
        "indexpath": "",
    }

    try:
        ds = xr.open_dataset(
            path,
            engine="cfgrib",
            backend_kwargs=backend_kwargs,
        )
        return ds
    except Exception:
        return None


def extract_field_from_file(path: Path, spec: dict) -> tuple[xr.DataArray | None, str]:
    short_names = spec["short_names"]
    type_of_levels = spec["type_of_levels"]
    level_hpa = spec["level_hpa"]

    attempted = []

    # First try shortName + typeOfLevel
    for short_name in short_names:
        for type_of_level in type_of_levels:
            attempted.append(f"shortName={short_name}, typeOfLevel={type_of_level}")

            ds = try_open_with_filter(path, short_name, type_of_level)

            if ds is None:
                continue

            try:
                da = get_first_dataarray(ds)

                if da is None:
                    ds.close()
                    continue

                if level_hpa is not None:
                    da = select_pressure_level(da, level_hpa)
                else:
                    da = select_surface_or_first_level(da)

                da = standardize_coordinate_names(da)
                da = standardize_longitude(da)

                message = f"Matched {path.name} using shortName={short_name}, typeOfLevel={type_of_level}"
                ds.close()
                return da, message

            except Exception as exc:
                try:
                    ds.close()
                except Exception:
                    pass
                attempted.append(f"failed selection: {exc}")
                continue

    # Then try shortName only
    for short_name in short_names:
        attempted.append(f"shortName={short_name}")

        ds = try_open_shortname_only(path, short_name)

        if ds is None:
            continue

        try:
            da = get_first_dataarray(ds)

            if da is None:
                ds.close()
                continue

            if level_hpa is not None:
                da = select_pressure_level(da, level_hpa)
            else:
                da = select_surface_or_first_level(da)

            da = standardize_coordinate_names(da)
            da = standardize_longitude(da)

            message = f"Matched {path.name} using shortName={short_name}"
            ds.close()
            return da, message

        except Exception as exc:
            try:
                ds.close()
            except Exception:
                pass
            attempted.append(f"failed selection: {exc}")
            continue

    return None, "No match. Attempts: " + " | ".join(attempted[:20])


def save_field(da: xr.DataArray, out_path: Path, var_name: str, attrs: dict) -> None:
    da.attrs.update(attrs)

    ds_out = da.to_dataset(name=var_name)

    if out_path.exists():
        out_path.unlink()

    ds_out.to_netcdf(out_path)

    print(f"Saved: {out_path}")


def extract_monthly_fields() -> pd.DataFrame:
    grib_files = sorted(GRIB_DIR.glob("*.grib.grb2"))

    if not grib_files:
        raise FileNotFoundError(f"No GRIB files found in {GRIB_DIR}")

    rows = []

    for month_code, month_label in TARGET_MONTHS.items():
        print("\n==================================================")
        print(f"Extracting {month_label} ({month_code})")
        print("==================================================")

        for field_name, spec in FIELD_SPECS.items():
            family = spec["family"]

            candidate_files = [
                p for p in grib_files
                if family_matches(p, family) and infer_valid_month(p) == month_code
            ]

            if not candidate_files:
                msg = f"No {family} GRIB file found for {month_code}"
                print(f"{field_name}: {msg}")

                rows.append(
                    {
                        "field": field_name,
                        "period": month_label,
                        "valid_month": month_code,
                        "status": "missing_grib_file",
                        "source_file": "",
                        "output_file": "",
                        "message": msg,
                    }
                )
                continue

            source_file = candidate_files[0]

            da, message = extract_field_from_file(source_file, spec)

            if da is None:
                print(f"{field_name}: field not found")

                rows.append(
                    {
                        "field": field_name,
                        "period": month_label,
                        "valid_month": month_code,
                        "status": "field_not_found",
                        "source_file": str(source_file),
                        "output_file": "",
                        "message": message,
                    }
                )
                continue

            out_path = OUT_DIR / f"CFSv2_{field_name}_{month_label}.nc"

            attrs = {
                "diagnostic_name": field_name,
                "period": month_label,
                "valid_month": month_code,
                "source_file": str(source_file),
                "description": spec["description"],
                "source_note": "NOMADS CFSv2 monthly GRIB forecast. Initialization date inferred from filename.",
                "match_message": message,
            }

            save_field(da, out_path, field_name, attrs)

            rows.append(
                {
                    "field": field_name,
                    "period": month_label,
                    "valid_month": month_code,
                    "status": "available",
                    "source_file": str(source_file),
                    "output_file": str(out_path),
                    "message": message,
                }
            )

    return pd.DataFrame(rows)


def create_seasonal_means(monthly_status: pd.DataFrame) -> pd.DataFrame:
    rows = []

    seasons = {
        "JJA_2026": ["Jun_2026", "Jul_2026", "Aug_2026"],
        "JJAS_2026": ["Jun_2026", "Jul_2026", "Aug_2026", "Sep_2026"],
    }

    for field_name in FIELD_SPECS:
        for season_name, months in seasons.items():
            paths = []

            for month in months:
                p = OUT_DIR / f"CFSv2_{field_name}_{month}.nc"
                if p.exists():
                    paths.append(p)

            if len(paths) == 0:
                rows.append(
                    {
                        "field": field_name,
                        "period": season_name,
                        "status": "no_monthly_files",
                        "output_file": "",
                        "message": "No monthly files available for seasonal mean.",
                    }
                )
                continue

            das = []

            for p in paths:
                ds = xr.open_dataset(p)
                var_name = list(ds.data_vars)[0]
                da = ds[var_name].load()
                ds.close()
                das.append(da)

            season_da = xr.concat(das, dim="season_month").mean("season_month", skipna=True)

            season_da.attrs.update(
                {
                    "diagnostic_name": field_name,
                    "period": season_name,
                    "aggregation": f"Mean over {', '.join(months)}",
                }
            )

            out_path = OUT_DIR / f"CFSv2_{field_name}_{season_name}.nc"

            if out_path.exists():
                out_path.unlink()

            season_da.to_dataset(name=field_name).to_netcdf(out_path)

            print(f"Saved seasonal mean: {out_path}")

            rows.append(
                {
                    "field": field_name,
                    "period": season_name,
                    "status": "available",
                    "output_file": str(out_path),
                    "message": "Seasonal mean created successfully.",
                }
            )

    return pd.DataFrame(rows)


def main():
    print("\n==================================================")
    print("CFSv2 dynamic field extractor v2")
    print("==================================================")
    print(f"GRIB directory: {GRIB_DIR}")
    print(f"Output directory: {OUT_DIR}")

    monthly_status = extract_monthly_fields()
    seasonal_status = create_seasonal_means(monthly_status)

    monthly_status["stage"] = "monthly_extraction"
    seasonal_status["stage"] = "seasonal_mean"

    status_df = pd.concat([monthly_status, seasonal_status], ignore_index=True, sort=False)
    status_df.to_csv(STATUS_CSV, index=False)

    print("\n==================================================")
    print("CFSv2 EXTRACTION V2 FINISHED")
    print("==================================================")
    print(f"Status table: {STATUS_CSV}")
    print(f"Organized NetCDFs: {OUT_DIR}")

    print("\nAvailability summary:")
    summary = (
        status_df.groupby(["stage", "field", "status"])
        .size()
        .reset_index(name="count")
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()