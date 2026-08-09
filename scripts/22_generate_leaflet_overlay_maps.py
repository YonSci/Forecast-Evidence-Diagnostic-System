"""
22_generate_leaflet_overlay_maps.py

Purpose
-------
Generate "clean" precipitation-anomaly raster images for use as real
react-leaflet <ImageOverlay> layers -- full-bleed, no title/colorbar/axis
labels/footer baked into the pixels, in plain equirectangular (PlateCarree,
central_longitude=0) projection so the image's four corners map linearly
onto the same [lon_min, lon_max, lat_min, lat_max] box used for the
region's area-mean statistics.

This is different from scripts 06/11/16/20, which render report-style
figures (title, colorbar, footer) meant to be viewed as static images.
Those stay as-is for the dashboard's map gallery. This script produces the
raster-only counterpart specifically for interactive Leaflet overlays,
where the legend/title/scale are rendered as separate UI elements around
the map, not inside the image.

Covers every (initialization, region, period) combination already
computed by scripts 04/21 (May), 15 (June), and 19 (July).

Outputs
-------
    outputs/maps/leaflet_overlays/<init>/prate_<region>_<period>.png
    outputs/maps/leaflet_overlays/overlay_index.json
        { "<init>/<region>/<period>": {file, bounds:[[latmin,lonmin],[latmax,lonmax]],
                                          vmin, vmax, unit, value_domain} }

Run from project root:
    python scripts\\22_generate_leaflet_overlay_maps.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
import cartopy.io.shapereader as shpreader
from cartopy.mpl.patch import geos_to_path
from shapely.ops import unary_union
import shapely


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "leaflet_overlays"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CMAP = LinearSegmentedColormap.from_list(
    "dry_wet", ["#8a3a1c", "#c2703f", "#e8b691", "#f5f1ea", "#a9d6cf", "#3fa89a", "#0f5f57"]
)

REGIONS = {
    "ethiopia": [32, 48, 3, 15],
    "greater_horn": [20, 55, -15, 25],
    "africa": [-20, 52, -35, 38],
    "global": [-180, 180, -90, 90],
}

# Leaflet's default CRS (EPSG:3857 / Web Mercator) is undefined at the poles
# and Leaflet itself clamps to this latitude internally, so a raster whose
# stated bounds go all the way to +/-90 gets silently mis-projected by the
# client.
WEB_MERCATOR_MAX_LAT = 85.05112878

# Leaflet's ImageOverlay places a raster on screen with a single, uniform
# affine stretch between the two lat/lon corners it's told about -- it does
# NOT re-warp the image's internal pixel spacing to match Web Mercator. Our
# source rasters were pixel-linear in latitude (equirectangular / Plate
# Carree), while the CARTO basemap tiles underneath are Web Mercator, which
# compresses latitude non-linearly. For a small box (e.g. Ethiopia, ~12 deg
# of latitude) that mismatch is a few pixels and invisible; for large boxes
# (Greater Horn's 40 deg, and especially "global" at 170 deg) it shows up as
# a clearly visible vertical misalignment against real coastlines. Fix: warp
# the raster's own pixel rows (and the clip geometry) into Web Mercator
# meters before rendering, so a uniform stretch back onto the Mercator
# basemap lines up exactly, the same way real map tiles are pre-projected.
MERCATOR_R = 6378137.0


def lon_to_merc_x(lon_deg):
    return np.radians(np.asarray(lon_deg, dtype=float)) * MERCATOR_R


def lat_to_merc_y(lat_deg):
    lat_deg = np.clip(np.asarray(lat_deg, dtype=float), -WEB_MERCATOR_MAX_LAT, WEB_MERCATOR_MAX_LAT)
    return MERCATOR_R * np.log(np.tan(np.pi / 4 + np.radians(lat_deg) / 2))


def project_geom_to_mercator(geom):
    def _tf(coords):
        return np.column_stack([lon_to_merc_x(coords[:, 0]), lat_to_merc_y(coords[:, 1])])

    return shapely.transform(geom, _tf)


def clamp_box_lat(box):
    lon_min, lon_max, lat_min, lat_max = box
    return [lon_min, lon_max, max(lat_min, -WEB_MERCATOR_MAX_LAT), min(lat_max, WEB_MERCATOR_MAX_LAT)]

# IGAD member states -- the standard "Greater Horn of Africa" country grouping
# (FEWS NET / USAID Horn of Africa definition). Natural Earth represents
# Somaliland as a separate polygon from Somalia (it functions as a de facto
# separate territory), so it has to be listed explicitly or that whole
# northern-Somalia strip along the Gulf of Aden is left unclipped/blank.
GREATER_HORN_COUNTRIES = {
    "Djibouti", "Eritrea", "Ethiopia", "Kenya", "Somalia", "Somaliland", "South Sudan", "Sudan", "Uganda",
}

# Region -> matching predicate over Natural Earth admin_0_countries attributes.
REGION_COUNTRY_FILTER = {
    "ethiopia": lambda attrs: attrs["NAME_LONG"] == "Ethiopia",
    "greater_horn": lambda attrs: attrs["NAME_LONG"] in GREATER_HORN_COUNTRIES,
    "africa": lambda attrs: attrs["CONTINENT"] == "Africa",
}


def load_region_clip_geoms() -> dict:
    """Build a shapely (multi)polygon per region so raster overlays can be
    clipped to the real coastline/border shape instead of the lon/lat
    bounding box used to subset data. Ethiopia/greater_horn/africa clip to
    their Natural Earth country outlines; "global" clips to all world land
    (physical land polygons, not split by country) so ocean pixels go
    transparent instead of the overlay painting a full lat/lon rectangle."""
    shp_path = shpreader.natural_earth(resolution="10m", category="cultural", name="admin_0_countries")
    records = list(shpreader.Reader(shp_path).records())

    geoms = {}
    for region, predicate in REGION_COUNTRY_FILTER.items():
        matched = [r.geometry for r in records if predicate(r.attributes)]
        geoms[region] = unary_union(matched)

    land_path = shpreader.natural_earth(resolution="10m", category="physical", name="land")
    land_geoms = [r.geometry for r in shpreader.Reader(land_path).records()]
    geoms["global"] = unary_union(land_geoms)

    return geoms

# (init_key, netcdf_dir, {period: (filename, varname, unit, is_seasonal)})
INIT_JOBS = {
    "may": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_may_init_regions",
        "periods": {
            "Jun": ("NMME_prate_Jun_2026_total_anomaly_mm_month.nc", "prate_Jun_2026_total_mm_month", "mm/month"),
            "Jul": ("NMME_prate_Jul_2026_total_anomaly_mm_month.nc", "prate_Jul_2026_total_mm_month", "mm/month"),
            "Aug": ("NMME_prate_Aug_2026_total_anomaly_mm_month.nc", "prate_Aug_2026_total_mm_month", "mm/month"),
            "Sep": ("NMME_prate_Sep_2026_total_anomaly_mm_month.nc", "prate_Sep_2026_total_mm_month", "mm/month"),
            "JJA": ("NMME_prate_JJA_2026_total_anomaly_mm_season.nc", "prate_JJA_2026_total_mm_season", "mm/season"),
            "JAS": ("NMME_prate_JAS_2026_total_anomaly_mm_season.nc", "prate_JAS_2026_total_mm_season", "mm/season"),
            "JJAS": ("NMME_prate_JJAS_2026_total_anomaly_mm_season.nc", "prate_JJAS_2026_total_mm_season", "mm/season"),
        },
    },
    "june": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_june_init",
        "periods": {
            "Jul": ("NMME_prate_Jul_2026_total_anomaly_mm_month.nc", "prate_Jul_2026_total_mm_month", "mm/month"),
            "Aug": ("NMME_prate_Aug_2026_total_anomaly_mm_month.nc", "prate_Aug_2026_total_mm_month", "mm/month"),
            "Sep": ("NMME_prate_Sep_2026_total_anomaly_mm_month.nc", "prate_Sep_2026_total_mm_month", "mm/month"),
            "JAS": ("NMME_prate_JAS_2026_total_anomaly_mm_season.nc", "prate_JAS_2026_total_mm_season", "mm/season"),
        },
    },
    "july": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_july_init",
        "periods": {
            "Aug": ("NMME_prate_Aug_2026_total_anomaly_mm_month.nc", "prate_Aug_2026_total_mm_month", "mm/month"),
            "Sep": ("NMME_prate_Sep_2026_total_anomaly_mm_month.nc", "prate_Sep_2026_total_mm_month", "mm/month"),
            "AS": ("NMME_prate_AS_2026_total_anomaly_mm_season.nc", "prate_AS_2026_total_mm_season", "mm/season"),
        },
    },
}


def area_sub(da, box):
    lon_min, lon_max, lat_min, lat_max = box
    lat = da["lat"].values
    lat_slice = slice(lat_min, lat_max) if lat[0] < lat[-1] else slice(lat_max, lat_min)
    return da.sel(lat=lat_slice, lon=slice(lon_min, lon_max))


def render_overlay(da, box, out_path: Path, clip_geom=None) -> tuple[float, float]:
    # box's lat range is expected to already be clamp_box_lat()'d by the caller.
    lon_min, lon_max, lat_min, lat_max = box
    vmax = max(float(np.nanpercentile(np.abs(da.values), 98)), 1e-6)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    # Render in Web Mercator meters (not raw lon/lat degrees) so pixel rows
    # are linear in the same space the Leaflet basemap projects into -- see
    # the module docstring note above MERCATOR_R for why a plain lon/lat
    # raster ends up visibly misaligned once Leaflet stretches it onto a
    # Mercator basemap.
    merc_x = lon_to_merc_x(da["lon"].values)
    merc_y = lat_to_merc_y(da["lat"].values)
    x_min, x_max = lon_to_merc_x(np.array([lon_min, lon_max]))
    y_min, y_max = lat_to_merc_y(np.array([lat_min, lat_max]))

    width_m = x_max - x_min
    height_m = max(y_max - y_min, 1.0)
    # target ~1600px on the long side, capped so global renders don't balloon
    px_per_m = 1600 / max(width_m, height_m)
    fig_w, fig_h = width_m * px_per_m / 100, height_m * px_per_m / 100

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.axis("off")
    mesh = ax.pcolormesh(merc_x, merc_y, da.values, cmap=CMAP, norm=norm, shading="auto")

    if clip_geom is not None and not clip_geom.is_empty:
        # Clip the raster to the region's actual country/coastline shape
        # (not the rectangular lon/lat box it was subset on), so the overlay
        # doesn't paint neighboring countries or open ocean. Geometry is in
        # lat/lon (Natural Earth); project it into the same Mercator meters
        # the mesh is now plotted in before turning it into a clip path.
        merc_clip = project_geom_to_mercator(clip_geom)
        paths = geos_to_path(merc_clip)
        patch = PathPatch(MplPath.make_compound_path(*paths), transform=ax.transData)
        mesh.set_clip_path(patch)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, transparent=True)
    plt.close(fig)
    return -vmax, vmax


def main():
    print("==================================================")
    print("Generate clean Leaflet ImageOverlay rasters")
    print("==================================================")

    print("Loading Natural Earth country boundaries for region clip masks...")
    clip_geoms = load_region_clip_geoms()

    index = {}
    written = 0

    for init_key, job in INIT_JOBS.items():
        nc_dir = job["dir"]
        for period, (fname, varname, unit) in job["periods"].items():
            path = nc_dir / fname
            if not path.exists():
                print(f"Missing: {path}, skipping.")
                continue
            ds = xr.open_dataset(path, decode_times=False)
            da_full = ds[varname]

            for region, box in REGIONS.items():
                da = area_sub(da_full, box)
                render_box = clamp_box_lat(box)
                out_path = OUT_DIR / init_key / f"prate_{region}_{period}.png"
                vmin, vmax = render_overlay(da, render_box, out_path, clip_geom=clip_geoms.get(region))

                # Record the clamped box: that's what the image actually
                # depicts, and it's what Leaflet needs to place it correctly
                # (it clamps to the same +/-85.05 internally anyway).
                lon_min, lon_max, lat_min, lat_max = render_box
                key = f"{init_key}/{region}/{period}"
                index[key] = {
                    "file": f"{init_key}/prate_{region}_{period}.png",
                    "bounds": [[lat_min, lon_min], [lat_max, lon_max]],
                    "vmin": round(vmin, 4),
                    "vmax": round(vmax, 4),
                    "unit": unit,
                }
                written += 1
                print(f"Saved: {out_path}")
            ds.close()

    index_path = OUT_DIR / "overlay_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"\nWrote {written} overlay images and {index_path}")


if __name__ == "__main__":
    main()
