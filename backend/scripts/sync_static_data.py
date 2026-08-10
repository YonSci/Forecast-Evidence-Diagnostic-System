"""
sync_static_data.py

One-time (re-runnable) sync of curated pipeline outputs into the FastAPI
backend's bundled static_data/ folder, so the deployed backend (Render)
carries its own copy of what it serves instead of depending on the local
project's outputs/ tree (which won't exist on the deploy host).

Run from anywhere:
    python backend\\scripts\\sync_static_data.py
"""
import shutil
from pathlib import Path
from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
STATIC = BACKEND_ROOT / "app" / "static_data"

# ---- 1. tables: copy every CSV in outputs/tables ----
tables_src = PROJECT_ROOT / "outputs" / "tables"
tables_dst = STATIC / "tables"
tables_dst.mkdir(parents=True, exist_ok=True)
n = 0
for f in tables_src.glob("*.csv"):
    shutil.copy2(f, tables_dst / f.name)
    n += 1
print(f"Copied {n} table CSVs -> {tables_dst}")

# ---- 2. overlays: copy the whole leaflet_overlays tree (already small) ----
overlays_src = PROJECT_ROOT / "outputs" / "maps" / "leaflet_overlays"
overlays_dst = STATIC / "overlays"
if overlays_dst.exists():
    shutil.rmtree(overlays_dst)
shutil.copytree(overlays_src, overlays_dst)
print(f"Copied overlay tree -> {overlays_dst}")

# ---- 2b. sst overlays: same pattern, separate tree (global tmpsfc/SST maps) ----
sst_overlays_src = PROJECT_ROOT / "outputs" / "maps" / "leaflet_overlays_sst"
sst_overlays_dst = STATIC / "sst_overlays"
if sst_overlays_dst.exists():
    shutil.rmtree(sst_overlays_dst)
shutil.copytree(sst_overlays_src, sst_overlays_dst)
print(f"Copied SST overlay tree -> {sst_overlays_dst}")

# ---- 3. gallery: curated report-style figures (resized), non-rainfall diagnostics ----
DYN = PROJECT_ROOT / "outputs" / "maps" / "dynamic_diagnostics"
GALLERY_SOURCES = {
    "prate_ethiopia_jjas.png": DYN / "01_nmme_precipitation_anomaly/ethiopia/NMME_precipitation_anomaly_JJAS_2026_ethiopia.png",
    "prate_greater_horn_jjas.png": DYN / "01_nmme_precipitation_anomaly/greater_horn/NMME_precipitation_anomaly_JJAS_2026_greater_horn.png",
    "sst_indian_ocean_jjas.png": DYN / "02_nmme_tmpsfc_sst_proxy/indian_ocean/NMME_tmpsfc_SST_proxy_anomaly_JJAS_2026_indian_ocean.png",
    "sst_pacific_enso_jjas.png": DYN / "02_nmme_tmpsfc_sst_proxy/pacific_enso/NMME_tmpsfc_SST_proxy_anomaly_JJAS_2026_pacific_enso.png",
    "dmi_proxy_chart.png": DYN / "08_summary_charts/NMME_tmpsfc_DMI_proxy_chart.png",
    "enso_iod_proxy_chart.png": DYN / "08_summary_charts/NMME_tmpsfc_ENSO_IOD_proxy_chart.png",
    "z200_greater_horn_jjas.png": DYN / "03_nmme_z200_anomaly/greater_horn/NMME_z200_anomaly_JJAS_2026_greater_horn.png",
    "tej_climatology_jjas.png": DYN / "04_era5_u200_tej_climatology/ERA5_u200_TEJ_climatology_JJAS_africa_indian.png",
    "moisture_flux_mfc_jjas.png": DYN / "05_era5_850hpa_moisture_flux/greater_horn/ERA5_850hPa_moisture_flux_MFC_JJAS_greater_horn.png",
    "omega500_jjas.png": DYN / "06_era5_omega_vertical_motion/omega500/greater_horn/ERA5_omega500_JJAS_greater_horn.png",
    "divergence200_jjas.png": DYN / "07_era5_200hpa_divergence/greater_horn/ERA5_divergence200_JJAS_greater_horn.png",
}

gallery_dst = STATIC / "gallery"
gallery_dst.mkdir(parents=True, exist_ok=True)
MAX_W = 1400
total_kb = 0
for name, src in GALLERY_SOURCES.items():
    if not src.exists():
        print(f"MISSING SOURCE: {src}")
        continue
    im = Image.open(src)
    if im.mode in ("RGBA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    w, h = im.size
    if w > MAX_W:
        im = im.resize((MAX_W, int(h * MAX_W / w)), Image.LANCZOS)
    out_path = gallery_dst / name
    im.save(out_path, format="PNG", optimize=True)
    kb = out_path.stat().st_size / 1024
    total_kb += kb
    print(f"{name:32s} {kb:7.1f} KB")

print(f"\nGallery total: {total_kb/1024:.2f} MB")
