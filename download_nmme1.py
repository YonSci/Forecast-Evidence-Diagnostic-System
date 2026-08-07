#!/usr/bin/env python3
"""
download_nmme.py
================
Download NMME precipitation forecast data from NOAA CPC and IRI Data Library.
Target: Ensemble mean forecasts initialized May 2026 for Jun-Sep 2026.

Usage:
    python download_nmme.py [--source {iri,cpc,cds}] [--output-dir DIR]

Dependencies:
    pip install requests netCDF4 xarray numpy
"""

import os
import sys
import argparse
import requests
import warnings
from urllib.parse import urlencode
from datetime import datetime

warnings.filterwarnings('ignore')


# =============================================================================
# CONFIGURATION
# =============================================================================

# Domain settings (matching your uploaded maps)
LON_MIN, LON_MAX = 30, 150
LAT_MIN, LAT_MAX = -35, 40

# Target months and their lead times from May initialization
TARGET_MONTHS = {
    'Jun': {'lead': 1.5, 'days': 30},
    'Jul': {'lead': 2.5, 'days': 31},
    'Aug': {'lead': 3.5, 'days': 31},
    'Sep': {'lead': 4.5, 'days': 30},
}

# IRI Data Library base URLs
IRI_BASE = "https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME"

# NMME models available at IRI
NMME_MODELS = {
    'ensemble_mean': '.NMME/.ensembleMean/.MONTHLY/.prec',
    'cfsv2': '.NCEP/.CFSv2/.MONTHLY/.prec',
    'cancm4i': '.CMCC/.CanCM4i/.MONTHLY/.prec',
    'gem5': '.CMC/.GEM5/.MONTHLY/.prec',
    'geos5': '.NASA/.GEOS5/.MONTHLY/.prec',
    'gfdl': '.GFDL/.GFDL/.MONTHLY/.prec',
    'ccsm4': '.NCAR/.CCSM4/.MONTHLY/.prec',
}

# NOAA CPC FTP paths
CPC_FTP_BASE = "ftp://ftp.cpc.ncep.noaa.gov/NMME"
CPC_REALTIME = f"{CPC_FTP_BASE}/realtime"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def ensure_dir(path):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)
    return path


def check_file_exists(filepath, min_size_bytes=1000):
    """Check if file exists and is non-empty."""
    return os.path.exists(filepath) and os.path.getsize(filepath) > min_size_bytes


def log(msg, level="INFO"):
    """Print formatted log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


# =============================================================================
# IRI DATA LIBRARY DOWNLOAD
# =============================================================================

def build_iri_url(model_key='ensemble_mean', init_year=2026, init_month=5,
                  lon_range=(30, 150), lat_range=(-35, 40)):
    """
    Build IRI Data Library URL for NMME data download.
    
    IRI uses a specific URL format with constraints embedded in the path.
    """
    model_path = NMME_MODELS.get(model_key, NMME_MODELS['ensemble_mean'])
    
    # Build the constraint string
    # Format: (T)(L)(X)(Y)/
    constraints = []
    
    # Time constraint: initialization month
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    init_month_name = month_names[init_month]
    constraints.append(f"T/%28{init_month_name}%20{init_year}%29")
    
    # Lead time constraint: all leads 1.5 to 4.5
    constraints.append("L/1.5/4.5")
    
    # Spatial constraints
    constraints.append(f"X/%28{lon_range[0]}%29%28{lon_range[1]}%29RANGEEDGES")
    constraints.append(f"Y/%28{lat_range[0]}%29%28{lat_range[1]}%29RANGEEDGES")
    
    # Data format
    constraints.append("data.nc")
    
    url = f"{IRI_BASE}{model_path}/{'/'.join(constraints)}"
    return url


def download_iri_data(output_dir='nmme_data', model='ensemble_mean',
                      init_year=2026, init_month=5, timeout=300):
    """
    Download NMME data from IRI Data Library.
    
    Note: IRI sometimes requires form submission. This attempts direct URL access.
    If it fails, manual download instructions are provided.
    """
    ensure_dir(output_dir)
    
    output_file = os.path.join(output_dir, f"nmme_{model}_May{init_year}.nc")
    
    if check_file_exists(output_file):
        log(f"File already exists: {output_file}")
        return output_file
    
    url = build_iri_url(model, init_year, init_month)
    log(f"Attempting download from IRI...")
    log(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Check if we got actual NetCDF data or an HTML page
        content_type = response.headers.get('content-type', '')
        
        if 'text/html' in content_type:
            log("Received HTML page instead of NetCDF. IRI may require manual download.", "WARNING")
            return None
        
        # Save file
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(output_file)
        log(f"Downloaded: {output_file} ({file_size / 1024 / 1024:.2f} MB)")
        return output_file
        
    except requests.exceptions.RequestException as e:
        log(f"Download failed: {e}", "ERROR")
        return None


def download_iri_interactive_guide():
    """
    Print step-by-step instructions for manual IRI download.
    This is the most reliable method.
    """
    guide = """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║         MANUAL DOWNLOAD FROM IRI DATA LIBRARY                        ║
    ╚══════════════════════════════════════════════════════════════════════╝
    
    Step 1: Open browser and go to:
        https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/
    
    Step 2: Navigate to ensemble mean:
        Click: .NMME → .ensembleMean → .MONTHLY → .prec
    
    Step 3: Set spatial constraints (left panel):
        X: 30 to 150
        Y: -35 to 40
    
    Step 4: Set temporal constraints:
        T (Initialization Time): May 2026
        L (Lead Time): 1.5, 2.5, 3.5, 4.5
           (or click each lead value while holding Ctrl/Cmd)
    
    Step 5: Download data:
        Click "Data Files" tab (top right)
        Click "netCDF" format
        Save file as: nmme_data/nmme_ensemble_mean_May2026.nc
    
    Alternative direct URL (try in browser):
        https://iridl.ldeo.columbia.edu/SOURCES/.Models/.NMME/.NMME/.ensembleMean/.MONTHLY/.prec/T/%28May%202026%29/L/1.5/4.5/X/%2830%29%28150%29RANGEEDGES/Y/%28-35%29%2840%29RANGEEDGES/data.nc
    
    ════════════════════════════════════════════════════════════════════════
    """
    print(guide)


# =============================================================================
# NOAA CPC DOWNLOAD
# =============================================================================

def download_cpc_data(output_dir='nmme_data', init_year=2026, init_month=5):
    """
    Download NMME data from NOAA CPC.
    
    CPC provides data via FTP and HTTP. Real-time forecasts are in:
    ftp://ftp.cpc.ncep.noaa.gov/NMME/realtime/YYYYMM/
    """
    ensure_dir(output_dir)
    
    init_ym = f"{init_year}{init_month:02d}"
    
    # CPC file naming patterns (may vary)
    cpc_files = {
        'ensemble_mean': f"nmme_ensmean_prec_{init_ym}.nc",
        'cfsv2': f"nmme_cfsv2_prec_{init_ym}.nc",
    }
    
    log(f"NOAA CPC realtime path: {CPC_REALTIME}/{init_ym}/")
    
    # Try HTTP first (more firewall-friendly)
    http_base = "https://ftp.cpc.ncep.noaa.gov/NMME/realtime"
    
    downloaded = []
    
    for data_type, filename in cpc_files.items():
        output_file = os.path.join(output_dir, filename)
        
        if check_file_exists(output_file):
            log(f"File exists: {filename}")
            downloaded.append(output_file)
            continue
        
        # Try HTTP
        url = f"{http_base}/{init_ym}/{filename}"
        log(f"Trying: {url}")
        
        try:
            response = requests.get(url, timeout=60, stream=True)
            if response.status_code == 200:
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                log(f"Downloaded: {filename}")
                downloaded.append(output_file)
            else:
                log(f"HTTP {response.status_code} for {filename}", "WARNING")
        except Exception as e:
            log(f"Failed {filename}: {e}", "WARNING")
    
    if not downloaded:
        log("No files downloaded from CPC. Try FTP or manual download.", "WARNING")
        print(f"""
        Manual CPC FTP download:
        ftp {CPC_FTP_BASE}
        cd realtime/{init_ym}
        get nmme_ensmean_prec_{init_ym}.nc
        """)
    
    return downloaded


# =============================================================================
# CDS (COPERNICUS) DOWNLOAD
# =============================================================================

def download_cds_data(output_dir='nmme_data', init_year=2026, init_month=5):
    """
    Download seasonal forecast data from Copernicus CDS.
    Requires CDS API key (~/.cdsapirc).
    """
    try:
        import cdsapi
    except ImportError:
        log("cdsapi not installed. Run: pip install cdsapi", "ERROR")
        return []
    
    ensure_dir(output_dir)
    
    output_file = os.path.join(output_dir, f"cds_seasonal_May{init_year}.grib")
    
    if check_file_exists(output_file):
        log(f"File exists: {output_file}")
        return [output_file]
    
    log("Connecting to Copernicus CDS...")
    
    try:
        c = cdsapi.Client()
        
        c.retrieve(
            'seasonal-monthly-single-levels',
            {
                'originating_centre': 'ncep',
                'system': '2',  # CFSv2
                'variable': 'total_precipitation',
                'product_type': 'monthly_mean',
                'year': str(init_year),
                'month': f"{init_month:02d}",
                'leadtime_month': ['1', '2', '3', '4'],
                'area': [LAT_MAX, LON_MIN, LAT_MIN, LON_MAX],  # N, W, S, E
                'format': 'grib',
            },
            output_file
        )
        
        log(f"Downloaded: {output_file}")
        return [output_file]
        
    except Exception as e:
        log(f"CDS download failed: {e}", "ERROR")
        return []


# =============================================================================
# CLI & MAIN
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Download NMME precipitation forecast data'
    )
    parser.add_argument(
        '--source', '-s',
        choices=['iri', 'cpc', 'cds', 'all'],
        default='all',
        help='Data source to use (default: all)'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default='nmme_data',
        help='Output directory for downloaded files (default: nmme_data)'
    )
    parser.add_argument(
        '--model', '-m',
        default='ensemble_mean',
        choices=list(NMME_MODELS.keys()),
        help='NMME model to download (default: ensemble_mean)'
    )
    parser.add_argument(
        '--init-year', '-y',
        type=int,
        default=2026,
        help='Initialization year (default: 2026)'
    )
    parser.add_argument(
        '--init-month', '-M',
        type=int,
        default=5,
        help='Initialization month, 1-12 (default: 5 = May)'
    )
    parser.add_argument(
        '--guide', '-g',
        action='store_true',
        help='Show manual download instructions and exit'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    if args.guide:
        download_iri_interactive_guide()
        return 0
    
    log("=" * 60)
    log("NMME DATA DOWNLOAD")
    log(f"Initialization: {args.init_year}-{args.init_month:02d}")
    log(f"Target months: Jun-Sep {args.init_year}")
    log(f"Domain: {LON_MIN}-{LON_MAX}°E, {LAT_MIN}-{LAT_MAX}°N")
    log("=" * 60)
    
    downloaded_files = []
    
    # Try IRI
    if args.source in ['iri', 'all']:
        log("\n--- Attempting IRI Data Library ---")
        iri_file = download_iri_data(
            output_dir=args.output_dir,
            model=args.model,
            init_year=args.init_year,
            init_month=args.init_month
        )
        if iri_file:
            downloaded_files.append(iri_file)
        else:
            download_iri_interactive_guide()
    
    # Try NOAA CPC
    if args.source in ['cpc', 'all']:
        log("\n--- Attempting NOAA CPC ---")
        cpc_files = download_cpc_data(
            output_dir=args.output_dir,
            init_year=args.init_year,
            init_month=args.init_month
        )
        downloaded_files.extend(cpc_files)
    
    # Try CDS
    if args.source in ['cds', 'all']:
        log("\n--- Attempting Copernicus CDS ---")
        cds_files = download_cds_data(
            output_dir=args.output_dir,
            init_year=args.init_year,
            init_month=args.init_month
        )
        downloaded_files.extend(cds_files)
    
    # Summary
    log("\n" + "=" * 60)
    log("DOWNLOAD SUMMARY")
    log("=" * 60)
    
    if downloaded_files:
        log(f"Successfully downloaded {len(downloaded_files)} file(s):")
        for f in downloaded_files:
            size = os.path.getsize(f) / 1024 / 1024
            log(f"  - {f} ({size:.2f} MB)")
    else:
        log("No files downloaded automatically.", "WARNING")
        log("Please use manual download instructions above.", "WARNING")
        return 1
    
    log("\nNext step: Run process_and_plot.py to create maps")
    return 0


if __name__ == "__main__":
    sys.exit(main())