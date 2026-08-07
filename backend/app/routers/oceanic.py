import pandas as pd
from fastapi import APIRouter

from app.services.data import sst_proxy, sst_driver_classification

router = APIRouter(prefix="/api/oceanic", tags=["oceanic"])


@router.get("/sst-proxy")
def get_sst_proxy() -> list[dict]:
    """
    NMME tmpsfc-derived Nino3.4 / IOD-West / IOD-East / DMI proxy indices,
    joined with their el_nino_like / positive_iod_like style classification.
    Not an official ENSO/IOD index product -- see /api/methodology.
    """
    sst = sst_proxy().copy()
    sst["period_short"] = sst["period"].str.replace("_2026", "", regex=False)

    drv = sst_driver_classification()[["period", "nino34_classification", "dmi_classification"]]

    merged = sst.merge(drv, left_on="period_short", right_on="period", suffixes=("", "_drv"))
    merged = merged.where(pd.notnull(merged), None)

    out = []
    for row in merged.to_dict(orient="records"):
        out.append({
            "period": row["period_short"],
            "nino34_anomaly": row["nino34_tmpsfc_anomaly"],
            "iod_west_anomaly": row["iod_west_tmpsfc_anomaly"],
            "iod_east_anomaly": row["iod_east_tmpsfc_anomaly"],
            "dmi_proxy": row["dmi_approx"],
            "units": row["units"],
            "nino34_classification": row["nino34_classification"],
            "dmi_classification": row["dmi_classification"],
        })
    return out
