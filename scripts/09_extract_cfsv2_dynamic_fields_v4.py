"""
09_extract_cfsv2_dynamic_fields_v4.py

Purpose
-------
Extract dynamic forecast fields from NOMADS CFSv2 monthly GRIB2 files using
the actual CFSv2 monthly-mean variable names found in the GRIB inventory.

This version fixes the problem where CFSv2 contains the same variable name
more than once, for example:
    avg_u  as a non-pressure-level field
    avg_u  again as a full pressure-level field

The script now continues searching until it finds the requested pressure level.

Inputs:
    data/cfsv2/monthly_grib/

Outputs:
    data/cfsv2/organized_v4/
    outputs/tables/cfsv2_extraction_status_v4.csv

Run:
    python scripts\\09_extract_cfsv2_dynamic_fields_v4.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr
import cfgrib


# ==========================================================
# PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GRIB_DIR = PROJECT_ROOT / "data" / "cfsv2" / "monthly_grib"
OUT_DIR = PROJECT_ROOT / "data" / "cfsv2" / "organized_v4"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"

OUT_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

STATUS_CSV = TABLE_DIR / "cfsv2_extraction_status_v4.csv"


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

    # OLR proxy from flux file.
    # This may still need one final adjustment after inspecting flxf variables.
    "olr_proxy": {
        "family": "flxf",
        "var_candidates": [
            "avg_ulwrf",
            "ulwrf",
            "avg_ttr",
            "ttr",
            "avg_lwrf",
            "lwrf",
            "avg_lwavr",
            "lwavr",
        ],
        "level_hpa": None,
        "description": "Outgoing longwave radiation proxy from CFSv2 flux file",
        "prefer_keywords": ["upward", "long", "wave", "top"],
        "prefer_coords": ["nominalTop", "topOfAtmosphere"],
    },

    # SST proxy from ocean file.
    "sst_proxy": {
        "family": "ocnh",
        "var_candidates": [
            "sst",
            "avg_sst",
            "wtmp",
            "avg_wtmp",
            "t",
            "avg_t",
            "water_temp",
        ],
        "level_hpa": None,
        "description": "Sea surface temperature or near-surface ocean temperature proxy",
        "prefer_keywords": ["sea", "surface", "temperature", "water"],
        "prefer_coords": ["surface", "depthBelowSea", "depthBelowSeaLayer"],
    },
}


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def infer_valid_month(path: Path) -> str:
    """
    Example filename:
        pgbf.01.2026061000.202607.avrg.grib.grb2

    Valid month:
        202607
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


def sanitize_attrs(obj: xr.Dataset | xr.DataArray) -> xr.Dataset | xr.DataArray:
    """
    NetCDF writing can fail if attributes are lists, arrays, dicts, or other
    non-serializable objects. This converts unusual attrs to strings.
    """
    cleaned = {}

    for key, value in obj.attrs.items():
        if isinstance(value, (str, int, float, np.integer, np.floating)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)

    obj.attrs = cleaned
    return obj


def open_all_datasets(path: Path) -> list[xr.Dataset]:
    """
    Open all cfgrib hypercubes in a GRIB2 file.
    """
    try:
        return cfgrib.open_datasets(
            str(path),
            backend_kwargs={"indexpath": ""},
        )
    except TypeError:
        return cfgrib.open_datasets(str(path))


def select_level(da: xr.DataArray, level_hpa: int | None) -> xr.DataArray:
    """
    Select requested pressure level if level_hpa is not None.
    If level_hpa is None, return a surface/first-level field.
    """
    if level_hpa is None:
        return select_first_vertical_level_if_needed(da)

    pressure_coord_candidates = [
        "isobaricInhPa",
        "isobaricInPa",
        "level",
    ]

    for coord in pressure_coord_candidates:
        if coord not in da.coords:
            continue

        values = np.asarray(da[coord].values)

        # Scalar pressure coordinate
        if values.ndim == 0:
            val = float(values)

            if not np.isfinite(val):
                raise ValueError(
                    f"Pressure coordinate {coord} is scalar NaN for this variable."
                )

            val_hpa = val / 100.0 if coord == "isobaricInPa" else val

            if abs(val_hpa - level_hpa) < 1e-6:
                return da.squeeze(drop=True)

            raise ValueError(
                f"Pressure coordinate {coord}={val_hpa} hPa does not match requested {level_hpa} hPa."
            )

        # Vector pressure coordinate
        if coord == "isobaricInPa":
            target = level_hpa * 100.0
        else:
            target = level_hpa

        selected = da.sel({coord: target}, method="nearest").squeeze(drop=True)

        # Check selected level is close enough
        selected_level = selected[coord].values if coord in selected.coords else target
        selected_level = float(np.asarray(selected_level))

        selected_level_hpa = selected_level / 100.0 if coord == "isobaricInPa" else selected_level

        if abs(selected_level_hpa - level_hpa) > 1e-3:
            raise ValueError(
                f"Nearest selected level {selected_level_hpa} hPa is not requested {level_hpa} hPa."
            )

        return selected

    raise ValueError(
        f"Could not find pressure coordinate for {level_hpa} hPa. "
        f"Available coords: {list(da.coords)}"
    )


def select_first_vertical_level_if_needed(da: xr.DataArray) -> xr.DataArray:
    """
    For SST/OLR-like variables, select the first vertical-like level if needed.
    """
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


def score_non_pressure_candidate(da: xr.DataArray, spec: dict) -> int:
    """
    Score OLR/SST proxy candidates so that we prefer physically relevant fields.
    """
    score = 0

    var_text = str(da.name).lower()
    long_name = str(da.attrs.get("long_name", "")).lower()
    standard_name = str(da.attrs.get("standard_name", "")).lower()
    units = str(da.attrs.get("units", "")).lower()

    combined = f"{var_text} {long_name} {standard_name}"

    for keyword in spec.get("prefer_keywords", []):
        if keyword.lower() in combined:
            score += 10

    for coord in spec.get("prefer_coords", []):
        if coord in da.coords or coord in da.dims:
            score += 20

    if "w" in units and ("m**-2" in units or "m-2" in units):
        score += 5

    if "k" == units.strip() or units.strip() == "k":
        score += 5

    return score


def find_and_select_var_in_datasets(
    datasets: list[xr.Dataset],
    candidates: list[str],
    level_hpa: int | None,
    spec: dict,
) -> tuple[xr.DataArray | None, str]:
    """
    Search all cfgrib datasets for a candidate variable.

    For pressure-level variables:
        Continue searching until requested level is found.

    For non-pressure variables:
        Collect all matching candidates and choose the best one using metadata.
    """
    candidates_lower = [c.lower() for c in candidates]
    attempts = []

    # ------------------------------------------------------
    # Pressure-level case
    # ------------------------------------------------------
    if level_hpa is not None:
        for i, ds in enumerate(datasets):
            ds = standardize_coordinate_names(ds)
            ds = standardize_longitude(ds)

            for var_name in ds.data_vars:
                if var_name.lower() not in candidates_lower:
                    continue

                da = ds[var_name]

                try:
                    selected = select_level(da, level_hpa)
                    selected = standardize_coordinate_names(selected)
                    selected = standardize_longitude(selected)
                    selected = sanitize_attrs(selected)
                    selected = selected.load()

                    message = (
                        f"dataset_index={i}, variable={var_name}, "
                        f"selected_level={level_hpa} hPa"
                    )

                    return selected, message

                except Exception as exc:
                    attempts.append(
                        f"dataset_index={i}, variable={var_name}, failed_level_selection={exc}"
                    )
                    continue

    # ------------------------------------------------------
    # Non-pressure case: OLR/SST proxy
    # ------------------------------------------------------
    else:
        scored_candidates = []

        for i, ds in enumerate(datasets):
            ds = standardize_coordinate_names(ds)
            ds = standardize_longitude(ds)

            for var_name in ds.data_vars:
                if var_name.lower() not in candidates_lower:
                    continue

                da = ds[var_name]

                try:
                    selected = select_level(da, None)
                    selected = standardize_coordinate_names(selected)
                    selected = standardize_longitude(selected)
                    selected = sanitize_attrs(selected)
                    selected = selected.load()

                    score = score_non_pressure_candidate(selected, spec)

                    scored_candidates.append(
                        {
                            "score": score,
                            "dataset_index": i,
                            "variable": var_name,
                            "data": selected,
                        }
                    )

                except Exception as exc:
                    attempts.append(
                        f"dataset_index={i}, variable={var_name}, failed_selection={exc}"
                    )
                    continue

        if scored_candidates:
            best = sorted(
                scored_candidates,
                key=lambda x: x["score"],
                reverse=True,
            )[0]

            message = (
                f"dataset_index={best['dataset_index']}, "
                f"variable={best['variable']}, "
                f"proxy_score={best['score']}"
            )

            return best["data"], message

    available = []

    for ds in datasets:
        available.extend(list(ds.data_vars))

    message = (
        "No valid candidate field found after trying all matching variables. "
        f"Candidates={candidates}. "
        f"Available variables include={sorted(set(available))[:120]}. "
        f"Attempts={attempts[:30]}"
    )

    return None, message


def extract_field_from_file(path: Path, spec: dict) -> tuple[xr.DataArray | None, str]:
    try:
        datasets = open_all_datasets(path)
    except Exception as exc:
        return None, f"open_error: {exc}"

    try:
        da, message = find_and_select_var_in_datasets(
            datasets=datasets,
            candidates=spec["var_candidates"],
            level_hpa=spec["level_hpa"],
            spec=spec,
        )

        if da is None:
            return None, message

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
    attrs: dict[str, Any],
) -> None:
    da = sanitize_attrs(da)
    da.attrs.update(attrs)
    da = sanitize_attrs(da)

    if out_path.exists():
        out_path.unlink()

    ds_out = da.to_dataset(name=var_name)
    ds_out = sanitize_attrs(ds_out)

    ds_out.to_netcdf(out_path)

    print(f"Saved: {out_path}")


# ==========================================================
# EXTRACTION
# ==========================================================

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

            season_da = sanitize_attrs(season_da)

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


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("\n==================================================")
    print("CFSv2 dynamic field extractor v4")
    print("==================================================")
    print(f"GRIB directory:   {GRIB_DIR}")
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
    print("CFSv2 EXTRACTION V4 FINISHED")
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

    print("\nNext step:")
    print("If u200, v200, u850, v850, q850, omega500, omega700, vp200, z200, and z500 are available,")
    print("we can compute CFSv2 dynamic diagnostics: TEJ, divergence200, moisture flux, and MFC.")


if __name__ == "__main__":
    main()