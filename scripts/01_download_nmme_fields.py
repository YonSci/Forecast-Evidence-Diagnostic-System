"""
01_download_nmme_fields.py

Purpose
-------
Download and organize available CPC NMME real-time anomaly files for
May 2026 initialization.

Main source:
https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/2026050800/

This script:
1. Creates a clean NMME data folder.
2. Reads the CPC directory listing.
3. Downloads all available NetCDF files, or only selected files.
4. Saves an inventory CSV.
5. Creates a diagnostic note showing which dynamic fields still need
   another source such as ERA5 or NMME Phase-II archive.

Run from project root:
    python scripts\\01_download_nmme_fields.py
"""

from __future__ import annotations

import csv
import socket
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry


# ==========================================================
# PROJECT PATHS
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Make config import work when running from project root or scripts folder
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import NMME_DIR
except Exception:
    NMME_DIR = PROJECT_ROOT / "data" / "nmme"


# ==========================================================
# USER SETTINGS
# ==========================================================

INIT_YYYYMM = "202605"
INIT_FOLDER = "2026050800"

BASE_HOST = "ftp.cpc.ncep.noaa.gov"

BASE_URLS = {
    "ENSMEAN": f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/{INIT_FOLDER}",
    "CFSv2": f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/CFSv2/{INIT_FOLDER}",
    "CanESM5": f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/CanESM5/{INIT_FOLDER}",
    "GEM5.2_NEMO": f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/GEM5.2_NEMO/{INIT_FOLDER}",
    "NASA_GEOS5v2": f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/NASA_GEOS5v2/{INIT_FOLDER}",
    "NCAR_CCSM4": f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/NCAR_CCSM4/{INIT_FOLDER}",
    "NCAR_CESM1": f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/NCAR_CESM1/{INIT_FOLDER}",
}

# Download mode:
#   "core" = only the most important ENSMEAN diagnostic files
#   "all_ensmean" = all NetCDF files in ENSMEAN folder
#   "all_models_precip" = ENSMEAN core + model precipitation anomalies
#   "all_available" = all NetCDF files from all listed model folders
DOWNLOAD_MODE = "all_ensmean"

# Core files available in the CPC ENSMEAN May 2026 anomaly folder
CORE_ENSMEAN_FILES = [
    f"NMME.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmp2m.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmpsfc.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmax.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmin.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.z200.{INIT_YYYYMM}.ENSMEAN.anom.nc",
]

MODEL_PRECIP_FILES = [
    f"CanESM5.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"CFSv2.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"GEM5.2_NEMO.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NASA_GEOS5v2.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NCAR_CCSM4.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NCAR_CESM1.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
]

# Desired dynamic fields for the full diagnostic package.
# Some are not available in the simple CPC real-time anomaly ENSMEAN folder.
DESIRED_DYNAMIC_FIELDS = [
    "prate",
    "sst or tmpsfc",
    "u200",
    "v200",
    "u850",
    "v850",
    "q850",
    "z200",
    "z500 or hgt500",
    "omega500 or omega700",
    "velocity_potential_200",
    "divergence_200",
    "olr",
]


# ==========================================================
# OUTPUT PATHS
# ==========================================================

OUT_ROOT = NMME_DIR / "realtime_anom"
INVENTORY_DIR = NMME_DIR / "inventory"
INVENTORY_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# DATA STRUCTURES
# ==========================================================

@dataclass
class RemoteFile:
    model: str
    base_url: str
    filename: str

    @property
    def url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.filename}"

    @property
    def out_dir(self) -> Path:
        return OUT_ROOT / self.model / INIT_FOLDER

    @property
    def out_path(self) -> Path:
        return self.out_dir / self.filename


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")

        if href:
            self.links.append(href)


# ==========================================================
# UTILITY FUNCTIONS
# ==========================================================

def check_dns(host: str) -> bool:
    print(f"Checking DNS resolution for: {host}")

    try:
        ip = socket.gethostbyname(host)
        print(f"DNS OK: {host} -> {ip}")
        return True
    except socket.gaierror as exc:
        print("\nDNS resolution failed.")
        print(f"Host: {host}")
        print(f"Error: {exc}")
        print("\nTry:")
        print("  1. Check your internet connection.")
        print("  2. Run: ipconfig /flushdns")
        print("  3. Try DNS 8.8.8.8 or 1.1.1.1")
        print("  4. Try VPN or another network if NOAA/CPC is blocked.")
        return False


def create_session() -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 NMME-diagnostic-downloader/1.0"
        }
    )

    return session


def list_remote_nc_files(session: requests.Session, model: str, base_url: str) -> list[RemoteFile]:
    print(f"\nReading directory listing: {base_url}")

    try:
        response = session.get(base_url, timeout=90)
        response.raise_for_status()
    except Exception as exc:
        print(f"Could not read directory for {model}: {exc}")
        return []

    parser = LinkParser()
    parser.feed(response.text)

    nc_files = sorted(
        link for link in parser.links
        if link.endswith(".nc")
    )

    remote_files = [
        RemoteFile(model=model, base_url=base_url, filename=fname)
        for fname in nc_files
    ]

    print(f"Found {len(remote_files)} NetCDF files for {model}.")
    return remote_files


def download_file(session: requests.Session, remote_file: RemoteFile) -> bool:
    remote_file.out_dir.mkdir(parents=True, exist_ok=True)

    out_path = remote_file.out_path
    tmp_path = out_path.with_suffix(out_path.suffix + ".part")

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"Already exists, skipping: {out_path}")
        return True

    print(f"\nDownloading: {remote_file.url}")

    try:
        with session.get(remote_file.url, stream=True, timeout=180) as response:
            if response.status_code == 404:
                print(f"File not found: {remote_file.url}")
                return False

            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            with open(tmp_path, "wb") as f, tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=remote_file.filename,
            ) as progress:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        progress.update(len(chunk))

        tmp_path.replace(out_path)
        print(f"Saved: {out_path}")
        return True

    except Exception as exc:
        print(f"Download failed: {remote_file.filename}")
        print(exc)

        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

        time.sleep(2)
        return False


def write_inventory(files: Iterable[RemoteFile], inventory_csv: Path) -> None:
    inventory_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(inventory_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "model",
                "filename",
                "url",
                "local_path",
                "exists",
                "size_mb",
            ]
        )

        for rf in files:
            exists = rf.out_path.exists()
            size_mb = rf.out_path.stat().st_size / (1024 * 1024) if exists else 0.0

            writer.writerow(
                [
                    rf.model,
                    rf.filename,
                    rf.url,
                    str(rf.out_path),
                    exists,
                    round(size_mb, 3),
                ]
            )

    print(f"\nInventory saved: {inventory_csv}")


def choose_files_for_mode(session: requests.Session) -> list[RemoteFile]:
    if DOWNLOAD_MODE == "core":
        return [
            RemoteFile(
                model="ENSMEAN",
                base_url=BASE_URLS["ENSMEAN"],
                filename=fname,
            )
            for fname in CORE_ENSMEAN_FILES
        ]

    if DOWNLOAD_MODE == "all_ensmean":
        return list_remote_nc_files(
            session=session,
            model="ENSMEAN",
            base_url=BASE_URLS["ENSMEAN"],
        )

    if DOWNLOAD_MODE == "all_models_precip":
        files: list[RemoteFile] = []

        files.extend(
            [
                RemoteFile(
                    model="ENSMEAN",
                    base_url=BASE_URLS["ENSMEAN"],
                    filename=fname,
                )
                for fname in CORE_ENSMEAN_FILES
            ]
        )

        files.extend(
            [
                RemoteFile(
                    model="ENSMEAN",
                    base_url=BASE_URLS["ENSMEAN"],
                    filename=fname,
                )
                for fname in MODEL_PRECIP_FILES
            ]
        )

        return files

    if DOWNLOAD_MODE == "all_available":
        all_files: list[RemoteFile] = []

        for model, base_url in BASE_URLS.items():
            all_files.extend(
                list_remote_nc_files(
                    session=session,
                    model=model,
                    base_url=base_url,
                )
            )

        return all_files

    raise ValueError(
        f"Unknown DOWNLOAD_MODE: {DOWNLOAD_MODE}. "
        "Use one of: core, all_ensmean, all_models_precip, all_available"
    )


def create_dynamic_fields_note(downloaded_files: list[RemoteFile]) -> None:
    available_names = [rf.filename.lower() for rf in downloaded_files]

    available_summary = []

    for field in DESIRED_DYNAMIC_FIELDS:
        field_lower = field.lower()

        if "sst" in field_lower:
            found = any("tmpsfc" in name for name in available_names)
        elif "z200" in field_lower:
            found = any("z200" in name for name in available_names)
        elif "prate" in field_lower:
            found = any("prate" in name for name in available_names)
        elif "tmp" in field_lower:
            found = any("tmp" in name for name in available_names)
        else:
            key = field_lower.split()[0].replace("or", "").strip()
            found = any(key in name for name in available_names)

        available_summary.append((field, found))

    note_path = INVENTORY_DIR / f"dynamic_fields_status_{INIT_YYYYMM}.txt"

    with open(note_path, "w", encoding="utf-8") as f:
        f.write("NMME dynamic diagnostic field status\n")
        f.write("====================================\n\n")
        f.write(f"Initialization: {INIT_YYYYMM}\n")
        f.write(f"CPC folder: {BASE_URLS['ENSMEAN']}\n")
        f.write(f"Download mode: {DOWNLOAD_MODE}\n\n")

        f.write("Desired diagnostic fields:\n")
        for field, found in available_summary:
            status = "AVAILABLE in downloaded CPC realtime_anom files" if found else "NOT FOUND in simple CPC realtime_anom folder"
            f.write(f" - {field}: {status}\n")

        f.write("\nImportant note:\n")
        f.write(
            "The simple CPC realtime_anom/ENSMEAN folder for May 2026 contains "
            "useful anomaly files such as precipitation, temperature, surface temperature, "
            "and z200. It may not contain all dynamic fields needed for full physical "
            "diagnosis, such as u200, v200, u850, v850, q850, omega, OLR, divergence, "
            "or velocity potential. Those fields should be obtained from NMME Phase-II, "
            "IRI Data Library, ERA5, NCEP/NCAR Reanalysis, or NOAA OLR datasets.\n"
        )

    print(f"Dynamic field status note saved: {note_path}")


# ==========================================================
# MAIN
# ==========================================================

def main() -> None:
    print("\n==================================================")
    print("NMME May 2026 field downloader")
    print("==================================================")
    print(f"Project root:   {PROJECT_ROOT}")
    print(f"NMME data dir:  {NMME_DIR}")
    print(f"Download mode:  {DOWNLOAD_MODE}")
    print(f"Init folder:    {INIT_FOLDER}")

    dns_ok = check_dns(BASE_HOST)

    if not dns_ok:
        print("\nStopping because DNS failed.")
        return

    session = create_session()

    files_to_download = choose_files_for_mode(session)

    if not files_to_download:
        print("\nNo files found for download.")
        return

    print("\nFiles selected for download:")
    for rf in files_to_download:
        print(f" - [{rf.model}] {rf.filename}")

    success: list[RemoteFile] = []
    failed: list[RemoteFile] = []

    for rf in files_to_download:
        ok = download_file(session, rf)

        if ok:
            success.append(rf)
        else:
            failed.append(rf)

    inventory_csv = INVENTORY_DIR / f"nmme_realtime_anom_inventory_{INIT_YYYYMM}_{DOWNLOAD_MODE}.csv"
    write_inventory(files_to_download, inventory_csv)

    create_dynamic_fields_note(success)

    print("\n==================================================")
    print("DOWNLOAD SUMMARY")
    print("==================================================")
    print(f"Selected files: {len(files_to_download)}")
    print(f"Successful:     {len(success)}")
    print(f"Failed:         {len(failed)}")

    if failed:
        print("\nFailed files:")
        for rf in failed:
            print(f" - [{rf.model}] {rf.filename}")

    print("\nOutput folders:")
    print(f" - Data:      {OUT_ROOT}")
    print(f" - Inventory: {INVENTORY_DIR}")


if __name__ == "__main__":
    main()