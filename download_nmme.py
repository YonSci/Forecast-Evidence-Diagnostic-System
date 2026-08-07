"""
download_nmme.py

Downloads NMME ensemble-mean precipitation anomaly files
for a given initialization date from NOAA CPC.

Output:
    ./nmme_data/<MODEL>.prate.<YYYYMM>.ENSMEAN.anom.nc
    for each of the 6 operational NMME v2 models.

Usage:
    python download_nmme.py
    python download_nmme.py --init 2026040800 --out ./my_data
    python download_nmme.py --models CFSv2 CanESM5
"""

import argparse
import os
import sys
import urllib.request

# Default: 6 operational NMME v2 models
DEFAULT_MODELS = [
    "CanESM5",
    "CFSv2",
    "NASA_GEOS5v2",
    "NCAR_CCSM4",
    "NCAR_CESM1",
    "GEM5.2_NEMO",
]

# Default init: 00z May 8 2026
DEFAULT_INIT = "2026050800"

BASE_URL = "https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/{init}"


def download_one(model: str, init: str, out_dir: str, force: bool = False) -> str:
    """Download one model's prate anomaly file. Returns local path."""
    # Extract YYYYMM from init (e.g. 2026050800 -> 202605)
    yyyymm = init[:6]
    fn   = f"{model}.prate.{yyyymm}.ENSMEAN.anom.nc"
    path = os.path.join(out_dir, fn)

    if not force and os.path.exists(path) and os.path.getsize(path) > 1_000_000:
        print(f"  cached: {fn}")
        return path

    url = f"{BASE_URL.format(init=init)}/{fn}"
    print(f"  downloading {url}")
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        if os.path.exists(path):
            os.remove(path)
        raise RuntimeError(f"Failed to download {url}: {e}") from e

    size_mb = os.path.getsize(path) / 1e6
    print(f"    -> {size_mb:.1f} MB")
    return path


def main():
    p = argparse.ArgumentParser(
        description="Download NMME ensemble-mean precipitation anomaly files."
    )
    p.add_argument(
        "--init", default=DEFAULT_INIT,
        help="Initialization tag, e.g. 2026050800 for 00z May 8 2026 "
             "(default: %(default)s)"
    )
    p.add_argument(
        "--models", nargs="+", default=DEFAULT_MODELS,
        help="Space-separated list of models "
             "(default: %(default)s)"
    )
    p.add_argument(
        "--out", default="./nmme_data",
        help="Output directory (default: ./nmme_data)"
    )
    p.add_argument(
        "--force", action="store_true",
        help="Re-download even if file already exists"
    )
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print(f"=== NMME anomaly download ===")
    print(f"  init   : {args.init}")
    print(f"  models : {', '.join(args.models)}")
    print(f"  out    : {args.out}")
    print()

    ok, failed = [], []
    for m in args.models:
        try:
            download_one(m, args.init, args.out, force=args.force)
            ok.append(m)
        except Exception as e:
            print(f"    ERROR: {e}")
            failed.append(m)

    print()
    print(f"Downloaded: {len(ok)}/{len(args.models)}")
    if failed:
        print(f"Failed   : {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
