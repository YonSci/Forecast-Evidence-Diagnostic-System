"""
09_extract_cfsv2_dynamic_fields_v3.py

Purpose
-------
Extract dynamic forecast fields from NOMADS CFSv2 monthly GRIB2 files using
the actual cfgrib variable names found in the inventory.

This version is based on the real CFSv2 pgbf inventory:
    avg_u  = Time-mean U component of wind
    avg_v  = Time-mean V component of wind
    avg_q  = Time-mean specific humidity
    avg_w  = Time-mean vertical velocity
    gh     = Geopotential height
    vp     = Velocity potential
    strf   = Stream function

Inputs:
    data/cfsv2/monthly_grib/

Outputs:
    data/cfsv2/organized_v3/
    outputs/tables/cfsv2_extraction_status_v3.csv

Run:
    python scripts\\09_extract_cfsv2_dynamic_fields_v3.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import cfgrib


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GRIB_DIR = PROJECT_ROOT / "data" / "cfsv2" / "monthly_grib"
OUT_DIR = PROJECT_ROOT / "data" / "cfsv2" / "organized_v3"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"

OUT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

STATUS_CSV = TABLE_DIR / "cfsv2_extraction_status_v3.csv"


# ==========================================================
# TARGET MONTHS
# ==========================================================

TARGET_MONTHS = {
    "202606": "Jun_2026",
    "202607": "Jul_2026",
    "202608": "Aug_2026",
    "202609": "Sep_2026",
}


# ==========================================================
# FIELD DEFINITIONS
# ==========================================================

FIELD_SPECS = {
    # ------------------------------------------------------
    # Pressure-level atmosphere from pgbf
    # ------------------------------------------------------
    "u200": {
        "family": "pgbf",
        "var_candidates": ["avg_u", "u"],
        "level_hpa": 200,
        "description": "200 hPa zonal wind",
    },
    "v200": {
        "family": "pgbf",
        "var_candidates": ["avg_v", "v"],
        "level_hpa": 200,
        "description": "200 hPa meridional wind",
    },
    "u850": {
        "family": "pgbf",
        "var_candidates": ["avg_u", "u"],
        "level_hpa": 850,
        "description": "850 hPa zonal wind",
    },
    "v850": {
        "family": "pgbf",
        "var_candidates": ["avg_v", "v"],
        "level_hpa": 850,
        "description": "850 hPa meridional wind",
    },
    "q850": {
        "family": "pgbf",
        "var_candidates": ["avg_q", "q", "spfh"],
        "level_hpa": 850,
        "description": "850 hPa specific humidity",
    },
    "omega500": {
        "family": "pgbf",
        "var_candidates": ["avg_w", "w", "vvel"],
        "level_hpa": 500,
        "description": "500 hPa vertical velocity / omega",
    },
    "omega700": {
        "family": "pgbf",
        "var_candidates": ["avg_w", "w", "vvel"],
        "level_hpa": 700,
        "description": "700 hPa vertical velocity / omega",
    },
    "z200": {
        "family": "pgbf",
        "var_candidates": ["gh", "hgt", "z"],
        "level_hpa": 200,
        "description": "200 hPa geopotential height",
    },
    "z500": {
        "family": "pgbf",
        "var_candidates": ["gh", "hgt", "z"],
        "level_hpa": 500,
        "description": "500 hPa geopotential height",
    },
    "vp200": {
        "family": "pgbf",
        "var_candidates": ["vp"],
        "level_hpa": 200,
        "description": "200 hPa velocity potential",
    },
    "strf200": {
        "family": "pgbf",
        "var_candidates": ["strf"],
        "level_hpa": 200,
        "description": "200 hPa stream function",
    },

    # ------------------------------------------------------
    # Flux/radiation file: OLR proxy if available
    # Candidate names will be checked against actual data_vars.
    # ------------------------------------------------------
    "olr_proxy": {
        "family": "flxf",
        "var_candidates": [
            "avg_ulwrf",
            "ulwrf",
            "avg_ttr",
            "ttr",
            "avg_lwrf",
            "lwrf",
        ],
        "level_hpa": None,
        "description": "Outgoing longwave radiation proxy from flux file",
    },

    # ------------------------------------------------------
    # Ocean file: SST proxy if available
    # Candidate names will be checked against actual data_vars.
    # ------------------------------------------------------
    "sst_proxy": {
        "family": "ocnh",
        "var_candidates": [
            "sst",
            "avg_sst",
            "wtmp",
            "avg_wtmp",
            "t",
            "avg_t",
        ],
        "level_hpa": None,
        "description": "Sea surface temperature or near-surface ocean temperature proxy",
    },
}


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def infer_valid_month(path: Path) -> str:
    """
    Example:
    pgbf.01.2026061000.202607.avrg.grib.grb2
    valid month = 202607
    """
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


def open_all_datasets(path: Path) -> list[xr.Dataset]:
    try:
        return cfgrib.open_datasets(
            str(path),
            backend_kwargs={"indexpath": ""},
        )
    except TypeError:
        # Older cfgrib versions may not accept backend_kwargs here
        return cfgrib.open_datasets(str(path))


def find_var_in_datasets(
    datasets: list[xr.Dataset],
    candidates: list[str],
) -> tuple[xr.DataArray | None, str]:
    candidates_lower = [c.lower() for c in candidates]

    for i, ds in enumerate(datasets):
        ds = standardize_coordinate_names(ds)
        ds = standardize_longitude(ds)

        for var_name in ds.data_vars:
            if var_name.lower() in candidates_lower:
                return ds[var_name], f"dataset_index={i}, variable={var_name}"

    return None, "No matching data variable found."


def select_level(da: xr.DataArray, level_hpa: int | None) -> xr.DataArray:
    if level_hpa is None:
        return select_first_vertical_level_if_needed(da)

    pressure_coord_candidates = [
        "isobaricInhPa",
        "isobaricInPa",
        "level",
    ]

    for coord in pressure_coord_candidates:
        if coord in da.coords:
            values = np.asarray(da[coord].values)

            if values.ndim == 0:
                val = float(values)

                if coord == "isobaricInPa":
                    val_hpa = val / 100.0
                else:
                    val_hpa = val

                if abs(val_hpa - level_hpa) < 1e-6:
                    return da.squeeze(drop=True)

                continue

            if coord == "isobaricInPa":
                target = level_hpa * 100.0
            else:
                target = level_hpa

            return da.sel({coord: target}, method="nearest").squeeze(drop=True)

    raise ValueError(
        f"Could not find pressure coordinate for {level_hpa} hPa. "
        f"Available coords: {list(da.coords)}"
    )


def select_first_vertical_level_if_needed(da: xr.DataArray) -> xr.DataArray:
    vertical_candidates = [
        "depthBelowSea",
        "depthBelowSeaLayer",
        "heightAboveGround",
        "nominalTop",
        "surface",
    ]

    for coord in vertical_candidates:
        if coord in da.dims:
            return da.isel({coord: 0}).squeeze(drop=True)

    return da.squeeze(drop=True)


def extract_field_from_file(path: Path, spec: dict) -> tuple[xr.DataArray | None, str]:
    try:
        datasets = open_all_datasets(path)
    except Exception as exc:
        return None, f"open_error: {exc}"

    try:
        da, message = find_var_in_datasets(
            datasets=datasets,
            candidates=spec["var_candidates"],
        )

        if da is None:
            available = []

            for ds in datasets:
                available.extend(list(ds.data_vars))

            return None, f"{message} Available variables include: {sorted(set(available))[:80]}"

        da = select_level(da, spec["level_hpa"])
        da = standardize_coordinate_names(da)
        da = standardize_longitude(da)
        da = da.load()

        return da, message

    except Exception as exc:
        return None, f"extract_error: {exc}"

    finally:
        for ds in datasets:
            try:
                ds.close()
            except Exception:
                pass


def save_field(
    da: xr.DataArray,
    out_path: Path,
    var_name: str,
    attrs: dict,
) -> None:
    da.attrs.update(attrs)

    if out_path.exists():
        out_path.unlink()

    da.to_dataset(name=var_name).to_netcdf(out_path)

    print(f"Saved: {out_path}")


def extract_monthly_fields() -> pd.DataFrame:
    grib_files = sorted(GRIB_DIR.glob("*.grib.grb2"))

    if not grib_files:
        raise FileNotFoundError(f"No GRIB files found in {GRIB_DIR}")

    rows = []

    for valid_month, period_label in TARGET_MONTHS.items():
        print("\n==================================================")
        print(f"Extracting CFSv2 fields for {period_label} ({valid_month})")
        print("==================================================")

        for field_name, spec in FIELD_SPECS.items():
            family = spec["family"]

            candidate_files = [
                p for p in grib_files
                if family_matches(p, family) and infer_valid_month(p) == valid_month
            ]

            if not candidate_files:
                msg = f"No {family} GRIB file found for {valid_month}"
                print(f"{field_name}: {msg}")

                rows.append(
                    {
                        "field": field_name,
                        "period": period_label,
                        "valid_month": valid_month,
                        "status": "missing_grib_file",
                        "source_file": "",
                        "output_file": "",
                        "message": msg,
                    }
                )
                continue

            source_file = candidate_files[0]

            da, msg = extract_field_from_file(source_file, spec)

            if da is None:
                print(f"{field_name}: NOT FOUND")

                rows.append(
                    {
                        "field": field_name,
                        "period": period_label,
                        "valid_month": valid_month,
                        "status": "field_not_found",
                        "source_file": str(source_file),
                        "output_file": "",
                        "message": msg,
                    }
                )
                continue

            out_path = OUT_DIR / f"CFSv2_{field_name}_{period_label}.nc"

            attrs = {
                "diagnostic_name": field_name,
                "period": period_label,
                "valid_month": valid_month,
                "source_file": str(source_file),
                "description": spec["description"],
                "source_note": (
                    "NOMADS CFSv2 monthly GRIB forecast. "
                    "Initialization date inferred from filename."
                ),
                "match_message": msg,
            }

            save_field(
                da=da,
                out_path=out_path,
                var_name=field_name,
                attrs=attrs,
            )

            rows.append(
                {
                    "field": field_name,
                    "period": period_label,
                    "valid_month": valid_month,
                    "status": "available",
                    "source_file": str(source_file),
                    "output_file": str(out_path),
                    "message": msg,
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

            if not paths:
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
    print("CFSv2 dynamic field extractor v3")
    print("==================================================")
    print(f"GRIB directory:  {GRIB_DIR}")
    print(f"Output directory: {OUT_DIR}")

    monthly_status = extract_monthly_fields()
    seasonal_status = create_seasonal_means(monthly_status)

    monthly_status["stage"] = "monthly_extraction"
    seasonal_status["stage"] = "seasonal_mean"

    status_df = pd.concat(
        [monthly_status, seasonal_status],
        ignore_index=True,
        sort=False,
    )

    status_df.to_csv(STATUS_CSV, index=False)

    print("\n==================================================")
    print("CFSv2 EXTRACTION V3 FINISHED")
    print("==================================================")
    print(f"Status table: {STATUS_CSV}")
    print(f"Organized NetCDFs: {OUT_DIR}")

    print("\nAvailability summary:")
    summary = (
        status_df.groupby(["stage", "field", "status"])
        .size()
        .reset_index(name="count")
        .sort_values(["stage", "field", "status"])
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()