import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import OVERLAYS_DIR, SST_OVERLAYS_DIR, GALLERY_DIR, FRONTEND_ORIGIN_DEFAULT
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

class RevalidateStaticFiles(StaticFiles):
    """Static overlays/gallery images get regenerated in place (same filename,
    new pixels) whenever the underlying data pipeline reruns. Without an
    explicit Cache-Control, browsers apply heuristic freshness to the default
    Last-Modified/ETag response and can keep serving a stale cached image
    indefinitely instead of revalidating. `no-cache` forces a conditional GET
    on every load, so a change on disk is always picked up."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static/overlays", RevalidateStaticFiles(directory=OVERLAYS_DIR), name="overlays")
app.mount("/static/sst_overlays", RevalidateStaticFiles(directory=SST_OVERLAYS_DIR), name="sst_overlays")
app.mount("/static/gallery", RevalidateStaticFiles(directory=GALLERY_DIR), name="gallery")

app.include_router(meta.router)
app.include_router(anomaly.router)
app.include_router(evidence.router)
app.include_router(oceanic.router)
app.include_router(atmospheric.router)
app.include_router(methodology.router)
app.include_router(gallery.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    # "service" is a distinguishing marker, not just a generic {"status":"ok"} --
    # useful when something else is already listening on the expected port
    # (e.g. another local API) and would otherwise look "healthy" too.
    return {"status": "ok", "service": "forecast-evidence-api"}


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": "Forecast Evidence and Diagnostic System API",
        "docs": "/docs",
        "health": "/api/health",
    }
