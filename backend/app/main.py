import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import OVERLAYS_DIR, GALLERY_DIR, FRONTEND_ORIGIN_DEFAULT
from app.routers import meta, anomaly, evidence, oceanic, atmospheric, methodology, gallery

app = FastAPI(
    title="Forecast Evidence and Diagnostic System API",
    description=(
        "Serves NMME/ERA5/CFSv2-derived rainfall, temperature, and circulation "
        "diagnostics for Ethiopia's Kiremt/JJAS 2026 rainfall outlook, across "
        "three real NMME initialization cycles (May, June, July 2026)."
    ),
    version="1.0.0",
)

# FRONTEND_ORIGIN can be a single origin or a comma-separated list (e.g. a
# Vercel preview URL plus the production domain).
_origins_env = os.environ.get("FRONTEND_ORIGIN", FRONTEND_ORIGIN_DEFAULT)
allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.mount("/static/overlays", StaticFiles(directory=OVERLAYS_DIR), name="overlays")
app.mount("/static/gallery", StaticFiles(directory=GALLERY_DIR), name="gallery")

app.include_router(meta.router)
app.include_router(anomaly.router)
app.include_router(evidence.router)
app.include_router(oceanic.router)
app.include_router(atmospheric.router)
app.include_router(methodology.router)
app.include_router(gallery.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": "Forecast Evidence and Diagnostic System API",
        "docs": "/docs",
        "health": "/api/health",
    }
