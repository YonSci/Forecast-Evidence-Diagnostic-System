"""
Cached readers over the curated CSVs in app/static_data/tables. Each
function loads its CSV once per process (lru_cache) -- the files are small
(a few hundred KB to ~200 KB each) and don't change while the server runs.
"""
from functools import lru_cache

import pandas as pd

from app.config import TABLES_DIR, INITIALIZATIONS


def _read(name: str) -> pd.DataFrame:
    path = TABLES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Expected static data table not found: {path}")
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def evidence_matrix() -> pd.DataFrame:
    return _read("integrated_nmme_cfsv2_evidence_matrix.csv")


@lru_cache(maxsize=1)
def evidence_summary() -> pd.DataFrame:
    return _read("integrated_nmme_cfsv2_summary_by_period.csv")


@lru_cache(maxsize=1)
def sst_proxy() -> pd.DataFrame:
    return _read("nmme_sst_indices_from_tmpsfc.csv")


@lru_cache(maxsize=1)
def sst_driver_classification() -> pd.DataFrame:
    return _read("nmme_sst_driver_diagnostics_from_tmpsfc.csv")


@lru_cache(maxsize=1)
def tej_climatology() -> pd.DataFrame:
    return _read("era5_tej_index_climatology.csv")


@lru_cache(maxsize=1)
def era5_moisture_flux() -> pd.DataFrame:
    return _read("era5_850hpa_moisture_flux_diagnostics.csv")


@lru_cache(maxsize=1)
def era5_vertical_divergence() -> pd.DataFrame:
    return _read("era5_vertical_divergence_height_diagnostics.csv")


@lru_cache(maxsize=1)
def cfsv2_area_mean() -> pd.DataFrame:
    return _read("cfsv2_dynamic_area_mean_diagnostics.csv")


@lru_cache(maxsize=4)
def anomaly_table(init_key: str) -> pd.DataFrame:
    """init_key is one of the INITIALIZATIONS[...]['csv_key'] values (may/june/july)."""
    return _read(f"nmme_area_mean_anomalies_{init_key}_init.csv")


def csv_key_for_init(init_date: str) -> str:
    meta = INITIALIZATIONS.get(init_date)
    if meta is None:
        raise KeyError(f"Unknown initialization: {init_date}")
    return meta["csv_key"]


def clear_caches() -> None:
    """Used by tests / hot-reload scenarios."""
    for fn in (
        evidence_matrix, evidence_summary, sst_proxy, sst_driver_classification,
        tej_climatology, era5_moisture_flux, era5_vertical_divergence,
        cfsv2_area_mean, anomaly_table,
    ):
        fn.cache_clear()
