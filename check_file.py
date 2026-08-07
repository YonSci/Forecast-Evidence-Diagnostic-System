import xarray as xr
from pathlib import Path

OUT_DIR = Path("NMME_May2026")

for nc_file in OUT_DIR.glob("*.nc"):
    print("\n==============================")
    print(nc_file.name)
    print("==============================")
    
    ds = xr.open_dataset(nc_file)
    print(ds)