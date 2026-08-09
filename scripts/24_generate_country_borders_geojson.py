"""
24_generate_country_borders_geojson.py

Purpose
-------
Export a compact country-boundaries GeoJSON (Natural Earth 50m admin_0
countries -- outline only, no fill/color data) for a togglable "Country
borders" overlay layer on the Leaflet dashboard maps. Useful mainly on
basemaps that don't already draw political borders (e.g. Satellite).

Written directly into the frontend's public/ folder so Vite serves it as a
static asset at /country_borders.geojson with no backend involvement --
it's a fixed reference layer, not project data.

Run from project root:
    python scripts\\24_generate_country_borders_geojson.py
"""

from __future__ import annotations

import json
from pathlib import Path

import cartopy.io.shapereader as shpreader
import shapely.geometry as sgeom

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "frontend" / "public" / "country_borders.geojson"


def main():
    print("==================================================")
    print("Generate country-borders GeoJSON (50m, outline only)")
    print("==================================================")

    shp_path = shpreader.natural_earth(resolution="50m", category="cultural", name="admin_0_countries")
    records = list(shpreader.Reader(shp_path).records())

    # Simplify (Douglas-Peucker, ~1km tolerance in degrees) -- this dashboard
    # never zooms in past country-level, so full survey-detail coastlines are
    # wasted bytes; this cuts the payload by ~85% with no visible loss at the
    # zoom levels actually used.
    SIMPLIFY_TOLERANCE_DEG = 0.03

    features = []
    for r in records:
        name = r.attributes.get("NAME_LONG") or r.attributes.get("NAME")
        geom = r.geometry.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        features.append(
            {
                "type": "Feature",
                "properties": {"name": name},
                "geometry": sgeom.mapping(geom),
            }
        )

    geojson = {"type": "FeatureCollection", "features": features}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(geojson, separators=(",", ":"))
    OUT_PATH.write_text(text, encoding="utf-8")

    print(f"Wrote {len(features)} country boundaries -> {OUT_PATH}")
    print(f"Size: {len(text.encode('utf-8')) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
