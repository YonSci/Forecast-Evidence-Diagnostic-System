import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# -----------------------------
# 1. Choose CPC May 2026 NMME file
# -----------------------------
url = (
    "https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/"
    "ENSMEAN/2026050800/NMME.prate.202605.ENSMEAN.anom.nc"
)

ds = xr.open_dataset(url)
print(ds)

# -----------------------------
# 2. Pick the main variable
# -----------------------------
# Usually this will be prate for precipitation anomaly
varname = list(ds.data_vars)[0]
da = ds[varname]

print("Selected variable:", varname)
print("Dimensions:", da.dims)
print("Units:", da.attrs.get("units", "unknown"))

# -----------------------------
# 3. Identify lat/lon names
# -----------------------------
lat_name = [c for c in da.coords if c.lower() in ["lat", "latitude", "y"]][0]
lon_name = [c for c in da.coords if c.lower() in ["lon", "longitude", "x"]][0]

# -----------------------------
# 4. Identify lead/time dimension
# -----------------------------
possible_leads = ["lead", "L", "time", "T", "target", "forecast_month"]
lead_dim = None

for d in da.dims:
    if d not in [lat_name, lon_name]:
        lead_dim = d
        break

print("Assumed lead dimension:", lead_dim)

# -----------------------------
# 5. Convert precipitation units if needed
# -----------------------------
# prate is often kg m-2 s-1, equivalent to mm/s.
# Multiplying by 86400 gives mm/day.
units = da.attrs.get("units", "").lower()

if "s-1" in units or "sec" in units:
    da = da * 86400
    da.attrs["units"] = "mm/day"

# -----------------------------
# 6. Select June, July, August 2026
# -----------------------------
# For May 2026 initialization:
# Lead 1 = June 2026
# Lead 2 = July 2026
# Lead 3 = August 2026
jun = da.isel({lead_dim: 0})
jul = da.isel({lead_dim: 1})
aug = da.isel({lead_dim: 2})

jja = xr.concat([jun, jul, aug], dim="month").mean("month")
jja.name = "JJA_2026_anomaly"

# -----------------------------
# 7. Plot function
# -----------------------------
def plot_map(data, title, extent=None, cmap="BrBG"):
    fig = plt.figure(figsize=(10, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())

    if extent:
        ax.set_extent(extent, crs=ccrs.PlateCarree())

    data.plot(
        ax=ax,
        transform=ccrs.PlateCarree(),
        cmap=cmap,
        cbar_kwargs={"label": data.attrs.get("units", "")}
    )

    ax.coastlines()
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    ax.add_feature(cfeature.LAKES, linewidth=0.3)
    ax.add_feature(cfeature.RIVERS, linewidth=0.3)

    ax.set_title(title, fontsize=13)
    plt.tight_layout()
    plt.show()

# -----------------------------
# 8. Global plots
# -----------------------------
plot_map(jun, "NMME precipitation anomaly: June 2026, May 2026 initialization")
plot_map(jul, "NMME precipitation anomaly: July 2026, May 2026 initialization")
plot_map(aug, "NMME precipitation anomaly: August 2026, May 2026 initialization")
plot_map(jja, "NMME precipitation anomaly: JJA 2026, May 2026 initialization")

# -----------------------------
# 9. East Africa zoom
# -----------------------------
east_africa_extent = [20, 55, -15, 20]

plot_map(
    jja,
    "NMME precipitation anomaly: JJA 2026, East Africa",
    extent=east_africa_extent
)