"""
Static configuration and metadata for the Forecast Evidence and Diagnostic
System API. Mirrors the REGION_META / INIT_META / VARIABLE_META / DOMAINS
definitions already validated in the project's scripts (04, 05, 15, 19, 21)
and in the earlier HTML-artifact build of this dashboard.
"""
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
STATIC_DATA = APP_ROOT / "static_data"
TABLES_DIR = STATIC_DATA / "tables"
OVERLAYS_DIR = STATIC_DATA / "overlays"
SST_OVERLAYS_DIR = STATIC_DATA / "sst_overlays"
GALLERY_DIR = STATIC_DATA / "gallery"

# Same four regions used throughout scripts 04/15/19/21 and the dashboard's
# region selector.
REGIONS: dict[str, dict] = {
    "ethiopia": {"label": "Ethiopia", "box": [32, 48, 3, 15]},
    "greater_horn": {"label": "Greater Horn of Africa", "box": [20, 55, -15, 25]},
    "africa": {"label": "Africa", "box": [-20, 52, -35, 38]},
    "global": {"label": "Global", "box": [-180, 180, -90, 90]},
}

VARIABLES: dict[str, str] = {
    "prate": "Rainfall",
    "tmpsfc": "Surface Temperature",
}

PERIOD_LABELS: dict[str, str] = {
    "Jun": "June 2026",
    "Jul": "July 2026",
    "Aug": "August 2026",
    "Sep": "September 2026",
    "JJA": "June-Aug 2026",
    "JAS": "Jul-Sep 2026",
    "AS": "Aug-Sep 2026",
    "JJAS": "June-Sep 2026",
}

# Each initialization cycle only forecasts full calendar months after the
# (partially elapsed) init month itself -- verified empirically against
# each cycle's raw target-month coordinate in scripts 13/17.
INITIALIZATIONS: dict[str, dict] = {
    "2026-05-08": {
        "label": "May 2026 (2026-05-08 00Z)",
        "short_label": "May 2026 init",
        "csv_key": "may",
        "periods": ["Jun", "Jul", "Aug", "Sep", "JJA", "JAS", "JJAS"],
        "note": "Backs every other dashboard section (Atmospheric, Oceanic, Integrated Evidence Matrix all use this cycle).",
    },
    "2026-06-08": {
        "label": "June 2026 (2026-06-08 00Z)",
        "short_label": "June 2026 init",
        "csv_key": "june",
        "periods": ["Jul", "Aug", "Sep", "JAS"],
        "note": "Rainfall and surface-temperature anomaly only. June itself is skipped because it was already partially elapsed at initialization, so June, JJA, and JJAS aren't available from this cycle.",
    },
    "2026-07-08": {
        "label": "July 2026 (2026-07-08 00Z) - most recent",
        "short_label": "July 2026 init",
        "csv_key": "july",
        "periods": ["Aug", "Sep", "AS"],
        "note": "Rainfall and surface-temperature anomaly only, narrower still: July itself is skipped the same way June was, leaving only August, September, and the two-month AS (Aug+Sep) season.",
    },
}

DOMAIN_REFERENCE: dict[str, list[float]] = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "africa": [-20, 52, -35, 38],
    "global": [-180, 180, -90, 90],
    "north_ethiopia": [35, 42, 10, 15],
    "central_ethiopia": [36, 41, 7, 11],
    "west_ethiopia": [33, 37.5, 6, 13],
    "east_ethiopia": [40, 48, 5, 12],
    "tej_core": [20, 100, 5, 20],
    "nino34_box": [-170, -120, -5, 5],
    "iod_west": [50, 70, -10, 10],
    "iod_east": [90, 110, -10, 0],
    "arabia_red_sea": [35, 60, 10, 30],
    "north_africa_arabia": [10, 60, 10, 35],
    "congo_moisture_corridor": [15, 38, -5, 12],
    "western_moisture_entry": [25, 36, 2, 12],
}

FRONTEND_ORIGIN_DEFAULT = "http://localhost:5173"
