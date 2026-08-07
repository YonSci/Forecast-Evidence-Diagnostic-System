from pathlib import Path
import requests
from tqdm import tqdm

# ==========================================================
# NMME May 2026 initialization
# NOAA CPC real-time anomaly directory
# ==========================================================

BASE_URL = "https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/2026050800"

OUT_DIR = Path("NMME_May2026")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Main NMME ensemble-mean anomaly files
files = [
    "NMME.prate.202605.ENSMEAN.anom.nc",   # precipitation anomaly
    "NMME.tmp2m.202605.ENSMEAN.anom.nc",   # 2m temperature anomaly
    "NMME.tmax.202605.ENSMEAN.anom.nc",    # maximum temperature anomaly
    "NMME.tmin.202605.ENSMEAN.anom.nc",    # minimum temperature anomaly
    "NMME.tmpsfc.202605.ENSMEAN.anom.nc",  # surface temperature anomaly
]


def download_file(url, out_path):
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with open(out_path, "wb") as f, tqdm(
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=out_path.name,
    ) as progress:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                progress.update(len(chunk))


for fname in files:
    url = f"{BASE_URL}/{fname}"
    out_path = OUT_DIR / fname

    if out_path.exists():
        print(f"Already exists, skipping: {out_path}")
        continue

    print(f"Downloading: {url}")
    download_file(url, out_path)

print("Download completed.")