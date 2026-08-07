from pathlib import Path
import socket
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm


# ==========================================================
# NMME May 2026 initialization
# NOAA CPC real-time anomaly directory
# Folder: 2026050800
# ==========================================================

HOST = "ftp.cpc.ncep.noaa.gov"

BASE_URLS = [
    "https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/2026050800",
    "http://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/2026050800",
]

OUT_DIR = Path("NMME_May2026")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    "NMME.prate.202605.ENSMEAN.anom.nc",
    "NMME.tmp2m.202605.ENSMEAN.anom.nc",
    "NMME.tmax.202605.ENSMEAN.anom.nc",
    "NMME.tmin.202605.ENSMEAN.anom.nc",
    "NMME.tmpsfc.202605.ENSMEAN.anom.nc",

    "CanESM5.prate.202605.ENSMEAN.anom.nc",
    "CFSv2.prate.202605.ENSMEAN.anom.nc",
    "GEM5.2_NEMO.prate.202605.ENSMEAN.anom.nc",
    "NASA_GEOS5v2.prate.202605.ENSMEAN.anom.nc",
    "NCAR_CCSM4.prate.202605.ENSMEAN.anom.nc",
    "NCAR_CESM1.prate.202605.ENSMEAN.anom.nc",
]


def check_dns(host: str) -> bool:
    print(f"Checking DNS resolution for: {host}")
    try:
        ip = socket.gethostbyname(host)
        print(f"DNS OK: {host} -> {ip}")
        return True
    except socket.gaierror as e:
        print("\nDNS resolution failed.")
        print(f"Host: {host}")
        print(f"Error: {e}")
        print("\nPossible fixes:")
        print("1. Check your internet connection.")
        print("2. Try opening the CPC URL in a browser.")
        print("3. Change DNS to 8.8.8.8 or 1.1.1.1.")
        print("4. Try a VPN or different network if your network blocks NOAA/CPC FTP domains.")
        print("5. If you are behind an institutional proxy, configure the proxy in Python.")
        return False


def create_session() -> requests.Session:
    session = requests.Session()

    retries = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )

    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def download_file(session: requests.Session, fname: str) -> bool:
    out_path = OUT_DIR / fname

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"Already exists, skipping: {out_path}")
        return True

    for base_url in BASE_URLS:
        url = f"{base_url}/{fname}"
        print(f"\nTrying: {url}")

        try:
            with session.get(url, stream=True, timeout=120) as response:
                if response.status_code == 404:
                    print(f"File not found at this URL: {url}")
                    continue

                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))

                tmp_path = out_path.with_suffix(out_path.suffix + ".part")

                with open(tmp_path, "wb") as f, tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=fname,
                ) as progress:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            progress.update(len(chunk))

                tmp_path.rename(out_path)
                print(f"Downloaded: {out_path}")
                return True

        except requests.exceptions.ConnectionError as e:
            print("Connection error.")
            print(e)
            time.sleep(3)

        except requests.exceptions.Timeout:
            print("Timeout. Retrying with next URL if available.")
            time.sleep(3)

        except requests.exceptions.HTTPError as e:
            print(f"HTTP error: {e}")
            time.sleep(3)

    print(f"FAILED: {fname}")
    return False


def main():
    dns_ok = check_dns(HOST)

    if not dns_ok:
        print("\nStopping before download because DNS failed.")
        print("Fix DNS/network first, then rerun this script.")
        return

    session = create_session()

    success = []
    failed = []

    for fname in FILES:
        ok = download_file(session, fname)
        if ok:
            success.append(fname)
        else:
            failed.append(fname)

    print("\n==============================")
    print("DOWNLOAD SUMMARY")
    print("==============================")
    print(f"Successful: {len(success)}")
    print(f"Failed:     {len(failed)}")

    if failed:
        print("\nFailed files:")
        for f in failed:
            print(f" - {f}")


if __name__ == "__main__":
    main()