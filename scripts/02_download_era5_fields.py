"""
02_download_era5_fields.py

Purpose
-------
Download ERA5 monthly reanalysis fields needed for dynamic diagnosis of
Ethiopia Kiremt/JJAS rainfall mechanisms.

This script downloads:

1. ERA5 pressure-level monthly means:
   - u wind
   - v wind
   - specific humidity
   - vertical velocity / omega
   - geopotential
   - divergence
   - velocity potential

2. ERA5 single-level monthly means:
   - sea surface temperature

The first run is in TEST mode by default to confirm that your CDS API works.
After the test succeeds, change RUN_MODE from "test" to "full".

Run from project root:
    python scripts\\02_download_era5_fields.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from datetime import datetime

import cdsapi


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import ERA5_DIR
except Exception:
    ERA5_DIR = PROJECT_ROOT / "data" / "era5"


# ==========================================================
# USER SETTINGS
# ==========================================================

# First run with "test".
# If test download succeeds, change to "full".
RUN_MODE = "full"   # options: "test", "full"

# Ethiopia Kiremt season months
JJAS_MONTHS = ["06", "07", "08", "09"]

# Climatology period
CLIM_START_YEAR = 1991
CLIM_END_YEAR = 2020

# TEST mode downloads only one year and two months to verify CDS setup
TEST_YEARS = ["2020"]
TEST_MONTHS = ["06", "07"]

# FULL mode downloads 1991-2020 JJAS
FULL_YEARS = [str(y) for y in range(CLIM_START_YEAR, CLIM_END_YEAR + 1)]
FULL_MONTHS = JJAS_MONTHS

# CDS area format:
# [North, West, South, East]
#
# Africa-Indian domain:
# Covers Atlantic/Congo moisture corridor, Ethiopia, East Africa,
# Arabian Sea, and western/central Indian Ocean.
PRESSURE_LEVEL_AREA = [40, -40, -40, 130]

# Tropical global SST domain:
# Useful for ENSO and IOD diagnostics.
SST_AREA = [30, -180, -30, 180]

# Pressure levels required for diagnostics
PRESSURE_LEVELS = ["200", "500", "700", "850"]

# Pressure-level variables
PRESSURE_LEVEL_VARIABLES = [
    "u_component_of_wind",
    "v_component_of_wind",
    "specific_humidity",
    "vertical_velocity",
    "geopotential",
    "divergence",
    "velocity_potential",
]

# Single-level variables
SINGLE_LEVEL_VARIABLES = [
    "sea_surface_temperature",
]

# Download switches
DOWNLOAD_PRESSURE_LEVELS = True
DOWNLOAD_SST = True


# ==========================================================
# OUTPUT FOLDERS
# ==========================================================

ERA5_MONTHLY_DIR = ERA5_DIR / "monthly"
ERA5_PRESSURE_DIR = ERA5_MONTHLY_DIR / "pressure_levels"
ERA5_SINGLE_DIR = ERA5_MONTHLY_DIR / "single_levels"
ERA5_INVENTORY_DIR = ERA5_DIR / "inventory"

ERA5_PRESSURE_DIR.mkdir(parents=True, exist_ok=True)
ERA5_SINGLE_DIR.mkdir(parents=True, exist_ok=True)
ERA5_INVENTORY_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def get_years_months():
    if RUN_MODE.lower() == "test":
        years = TEST_YEARS
        months = TEST_MONTHS
        tag = "TEST"
    elif RUN_MODE.lower() == "full":
        years = FULL_YEARS
        months = FULL_MONTHS
        tag = f"{CLIM_START_YEAR}_{CLIM_END_YEAR}_JJAS"
    else:
        raise ValueError("RUN_MODE must be either 'test' or 'full'.")

    return years, months, tag


def write_request_summary(
    out_csv: Path,
    dataset: str,
    target_file: Path,
    request: dict,
    status: str,
    message: str,
):
    file_exists = target_file.exists()
    size_mb = target_file.stat().st_size / (1024 * 1024) if file_exists else 0.0

    write_header = not out_csv.exists()

    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if write_header:
            writer.writerow(
                [
                    "timestamp",
                    "dataset",
                    "target_file",
                    "status",
                    "message",
                    "exists",
                    "size_mb",
                    "run_mode",
                    "years",
                    "months",
                    "area",
                    "variables",
                    "pressure_levels",
                ]
            )

        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
                dataset,
                str(target_file),
                status,
                message,
                file_exists,
                round(size_mb, 3),
                RUN_MODE,
                ",".join(request.get("year", [])),
                ",".join(request.get("month", [])),
                request.get("area", ""),
                ",".join(request.get("variable", [])),
                ",".join(request.get("pressure_level", []))
                if "pressure_level" in request
                else "",
            ]
        )


def retrieve_cds_dataset(
    client: cdsapi.Client,
    dataset: str,
    request: dict,
    target_file: Path,
    inventory_csv: Path,
):
    if target_file.exists() and target_file.stat().st_size > 0:
        print(f"\nAlready exists, skipping:")
        print(target_file)

        write_request_summary(
            out_csv=inventory_csv,
            dataset=dataset,
            target_file=target_file,
            request=request,
            status="skipped_existing",
            message="File already exists.",
        )
        return

    print("\n==================================================")
    print(f"Downloading dataset: {dataset}")
    print("Target:")
    print(target_file)
    print("==================================================")

    try:
        client.retrieve(dataset, request, str(target_file))

        print("\nDownload completed:")
        print(target_file)

        write_request_summary(
            out_csv=inventory_csv,
            dataset=dataset,
            target_file=target_file,
            request=request,
            status="success",
            message="Download completed.",
        )

    except Exception as exc:
        print("\nDownload failed.")
        print(f"Dataset: {dataset}")
        print(f"Target:  {target_file}")
        print("Error:")
        print(exc)

        print("\nCommon fixes:")
        print("1. Make sure %USERPROFILE%\\.cdsapirc exists.")
        print("2. Make sure the CDS API key is correct.")
        print("3. Log in to CDS and accept the dataset license terms.")
        print("4. If the request is too large, keep RUN_MODE='test' first.")
        print("5. Try again later if the CDS queue is busy.")

        write_request_summary(
            out_csv=inventory_csv,
            dataset=dataset,
            target_file=target_file,
            request=request,
            status="failed",
            message=str(exc),
        )


# ==========================================================
# REQUEST BUILDERS
# ==========================================================

def build_pressure_level_request(years: list[str], months: list[str]) -> dict:
    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": PRESSURE_LEVEL_VARIABLES,
        "pressure_level": PRESSURE_LEVELS,
        "year": years,
        "month": months,
        "time": ["00:00"],
        "area": PRESSURE_LEVEL_AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }

    return request


def build_sst_request(years: list[str], months: list[str]) -> dict:
    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": SINGLE_LEVEL_VARIABLES,
        "year": years,
        "month": months,
        "time": ["00:00"],
        "area": SST_AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }

    return request


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("ERA5 monthly field downloader")
    print("==================================================")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"ERA5 dir:     {ERA5_DIR}")
    print(f"Run mode:     {RUN_MODE}")

    years, months, tag = get_years_months()

    print(f"Years:        {years[0]} to {years[-1]}")
    print(f"Months:       {', '.join(months)}")

    inventory_csv = ERA5_INVENTORY_DIR / f"era5_download_inventory_{RUN_MODE}.csv"

    client = cdsapi.Client()

    if DOWNLOAD_PRESSURE_LEVELS:
        pressure_dataset = "reanalysis-era5-pressure-levels-monthly-means"

        pressure_request = build_pressure_level_request(
            years=years,
            months=months,
        )

        pressure_out = (
            ERA5_PRESSURE_DIR
            / f"era5_pressure_levels_africa_indian_{tag}.nc"
        )

        retrieve_cds_dataset(
            client=client,
            dataset=pressure_dataset,
            request=pressure_request,
            target_file=pressure_out,
            inventory_csv=inventory_csv,
        )

    if DOWNLOAD_SST:
        sst_dataset = "reanalysis-era5-single-levels-monthly-means"

        sst_request = build_sst_request(
            years=years,
            months=months,
        )

        sst_out = (
            ERA5_SINGLE_DIR
            / f"era5_sst_tropical_global_{tag}.nc"
        )

        retrieve_cds_dataset(
            client=client,
            dataset=sst_dataset,
            request=sst_request,
            target_file=sst_out,
            inventory_csv=inventory_csv,
        )

    print("\n==================================================")
    print("ERA5 DOWNLOAD STAGE FINISHED")
    print("==================================================")
    print(f"Inventory: {inventory_csv}")
    print(f"Pressure-level files: {ERA5_PRESSURE_DIR}")
    print(f"Single-level files:   {ERA5_SINGLE_DIR}")

    if RUN_MODE.lower() == "test":
        print("\nYou are currently in TEST mode.")
        print("If the test files downloaded successfully, open this script and change:")
        print('    RUN_MODE = "test"')
        print("to:")
        print('    RUN_MODE = "full"')
        print("Then run again:")
        print("    python scripts\\02_download_era5_fields.py")


if __name__ == "__main__":
    main()