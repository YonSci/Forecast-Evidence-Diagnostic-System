"""
08_inspect_cfsv2_grib.py

Purpose
-------
Inspect downloaded NOMADS CFSv2 monthly GRIB2 files.

This script reads:
    data/cfsv2/monthly_grib/*.grib.grb2

It creates:
    outputs/tables/cfsv2_grib_inventory.csv

Run:
    python scripts\\08_inspect_cfsv2_grib.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import cfgrib


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GRIB_DIR = PROJECT_ROOT / "data" / "cfsv2" / "monthly_grib"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
TABLE_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = TABLE_DIR / "cfsv2_grib_inventory.csv"


def infer_family(path: Path) -> str:
    name = path.name.lower()

    if name.startswith("pgbf"):
        return "pgbf_pressure_level_atmosphere"
    if name.startswith("flxf"):
        return "flxf_flux_radiation_surface"
    if name.startswith("ocnh"):
        return "ocnh_ocean"

    return "unknown"


def infer_valid_month(path: Path) -> str:
    """
    Example filename:
    pgbf.01.2026061000.202607.avrg.grib.grb2
    """
    parts = path.name.split(".")

    for part in parts:
        if part.isdigit() and len(part) == 6 and part.startswith("2026"):
            return part

    return "unknown"


def inspect_file(path: Path) -> list[dict]:
    print("\n==================================================")
    print(f"Inspecting: {path.name}")
    print("==================================================")

    rows = []

    try:
        datasets = cfgrib.open_datasets(str(path))
    except Exception as exc:
        print(f"FAILED to open {path.name}")
        print(exc)

        return [
            {
                "file": path.name,
                "family": infer_family(path),
                "valid_month": infer_valid_month(path),
                "dataset_index": -1,
                "variable": "OPEN_ERROR",
                "long_name": str(exc),
                "units": "",
                "dims": "",
                "shape": "",
                "typeOfLevel": "",
                "level_values": "",
                "step": "",
            }
        ]

    print(f"Number of cfgrib datasets: {len(datasets)}")

    for i, ds in enumerate(datasets):
        type_of_level = ""
        if "typeOfLevel" in ds.attrs:
            type_of_level = ds.attrs.get("typeOfLevel", "")

        for var in ds.data_vars:
            da = ds[var]

            level_values = ""

            for level_coord in [
                "isobaricInhPa",
                "isobaricInPa",
                "heightAboveGround",
                "depthBelowLandLayer",
                "depthBelowSea",
                "surface",
                "nominalTop",
            ]:
                if level_coord in da.coords:
                    vals = da[level_coord].values
                    level_values = str(vals)
                    break

            step = ""
            if "step" in da.coords:
                step = str(da["step"].values)

            rows.append(
                {
                    "file": path.name,
                    "family": infer_family(path),
                    "valid_month": infer_valid_month(path),
                    "dataset_index": i,
                    "variable": var,
                    "long_name": da.attrs.get("long_name", ""),
                    "standard_name": da.attrs.get("standard_name", ""),
                    "units": da.attrs.get("units", ""),
                    "dims": ", ".join(da.dims),
                    "shape": str(tuple(da.shape)),
                    "typeOfLevel": type_of_level,
                    "level_values": level_values,
                    "step": step,
                }
            )

        ds.close()

    return rows


def main():
    print("\n==================================================")
    print("Inspect CFSv2 monthly GRIB files")
    print("==================================================")
    print(f"GRIB directory: {GRIB_DIR}")

    grib_files = sorted(GRIB_DIR.glob("*.grib.grb2"))

    if not grib_files:
        raise FileNotFoundError(f"No GRIB files found in {GRIB_DIR}")

    print(f"Found {len(grib_files)} GRIB files.")

    all_rows = []

    for path in grib_files:
        rows = inspect_file(path)
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_CSV, index=False)

    print("\n==================================================")
    print("CFSv2 GRIB INVENTORY SAVED")
    print("==================================================")
    print(OUT_CSV)

    print("\nVariable summary:")
    summary = (
        df.groupby(["family", "variable", "long_name", "units"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["family", "variable"])
    )

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()