"""
26_generate_sst_leaflet_overlay_maps.py

Purpose
-------
Generate a global NMME tmpsfc-anomaly raster (SST-proxy) for a react-leaflet
<ImageOverlay>, matching the pattern already used for rainfall by
scripts 22/23 -- Web-Mercator-projected pixel spacing (so it lines up with
the Leaflet basemap), clipped so pixels only paint over OCEAN (land is
masked out, since this is meant to read as a sea-surface-temperature map,
the same convention as BOM/NOAA SST outlook pages), plus a matching raw
grid JSON for exact-value hover tooltips.

Outputs
-------
    outputs/maps/leaflet_overlays_sst/<init>/tmpsfc_global_<period>.png
    outputs/maps/leaflet_overlays_sst/overlay_index.json
    outputs/maps/leaflet_overlays_sst/grid_data/<init>/tmpsfc_global_<period>.json

Run from project root:
    python scripts\\26_generate_sst_leaflet_overlay_maps.py
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
import shapely.geometry as sgeom
import shapely

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "outputs" / "maps" / "leaflet_overlays_sst"
GRID_OUT_DIR = OUT_DIR / "grid_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Classic SST-anomaly diverging scheme: cool blue (below normal) through
# white to warm red (above normal) -- distinct from the precip dry/wet
# brown-teal scheme so the two variables read as visually different things.
CMAP = LinearSegmentedColormap.from_list(
    "cool_warm", ["#08306b", "#4292c6", "#c6dbef", "#f7f7f7", "#fcbba1", "#cb181d", "#67000d"]
)

BOX = [-180, 180, -90, 90]

WEB_MERCATOR_MAX_LAT = 85.05112878
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


def load_ocean_clip_geom():
    """World rectangle minus all land -- the inverse of script 22's land
    mask, so the SST raster only paints over ocean pixels."""
    land_path = shpreader.natural_earth(resolution="10m", category="physical", name="land")
    land_union = unary_union([r.geometry for r in shpreader.Reader(land_path).records()])
    world = sgeom.box(-180, -90, 180, 90)
    return world.difference(land_union)


INIT_JOBS = {
    "may": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_may_init_regions",
        "periods": {
            "Jun": ("NMME_tmpsfc_Jun_2026_anomaly.nc", "tmpsfc_Jun_2026_anomaly", "K"),
            "Jul": ("NMME_tmpsfc_Jul_2026_anomaly.nc", "tmpsfc_Jul_2026_anomaly", "K"),
            "Aug": ("NMME_tmpsfc_Aug_2026_anomaly.nc", "tmpsfc_Aug_2026_anomaly", "K"),
            "Sep": ("NMME_tmpsfc_Sep_2026_anomaly.nc", "tmpsfc_Sep_2026_anomaly", "K"),
            "JJA": ("NMME_tmpsfc_JJA_2026_mean_anomaly.nc", "tmpsfc_JJA_2026_mean_anomaly", "K"),
            "JJAS": ("NMME_tmpsfc_JJAS_2026_mean_anomaly.nc", "tmpsfc_JJAS_2026_mean_anomaly", "K"),
        },
    },
    "june": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_june_init",
        "periods": {
            "Jul": ("NMME_tmpsfc_Jul_2026_anomaly.nc", "tmpsfc_Jul_2026_anomaly", "K"),
            "Aug": ("NMME_tmpsfc_Aug_2026_anomaly.nc", "tmpsfc_Aug_2026_anomaly", "K"),
            "Sep": ("NMME_tmpsfc_Sep_2026_anomaly.nc", "tmpsfc_Sep_2026_anomaly", "K"),
            "JAS": ("NMME_tmpsfc_JAS_2026_mean_anomaly.nc", "tmpsfc_JAS_2026_mean_anomaly", "K"),
        },
    },
    "july": {
        "dir": PROJECT_ROOT / "outputs" / "netcdf" / "nmme_anomalies_july_init",
        "periods": {
            "Aug": ("NMME_tmpsfc_Aug_2026_anomaly.nc", "tmpsfc_Aug_2026_anomaly", "K"),
            "Sep": ("NMME_tmpsfc_Sep_2026_anomaly.nc", "tmpsfc_Sep_2026_anomaly", "K"),
            "AS": ("NMME_tmpsfc_AS_2026_mean_anomaly.nc", "tmpsfc_AS_2026_mean_anomaly", "K"),
        },
    },
}


def standardize_longitude(da: xr.DataArray) -> xr.DataArray:
    lon = da["lon"]
    if float(lon.max()) > 180:
        da = da.assign_coords(lon=((lon + 180) % 360) - 180).sortby("lon")
    return da


def render_overlay(da, box, out_path: Path, clip_geom) -> tuple[float, float]:
    lon_min, lon_max, lat_min, lat_max = box
    vmax = max(float(np.nanpercentile(np.abs(da.values), 98)), 1e-6)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

    merc_x = lon_to_merc_x(da["lon"].values)
    merc_y = lat_to_merc_y(da["lat"].values)
    x_min, x_max = lon_to_merc_x(np.array([lon_min, lon_max]))
    y_min, y_max = lat_to_merc_y(np.array([lat_min, lat_max]))

    width_m = x_max - x_min
    height_m = max(y_max - y_min, 1.0)
    px_per_m = 1600 / max(width_m, height_m)
    fig_w, fig_h = width_m * px_per_m / 100, height_m * px_per_m / 100

    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.axis("off")
    mesh = ax.pcolormesh(merc_x, merc_y, da.values, cmap=CMAP, norm=norm, shading="auto")

    merc_clip = project_geom_to_mercator(clip_geom)
    paths = geos_to_path(merc_clip)
    patch = PathPatch(MplPath.make_compound_path(*paths), transform=ax.transData)
    mesh.set_clip_path(patch)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100, transparent=True)
    plt.close(fig)
    return -vmax, vmax


def to_json_value(v: float) -> float | None:
    return None if not np.isfinite(v) else round(float(v), 2)


def main():
    print("==================================================")
    print("Generate global SST (tmpsfc) leaflet overlays + grid JSON")
    print("==================================================")

    print("Loading Natural Earth land mask for ocean clip...")
    ocean_clip = load_ocean_clip_geom()
    render_box = clamp_box_lat(BOX)

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
            da = standardize_longitude(ds[varname])

            out_path = OUT_DIR / init_key / f"tmpsfc_global_{period}.png"
            vmin, vmax = render_overlay(da, render_box, out_path, ocean_clip)

            lon_min, lon_max, lat_min, lat_max = render_box
            key = f"{init_key}/global/{period}"
            index[key] = {
                "file": f"{init_key}/tmpsfc_global_{period}.png",
                "bounds": [[lat_min, lon_min], [lat_max, lon_max]],
                "vmin": round(vmin, 4),
                "vmax": round(vmax, 4),
                "unit": unit,
            }

            # Raw grid JSON for exact-value hover tooltips (same pattern as
            # script 23 for rainfall) -- downsample a bit (every 2nd point)
            # since a full 1-degree global grid here is purely for tooltips,
            # not visual resolution.
            da_thin = da.isel(lat=slice(None, None, 2), lon=slice(None, None, 2))
            lats = [round(float(v), 3) for v in da_thin["lat"].values]
            lons = [round(float(v), 3) for v in da_thin["lon"].values]
            values = [[to_json_value(v) for v in row] for row in da_thin.values]

            grid_path = GRID_OUT_DIR / init_key / f"tmpsfc_global_{period}.json"
            grid_path.parent.mkdir(parents=True, exist_ok=True)
            grid_path.write_text(
                json.dumps({"lats": lats, "lons": lons, "values": values, "unit": unit}, separators=(",", ":")),
                encoding="utf-8",
            )

            written += 1
            print(f"Saved: {out_path}")
            ds.close()

    index_path = OUT_DIR / "overlay_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(f"\nWrote {written} overlay images + grid files, and {index_path}")


if __name__ == "__main__":
    main()
