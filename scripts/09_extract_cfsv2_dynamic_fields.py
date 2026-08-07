"""
09_extract_cfsv2_dynamic_fields.py

Purpose
-------
Extract dynamic forecast fields from downloaded NOMADS CFSv2 monthly GRIB2 files.

Inputs:
    data/cfsv2/monthly_grib/pgbf.*.grib.grb2
    data/cfsv2/monthly_grib/flxf.*.grib.grb2
    data/cfsv2/monthly_grib/ocnh.*.grib.grb2

Outputs:
    data/cfsv2/organized/
    outputs/tables/cfsv2_extraction_status.csv

Extracted fields:
    u200, v200, u850, v850, q850, z500, omega500, omega700
    olr_proxy if found
    sst_proxy if found

Run:
    python scripts\\09_extract_cfsv2_dynamic_fields.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import cfgrib


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GRIB_DIR = PROJECT_ROOT / "data" / "cfsv2" / "monthly_grib"
OUT_DIR = PROJECT_ROOT / "data" / "cfsv2" / "organized"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"

OUT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

STATUS_CSV = TABLE_DIR / "cfsv2_extraction_status.csv"


TARGET_MONTHS = {
    "202606": "Jun_2026",
    "202607": "Jul_2026",
    "202608": "Aug_2026",
    "202609": "Sep_2026",
}


FIELD_SPECS = {
    "u200": {
        "family": "pgbf",
        "var_candidates": ["u"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 200,
        "description": "200 hPa zonal wind",
    },
    "v200": {
        "family": "pgbf",
        "var_candidates": ["v"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 200,
        "description": "200 hPa meridional wind",
    },
    "u850": {
        "family": "pgbf",
        "var_candidates": ["u"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 850,
        "description": "850 hPa zonal wind",
    },
    "v850": {
        "family": "pgbf",
        "var_candidates": ["v"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 850,
        "description": "850 hPa meridional wind",
    },
    "q850": {
        "family": "pgbf",
        "var_candidates": ["q", "spfh"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 850,
        "description": "850 hPa specific humidity",
    },
    "z500": {
        "family": "pgbf",
        "var_candidates": ["gh", "hgt", "z"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 500,
        "description": "500 hPa geopotential height",
    },
    "omega500": {
        "family": "pgbf",
        "var_candidates": ["w", "vvel"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 500,
        "description": "500 hPa vertical velocity / omega",
    },
    "omega700": {
        "family": "pgbf",
        "var_candidates": ["w", "vvel"],
        "level_candidates": ["isobaricInhPa"],
        "level_value": 700,
        "description": "700 hPa vertical velocity / omega",
    },
    "olr_proxy": {
        "family": "flxf",
        "var_candidates": ["ulwrf", "ttr", "lwrad"],
        "level_candidates": ["nominalTop", "surface"],
        "level_value": None,
        "description": "Outgoing longwave radiation proxy, preferably upward longwave radiation at top of atmosphere",
    },
    "sst_proxy": {
        "family": "ocnh",
        "var_candidates": ["sst", "t", "wtmp", "water_temp"],
        "level_candidates": ["depthBelowSea", "surface"],
        "level_value": None,
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
    name = path.name.lower()
    return name.startswith(family.lower())


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


def open_grib_datasets(path: Path) -> list[xr.Dataset]:
    try:
        return cfgrib.open_datasets(str(path))
    except Exception as exc:
        print(f"Failed to open with cfgrib.open_datasets: {path.name}")
        print(exc)
        return []


def find_field_in_datasets(
    datasets: list[xr.Dataset],
    spec: dict,
) -> xr.DataArray | None:
    var_candidates = [v.lower() for v in spec["var_candidates"]]
    level_candidates = spec["level_candidates"]
    level_value = spec["level_value"]

    for ds in datasets:
        ds = standardize_coordinate_names(ds)
        ds = standardize_longitude(ds)

        for var in ds.data_vars:
            if var.lower() not in var_candidates:
                continue

            da = ds[var]

            # If no level is requested, return first matching variable
            if level_value is None:
                return da.squeeze(drop=True)

            # Otherwise select pressure level
            for level_coord in level_candidates:
                if level_coord in da.coords:
                    levels = np.asarray(da[level_coord].values)

                    try:
                        selected = da.sel({level_coord: level_value}, method="nearest").squeeze(drop=True)
                        return selected
                    except Exception:
                        continue

    return None


def save_field(da: xr.DataArray, out_path: Path, var_name: str, attrs: dict) -> None:
    da = standardize_coordinate_names(da)
    da = standardize_longitude(da)

    da.attrs.update(attrs)

    ds_out = da.to_dataset(name=var_name)

    if out_path.exists():
        out_path.unlink()

    ds_out.to_netcdf(out_path)

    print(f"Saved: {out_path}")


def extract_monthly_fields() -> pd.DataFrame:
    rows = []

    grib_files = sorted(GRIB_DIR.glob("*.grib.grb2"))

    if not grib_files:
        raise FileNotFoundError(f"No GRIB files found in {GRIB_DIR}")

    for month_code, month_label in TARGET_MONTHS.items():
        print("\n==================================================")
        print(f"Extracting fields for {month_label} ({month_code})")
        print("==================================================")

        for field_name, spec in FIELD_SPECS.items():
            family = spec["family"]

            candidate_files = [
                p for p in grib_files
                if family_matches(p, family) and infer_valid_month(p) == month_code
            ]

            if not candidate_files:
                print(f"No {family} file found for {month_code} and field {field_name}")

                rows.append(
                    {
                        "field": field_name,
                        "period": month_label,
                        "status": "missing_grib_file",
                        "source_file": "",
                        "output_file": "",
                        "message": f"No {family} GRIB file found for {month_code}",
                    }
                )
                continue

            source_file = candidate_files[0]
            datasets = open_grib_datasets(source_file)

            da = find_field_in_datasets(datasets, spec)

            for ds in datasets:
                try:
                    ds.close()
                except Exception:
                    pass

            if da is None:
                print(f"Field not found: {field_name} in {source_file.name}")

                rows.append(
                    {
                        "field": field_name,
                        "period": month_label,
                        "status": "field_not_found",
                        "source_file": str(source_file),
                        "output_file": "",
                        "message": f"Variable candidates not found: {spec['var_candidates']}",
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
            }

            save_field(da, out_path, field_name, attrs)

            rows.append(
                {
                    "field": field_name,
                    "period": month_label,
                    "status": "available",
                    "source_file": str(source_file),
                    "output_file": str(out_path),
                    "message": "Extracted successfully",
                }
            )

    return pd.DataFrame(rows)


def create_seasonal_means(status_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    available = status_df[status_df["status"] == "available"].copy()

    for field_name in FIELD_SPECS:
        for season_name, months in {
            "JJA_2026": ["Jun_2026", "Jul_2026", "Aug_2026"],
            "JJAS_2026": ["Jun_2026", "Jul_2026", "Aug_2026", "Sep_2026"],
        }.items():
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
                var = list(ds.data_vars)[0]
                das.append(ds[var])
                ds.close()

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
    print("Extract CFSv2 dynamic fields from GRIB")
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
    print("CFSv2 EXTRACTION FINISHED")
    print("==================================================")
    print(f"Status table: {STATUS_CSV}")
    print(f"Organized NetCDFs: {OUT_DIR}")

    print("\nAvailability summary:")
    print(
        status_df.groupby(["stage", "field", "status"])
        .size()
        .reset_index(name="count")
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()