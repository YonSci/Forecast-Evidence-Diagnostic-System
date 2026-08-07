"""
17_download_nmme_july_init.py

Purpose
-------
Download CPC NMME real-time ENSMEAN anomaly files for the July 2026
initialization (2026070800), as a third initialization cycle alongside
May 2026 (2026050800) and June 2026 (2026060800).

Main source:
https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/2026070800/

Target months
-------------
Following the same convention already verified for May-init (first
target = June) and June-init (first target = July), the July 2026
init's first available forecast target is AUGUST 2026. July itself is
skipped. Within this project's Kiremt/JJAS scope, that leaves only
August and September 2026 as monthly targets.

This script:
1. Downloads the core ENSMEAN files (prate, tmp2m, tmpsfc, tmax, tmin, z200)
   for the July 2026 initialization.
2. Saves them into data/nmme/realtime_anom/, namespaced under the
   2026070800 init folder (no collision with May/June cycles).
3. Saves an inventory CSV namespaced by init month.

Run from project root:
    python scripts\\17_download_nmme_july_init.py
"""

from __future__ import annotations

import csv
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.project_config import NMME_DIR
except Exception:
    NMME_DIR = PROJECT_ROOT / "data" / "nmme"


INIT_YYYYMM = "202607"
INIT_FOLDER = "2026070800"

BASE_HOST = "ftp.cpc.ncep.noaa.gov"
ENSMEAN_BASE_URL = f"https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/{INIT_FOLDER}"

CORE_ENSMEAN_FILES = [
    f"NMME.prate.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmp2m.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmpsfc.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmax.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.tmin.{INIT_YYYYMM}.ENSMEAN.anom.nc",
    f"NMME.z200.{INIT_YYYYMM}.ENSMEAN.anom.nc",
]

OUT_ROOT = NMME_DIR / "realtime_anom"
INVENTORY_DIR = NMME_DIR / "inventory"
INVENTORY_DIR.mkdir(parents=True, exist_ok=True)


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


def check_dns(host: str) -> bool:
    print(f"Checking DNS resolution for: {host}")
    try:
        ip = socket.gethostbyname(host)
        print(f"DNS OK: {host} -> {ip}")
        return True
    except socket.gaierror as exc:
        print(f"DNS resolution failed: {exc}")
        return False


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5, connect=5, read=5, backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0 NMME-diagnostic-downloader/1.0"})
    return session


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
                total=total_size, unit="B", unit_scale=True, unit_divisor=1024,
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
        print(f"Download failed: {remote_file.filename}\n{exc}")
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
        writer.writerow(["model", "filename", "url", "local_path", "exists", "size_mb"])
        for rf in files:
            exists = rf.out_path.exists()
            size_mb = rf.out_path.stat().st_size / (1024 * 1024) if exists else 0.0
            writer.writerow([rf.model, rf.filename, rf.url, str(rf.out_path), exists, round(size_mb, 3)])
    print(f"\nInventory saved: {inventory_csv}")


def main() -> None:
    print("==================================================")
    print("NMME July 2026 init field downloader")
    print("==================================================")
    print(f"Init folder: {INIT_FOLDER}")
    print(
        "\nNote: this cycle's first available forecast target is AUGUST 2026 "
        "(July itself is skipped). Within Kiremt/JJAS scope this leaves only "
        "August and September 2026."
    )

    if not check_dns(BASE_HOST):
        print("\nStopping because DNS failed.")
        return

    session = create_session()
    files_to_download = [
        RemoteFile(model="ENSMEAN", base_url=ENSMEAN_BASE_URL, filename=fname)
        for fname in CORE_ENSMEAN_FILES
    ]

    print("\nFiles selected for download:")
    for rf in files_to_download:
        print(f" - [{rf.model}] {rf.filename}")

    success, failed = [], []
    for rf in files_to_download:
        (success if download_file(session, rf) else failed).append(rf)

    inventory_csv = INVENTORY_DIR / f"nmme_realtime_anom_inventory_{INIT_YYYYMM}_core.csv"
    write_inventory(files_to_download, inventory_csv)

    print("\n==================================================")
    print("DOWNLOAD SUMMARY")
    print("==================================================")
    print(f"Successful: {len(success)}  Failed: {len(failed)}")
    if failed:
        for rf in failed:
            print(f" - FAILED [{rf.model}] {rf.filename}")


if __name__ == "__main__":
    main()
