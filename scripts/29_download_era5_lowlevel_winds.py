"""
29_download_era5_lowlevel_winds.py

Purpose
-------
Download ERA5 monthly-mean u/v wind on every pressure level at or below
600 hPa, for all twelve calendar months, 1991-2020.

Why a separate download instead of extending script 02: script 02 grabs
seven variables on four levels (200/500/700/850) for JJAS only, which is
the right shape for the TEJ diagnostics but cannot resolve a low-level
jet. The Somali jet core sits somewhere between roughly 950 and 700 hPa
and migrates in both height and position through the season, so locating
it needs the full sub-600-hPa stack rather than a single 850 hPa slice.
All twelve months are downloaded (not just JJAS) so the page can show the
jet's full seasonal cycle -- the monsoon low-level jet is absent, and the
cross-equatorial flow reversed, in boreal winter, which is what makes the
summer core location meaningful rather than arbitrary.

Only u and v are requested. Everything else the low-level-jet diagnostics
need is derived from those two fields.

Downloads are chunked one file per year and skip files that already
exist, so an interrupted run resumes by simply being re-run rather than
restarting a ~5 GB transfer.

Run from project root:
    python scripts\\29_download_era5_lowlevel_winds.py
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from datetime import datetime

import cdsapi


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

RUN_MODE = "full"   # options: "test", "full"

CLIM_START_YEAR = 1991
CLIM_END_YEAR = 2020

ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]

TEST_YEARS = ["2020"]
TEST_MONTHS = ["07"]

FULL_YEARS = [str(y) for y in range(CLIM_START_YEAR, CLIM_END_YEAR + 1)]
FULL_MONTHS = ALL_MONTHS

# Every ERA5 pressure level at or below 600 hPa. "Below 600 hPa" is meant
# in height, so these are the levels with pressure >= 600.
PRESSURE_LEVELS = [
    "600", "650", "700", "750", "775", "800", "825",
    "850", "875", "900", "925", "950", "975", "1000",
]

VARIABLES = ["u_component_of_wind", "v_component_of_wind"]

# CDS area format: [North, West, South, East].
#
# Covers scripts/27's LARGE_SCALE_BOX (20W-100E, 20S-40N) with ~2 degrees
# of padding on each side, so centered finite differences and any edge
# smoothing stay valid right out to the rendered domain boundary. Spans
# the whole Somali jet system: Mascarene High source region in the
# southern Indian Ocean, the cross-equatorial East African coastal
# branch, the Turkana channel, and the Arabian Sea exit into India.
AREA = [42, -22, -22, 102]

MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 60


# ==========================================================
# OUTPUT FOLDERS
# ==========================================================

LOWLEVEL_DIR = ERA5_DIR / "monthly" / "lowlevel_winds"
ERA5_INVENTORY_DIR = ERA5_DIR / "inventory"

LOWLEVEL_DIR.mkdir(parents=True, exist_ok=True)
ERA5_INVENTORY_DIR.mkdir(parents=True, exist_ok=True)


def get_years_months() -> tuple[list[str], list[str]]:
    if RUN_MODE.lower() == "test":
        return TEST_YEARS, TEST_MONTHS
    if RUN_MODE.lower() == "full":
        return FULL_YEARS, FULL_MONTHS
    raise ValueError("RUN_MODE must be either 'test' or 'full'.")


def write_request_summary(
    out_csv: Path,
    target_file: Path,
    request: dict,
    status: str,
    message: str,
) -> None:
    file_exists = target_file.exists()
    size_mb = target_file.stat().st_size / (1024 * 1024) if file_exists else 0.0
    write_header = not out_csv.exists()

    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(
                [
                    "timestamp", "target_file", "status", "message", "exists",
                    "size_mb", "run_mode", "years", "months", "area",
                    "variables", "pressure_levels",
                ]
            )
        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
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
                ",".join(request.get("pressure_level", [])),
            ]
        )


def build_request(year: str, months: list[str]) -> dict:
    return {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": VARIABLES,
        "pressure_level": PRESSURE_LEVELS,
        "year": [year],
        "month": months,
        "time": ["00:00"],
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def retrieve_year(
    client: cdsapi.Client,
    year: str,
    months: list[str],
    inventory_csv: Path,
) -> str:
    target_file = LOWLEVEL_DIR / f"era5_lowlevel_uv_{year}.nc"
    request = build_request(year, months)

    if target_file.exists() and target_file.stat().st_size > 0:
        print(f"Already exists, skipping: {target_file.name}")
        write_request_summary(
            inventory_csv, target_file, request,
            "skipped_existing", "File already exists.",
        )
        return "skipped"

    dataset = "reanalysis-era5-pressure-levels-monthly-means"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\nDownloading {year} (attempt {attempt}/{MAX_ATTEMPTS}) -> {target_file.name}")
        try:
            client.retrieve(dataset, request, str(target_file))
        except Exception as exc:
            print(f"Attempt {attempt} failed for {year}: {exc}")
            # A failed retrieve can leave a truncated file behind, which the
            # skip-if-exists check above would later mistake for a complete
            # download.
            if target_file.exists():
                target_file.unlink()
            if attempt == MAX_ATTEMPTS:
                write_request_summary(inventory_csv, target_file, request, "failed", str(exc))
                return "failed"
            time.sleep(RETRY_SLEEP_SECONDS)
            continue

        size_mb = target_file.stat().st_size / (1024 * 1024)
        print(f"Completed {year}: {size_mb:.1f} MB")
        write_request_summary(inventory_csv, target_file, request, "success", "Download completed.")
        return "success"

    return "failed"


def main() -> None:
    print("==================================================")
    print("ERA5 low-level (<= 600 hPa) u/v monthly downloader")
    print("==================================================")

    years, months = get_years_months()

    print(f"ERA5 dir:  {ERA5_DIR}")
    print(f"Run mode:  {RUN_MODE}")
    print(f"Years:     {years[0]} to {years[-1]} ({len(years)} files)")
    print(f"Months:    {', '.join(months)}")
    print(f"Levels:    {', '.join(PRESSURE_LEVELS)}")
    print(f"Area:      N{AREA[0]} W{AREA[1]} S{AREA[2]} E{AREA[3]}")

    inventory_csv = ERA5_INVENTORY_DIR / f"era5_lowlevel_download_inventory_{RUN_MODE}.csv"
    client = cdsapi.Client()

    counts = {"success": 0, "skipped": 0, "failed": 0}
    failed_years = []

    for i, year in enumerate(years, start=1):
        print(f"\n--- [{i}/{len(years)}] {year} ---")
        status = retrieve_year(client, year, months, inventory_csv)
        counts[status] += 1
        if status == "failed":
            failed_years.append(year)

    print("\n==================================================")
    print("ERA5 LOW-LEVEL WIND DOWNLOAD FINISHED")
    print("==================================================")
    print(f"Downloaded: {counts['success']}   Skipped: {counts['skipped']}   Failed: {counts['failed']}")
    print(f"Output dir: {LOWLEVEL_DIR}")
    print(f"Inventory:  {inventory_csv}")

    if failed_years:
        print(f"\nFailed years: {', '.join(failed_years)}")
        print("Re-run this script to retry only those years; completed files are skipped.")


if __name__ == "__main__":
    main()
