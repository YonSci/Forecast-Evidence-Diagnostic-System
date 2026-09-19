"""
31_compute_lowlevel_jet_diagnostics.py

Purpose
-------
Turn the raw sub-600-hPa ERA5 wind stack from script 29 into the
low-level-jet (Somali jet) diagnostics the Atmospheric Evidence page
shows, for all twelve calendar months plus JJA and JJAS.

The jet is a three-dimensional feature that moves in height as well as
position, so a single 850 hPa slice cannot locate it. Instead every
sub-600-hPa level is searched at each grid point for the wind maximum,
which yields three fields per period:

    llj_speed  -- the speed of that maximum (how strong the jet is)
    llj_level  -- the pressure it occurs at  (how high the jet core is)
    llj_u/v    -- the wind vector at that level (which way the core flows)

llj_u/llj_v together form the wind field *on the jet-core surface* rather
than on any fixed pressure surface, which is what makes tracing a single
continuous pathway possible: the Somali jet rises and sinks by well over
100 hPa between the Mascarene source region and the Indian coast, so a
streamline drawn on a fixed level would leave the core partway along.

Below-ground masking
--------------------
ERA5 reports pressure-level values underneath the ground by downward
extrapolation. Over the Ethiopian highlands the surface is near 800-700
hPa, so an unmasked search would place the "core" underground across
precisely the region of interest. Every level below the climatological
surface pressure (script 30) is therefore set to NaN before the search,
and grid points whose entire sub-600-hPa column is underground come out
as NaN rather than as a spurious core.

Core and pathway
----------------
For each period the core is the single strongest point of llj_speed
inside SOMALI_JET_SEARCH_BOX, and the pathway is a streamline integrated
both forward and backward from it across the llj_u/llj_v surface. The
trace stops where the core surface weakens below a fraction of the core
speed, so the line ends where the jet ends instead of wandering off into
unrelated flow. A period whose core is weaker than MIN_CORE_SPEED is
reported as having no jet at all and gets no pathway -- which is the
honest result for the boreal-winter months, when the cross-equatorial
flow reverses and the monsoon jet is simply absent. That seasonal
appearance and disappearance is the point of carrying all twelve months
rather than JJAS alone.

Outputs
-------
    outputs/netcdf/era5_climatology/ERA5_lowlevel_uv_monthly_climatology_1991_2020.nc
        u, v  (month, level, lat, lon)   -- the full masked 3-D stack
    outputs/netcdf/dynamic_diagnostics/ERA5_lowlevel_jet_<period>_climatology_1991_2020.nc
        llj_speed, llj_level, llj_u, llj_v  (lat, lon)
    outputs/tables/era5_lowlevel_jet_core.csv
    outputs/tables/era5_lowlevel_jet_pathway.json

Run from project root (after scripts 29 and 30):
    python scripts\\31_compute_lowlevel_jet_diagnostics.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr
from scipy.interpolate import RegularGridInterpolator


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ERA5_DIR = PROJECT_ROOT / "data" / "era5"
LOWLEVEL_DIR = ERA5_DIR / "monthly" / "lowlevel_winds"
SURFACE_PRESSURE_FILE = ERA5_DIR / "monthly" / "single_levels" / "era5_surface_pressure_1991_2020_monthly.nc"

NETCDF_OUT_DIR = PROJECT_ROOT / "outputs" / "netcdf"
ERA5_CLIM_DIR = NETCDF_OUT_DIR / "era5_climatology"
DYNAMIC_DIAG_DIR = NETCDF_OUT_DIR / "dynamic_diagnostics"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

for d in (ERA5_CLIM_DIR, DYNAMIC_DIAG_DIR, TABLES_DIR):
    d.mkdir(parents=True, exist_ok=True)

CLIM_START_YEAR = 1991
CLIM_END_YEAR = 2020

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SEASONS = {"JJA": [6, 7, 8], "JJAS": [6, 7, 8, 9]}

# Where the Somali jet core is looked for: the East African coast and the
# Arabian Sea. Deliberately does NOT extend south of 5S -- the southern
# Indian Ocean trades are also fast and would out-compete the jet core in
# a wider box. The cross-equatorial southern branch still appears in the
# result because the pathway is integrated backwards out of the core,
# rather than being searched for directly.
SOMALI_JET_SEARCH_BOX = [38.0, 62.0, -5.0, 18.0]   # lon_min, lon_max, lat_min, lat_max

# The core is identified by what the Somali jet physically IS, not merely
# by being the fastest thing in the box. Without these two constraints
# the search returns the lower flank of the subtropical westerly jet
# every non-summer month -- it shows up pinned to the box's north-east
# corner at exactly 600 hPa, which is the giveaway that the real maximum
# lies outside the searched volume entirely.
#
#   southerly: the jet is the cross-equatorial branch of the monsoon
#   circulation, so its core flows northward. In boreal winter the flow
#   here reverses to the north-easterly monsoon and nothing qualifies,
#   which is the correct answer rather than a missing one.
#
#   depth: a genuine low-level jet core sits well below 700 hPa. This
#   excludes the 600 hPa subtropical-jet flank without excluding any
#   real Somali jet core, which is observed near 850-950 hPa.
CORE_REQUIRE_SOUTHERLY = True
CORE_MIN_LEVEL_HPA = 700.0

# Findlater's conventional low-level-jet threshold.
MIN_CORE_SPEED = 12.0       # m/s

# Final test for whether the core found is actually the Somali jet: its
# upstream streamline must originate at or south of this latitude. The
# Somali jet draws on near-equatorial and southern-hemisphere air, which
# separates it from the other southerly low-level maxima in the same box
# -- the Bab-el-Mandeb/Gulf of Aden channel flow in particular, which is
# fast and southerly in winter but is fed from the Red Sea and never
# reaches below about 12N.
#
# Phrased as an origin latitude rather than as a strict equator crossing
# because the crossing itself is sensitive to PATHWAY_STOP_SPEED: in
# September the jet has weakened enough that the upstream trace halts
# within a fraction of a degree of the equator, and a strict test would
# throw away a month whose core is unmistakably the Somali jet (about 20
# m/s at 52E, 10N, 950 hPa). Whether the pathway does in fact cross is
# recorded per period as `crosses_equator` instead.
CORE_MAX_ORIGIN_LAT = 5.0   # degrees north
# The pathway stops where the core surface drops below this absolute
# speed. Deliberately not a fraction of the core speed: the jet
# accelerates roughly threefold between the equator and the core, so any
# fraction large enough to end the downstream branch sensibly also severs
# the upstream branch before it reaches the equator -- which is exactly
# the cross-equatorial stretch the pathway exists to show.
PATHWAY_STOP_SPEED = 8.0    # m/s
PATHWAY_STEP_M = 25_000.0   # ~0.22 deg per integration step
PATHWAY_MAX_STEPS = 600     # 600 * 25 km = 15,000 km per direction

EARTH_M_PER_DEG = 111_320.0


# ==========================================================
# Climatology
# ==========================================================

def load_monthly_climatology() -> xr.Dataset:
    """Mean u/v for each calendar month over CLIM_START_YEAR..CLIM_END_YEAR.

    Accumulated one year-file at a time rather than via open_mfdataset:
    dask is not installed in this environment, so a lazy multi-file open
    would load all thirty years (~4 GB) into memory at once."""
    files = sorted(LOWLEVEL_DIR.glob("era5_lowlevel_uv_*.nc"))
    if not files:
        raise FileNotFoundError(
            f"No low-level wind files in {LOWLEVEL_DIR}. Run scripts/29 first."
        )

    print(f"Building monthly climatology from {len(files)} year files")

    u_sum = v_sum = None
    counts = np.zeros(12, dtype=np.int64)
    level = lat = lon = None
    used_years: list[int] = []
    unreadable: list[str] = []

    for path in files:
        year = int(path.stem.split("_")[-1])
        if not (CLIM_START_YEAR <= year <= CLIM_END_YEAR):
            print(f"  skipping {path.name}: outside {CLIM_START_YEAR}-{CLIM_END_YEAR}")
            continue

        try:
            probe = xr.open_dataset(path)
        except OSError as exc:
            # Most likely a file scripts/29 is still writing. Skipping is
            # safe only because the incompleteness is reported loudly
            # below -- a quietly short climatology would still be labelled
            # 1991-2020 and look entirely normal.
            print(f"  UNREADABLE {path.name}: {exc}")
            unreadable.append(path.name)
            continue
        probe.close()

        used_years.append(year)

        with xr.open_dataset(path) as ds:
            ds = ds.rename({"valid_time": "time", "latitude": "lat", "longitude": "lon"})
            if u_sum is None:
                level = ds["pressure_level"].values.astype(float)
                lat = ds["lat"].values.astype(float)
                lon = ds["lon"].values.astype(float)
                shape = (12, len(level), len(lat), len(lon))
                u_sum = np.zeros(shape, dtype=np.float64)
                v_sum = np.zeros(shape, dtype=np.float64)

            months = ds["time"].dt.month.values
            u_year = ds["u"].values
            v_year = ds["v"].values

            for i, m in enumerate(months):
                u_sum[m - 1] += u_year[i]
                v_sum[m - 1] += v_year[i]
                counts[m - 1] += 1

        print(f"  {path.name}: {len(months)} months")

    if np.any(counts == 0):
        missing = [MONTH_ABBR[i] for i in np.where(counts == 0)[0]]
        raise ValueError(f"No data for month(s): {', '.join(missing)}")
    if len(set(counts.tolist())) != 1:
        print(f"  warning: uneven year counts per month: {counts.tolist()}")

    expected = CLIM_END_YEAR - CLIM_START_YEAR + 1
    if len(used_years) != expected:
        print("")
        print("*" * 62)
        print(f"*  INCOMPLETE CLIMATOLOGY: {len(used_years)} of {expected} years used")
        print(f"*  Range present: {min(used_years)}-{max(used_years)}")
        if unreadable:
            print(f"*  Unreadable (still downloading?): {', '.join(unreadable)}")
        print("*  Re-run once scripts/29 has finished to get the real")
        print(f"*  {CLIM_START_YEAR}-{CLIM_END_YEAR} climatology.")
        print("*" * 62)
        print("")

    denom = counts[:, None, None, None]
    dims = ("month", "level", "lat", "lon")
    coords = {"month": np.arange(1, 13), "level": level, "lat": lat, "lon": lon}

    return xr.Dataset(
        {
            "u": (dims, (u_sum / denom).astype(np.float32)),
            "v": (dims, (v_sum / denom).astype(np.float32)),
        },
        coords=coords,
    )


def load_surface_pressure_climatology(lat: np.ndarray, lon: np.ndarray) -> np.ndarray | None:
    """Monthly-mean surface pressure in hPa, shape (12, nlat, nlon)."""
    if not SURFACE_PRESSURE_FILE.exists():
        print(f"WARNING: {SURFACE_PRESSURE_FILE.name} not found -- below-ground levels will NOT be masked.")
        print("         Run scripts/30 to remove extrapolated sub-surface winds over high terrain.")
        return None

    with xr.open_dataset(SURFACE_PRESSURE_FILE) as ds:
        ds = ds.rename({"valid_time": "time", "latitude": "lat", "longitude": "lon"})
        ds = ds.sel(time=ds["time"].dt.year.isin(range(CLIM_START_YEAR, CLIM_END_YEAR + 1)))
        sp = ds["sp"].groupby("time.month").mean("time")
        sp = sp.reindex(month=np.arange(1, 13))

        if not (np.allclose(sp["lat"].values, lat) and np.allclose(sp["lon"].values, lon)):
            sp = sp.interp(lat=lat, lon=lon)

        return (sp.values / 100.0).astype(np.float32)


def apply_below_ground_mask(ds: xr.Dataset, sp_hpa: np.ndarray | None) -> xr.Dataset:
    if sp_hpa is None:
        return ds

    level = ds["level"].values.astype(np.float32)
    # (month, level, lat, lon): a level is underground where its pressure
    # exceeds the surface pressure at that point.
    underground = level[None, :, None, None] > sp_hpa[:, None, :, :]

    masked = ds.copy()
    for name in ("u", "v"):
        values = ds[name].values.astype(np.float32)
        values[underground] = np.nan
        masked[name] = (ds[name].dims, values)

    frac = float(underground.mean()) * 100.0
    print(f"Masked {frac:.1f}% of sub-600-hPa grid cells as below ground")
    return masked


# ==========================================================
# Column search for the jet core surface
# ==========================================================

def compute_core_surface(u: np.ndarray, v: np.ndarray, level: np.ndarray) -> dict[str, np.ndarray]:
    """At every grid point, find the sub-600-hPa level of maximum wind
    speed and return the speed, pressure and wind vector there.

    u/v are (level, lat, lon) with NaN where below ground."""
    speed = np.sqrt(u**2 + v**2)

    all_nan = np.all(np.isnan(speed), axis=0)
    searchable = np.where(np.isnan(speed), -np.inf, speed)
    idx = np.argmax(searchable, axis=0)

    ny, nx = idx.shape
    yy, xx = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")

    out = {
        "llj_speed": speed[idx, yy, xx],
        "llj_level": level[idx].astype(np.float32),
        "llj_u": u[idx, yy, xx],
        "llj_v": v[idx, yy, xx],
    }
    for key in out:
        out[key] = np.where(all_nan, np.nan, out[key]).astype(np.float32)
    return out


# ==========================================================
# Core location and pathway
# ==========================================================

def find_core(
    llj_speed: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    llj_level: np.ndarray,
    llj_v: np.ndarray,
) -> dict | None:
    lon_min, lon_max, lat_min, lat_max = SOMALI_JET_SEARCH_BOX
    lat_in = (lat >= lat_min) & (lat <= lat_max)
    lon_in = (lon >= lon_min) & (lon <= lon_max)

    eligible = np.zeros_like(llj_speed, dtype=bool)
    eligible[np.ix_(lat_in, lon_in)] = True
    eligible &= np.isfinite(llj_speed)
    eligible &= llj_level >= CORE_MIN_LEVEL_HPA
    if CORE_REQUIRE_SOUTHERLY:
        eligible &= llj_v > 0

    if not eligible.any():
        return None

    box = np.where(eligible, llj_speed, -np.inf)
    iy, ix = np.unravel_index(int(np.argmax(box)), box.shape)
    speed = float(box[iy, ix])

    return {
        "lon": float(lon[ix]),
        "lat": float(lat[iy]),
        "level": float(llj_level[iy, ix]),
        "speed": speed,
        "is_jet": speed >= MIN_CORE_SPEED,
    }


def trace_pathway(
    llj_u: np.ndarray,
    llj_v: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    llj_level: np.ndarray,
    core: dict,
) -> dict[str, list[float]]:
    """Integrate a streamline through the core across the jet-core
    surface, forward and backward, stopping where the surface weakens."""
    # RegularGridInterpolator needs ascending axes; ERA5 latitude runs
    # north to south.
    order = np.argsort(lat)
    lat_asc = lat[order]

    def interp_for(field: np.ndarray) -> RegularGridInterpolator:
        return RegularGridInterpolator(
            (lat_asc, lon), field[order, :],
            bounds_error=False, fill_value=np.nan,
        )

    u_at = interp_for(llj_u)
    v_at = interp_for(llj_v)
    level_at = interp_for(llj_level)

    stop_speed = PATHWAY_STOP_SPEED
    lat_lo, lat_hi = float(lat_asc[0]), float(lat_asc[-1])
    lon_lo, lon_hi = float(lon[0]), float(lon[-1])

    def step(point: tuple[float, float], sign: int) -> tuple[float, float] | None:
        """One midpoint-method step of PATHWAY_STEP_M along the flow."""
        def velocity(p):
            q = np.array([[p[0], p[1]]])
            u = float(u_at(q)[0])
            v = float(v_at(q)[0])
            if not (np.isfinite(u) and np.isfinite(v)):
                return None
            return u, v

        def advance(p, uv, distance_m):
            u, v = uv
            speed = np.hypot(u, v)
            if speed <= 0:
                return None
            dt = distance_m / speed
            cos_lat = max(np.cos(np.radians(p[0])), 0.05)
            return (
                p[0] + sign * v * dt / EARTH_M_PER_DEG,
                p[1] + sign * u * dt / (EARTH_M_PER_DEG * cos_lat),
            )

        uv0 = velocity(point)
        if uv0 is None or np.hypot(*uv0) < stop_speed:
            return None

        mid = advance(point, uv0, PATHWAY_STEP_M / 2)
        if mid is None:
            return None
        uv_mid = velocity(mid)
        if uv_mid is None:
            return None

        return advance(point, uv_mid, PATHWAY_STEP_M)

    def run(sign: int) -> list[tuple[float, float]]:
        pts = []
        p = (core["lat"], core["lon"])
        for _ in range(PATHWAY_MAX_STEPS):
            nxt = step(p, sign)
            if nxt is None:
                break
            if not (lat_lo <= nxt[0] <= lat_hi and lon_lo <= nxt[1] <= lon_hi):
                break
            pts.append(nxt)
            p = nxt
        return pts

    upstream = run(-1)[::-1]
    downstream = run(+1)
    points = upstream + [(core["lat"], core["lon"])] + downstream

    coords = np.array([[p[0], p[1]] for p in points])
    speeds = np.hypot(u_at(coords), v_at(coords))
    levels = level_at(coords)

    return {
        "lat": [round(float(p[0]), 3) for p in points],
        "lon": [round(float(p[1]), 3) for p in points],
        "speed": [None if not np.isfinite(s) else round(float(s), 2) for s in speeds],
        "level": [None if not np.isfinite(v) else round(float(v), 1) for v in levels],
    }


# ==========================================================
# Main
# ==========================================================

def period_fields(clim: xr.Dataset, months: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Mean u/v over the given calendar months of the climatology.

    Averaged before the column search, never after: averaging per-month
    core heights would invent a level the wind maximum never occupied."""
    sub = clim.sel(month=months)
    return (
        sub["u"].mean("month").values.astype(np.float32),
        sub["v"].mean("month").values.astype(np.float32),
    )


def main() -> None:
    print("==================================================")
    print("ERA5 low-level (Somali) jet diagnostics")
    print("==================================================")

    clim = load_monthly_climatology()
    lat = clim["lat"].values
    lon = clim["lon"].values
    level = clim["level"].values

    sp_hpa = load_surface_pressure_climatology(lat, lon)
    clim = apply_below_ground_mask(clim, sp_hpa)

    clim_path = ERA5_CLIM_DIR / "ERA5_lowlevel_uv_monthly_climatology_1991_2020.nc"
    clim.attrs.update(
        title="ERA5 monthly-mean u/v climatology, all pressure levels <= 600 hPa",
        reference_period=f"{CLIM_START_YEAR}-{CLIM_END_YEAR}",
        note="Levels below the climatological surface pressure are set to NaN.",
    )
    clim.to_netcdf(clim_path)
    print(f"\nWrote {clim_path}")

    periods: dict[str, list[int]] = {MONTH_ABBR[m - 1]: [m] for m in range(1, 13)}
    periods.update(SEASONS)

    core_rows = []
    pathways: dict[str, dict] = {}

    for period, months in periods.items():
        u, v = period_fields(clim, months)
        fields = compute_core_surface(u, v, level)

        ds_out = xr.Dataset(
            {k: (("lat", "lon"), val) for k, val in fields.items()},
            coords={"lat": lat, "lon": lon},
        )
        ds_out["llj_speed"].attrs.update(units="m s-1", long_name="Sub-600-hPa maximum wind speed")
        ds_out["llj_level"].attrs.update(units="hPa", long_name="Pressure of the sub-600-hPa wind maximum")
        ds_out["llj_u"].attrs.update(units="m s-1", long_name="Zonal wind on the jet-core surface")
        ds_out["llj_v"].attrs.update(units="m s-1", long_name="Meridional wind on the jet-core surface")
        ds_out.attrs.update(
            title=f"ERA5 low-level jet diagnostics, {period}",
            reference_period=f"{CLIM_START_YEAR}-{CLIM_END_YEAR}",
            months=",".join(str(m) for m in months),
        )
        out_path = DYNAMIC_DIAG_DIR / f"ERA5_lowlevel_jet_{period}_climatology_1991_2020.nc"
        ds_out.to_netcdf(out_path)

        core = find_core(fields["llj_speed"], lat, lon, fields["llj_level"], fields["llj_v"])
        if core is None:
            pathways[period] = {"core": None, "pathway": None}
            core_rows.append(
                {
                    "period": period,
                    "core_lon": None,
                    "core_lat": None,
                    "core_level_hpa": None,
                    "core_speed_ms": None,
                    "is_jet": False,
                    "crosses_equator": False,
                }
            )
            print(f"{period:5s}: no southerly low-level core -- jet absent")
            continue

        if core["is_jet"]:
            path = trace_pathway(fields["llj_u"], fields["llj_v"], lat, lon, fields["llj_level"], core)
            origin_lat = min(path["lat"])
            if origin_lat > CORE_MAX_ORIGIN_LAT:
                core["is_jet"] = False
                pathways[period] = {"core": core, "pathway": None}
                span = f"origin {origin_lat:.1f}N -- local maximum, not the Somali jet"
            else:
                core["crosses_equator"] = origin_lat < 0
                pathways[period] = {"core": core, "pathway": path}
                span = (
                    f"{len(path['lon'])} pts, "
                    f"{origin_lat:.1f}N->{max(path['lat']):.1f}N, "
                    f"{min(path['lon']):.1f}E->{max(path['lon']):.1f}E"
                    f"{'' if core['crosses_equator'] else ', does not reach the equator'}"
                )
        else:
            pathways[period] = {"core": core, "pathway": None}
            span = "below jet threshold"

        core_rows.append(
            {
                "period": period,
                "core_lon": round(core["lon"], 3),
                "core_lat": round(core["lat"], 3),
                "core_level_hpa": round(core["level"], 1),
                "core_speed_ms": round(core["speed"], 2),
                "is_jet": core["is_jet"],
                "crosses_equator": core.get("crosses_equator", False),
            }
        )
        print(
            f"{period:5s}: core {core['speed']:5.1f} m/s at "
            f"{core['lon']:6.2f}E {core['lat']:6.2f}N {core['level']:6.1f} hPa  -- {span}"
        )

    csv_path = TABLES_DIR / "era5_lowlevel_jet_core.csv"
    import csv as _csv

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=list(core_rows[0].keys()))
        writer.writeheader()
        writer.writerows(core_rows)

    json_path = TABLES_DIR / "era5_lowlevel_jet_pathway.json"
    json_path.write_text(json.dumps(pathways, separators=(",", ":")), encoding="utf-8")

    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {len(periods)} period files to {DYNAMIC_DIAG_DIR}")


if __name__ == "__main__":
    main()
