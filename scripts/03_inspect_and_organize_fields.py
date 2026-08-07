"""
03_inspect_and_organize_fields.py

Purpose
-------
Inspect and organize downloaded NMME and ERA5 fields for dynamic diagnosis
of Ethiopia Kiremt/JJAS rainfall mechanisms.

This script will:

1. Inspect downloaded NMME realtime anomaly files.
2. Inspect downloaded ERA5 pressure-level and SST files.
3. Extract key ERA5 diagnostic fields:
   - u200, v200
   - u850, v850
   - q850
   - omega500, omega700
   - z200, z500 converted to geopotential height in meters
   - divergence200
   - velocity_potential200
   - sst
4. Save organized NetCDF files into:
   data/era5/organized/
   data/nmme/organized/
5. Save field inventories and status tables into:
   outputs/tables/

Run from project root:
    python scripts\\03_inspect_and_organize_fields.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import (
        NMME_DIR,
        ERA5_DIR,
        TABLE_DIR,
    )
except Exception:
    NMME_DIR = PROJECT_ROOT / "data" / "nmme"
    ERA5_DIR = PROJECT_ROOT / "data" / "era5"
    TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"


# ==========================================================
# INPUT FILE LOCATIONS
# ==========================================================

NMME_REALTIME_DIR = NMME_DIR / "realtime_anom" / "ENSMEAN" / "2026050800"

ERA5_PRESSURE_DIR = ERA5_DIR / "monthly" / "pressure_levels"
ERA5_SINGLE_DIR = ERA5_DIR / "monthly" / "single_levels"

# Prefer full climatology files, but fall back to TEST files if needed
ERA5_PRESSURE_FULL = ERA5_PRESSURE_DIR / "era5_pressure_levels_africa_indian_1991_2020_JJAS.nc"
ERA5_PRESSURE_TEST = ERA5_PRESSURE_DIR / "era5_pressure_levels_africa_indian_TEST.nc"

ERA5_SST_FULL = ERA5_SINGLE_DIR / "era5_sst_tropical_global_1991_2020_JJAS.nc"
ERA5_SST_TEST = ERA5_SINGLE_DIR / "era5_sst_tropical_global_TEST.nc"


# ==========================================================
# OUTPUT LOCATIONS
# ==========================================================

ERA5_ORG_DIR = ERA5_DIR / "organized"
NMME_ORG_DIR = NMME_DIR / "organized"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
ERA5_ORG_DIR.mkdir(parents=True, exist_ok=True)
NMME_ORG_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# FIELD DEFINITIONS
# ==========================================================

ERA5_PRESSURE_TARGETS = {
    "u200": {
        "var_candidates": ["u", "u_component_of_wind"],
        "level": 200,
        "description": "200 hPa zonal wind for TEJ diagnosis",
        "expected_units": "m s**-1",
    },
    "v200": {
        "var_candidates": ["v", "v_component_of_wind"],
        "level": 200,
        "description": "200 hPa meridional wind",
        "expected_units": "m s**-1",
    },
    "u850": {
        "var_candidates": ["u", "u_component_of_wind"],
        "level": 850,
        "description": "850 hPa zonal wind for low-level moisture transport",
        "expected_units": "m s**-1",
    },
    "v850": {
        "var_candidates": ["v", "v_component_of_wind"],
        "level": 850,
        "description": "850 hPa meridional wind for low-level moisture transport",
        "expected_units": "m s**-1",
    },
    "q850": {
        "var_candidates": ["q", "specific_humidity"],
        "level": 850,
        "description": "850 hPa specific humidity",
        "expected_units": "kg kg**-1",
    },
    "omega500": {
        "var_candidates": ["w", "vertical_velocity"],
        "level": 500,
        "description": "500 hPa vertical velocity / omega",
        "expected_units": "Pa s**-1",
    },
    "omega700": {
        "var_candidates": ["w", "vertical_velocity"],
        "level": 700,
        "description": "700 hPa vertical velocity / omega",
        "expected_units": "Pa s**-1",
    },
    "z200": {
        "var_candidates": ["z", "geopotential"],
        "level": 200,
        "description": "200 hPa geopotential height",
        "expected_units": "m",
        "convert_geopotential_to_height": True,
    },
    "z500": {
        "var_candidates": ["z", "geopotential"],
        "level": 500,
        "description": "500 hPa geopotential height",
        "expected_units": "m",
        "convert_geopotential_to_height": True,
    },
    "divergence200": {
        "var_candidates": ["d", "divergence"],
        "level": 200,
        "description": "200 hPa divergence",
        "expected_units": "s**-1",
    },
    "velocity_potential200": {
        "var_candidates": ["vp", "velocity_potential"],
        "level": 200,
        "description": "200 hPa velocity potential",
        "expected_units": "m**2 s**-1",
    },
}

ERA5_SINGLE_TARGETS = {
    "sst": {
        "var_candidates": ["sst", "sea_surface_temperature"],
        "description": "Sea surface temperature",
        "expected_units": "K",
    },
}

NMME_KEYWORDS_TO_ORGANIZE = [
    "prate",
    "tmpsfc",
    "tmp2m",
    "z200",
]


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def pick_existing_file(primary: Path, fallback: Path | None = None) -> Path | None:
    if primary.exists() and primary.stat().st_size > 0:
        return primary

    if fallback is not None and fallback.exists() and fallback.stat().st_size > 0:
        return fallback

    return None


def open_dataset_safely(path: Path, decode_times: bool = True) -> xr.Dataset:
    try:
        return xr.open_dataset(path, decode_times=decode_times)
    except Exception:
        return xr.open_dataset(path, decode_times=False)


def standardize_coordinate_names(ds: xr.Dataset) -> xr.Dataset:
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

        if lower in ["valid_time", "time"] and name != "time":
            if "time" not in ds.coords and "time" not in ds.dims:
                rename[name] = "time"

        if lower in ["pressure_level", "level", "isobaricinhpa", "plev"] and name != "level":
            if "level" not in ds.coords and "level" not in ds.dims:
                rename[name] = "level"

    if rename:
        ds = ds.rename(rename)

    return ds


def standardize_longitude(ds: xr.Dataset) -> xr.Dataset:
    if "lon" not in ds.coords:
        return ds

    lon = ds["lon"]

    if float(lon.max()) > 180:
        new_lon = ((lon + 180) % 360) - 180
        ds = ds.assign_coords(lon=new_lon)
        ds = ds.sortby("lon")

    return ds


def find_variable(ds: xr.Dataset, candidates: list[str]) -> str | None:
    lower_map = {name.lower(): name for name in ds.data_vars}

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    return None


def find_level_coord(ds: xr.Dataset) -> str | None:
    for candidate in ["level", "pressure_level", "isobaricInhPa", "plev"]:
        if candidate in ds.coords or candidate in ds.dims:
            return candidate

    return None


def inspect_dataset(ds: xr.Dataset, source: str, path: Path) -> list[dict]:
    rows = []

    for var_name, da in ds.data_vars.items():
        units = da.attrs.get("units", "")
        long_name = da.attrs.get("long_name", da.attrs.get("standard_name", ""))

        rows.append(
            {
                "source": source,
                "file": str(path),
                "variable": var_name,
                "dims": ", ".join(da.dims),
                "shape": str(tuple(da.shape)),
                "units": units,
                "long_name": long_name,
            }
        )

    return rows


def choose_main_nmme_variable(ds: xr.Dataset) -> str | None:
    priority = [
        "prate",
        "tmpsfc",
        "tmp2m",
        "z200",
        "tmax",
        "tmin",
        "precip",
        "sst",
    ]

    lower_map = {name.lower(): name for name in ds.data_vars}

    for p in priority:
        for lower_name, original_name in lower_map.items():
            if p in lower_name:
                return original_name

    if not ds.data_vars:
        return None

    # Choose the variable with the most dimensions
    return max(ds.data_vars, key=lambda x: ds[x].ndim)


def sanitize_name(text: str) -> str:
    clean = (
        text.replace(".", "_")
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )
    return clean


def save_dataarray_as_netcdf(da: xr.DataArray, out_path: Path, var_name: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ds_out = da.to_dataset(name=var_name)

    if out_path.exists():
        out_path.unlink()

    ds_out.to_netcdf(out_path)


# ==========================================================
# ERA5 ORGANIZATION
# ==========================================================

def organize_era5_pressure_fields(path: Path) -> tuple[list[dict], dict]:
    print("\n==================================================")
    print("Inspecting and organizing ERA5 pressure-level file")
    print("==================================================")
    print(path)

    ds = open_dataset_safely(path, decode_times=True)
    ds = standardize_coordinate_names(ds)
    ds = standardize_longitude(ds)

    print("\nERA5 pressure dataset:")
    print(ds)

    inventory_rows = inspect_dataset(ds, "ERA5_pressure_levels", path)

    level_coord = find_level_coord(ds)

    if level_coord is None:
        raise ValueError(
            "Could not find pressure-level coordinate. "
            "Expected one of: level, pressure_level, isobaricInhPa, plev."
        )

    registry = {}

    available_levels = ds[level_coord].values
    print(f"\nDetected pressure levels: {available_levels}")

    for out_name, spec in ERA5_PRESSURE_TARGETS.items():
        var_name = find_variable(ds, spec["var_candidates"])

        out_path = ERA5_ORG_DIR / f"era5_{out_name}_1991_2020_JJAS.nc"

        if var_name is None:
            print(f"Missing variable for {out_name}: {spec['var_candidates']}")
            registry[out_name] = {
                "status": "missing_variable",
                "source": "ERA5",
                "path": "",
                "description": spec["description"],
            }
            continue

        level_value = spec["level"]

        try:
            da = ds[var_name].sel({level_coord: level_value}, method="nearest").squeeze(drop=True)
        except Exception as exc:
            print(f"Could not extract {out_name} at {level_value} hPa: {exc}")
            registry[out_name] = {
                "status": "failed_extract_level",
                "source": "ERA5",
                "path": "",
                "description": spec["description"],
            }
            continue

        # Convert ERA5 geopotential from m2/s2 to geopotential height in meters
        if spec.get("convert_geopotential_to_height", False):
            da = da / 9.80665
            da.attrs["units"] = "m"
            da.attrs["conversion_note"] = "Converted from geopotential to geopotential height by dividing by 9.80665."
            da.attrs["long_name"] = spec["description"]

        da.attrs["diagnostic_name"] = out_name
        da.attrs["description"] = spec["description"]
        da.attrs["source_file"] = str(path)

        save_dataarray_as_netcdf(da, out_path, out_name)

        print(f"Saved organized ERA5 field: {out_path}")

        registry[out_name] = {
            "status": "available",
            "source": "ERA5",
            "path": str(out_path),
            "description": spec["description"],
            "units": da.attrs.get("units", ""),
        }

    ds.close()

    return inventory_rows, registry


def organize_era5_single_level_fields(path: Path) -> tuple[list[dict], dict]:
    print("\n==================================================")
    print("Inspecting and organizing ERA5 single-level file")
    print("==================================================")
    print(path)

    ds = open_dataset_safely(path, decode_times=True)
    ds = standardize_coordinate_names(ds)
    ds = standardize_longitude(ds)

    print("\nERA5 single-level dataset:")
    print(ds)

    inventory_rows = inspect_dataset(ds, "ERA5_single_levels", path)

    registry = {}

    for out_name, spec in ERA5_SINGLE_TARGETS.items():
        var_name = find_variable(ds, spec["var_candidates"])

        out_path = ERA5_ORG_DIR / f"era5_{out_name}_1991_2020_JJAS.nc"

        if var_name is None:
            print(f"Missing variable for {out_name}: {spec['var_candidates']}")
            registry[out_name] = {
                "status": "missing_variable",
                "source": "ERA5",
                "path": "",
                "description": spec["description"],
            }
            continue

        da = ds[var_name].squeeze(drop=True)

        da.attrs["diagnostic_name"] = out_name
        da.attrs["description"] = spec["description"]
        da.attrs["source_file"] = str(path)

        save_dataarray_as_netcdf(da, out_path, out_name)

        print(f"Saved organized ERA5 field: {out_path}")

        registry[out_name] = {
            "status": "available",
            "source": "ERA5",
            "path": str(out_path),
            "description": spec["description"],
            "units": da.attrs.get("units", ""),
        }

    ds.close()

    return inventory_rows, registry


# ==========================================================
# NMME ORGANIZATION
# ==========================================================

def organize_nmme_key_fields(nmme_dir: Path) -> tuple[list[dict], dict]:
    print("\n==================================================")
    print("Inspecting and organizing NMME realtime anomaly files")
    print("==================================================")
    print(nmme_dir)

    if not nmme_dir.exists():
        print(f"NMME folder not found: {nmme_dir}")
        return [], {}

    nc_files = sorted(nmme_dir.glob("*.nc"))

    print(f"Found {len(nc_files)} NMME NetCDF files.")

    inventory_rows = []
    registry = {}

    for nc_file in nc_files:
        try:
            ds = open_dataset_safely(nc_file, decode_times=False)
            ds = standardize_coordinate_names(ds)
            ds = standardize_longitude(ds)

            inventory_rows.extend(
                inspect_dataset(ds, "NMME_realtime_anom", nc_file)
            )

            lower_name = nc_file.name.lower()

            should_organize = (
                nc_file.name.startswith("NMME.")
                and any(keyword in lower_name for keyword in NMME_KEYWORDS_TO_ORGANIZE)
            )

            if should_organize:
                main_var = choose_main_nmme_variable(ds)

                if main_var is not None:
                    out_key = f"nmme_{sanitize_name(nc_file.stem)}"
                    out_path = NMME_ORG_DIR / f"{out_key}.nc"

                    da = ds[main_var].squeeze(drop=True)
                    da.attrs["diagnostic_name"] = out_key
                    da.attrs["source_file"] = str(nc_file)
                    da.attrs["source_note"] = "CPC NMME realtime anomaly ENSMEAN file."

                    save_dataarray_as_netcdf(da, out_path, main_var)

                    print(f"Saved organized NMME field: {out_path}")

                    registry[out_key] = {
                        "status": "available",
                        "source": "NMME_CPC_realtime_anom",
                        "path": str(out_path),
                        "description": f"NMME organized field from {nc_file.name}",
                        "variable": main_var,
                        "units": da.attrs.get("units", ""),
                    }

            ds.close()

        except Exception as exc:
            print(f"Could not inspect NMME file: {nc_file}")
            print(exc)

            inventory_rows.append(
                {
                    "source": "NMME_realtime_anom",
                    "file": str(nc_file),
                    "variable": "ERROR",
                    "dims": "",
                    "shape": "",
                    "units": "",
                    "long_name": str(exc),
                }
            )

    return inventory_rows, registry


# ==========================================================
# STATUS TABLE
# ==========================================================

def build_diagnostic_status_table(
    era5_registry: dict,
    nmme_registry: dict,
) -> pd.DataFrame:
    rows = []

    required_fields = [
        {
            "diagnostic": "Rainfall anomaly",
            "preferred_field": "NMME prate",
            "source": "NMME",
            "status": "available" if any("prate" in k.lower() for k in nmme_registry) else "missing",
            "notes": "Used for rainfall anomaly maps.",
        },
        {
            "diagnostic": "SST / surface temperature anomaly",
            "preferred_field": "NMME tmpsfc + ERA5 sst climatology",
            "source": "NMME/ERA5",
            "status": "available" if any("tmpsfc" in k.lower() for k in nmme_registry) and "sst" in era5_registry else "partial_or_missing",
            "notes": "NMME tmpsfc is useful; ERA5 SST is used for climatology and index boxes.",
        },
        {
            "diagnostic": "TEJ / upper-level zonal wind",
            "preferred_field": "u200",
            "source": "ERA5 climatology",
            "status": era5_registry.get("u200", {}).get("status", "missing"),
            "notes": "Needed for TEJ climatology and anomaly diagnostics.",
        },
        {
            "diagnostic": "Upper-level meridional wind",
            "preferred_field": "v200",
            "source": "ERA5 climatology",
            "status": era5_registry.get("v200", {}).get("status", "missing"),
            "notes": "Supports upper-level circulation diagnosis.",
        },
        {
            "diagnostic": "Low-level zonal wind",
            "preferred_field": "u850",
            "source": "ERA5 climatology",
            "status": era5_registry.get("u850", {}).get("status", "missing"),
            "notes": "Needed for moisture flux.",
        },
        {
            "diagnostic": "Low-level meridional wind",
            "preferred_field": "v850",
            "source": "ERA5 climatology",
            "status": era5_registry.get("v850", {}).get("status", "missing"),
            "notes": "Needed for moisture flux.",
        },
        {
            "diagnostic": "Low-level moisture",
            "preferred_field": "q850",
            "source": "ERA5 climatology",
            "status": era5_registry.get("q850", {}).get("status", "missing"),
            "notes": "Needed for q*u and q*v moisture transport.",
        },
        {
            "diagnostic": "Vertical motion",
            "preferred_field": "omega500/omega700",
            "source": "ERA5 climatology",
            "status": "available"
            if era5_registry.get("omega500", {}).get("status") == "available"
            and era5_registry.get("omega700", {}).get("status") == "available"
            else "partial_or_missing",
            "notes": "Positive omega means subsidence; negative omega means rising motion.",
        },
        {
            "diagnostic": "Upper-level divergence",
            "preferred_field": "divergence200",
            "source": "ERA5 climatology",
            "status": era5_registry.get("divergence200", {}).get("status", "missing"),
            "notes": "Positive divergence supports convection.",
        },
        {
            "diagnostic": "Walker circulation proxy",
            "preferred_field": "velocity_potential200",
            "source": "ERA5 climatology",
            "status": era5_registry.get("velocity_potential200", {}).get("status", "missing"),
            "notes": "Positive VP anomaly can indicate suppressed convection.",
        },
        {
            "diagnostic": "Rossby-wave / height pattern",
            "preferred_field": "z200/z500",
            "source": "NMME/ERA5",
            "status": "available"
            if era5_registry.get("z200", {}).get("status") == "available"
            and era5_registry.get("z500", {}).get("status") == "available"
            else "partial_or_missing",
            "notes": "Used to diagnose upper/mid-level circulation wave patterns.",
        },
    ]

    for item in required_fields:
        rows.append(item)

    return pd.DataFrame(rows)


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("Inspect and organize NMME + ERA5 diagnostic fields")
    print("==================================================")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"NMME dir:     {NMME_DIR}")
    print(f"ERA5 dir:     {ERA5_DIR}")
    print(f"Table dir:    {TABLE_DIR}")

    pressure_file = pick_existing_file(ERA5_PRESSURE_FULL, ERA5_PRESSURE_TEST)
    sst_file = pick_existing_file(ERA5_SST_FULL, ERA5_SST_TEST)

    if pressure_file is None:
        raise FileNotFoundError(
            "No ERA5 pressure-level file found. Expected one of:\n"
            f"  {ERA5_PRESSURE_FULL}\n"
            f"  {ERA5_PRESSURE_TEST}"
        )

    if sst_file is None:
        raise FileNotFoundError(
            "No ERA5 SST single-level file found. Expected one of:\n"
            f"  {ERA5_SST_FULL}\n"
            f"  {ERA5_SST_TEST}"
        )

    all_inventory_rows = []
    full_registry = {
        "era5": {},
        "nmme": {},
    }

    # 1. Organize NMME
    nmme_rows, nmme_registry = organize_nmme_key_fields(NMME_REALTIME_DIR)
    all_inventory_rows.extend(nmme_rows)
    full_registry["nmme"] = nmme_registry

    # 2. Organize ERA5 pressure levels
    era5_pressure_rows, era5_pressure_registry = organize_era5_pressure_fields(pressure_file)
    all_inventory_rows.extend(era5_pressure_rows)

    # 3. Organize ERA5 SST
    era5_sst_rows, era5_sst_registry = organize_era5_single_level_fields(sst_file)
    all_inventory_rows.extend(era5_sst_rows)

    era5_registry = {}
    era5_registry.update(era5_pressure_registry)
    era5_registry.update(era5_sst_registry)

    full_registry["era5"] = era5_registry

    # 4. Save inventory
    inventory_df = pd.DataFrame(all_inventory_rows)
    inventory_csv = TABLE_DIR / "field_inventory_nmme_era5.csv"
    inventory_df.to_csv(inventory_csv, index=False)

    print(f"\nSaved field inventory: {inventory_csv}")

    # 5. Save registry JSON
    registry_json = TABLE_DIR / "organized_field_registry.json"

    with open(registry_json, "w", encoding="utf-8") as f:
        json.dump(full_registry, f, indent=2)

    print(f"Saved organized field registry: {registry_json}")

    # 6. Save diagnostic status table
    status_df = build_diagnostic_status_table(
        era5_registry=era5_registry,
        nmme_registry=nmme_registry,
    )

    status_csv = TABLE_DIR / "diagnostic_field_status.csv"
    status_df.to_csv(status_csv, index=False)

    print(f"Saved diagnostic status table: {status_csv}")

    print("\n==================================================")
    print("ORGANIZATION SUMMARY")
    print("==================================================")

    print("\nERA5 organized fields:")
    for key, value in era5_registry.items():
        print(f" - {key}: {value.get('status')} -> {value.get('path', '')}")

    print("\nNMME organized fields:")
    for key, value in nmme_registry.items():
        print(f" - {key}: {value.get('status')} -> {value.get('path', '')}")

    print("\nNext output folders:")
    print(f" - ERA5 organized: {ERA5_ORG_DIR}")
    print(f" - NMME organized: {NMME_ORG_DIR}")
    print(f" - Tables:         {TABLE_DIR}")

    print("\nDone.")


if __name__ == "__main__":
    main()