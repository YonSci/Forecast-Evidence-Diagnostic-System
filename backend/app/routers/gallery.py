from fastapi import APIRouter

from app.config import GALLERY_DIR
from app.models import GalleryImage

router = APIRouter(prefix="/api/gallery", tags=["gallery"])

_CAPTIONS: dict[str, tuple[str, str]] = {
    "prate_ethiopia_jjas.png": ("NMME precipitation anomaly — Ethiopia — JJAS 2026", "rainfall"),
    "prate_greater_horn_jjas.png": ("NMME precipitation anomaly — Greater Horn of Africa — JJAS 2026", "rainfall"),
    "sst_indian_ocean_jjas.png": ("NMME tmpsfc SST-proxy anomaly — Indian Ocean (IOD boxes) — JJAS 2026", "oceanic"),
    "sst_pacific_enso_jjas.png": ("NMME tmpsfc SST-proxy anomaly — Pacific / Nino3.4 box — JJAS 2026", "oceanic"),
    "dmi_proxy_chart.png": ("NMME-derived DMI proxy by forecast period", "oceanic"),
    "enso_iod_proxy_chart.png": ("NMME-derived Nino3.4 / IOD-West / IOD-East proxy indices by period", "oceanic"),
    "z200_greater_horn_jjas.png": ("NMME 200 hPa geopotential height anomaly — Greater Horn — JJAS 2026", "circulation"),
    "tej_climatology_jjas.png": ("ERA5 1991-2020 climatology: 200 hPa zonal wind / Tropical Easterly Jet — JJAS", "circulation"),
    "moisture_flux_mfc_jjas.png": ("ERA5 climatology: 850 hPa moisture flux and moisture-flux convergence — Greater Horn — JJAS", "circulation"),
    "omega500_jjas.png": ("ERA5 climatology: 500 hPa vertical velocity (omega) — Greater Horn — JJAS", "circulation"),
    "divergence200_jjas.png": ("ERA5 climatology: 200 hPa divergence — Greater Horn — JJAS", "circulation"),
}


@router.get("", response_model=list[GalleryImage])
def get_gallery() -> list[GalleryImage]:
    images = []
    for fname in sorted(_CAPTIONS):
        if not (GALLERY_DIR / fname).exists():
            continue
        caption, group = _CAPTIONS[fname]
        images.append(GalleryImage(key=fname, url=f"/static/gallery/{fname}", caption=caption, group=group))
    return images
