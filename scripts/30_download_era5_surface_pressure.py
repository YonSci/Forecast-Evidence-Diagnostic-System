"""
30_download_era5_surface_pressure.py

Purpose
-------
Download ERA5 monthly-mean surface pressure, all twelve calendar months,
1991-2020, on the same grid and domain as the low-level winds from
script 29.

Why this is needed: ERA5 pressure-level fields exist everywhere on the
globe, including at pressures that are physically below the ground. Over
the Ethiopian highlands the surface sits near 800-700 hPa, so the 1000,
975, 950, 925, 900, 875 and 850 hPa levels are all underground there, and
the values ERA5 reports are a downward extrapolation rather than real
wind. Searching the sub-600-hPa stack for a wind maximum without masking
those out would put the "jet core" underground across exactly the region
this analysis is about -- the highlands and the Turkana channel.

Surface pressure is tiny compared with the wind stack (one level, two
fields' worth of bytes for thirty years), so it is downloaded as a single
request rather than chunked by year.

Run from project root:
    python scripts\\30_download_era5_surface_pressure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cdsapi


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import ERA5_DIR
except Exception:
    ERA5_DIR = PROJECT_ROOT / "data" / "era5"


CLIM_START_YEAR = 1991
CLIM_END_YEAR = 2020

YEARS = [str(y) for y in range(CLIM_START_YEAR, CLIM_END_YEAR + 1)]
MONTHS = [f"{m:02d}" for m in range(1, 13)]

# Must match scripts/29's AREA exactly so the mask lines up with the wind
# stack cell for cell and needs no regridding.
AREA = [42, -22, -22, 102]

SINGLE_DIR = ERA5_DIR / "monthly" / "single_levels"
SINGLE_DIR.mkdir(parents=True, exist_ok=True)

TARGET = SINGLE_DIR / "era5_surface_pressure_1991_2020_monthly.nc"


def main() -> None:
    print("==================================================")
    print("ERA5 surface pressure downloader (for below-ground masking)")
    print("==================================================")
    print(f"Target: {TARGET}")

    if TARGET.exists() and TARGET.stat().st_size > 0:
        size_mb = TARGET.stat().st_size / (1024 * 1024)
        print(f"Already exists ({size_mb:.1f} MB), skipping.")
        return

    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": ["surface_pressure"],
        "year": YEARS,
        "month": MONTHS,
        "time": ["00:00"],
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }

    client = cdsapi.Client()

    try:
        client.retrieve("reanalysis-era5-single-levels-monthly-means", request, str(TARGET))
    except Exception as exc:
        if TARGET.exists():
            TARGET.unlink()
        print(f"Download failed: {exc}")
        raise

    size_mb = TARGET.stat().st_size / (1024 * 1024)
    print(f"Completed: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
